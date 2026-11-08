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
from .agent import Agent, build_llm_client
from .chaves_llm import chave_agente
from .google_shopping import ofertas_google, ofertas_regionais, resolver_links_das_lojas
from .busca import buscar, eh_pagina_de_listagem, montar_consulta
from .calculo import Calculo, calcular
from .config import get_settings, load_prompt
from .modelos import ItemEntrada, ResultadoItem
from .precos import (TENTATIVAS_RESPOSTA_VAZIA, Oferta, RespostaVazia, ResultadoExtracao, conferir_resposta,
                     extrair_e_conferir, semaforo_do_loop)
from .tools import ToolArgs, ToolRegistry
from .especificacao import orientacao, nao_confirmados
from .paginas_produto import aprofundar
from .imagens import imagem_do_cache

logger = logging.getLogger(__name__)

MODELO_RESERVA_AGENTE = "Qwen/Qwen3-32B"
MIN_TEMPO_AGENTE_S = 8   # com menos que isso não dá nem uma chamada ao GLM (9–13 s medidos): nem começa

# Pergunta ao arquiteto por tipo de material (regras, sem LLM). A primeira que casar vale.
# É um CONVITE, não um bloqueio: sem a resposta o item segue com a faixa estimada (produtos parecidos).
SEM_RESPOSTA = " Sem isso, usamos a média de produtos parecidos."
PERGUNTAS = [
    (r"tinta|esmalte|verniz|textura|selador",
     "Quer especificar marca, linha, cor e acabamento (fosco, acetinado, semibrilho)?" + SEM_RESPOSTA),
    (r"porcelanato|piso|revestimento|azulejo|ceramic|pastilha|laminado|vinilico",
     "Quer especificar marca, linha, dimensão (ex.: 60x60) e acabamento?" + SEM_RESPOSTA),
    (r"misturador|torneira|registro|ducha|chuveiro|valvula|monocomando",
     "Quer especificar marca e modelo (ou o código do fabricante)?" + SEM_RESPOSTA),
    (r"cuba|pia|vaso|bacia|louca|lavatorio|tanque", "Quer especificar marca, modelo e medidas?" + SEM_RESPOSTA),
]
PERGUNTA_PADRAO = "Quer especificar marca e modelo?" + SEM_RESPOSTA


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def pergunta_para(descricao: str) -> str:
    return orientacao(descricao)


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

    def lojas_conferidas(self, generico: bool = False) -> int:
        """Lojas que contam para parar: o mesmo produto; no item genérico (estimativa), também os parecidos."""
        if generico:
            return len({o.loja for o in self.ofertas if o.mesmo_produto in ("sim", "parecido") and o.preco})
        # página de listagem não confirma o produto exato (src/calculo.py): não conta para o agente parar
        return len({o.loja for o in self.ofertas if o.mesmo_produto == "sim" and o.preco
                    and not eh_pagina_de_listagem(o.dominio, o.url)})


def resumo_para_agente(ofertas: list[Oferta], coleta: Coleta, generico: bool = False) -> dict:
    """Observação enxuta: só o que ajuda a reformular (sem texto de anúncio inteiro)."""
    def titulo(o): return o.titulo[:90]
    if generico:   # item sem marca: o parecido com preço também serve para a faixa estimada
        return {
            "servem_para_estimar": [f"{o.loja}: R$ {o.preco:.2f} ({o.embalagem or '?'})" for o in ofertas
                                    if o.mesmo_produto in ("sim", "parecido") and o.preco],
            "outros": [titulo(o) for o in ofertas if o.mesmo_produto == "nao" or not o.preco][:5],
            "lojas_acumuladas": coleta.lojas_conferidas(generico=True),
            "buscas_restantes": max(0, get_settings().pesquisa_max_refazer - coleta.buscas_agente),
        }
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
        b.resultados = await aprofundar(produto, b.resultados)
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
    if args.consulta.casefold().strip() in {c.casefold().strip() for c in coleta.consultas}:
        return {"ok": False, "error": "consulta repetida; preserve as especificações e use outra formulação"}
    if faltam := nao_confirmados(item.descricao, args.consulta):
        return {"ok": False, "error": "preserve as especificações: " + "; ".join(faltam)}
    coleta.consultas.append(args.consulta)
    b, ext = await buscar_e_extrair(args.consulta, item.descricao)
    coleta.juntar(ext.ofertas)
    coleta.imagem = coleta.imagem or b.imagem
    return {"ok": True, "result": resumo_para_agente(ext.ofertas, coleta, _generico(item))}


