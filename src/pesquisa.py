"""Orquestra a pesquisa de preço de cada item (fatia B), juntando as etapas:

    ① cache  →  ② busca  →  ③ extrai e confere  →  ④ agente refaz (se precisar)  →  ⑤ cálculo  →  resultado

- O caminho fixo resolve a maioria dos itens sem agente (rápido e barato).
- O **agente ReAct** (GLM-5.2) só entra quando faltam lojas com o MESMO produto: ele lê o que veio
  errado e reformula a consulta (até 2 buscas extras). É a parte "pesquisa → avalia → refaz" do pitch.
- Item genérico → faixa estimada + pergunta ao arquiteto (sem agente: perguntar é melhor que chutar).
- Nenhum preço sem fonte; falha total → cache vencido ("preço de dd/mm") ou "não encontrado".

Orçamento inteiro (`pesquisar_itens`) em duas fases: 1ª o caminho rápido de todos os itens, gravando cada um
(Realtime); 2ª o agente só nos itens com poucas lojas, com cota própria de LLM e prazo total.
A gravação no Supabase (orcamento_itens) é feita pelo `ao_terminar` (src/orcamento.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import unicodedata
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from langfuse import observe
from pydantic import Field

from . import cache
from . import custo as _custo
from .agent import Agent
from .busca import buscar, montar_consulta
from .calculo import Calculo, calcular
from .config import get_settings, load_prompt
from .modelos import ItemEntrada, ResultadoItem
from .precos import (TENTATIVAS_RESPOSTA_VAZIA, Oferta, RespostaVazia, ResultadoExtracao, conferir_resposta,
                     extrair_e_conferir, semaforo_do_loop)
from .tools import ToolArgs, ToolRegistry

logger = logging.getLogger(__name__)

MODELO_RESERVA_AGENTE = "Qwen/Qwen3-32B"
MIN_TEMPO_AGENTE_S = 8   # com menos que isso não dá nem uma chamada ao GLM (9–13 s medidos): nem começa

# Pergunta ao arquiteto por tipo de material (regras, sem LLM). A primeira que casar vale.
PERGUNTAS = [
    (r"tinta|esmalte|verniz|textura|selador", "Qual marca, linha, cor e acabamento (fosco, acetinado, semibrilho)?"),
    (r"porcelanato|piso|revestimento|azulejo|ceramic|pastilha|laminado|vinilico",
     "Qual marca, linha, dimensão (ex.: 60x60) e acabamento?"),
    (r"misturador|torneira|registro|ducha|chuveiro|valvula|monocomando", "Qual marca e modelo (ou o código do fabricante)?"),
    (r"cuba|pia|vaso|bacia|louca|lavatorio|tanque", "Qual marca, modelo e medidas?"),
]
PERGUNTA_PADRAO = "Qual marca e modelo exatos?"


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def pergunta_para(descricao: str) -> str:
    d = _norm(descricao)
    return next((p for padrao, p in PERGUNTAS if re.search(padrao, d)), PERGUNTA_PADRAO)


# ------------------------------------------------------------------ estado de um item
@dataclass
class Coleta:
    """O que a pesquisa de um item juntou somando todas as buscas (a 1ª e as do agente)."""
    ofertas: list[Oferta] = field(default_factory=list)
    imagem: str | None = None
    provedor: str | None = None
    modelo: str = ""
    consultas: list[str] = field(default_factory=list)
    buscas_agente: int = 0

    def juntar(self, ofertas: list[Oferta]) -> None:
        urls = {o.url for o in self.ofertas}
        self.ofertas += [o for o in ofertas if o.url not in urls]

    def extracao(self) -> ResultadoExtracao:
        return ResultadoExtracao(ofertas=list(self.ofertas), modelo=self.modelo)

    def lojas_conferidas(self) -> int:
        return len({o.loja for o in self.ofertas if o.mesmo_produto == "sim" and o.preco})


def resumo_para_agente(ofertas: list[Oferta], coleta: Coleta) -> dict:
    """Observação enxuta: só o que ajuda a reformular (sem texto de anúncio inteiro)."""
    def titulo(o): return o.titulo[:90]
    return {
        "mesmo_produto": [f"{o.loja}: R$ {o.preco:.2f} ({o.embalagem or '?'})" for o in ofertas
                          if o.mesmo_produto == "sim" and o.preco],
        "parecidos": [titulo(o) for o in ofertas if o.mesmo_produto == "parecido"][:5],
        "outros": [titulo(o) for o in ofertas if o.mesmo_produto == "nao" or
                   (o.mesmo_produto == "sim" and not o.preco)][:5],
        "lojas_acumuladas": coleta.lojas_conferidas(),
        "buscas_restantes": max(0, get_settings().pesquisa_max_refazer - coleta.buscas_agente),
    }


# ------------------------------------------------------------------ limites
_semaforos_busca: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_semaforos_agente: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _porteiro_busca() -> asyncio.Semaphore:
    return semaforo_do_loop(_semaforos_busca, get_settings().pesquisa_concorrencia_busca)


def _porteiro_agente() -> asyncio.Semaphore:
    """Cota própria do GLM do agente: não disputa vaga com as extrações (achado da etapa 9)."""
    return semaforo_do_loop(_semaforos_agente, get_settings().pesquisa_concorrencia_agente)


async def buscar_e_extrair(consulta: str, produto: str):
    async with _porteiro_busca():
        b = await buscar(consulta)
    return b, await extrair_e_conferir(produto, b.resultados)


# ------------------------------------------------------------------ agente que refaz a busca
class BuscarPrecoArgs(ToolArgs):
    consulta: str = Field(min_length=3, max_length=120,
                          description="Nova consulta, curta, como alguém digitaria numa loja online")


FERRAMENTAS = ToolRegistry()   # só a ferramenta do pesquisador (não mistura com as do agente genérico)


@FERRAMENTAS.tool(description="Pesquisa o produto nas lojas brasileiras de construção com uma nova consulta "
                              "e devolve quais lojas têm o MESMO produto com preço.")
def buscar_preco(args: BuscarPrecoArgs) -> dict:
    """Assinatura para o schema/validação. A execução real é assíncrona e acumula na coleta do item
    (ver _executar_busca), porque precisa rodar no mesmo event loop da pesquisa."""
    raise RuntimeError("use _executar_busca")


async def _executar_busca(item: ItemEntrada, coleta: Coleta, argumentos: str) -> dict:
    if coleta.buscas_agente >= get_settings().pesquisa_max_refazer:
        return {"ok": False, "error": "limite de buscas atingido"}
    try:
        args = BuscarPrecoArgs.model_validate_json(argumentos or "{}")
    except Exception as exc:  # noqa: BLE001 — argumento ruim volta ao LLM como observação
        return {"ok": False, "error": f"Argumentos inválidos: {exc}"}
    coleta.buscas_agente += 1
    coleta.consultas.append(args.consulta)
    b, ext = await buscar_e_extrair(args.consulta, item.descricao)
    coleta.juntar(ext.ofertas)
    coleta.imagem = coleta.imagem or b.imagem
    return {"ok": True, "result": resumo_para_agente(ext.ofertas, coleta)}


def criar_agente(cliente=None) -> Agent:
    """Reaproveita o Agent de src/agent.py para o LLM: modelo, reserva em 400/503, custo e tracing."""
    s = get_settings()
    agente = Agent(name="pesquisador", system_prompt=load_prompt("pesquisador_precos"), tools=FERRAMENTAS,
                   model=s.pesquisa_modelo_agente or s.featherless_model, client=cliente)
    agente.fallback_model = agente.fallback_model or MODELO_RESERVA_AGENTE
    return agente


async def _chamar_agente(agente: Agent, mensagens: list[dict]):
    """O GLM do agente tem cota própria de chamadas simultâneas (pesquisa_concorrencia_agente).
    Histórico: fora de qualquer limite sobrecarregava a conta; dentro do mesmo limite das extrações,
    o agente esperava vaga até estourar o tempo (etapa 9). Resposta vazia ganha uma nova tentativa."""
    for tentativa in range(TENTATIVAS_RESPOSTA_VAZIA):
        async with _porteiro_agente():
            r = await asyncio.to_thread(agente._complete, mensagens)
        _custo.registrar(getattr(getattr(r, "usage", None), "cost", 0))
        try:
            conferir_resposta(r)
            return r
        except RespostaVazia:
            if tentativa == TENTATIVAS_RESPOSTA_VAZIA - 1:
                raise
            await asyncio.sleep(1.0 + random.random())


@observe(as_type="agent", name="agente.pesquisador")
async def _loop_react(item: ItemEntrada, coleta: Coleta, primeira: dict, cliente=None) -> str:
    """ReAct enxuto: Pensa (LLM) → Age (buscar_preco) → Observa → repete.
    Quem decide PARAR é o código, não o LLM: com lojas suficientes ou sem buscas restantes, encerra
    sem gastar mais uma chamada só para ouvir "FIM" (medido: ~10 s a menos por item difícil)."""
    s = get_settings()
    agente = criar_agente(cliente)
    mensagens = [{"role": "system", "content": agente.system_prompt},
                 {"role": "user", "content": (f"Produto pedido: {item.descricao}\n"
                                              f"Primeira consulta: {coleta.consultas[0] if coleta.consultas else item.descricao}\n"
                                              f"Resultado da primeira busca: {json.dumps(primeira, ensure_ascii=False)}")}]
    for _ in range(s.pesquisa_max_refazer + 1):
        resposta = await _chamar_agente(agente, mensagens)
        msg = resposta.choices[0].message
        mensagens.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            return msg.content or "FIM"
        for call in msg.tool_calls:
            obs = (await _executar_busca(item, coleta, call.function.arguments) if call.function.name == "buscar_preco"
                   else {"ok": False, "error": f"Ferramenta desconhecida: {call.function.name}"})
            mensagens.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(obs, ensure_ascii=False)})
        if coleta.lojas_conferidas() >= s.pesquisa_min_lojas:
            return f"parou: {coleta.lojas_conferidas()} lojas com o mesmo produto"
        if coleta.buscas_agente >= s.pesquisa_max_refazer:
            return "parou: limite de buscas"
    return "parou: limite de passos"


async def refazer_com_agente(item: ItemEntrada, coleta: Coleta, primeira: dict, cliente=None,
                             timeout: float | None = None) -> str:
    """Devolve como o agente terminou. Nunca passa do tempo limite: segue com o que já achou
    (a coleta é preenchida durante o loop, então o que veio antes do tempo esgotar não se perde)."""
    try:
        return await asyncio.wait_for(_loop_react(item, coleta, primeira, cliente),
                                      timeout=timeout or get_settings().pesquisa_timeout_agente_s)
    except asyncio.TimeoutError:
        logger.warning("Agente passou do tempo em '%s': seguindo com o que achou", item.descricao)
        return "parou: tempo esgotado"
    except Exception as exc:  # noqa: BLE001 — LLM fora do ar: o item segue com a 1ª busca
        logger.warning("Agente falhou em '%s' (%s): seguindo com a 1ª busca", item.descricao, type(exc).__name__)
        return f"parou: {type(exc).__name__}"


# ------------------------------------------------------------------ resultado
def _resultado(item: ItemEntrada, calc: Calculo, status: str, imagem: str | None, preco_data: datetime | None,
               iteracoes: int, pergunta: str | None = None, motivo: str | None = None) -> ResultadoItem:
    return ResultadoItem(
        item_id=item.id, status=status, produto_normalizado=item.descricao, imagem_url=imagem,
        embalagem=calc.embalagem, qtd_embalagens=calc.qtd_embalagens,
        preco_emb_min=calc.preco_emb_min, preco_emb_med=calc.preco_emb_med, preco_emb_max=calc.preco_emb_max,
        preco_un_min=calc.preco_un_min, preco_un_med=calc.preco_un_med, preco_un_max=calc.preco_un_max,
        unidade_preco=calc.unidade_preco, confianca=calc.confianca, estimativa=calc.estimativa,
        fontes=calc.fontes, premissa=calc.premissa if calc.tem_preco else None,
        pergunta=pergunta, motivo=motivo, preco_data=preco_data if calc.tem_preco else None, iteracoes=iteracoes)


def _precisa_refazer(calc: Calculo) -> bool:
    return not calc.tem_preco or len(calc.fontes) < get_settings().pesquisa_min_lojas


@dataclass
class Rascunho:
    """Fim da fase 1 (caminho rápido) de um item.
    `primeira` preenchida = faltam lojas e o agente deve refazer a busca na fase 2."""
    item: ItemEntrada
    resultado: ResultadoItem
    coleta: Coleta | None = None
    anterior: cache.EntradaCache | None = None
    erro_busca: str | None = None
    primeira: dict | None = None

    @property
    def precisa_agente(self) -> bool:
        return self.primeira is not None


def _erro(item: ItemEntrada, exc: Exception) -> ResultadoItem:
    logger.exception("Pesquisa do item %s falhou (%s)", item.id, type(exc).__name__)
    return ResultadoItem(item_id=item.id, status="erro", motivo=f"falha interna na pesquisa ({type(exc).__name__})")


@observe(name="pesquisa.item")
async def _fase_rapida(item: ItemEntrada, usar_agente: bool, usar_cache: bool) -> Rascunho:
    """① cache → ② busca → ③ extração → ⑤ cálculo, SEM agente. Se faltar loja, devolve um resultado
    provisório e marca o item para a fase 2 (o cache só é gravado no resultado final)."""
    generico = item.classificacao == "pendente_especificacao"

    # ① cache válido
    anterior = await cache.ler(item.descricao, aceitar_vencido=True) if usar_cache else None
    if anterior and not anterior.vencido:
        calc = calcular(item, anterior.extracao, generico)
        if calc.tem_preco:
            return Rascunho(item, _resultado(
                item, calc, "pendente_especificacao" if generico else "definido", anterior.imagem_url,
                anterior.atualizado_em, anterior.iteracoes, pergunta=pergunta_para(item.descricao) if generico else None))

    # ② busca + ③ extração
    consulta = montar_consulta(item)
    b, ext = await buscar_e_extrair(consulta, item.descricao)
    coleta = Coleta(imagem=b.imagem, provedor=b.provedor, modelo=ext.modelo, consultas=[consulta])
    coleta.juntar(ext.ofertas)
    calc = calcular(item, coleta.extracao(), generico)

    precisa = usar_agente and not generico and _precisa_refazer(calc) and get_settings().llm_configured
    resultado = await _concluir(item, coleta, anterior, b.erro, gravar_cache=not precisa)
    return Rascunho(item, resultado, coleta, anterior, b.erro,
                    primeira=resumo_para_agente(ext.ofertas, coleta) if precisa else None)


async def _concluir(item: ItemEntrada, coleta: Coleta, anterior: cache.EntradaCache | None, erro_busca: str | None,
                    gravar_cache: bool = True) -> ResultadoItem:
    """⑤ Resultado a partir de tudo que a coleta juntou (1ª busca + as do agente)."""
    generico = item.classificacao == "pendente_especificacao"
    agora = datetime.now(timezone.utc)
    calc = calcular(item, coleta.extracao(), generico)
    iteracoes = coleta.buscas_agente

    if calc.tem_preco:
        if gravar_cache:
            await cache.gravar(item.descricao, coleta.extracao(), coleta.imagem, coleta.provedor, anterior=anterior,
                               iteracoes=iteracoes)
        imagem = anterior.imagem_url if anterior and anterior.imagem_url else coleta.imagem
        if generico:
            return _resultado(item, calc, "pendente_especificacao", imagem, agora, iteracoes,
                              pergunta=pergunta_para(item.descricao))
        return _resultado(item, calc, "definido", imagem, agora, iteracoes)

    # sem o produto exato: se há parecidos com preço, vira estimativa + pergunta (a B "rebaixa")
    if not generico:
        estimada = calcular(item, coleta.extracao(), generico=True)
        if estimada.tem_preco:
            return _resultado(item, estimada, "pendente_especificacao", coleta.imagem, agora, iteracoes,
                              pergunta=f"Não achamos à venda exatamente este produto. {pergunta_para(item.descricao)}",
                              motivo="só produtos parecidos: a faixa é uma estimativa")

    # falha total: cache vencido vale como reserva, com a data
    if anterior:
        calc_v = calcular(item, anterior.extracao, generico)
        if calc_v.tem_preco:
            return _resultado(item, calc_v, "pendente_especificacao" if generico else "definido", anterior.imagem_url,
                              anterior.atualizado_em, iteracoes, pergunta=pergunta_para(item.descricao) if generico else None,
                              motivo=f"a busca de hoje falhou; preço de {anterior.data_preco}")

    if generico:
        return ResultadoItem(item_id=item.id, status="pendente_especificacao", imagem_url=coleta.imagem,
                             pergunta=pergunta_para(item.descricao), iteracoes=iteracoes,
                             motivo="item genérico e sem preço de referência na busca")
    motivo = erro_busca or calc.motivo or "nenhuma loja com preço para este produto"
    return ResultadoItem(item_id=item.id, status="nao_encontrado", imagem_url=coleta.imagem, iteracoes=iteracoes,
                         motivo=f"{motivo} (consultas: {' | '.join(coleta.consultas)})")


async def _fase_agente(r: Rascunho, cliente_llm=None, timeout: float | None = None) -> ResultadoItem:
    """Fase 2 de um item: o agente refaz a busca e o resultado é refeito com tudo que juntou."""
    if timeout is None or timeout > 0:
        await refazer_com_agente(r.item, r.coleta, r.primeira, cliente_llm, timeout=timeout)
    else:
        logger.warning("Sem tempo para o agente em '%s': fica com a 1ª busca", r.item.descricao)
    return await _concluir(r.item, r.coleta, r.anterior, r.erro_busca)


async def pesquisar_item(item: ItemEntrada, *, usar_agente: bool = True, usar_cache: bool = True,
                         cliente_llm=None) -> ResultadoItem:
    """Um item só, do começo ao fim (usado por repesquisar_item). Nunca levanta exceção:
    qualquer falha vira status 'erro' com motivo (o orçamento continua)."""
    try:
        r = await _fase_rapida(item, usar_agente, usar_cache)
        return await _fase_agente(r, cliente_llm) if r.precisa_agente else r.resultado
    except Exception as exc:  # noqa: BLE001
        return _erro(item, exc)


@observe(name="pesquisa.itens")
async def pesquisar_itens(itens: list[ItemEntrada], ao_terminar: Callable[[ResultadoItem], Awaitable[None]] | None = None,
                          *, usar_agente: bool = True, usar_cache: bool = True, cliente_llm=None) -> list[ResultadoItem]:
    """Orçamento inteiro em DUAS FASES (achado da etapa 9: agente e extrações disputando as mesmas vagas
    atrasavam o 1º item para 33 s e estouravam o tempo do agente):

    Fase 1 — caminho rápido de TODOS os itens em paralelo, sem agente. Cada item é avisado em `ao_terminar`
             assim que fica pronto (é por aí que a etapa 7 grava no Supabase e o Realtime atualiza a tela).
             Item que vai para o agente mas já tem preço é avisado com o resultado provisório; sem preço,
             continua "buscando" na tela até a fase 2.
    Fase 2 — agente só nos itens com < pesquisa_min_lojas, depois da fase 1, com cota própria de LLM,
             no máximo `pesquisa_agentes_simultaneos` por vez e prazo total `pesquisa_prazo_agentes_s`.
             Os sem preço vão primeiro. Item que não coube no prazo fica com o resultado da fase 1.
    """
    s = get_settings()

    async def avisar(r: ResultadoItem) -> None:
        if ao_terminar:
            try:
                await ao_terminar(r)
            except Exception:  # noqa: BLE001 — falha ao gravar um item não derruba os outros
                logger.exception("ao_terminar falhou para o item %s", r.item_id)

    async def fase1(item: ItemEntrada) -> Rascunho:
        try:
            r = await _fase_rapida(item, usar_agente, usar_cache)
        except Exception as exc:  # noqa: BLE001
            r = Rascunho(item, _erro(item, exc))
        if not r.precisa_agente or r.resultado.preco_emb_med is not None:
            await avisar(r.resultado)
        return r

    rascunhos = list(await asyncio.gather(*(fase1(i) for i in itens)))
    finais = {r.item.id: r.resultado for r in rascunhos}

    pendentes = sorted((r for r in rascunhos if r.precisa_agente), key=lambda r: r.resultado.preco_emb_med is not None)
    if pendentes:
        loop = asyncio.get_running_loop()
        prazo = loop.time() + s.pesquisa_prazo_agentes_s
        vagas = asyncio.Semaphore(max(1, s.pesquisa_agentes_simultaneos))

        async def fase2(r: Rascunho) -> None:
            async with vagas:
                restante = prazo - loop.time()
                timeout = min(s.pesquisa_timeout_agente_s, restante) if restante >= MIN_TEMPO_AGENTE_S else 0
                try:
                    final = await _fase_agente(r, cliente_llm, timeout=timeout)
                except Exception as exc:  # noqa: BLE001
                    final = r.resultado if r.resultado.status != "erro" else _erro(r.item, exc)
            finais[r.item.id] = final
            await avisar(final)

        await asyncio.gather(*(fase2(r) for r in pendentes))
    return [finais[i.id] for i in itens]