def _generico(item: ItemEntrada) -> bool:
    return item.classificacao == "pendente_especificacao"


# Item sem marca: o agente melhora a FAIXA ESTIMADA (a pergunta ao arquiteto continua). Medido em 07/11: numa lista
# sem marcas o agente nunca rodava e o "pesquisa → avalia → refaz" do pitch não aparecia.
INSTRUCAO_GENERICO = ("Item GENÉRICO (sem marca/modelo): não escolha marca. Produtos parecidos da mesma categoria, "
                      "medida e unidade servem para estimar a faixa de preço; reformule para achar mais lojas com "
                      "preço (ex.: tipo do produto + medida principal).")


def criar_agente(cliente=None) -> Agent:
    """Reaproveita o Agent de src/agent.py para o LLM: modelo, reserva em 400/503, custo e tracing."""
    s = get_settings()
    # Com 2+ chaves, o agente usa a última, que fica só para ele (src/chaves_llm.py): não disputa cota com as extrações.
    agente = Agent(name="pesquisador", system_prompt=load_prompt("pesquisador_precos"), tools=FERRAMENTAS,
                   model=s.pesquisa_modelo_agente or s.featherless_model,
                   client=cliente or build_llm_client(api_key=chave_agente()).with_options(max_retries=0),
                   max_tokens=s.pesquisa_max_tokens_saida)
    agente.fallback_model = agente.fallback_model or MODELO_RESERVA_AGENTE
    return agente


async def _chamar_agente(agente: Agent, mensagens: list[dict]):
    """O GLM do agente tem cota própria de chamadas simultâneas (pesquisa_concorrencia_agente).
    Histórico: fora de qualquer limite sobrecarregava a conta; dentro do mesmo limite das extrações,
    o agente esperava vaga até estourar o tempo (etapa 9). Resposta vazia ganha uma nova tentativa."""
    for tentativa in range(TENTATIVAS_RESPOSTA_VAZIA):
        async with _porteiro_agente():
            r = await asyncio.to_thread(agente._complete, mensagens)
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
    generico = _generico(item)
    agente = criar_agente(cliente)
    mensagens = [{"role": "system", "content": agente.system_prompt},
                 {"role": "user", "content": (f"Produto pedido: {item.descricao}\n"
                                              + (f"{INSTRUCAO_GENERICO}\n" if generico else "")
                                              + f"Primeira consulta: {coleta.consultas[0] if coleta.consultas else item.descricao}\n"
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
        if coleta.lojas_conferidas(generico) >= s.pesquisa_min_lojas:
            return f"parou: {coleta.lojas_conferidas(generico)} lojas com preço"
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


MOTIVO_SEM_TEMPO = "a pesquisa deste item passou do tempo; use Pesquisar de novo"
MOTIVO_MAIS_PROXIMO ="não achamos à venda exatamente a sua especificação: este é o produto mais próximo; confira nas fontes"


def aceitar_mais_proximo(r: ResultadoItem) -> ResultadoItem:
    """Depois que o arquiteto RESPONDEU a pergunta, não se pergunta de novo. Se só vieram parecidos, o item vira
    definido com confiança baixa e o aviso, mantendo `estimativa` e as fontes. Medido no site em 07/11: a resposta
    "Tramontina Liz tomada 2P+T 20A branca" achou preço na loja oficial e voltou pendente com a MESMA pergunta."""
    if r.status != "pendente_especificacao" or r.preco_emb_med is None:
        return r
    return ResultadoItem(**(r.model_dump() | {"status": "definido", "pergunta": None, "confianca": "baixa",
                                              "estimativa": True, "motivo": MOTIVO_MAIS_PROXIMO}))


MOTIVO_MEDIA_ACEITA = "sem marca nem modelo: o preço é a média de produtos parecidos, aceita por você; confira nas fontes"


def aceitar_media_estimada(r: ResultadoItem) -> ResultadoItem:
    """O arquiteto escolheu "Usar a média mesmo assim": não quer especificar marca e modelo. Se a pesquisa achou
    preço de produtos parecidos, o item deixa de ser pendente (sem pergunta) e segue como estimativa, com o aviso e as
    fontes. Sem preço, fica como a pesquisa devolveu: não existe média para aceitar."""
    if r.status != "pendente_especificacao" or r.preco_emb_med is None:
        return r
    return ResultadoItem(**(r.model_dump() | {"status": "definido", "pergunta": None, "estimativa": True,
                                              "motivo": MOTIVO_MEDIA_ACEITA}))


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
    consumo: _custo.Acumulador | None = None

    @property
    def precisa_agente(self) -> bool:
        return self.primeira is not None


def _com_consumo(resultado: ResultadoItem, consumo: _custo.Acumulador, descricao: str) -> ResultadoItem:
    resultado.pesquisa_detalhes = {**consumo.resumo(), "orientacao": orientacao(descricao)}
    logger.info("Pesquisa item %s: %s", resultado.item_id, consumo.resumo())
    return resultado

def _erro(item: ItemEntrada, exc: Exception) -> ResultadoItem:
    logger.exception("Pesquisa do item %s falhou (%s)", item.id, type(exc).__name__)
    return ResultadoItem(item_id=item.id, status="erro", motivo=f"falha interna na pesquisa ({type(exc).__name__})")


@observe(name="pesquisa.item")
async def _fase_rapida(item: ItemEntrada, usar_agente: bool, usar_cache: bool) -> Rascunho:
    with _custo.acumular(item=True) as consumo:
        try:
            r = await _fase_rapida_impl(item, usar_agente, usar_cache)
        except asyncio.CancelledError:
            r = Rascunho(item, ResultadoItem(item_id=item.id, status="erro", motivo=MOTIVO_SEM_TEMPO))
        except Exception as exc:
            r = Rascunho(item, _erro(item, exc))
        r.consumo = consumo
        r.resultado = _com_consumo(r.resultado, consumo, item.descricao)
        return r


async def _fase_rapida_impl(item: ItemEntrada, usar_agente: bool, usar_cache: bool) -> Rascunho:
    """① cache → ② busca → ③ extração → ⑤ cálculo, SEM agente. Se faltar loja, devolve um resultado
    provisório e marca o item para a fase 2 (o cache só é gravado no resultado final)."""
    generico = item.classificacao == "pendente_especificacao"

    # ① cache válido
    anterior = await cache.ler(item.descricao, aceitar_vencido=True) if usar_cache else None
    if anterior and not anterior.vencido:
        calc = calcular(item, anterior.extracao, generico)
        if calc.tem_preco:
            imagem = await imagem_do_cache(anterior, item.descricao)
            return Rascunho(item, _resultado(
                item, calc, "pendente_especificacao" if generico else "definido", imagem,
                anterior.atualizado_em, anterior.iteracoes, pergunta=pergunta_para(item.descricao) if generico else None))

    # ② busca + ③ extração
    consulta = montar_consulta(item)
    # Google Shopping em paralelo: dezenas de lojas com preço estruturado (medido em 07/11: com só a busca, 33 de 113
    # itens dos exemplos ficavam a mais de 50% da mediana do Google)
    # e as lojas PERTO DA OBRA (Google Maps pelo CEP -> busca do Google nos sites delas): o diferencial do Orça
    (b, ext), google, regionais = await asyncio.gather(buscar_e_extrair(consulta, item.descricao),
                                                       ofertas_google(item.descricao, item.unidade, generico),
                                                       ofertas_regionais(item.descricao, item.unidade))
    google = await resolver_links_das_lojas(item.descricao, google)   # link da loja, não o da página do Google
    coleta = Coleta(imagem=b.imagem, provedor=b.provedor, modelo=ext.modelo, consultas=[consulta])
    coleta.juntar(regionais)
    coleta.juntar(ext.ofertas)
    coleta.juntar(google)
    calc = calcular(item, coleta.extracao(), generico)

    precisa = usar_agente and _precisa_refazer(calc) and get_settings().llm_configured
    resultado = await _concluir(item, coleta, anterior, b.erro, gravar_cache=not precisa)
    return Rascunho(item, resultado, coleta, anterior, b.erro,
                    primeira=resumo_para_agente(ext.ofertas, coleta, generico) if precisa else None)


def imagem_das_ofertas(ofertas: list[Oferta], usadas: set[str] | None = None) -> str | None:
    """Foto de uma oferta que entrou na conta (`usadas` = links das fontes); senão a de qualquer oferta do mesmo produto.
    As ofertas do Shopping já vêm ordenadas da mais parecida para a menos."""
    com_foto = [o for o in ofertas if o.imagem]
    escolhida = next((o for o in com_foto if usadas and o.url in usadas), None)         or next((o for o in com_foto if o.mesmo_produto == "sim"), None)
    return escolhida.imagem if escolhida else None


async def _concluir(item: ItemEntrada, coleta: Coleta, anterior: cache.EntradaCache | None, erro_busca: str | None,
                    gravar_cache: bool = True) -> ResultadoItem:
    """⑤ Resultado a partir de tudo que a coleta juntou (1ª busca + as do agente)."""
    generico = item.classificacao == "pendente_especificacao"
    agora = datetime.now(timezone.utc)
    calc = calcular(item, coleta.extracao(), generico)
    iteracoes = coleta.buscas_agente
    if not coleta.imagem:   # sem foto da busca: usa a do anúncio do Google Shopping (medido em 08/11: 6 de 7 itens sem foto)
        coleta.imagem = imagem_das_ofertas(coleta.ofertas, {f.url for f in calc.fontes})

    if calc.tem_preco:
        if gravar_cache:
            await cache.gravar(item.descricao, coleta.extracao(), coleta.imagem, coleta.provedor, anterior=anterior,
                               iteracoes=iteracoes)
        imagem = coleta.imagem or (anterior.imagem_url if anterior else None)
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
    with _custo.acumular(r.consumo, item=True) as consumo:
        try:
            resultado = await _fase_agente_impl(r, cliente_llm, timeout)
        except Exception as exc:
            resultado = r.resultado if r.resultado.status != "erro" else _erro(r.item, exc)
        return _com_consumo(resultado, consumo, r.item.descricao)


async def _fase_agente_impl(r: Rascunho, cliente_llm=None, timeout: float | None = None) -> ResultadoItem:
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
    loop = asyncio.get_running_loop()
    fim_total = loop.time() + s.pesquisa_prazo_total_s

    async def avisar(r: ResultadoItem) -> None:
        if not ao_terminar:
            return
        try:
            await ao_terminar(r)
        except Exception:  # noqa: BLE001 — falha ao gravar um item não derruba os outros
            logger.exception("ao_terminar falhou para o item %s", r.item_id)
            # Sem isto o item ficava "buscando" para sempre na tela. Uma linha mínima (sem preço) quase sempre
            # grava; com "erro", a tela oferece "Pesquisar de novo".
            try:
                await ao_terminar(ResultadoItem(item_id=r.item_id, status="erro",
                                                motivo="não consegui salvar o resultado; use Pesquisar de novo"))
            except Exception:  # noqa: BLE001
                logger.exception("Nem o erro do item %s foi gravado", r.item_id)

    async def fase1(item: ItemEntrada) -> Rascunho:
        try:
            r = await _fase_rapida(item, usar_agente, usar_cache)
        except Exception as exc:  # noqa: BLE001
            r = Rascunho(item, _erro(item, exc))
        if not r.precisa_agente or r.resultado.preco_emb_med is not None:
            await avisar(r.resultado)
        return r

    # Fase 1 com prazo: a função da Vercel morre no limite e o orçamento ficaria "pesquisando" (reenvio recusado por
    # minutos) com itens "buscando" para sempre. Item que não terminou a tempo vira "erro" com "Pesquisar de novo".
    tarefas = {asyncio.create_task(fase1(i)): i for i in itens}
    if tarefas:
        await asyncio.wait(tarefas, timeout=max(0.0, fim_total - loop.time()))
    pendurados = [t for t in tarefas if not t.done()]
    for tarefa in pendurados:
        tarefa.cancel()
    if pendurados:
        await asyncio.gather(*pendurados, return_exceptions=True)
    rascunhos = []
    for tarefa, item in tarefas.items():
        if tarefa.done() and not tarefa.cancelled() and tarefa.exception() is None:
            rascunhos.append(tarefa.result())
            continue
        tarefa.cancel()
        logger.warning("Item %s passou do prazo total da pesquisa (%.0f s)", item.id, s.pesquisa_prazo_total_s)
        r = ResultadoItem(item_id=item.id, status="erro", motivo=MOTIVO_SEM_TEMPO)
        await avisar(r)
        rascunhos.append(Rascunho(item, r))
    finais = {r.item.id: r.resultado for r in rascunhos}

    pendentes = sorted((r for r in rascunhos if r.precisa_agente), key=lambda r: r.resultado.preco_emb_med is not None)
    if pendentes:
        prazo = min(loop.time() + s.pesquisa_prazo_agentes_s, fim_total)
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
