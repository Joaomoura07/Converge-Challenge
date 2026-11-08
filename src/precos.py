"""Etapa ③ da pesquisa: lê os anúncios achados na busca, extrai o preço de cada um e
confere se é o MESMO produto pedido. Usa um modelo rápido (medido na avaliação da etapa 3:
Qwen3-32B, 5 s e 5/5 com o formato curto `i|preco|embalagem|M`).

Trava "nunca inventar preço": o preço devolvido pelo LLM só é aceito se aparecer escrito
no texto do anúncio.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
import weakref
from dataclasses import dataclass, field
from typing import Literal

from langfuse import get_client, observe
from openai import APIStatusError, AsyncOpenAI
from pydantic import BaseModel

from . import custo as _custo
from . import chaves_llm
from .busca import ResultadoWeb
from .config import get_settings, load_prompt
from .modelos import Fonte

logger = logging.getLogger(__name__)

# Reserva: medido em 07/11 no caso de controle (3 rodadas + 2): Mistral Small 3.2 acertou todas em 2,7–3,4 s (uma de
# 12 s); a Gemma 4 31B (reserva anterior) acertou em 4,6–19,8 s. Qwen3-8B devolveu resposta vazia.
MODELO_RESERVA_EXTRACAO = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
LIMITE_TRECHO = 500
# Palavras inteiras no prompt: com letras soltas (S/P/N) os modelos copiavam o NOME do campo ("M")
# em vez do valor (medido na revisão da etapa 3). Valor desconhecido = linha rejeitada, nunca "nao" silencioso.
MAPA_IGUAL = {"SIM": "sim", "S": "sim", "PARECIDO": "parecido", "P": "parecido", "NAO": "nao", "NÃO": "nao", "N": "nao"}
TIMEOUT_EXTRACAO_S = 20


class Oferta(BaseModel):
    loja: str
    dominio: str
    url: str
    titulo: str
    preco: float | None
    embalagem: str | None
    mesmo_produto: Literal["sim", "parecido", "nao"]
    link_verificado: bool = False
    imagem: str | None = None   # foto do anúncio (o Google Shopping devolve `imageUrl` em todos os anúncios)

    def para_fonte(self) -> Fonte:
        assert self.preco, "oferta sem preço não vira fonte"
        return Fonte(loja=self.loja, dominio=self.dominio, url=self.url,
                     preco_embalagem=self.preco, embalagem=self.embalagem)


@dataclass
class ResultadoExtracao:
    ofertas: list[Oferta] = field(default_factory=list)
    modelo: str = ""
    ms: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    descartadas_alucinacao: int = 0
    erro: str | None = None
    tentativas: list[str] = field(default_factory=list)   # diagnóstico: "modelo: 4.7s ok" / "modelo: HTTP 503"

    @property
    def conferidas(self) -> list[Oferta]:
        """Ofertas do MESMO produto e com preço: as únicas que entram na média."""
        return [o for o in self.ofertas if o.mesmo_produto == "sim" and o.preco]


# ------------------------------------------------------------------ trava anti-alucinação
def _variantes_preco(p: float) -> tuple[set[str], set[str]]:
    """(com centavos, sem centavos). 739.9 -> ({'739,90', '739.90', '739,9'}, {});
    1599.0 -> ({'1.599,00', '1599,00', ...}, {'1.599', '1599'})."""
    br = f"{p:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    com = {br, br.replace(".", ""), f"{p:.2f}", f"{p:.2f}".replace(".", ","), f"{p:,.2f}"}
    sem = set()
    if br.endswith(",00"):
        sem = {br[:-3], br[:-3].replace(".", "")}
    if br.endswith("0"):
        com.add(br[:-1])
    return com, sem


def preco_no_texto(preco: float, texto: str) -> bool:
    """O preço precisa estar escrito no anúncio. Com centavos ('1.470,00') vale em qualquer lugar; um número
    redondo SEM centavos só vale depois de 'R$'. Medido no site em 07/11: o LLM leu o código do produto no título
    ('Selador Acrílico 3,6L 1470 - Coral') como preço de R$ 1.470, e a trava aceitava porque '1470' estava escrito."""
    t = re.sub(r"(?<=R\$)\s+", "", texto)
    com, sem = _variantes_preco(preco)
    if any(re.search(rf"(?<![\d.,]){re.escape(x)}(?![\d])", t) for x in com):
        return True
    return any(re.search(rf"R\${re.escape(x)}(?![\d]|[.,]\d)", t) for x in sem)


# ------------------------------------------------------------------ montagem e leitura
def montar_anuncios(resultados: list[ResultadoWeb]) -> str:
    return "\n".join(f"[{i}] {r.loja}: {r.titulo} — {r.trecho[:LIMITE_TRECHO]}" for i, r in enumerate(resultados))


def ler_resposta(texto: str, resultados: list[ResultadoWeb]) -> tuple[list[Oferta], int]:
    """Lê as linhas i|preco|embalagem|M. Ignora lixo, índices fora da lista e preços não encontrados no texto."""
    texto = re.sub(r"<think>.*?</think>", "", texto or "", flags=re.S)
    ofertas, vistos, alucinadas = [], set(), 0
    for linha in texto.splitlines():
        partes = [p.strip() for p in linha.strip().strip("`").split("|")]
        if len(partes) != 4 or not partes[0].isdigit():
            continue
        i = int(partes[0])
        if i >= len(resultados) or i in vistos:
            continue
        vistos.add(i)
        r = resultados[i]
        try:
            preco = float(partes[1].replace("R$", "").strip())
            preco = preco if preco > 0 else None
        except ValueError:
            preco = None
        if preco and not preco_no_texto(preco, f"{r.titulo} {r.trecho}"):
            logger.warning("Preço %.2f não aparece no anúncio %d (%s): descartado", preco, i, r.loja)
            preco, alucinadas = None, alucinadas + 1
        emb = partes[2] if partes[2] not in ("", "-") else None
        igual = MAPA_IGUAL.get(partes[3].upper().strip(" .*"))
        if igual is None:
            logger.warning("Linha %d com valor de comparação desconhecido %r: rejeitada", i, partes[3])
            vistos.discard(i)
            continue
        ofertas.append(Oferta(loja=r.loja, dominio=r.dominio, url=r.url, titulo=r.titulo,
                              preco=preco, embalagem=emb, mesmo_produto=igual))
    return ofertas, alucinadas


# ------------------------------------------------------------------ chamada ao LLM
def semaforo_do_loop(registro: weakref.WeakKeyDictionary, vagas: int) -> asyncio.Semaphore:
    """Um semáforo por event loop, guardado pelo PRÓPRIO loop (referência fraca), não por id(loop):
    o Python reaproveita o id de um loop já fechado, e o loop novo herdava um semáforo com vagas
    presas (travou a suíte de testes; em produção, um `asyncio.run` por requisição teria o mesmo risco)."""
    loop = asyncio.get_running_loop()
    if loop not in registro:
        registro[loop] = asyncio.Semaphore(vagas)
    return registro[loop]


def _cliente(chave: str | None = None) -> AsyncOpenAI:
    s = get_settings()
    # Tempo curto + 1 nova tentativa: se o modelo principal travar, a reserva assume rápido (demo de ~30 s).
    return AsyncOpenAI(api_key=chave or s.featherless_key or "missing", base_url=s.featherless_base_url,
                       timeout=TIMEOUT_EXTRACAO_S, max_retries=1)


ERROS_DA_CHAVE = {429, 500, 502, 503, 504}   # problema da conta/servidor: vale tentar com outra chave


class RespostaVazia(Exception):
    """A Featherless sobrecarregada responde HTTP 200 SEM `choices` (só um campo `error`: failed_generation).
    O SDK não tenta de novo (o status é 200), então o tratamos aqui. Medido: 6 chamadas simultâneas ao Qwen3-32B → 3 vazias."""


def conferir_resposta(r) -> None:
    if not getattr(r, "choices", None):
        erro = getattr(r, "error", None) or (getattr(r, "model_extra", None) or {}).get("error")
        raise RespostaVazia(str(erro)[:160] if erro else "resposta sem choices")


TENTATIVAS_RESPOSTA_VAZIA = 2


@observe(as_type="generation", name="llm.extracao", capture_input=False, capture_output=False)
async def _chamar(cliente, modelo: str, produto: str, anuncios: str):
    sufixo = " /no_think" if "qwen3" in modelo.lower() else ""   # desliga o raciocínio do Qwen3 (medido: 16 s -> 5 s)
    mensagens = [{"role": "system", "content": load_prompt("extrator_precos")},
                 {"role": "user", "content": f"Produto pedido: {produto}\n\n{anuncios}{sufixo}"}]
    lf = get_client()
    lf.update_current_generation(model=modelo, input=mensagens)
    falhou = None
    for tentativa in range(TENTATIVAS_RESPOSTA_VAZIA):
        # vaga numa das chaves de extração (a menos ocupada; evita a que acabou de falhar)
        async with chaves_llm.pool_extracao().vaga(evitar=falhou) as chave:
            cli = cliente or _cliente(chave)
            try:
                r = await cli.chat.completions.create(model=modelo, messages=mensagens, temperature=0, top_p=get_settings().llm_top_p,
                                                      max_tokens=400)
            except APIStatusError as exc:
                if exc.status_code in ERROS_DA_CHAVE:
                    chaves_llm.esfriar(chave)
                raise
            finally:
                if cliente is None:
                    await cli.close()   # sem isso o httpx reclama "Event loop is closed" ao sair
        try:
            conferir_resposta(r)
            break
        except RespostaVazia:
            chaves_llm.esfriar(chave)   # a próxima tentativa vai para outra chave
            falhou = chave
            if tentativa == TENTATIVAS_RESPOSTA_VAZIA - 1:
                raise
            logger.info("Featherless devolveu resposta vazia (%s); tentando de novo", modelo)
            await asyncio.sleep(0.3 + random.random() / 2)   # espalha as novas tentativas
    custo = getattr(r.usage, "cost", None) if r.usage else None
    lf.update_current_generation(
        output=r.choices[0].message.content,
        usage_details={"input": r.usage.prompt_tokens, "output": r.usage.completion_tokens} if r.usage else None,
        cost_details={"total": float(custo)} if custo is not None else None)
    return r


async def extrair_e_conferir(produto: str, resultados: list[ResultadoWeb], cliente=None) -> ResultadoExtracao:
    """Uma chamada ao modelo rápido para todos os anúncios do item. Reserva: Gemma 4, se o principal
    der erro ou não devolver nenhuma linha válida."""
    if not resultados:
        return ResultadoExtracao(erro="nenhum anúncio para ler")
    # cliente=None (produção): cada chamada usa a chave que o rodízio escolher (src/chaves_llm.py)
    return await _extrair(produto, resultados, cliente)


# Disjuntor: modelo que a Featherless recusa com 400 ("not available for inference" / frio carregando)
# fica fora por um tempo. Medido em 07/11 14h: o Qwen3-32B saiu do ar e CADA extração gastava até 19 s
# numa chamada perdida antes da reserva — o agente estourava os 40 s por isso.
PAUSA_MODELO_INDISPONIVEL_S = 600
_indisponivel_ate: dict[str, float] = {}


def _disponivel(modelo: str) -> bool:
    return _indisponivel_ate.get(modelo, 0) <= time.monotonic()


def _marcar_indisponivel(modelo: str) -> None:
    _indisponivel_ate[modelo] = time.monotonic() + PAUSA_MODELO_INDISPONIVEL_S
    logger.warning("Modelo %s indisponível na Featherless: pulado por %d min", modelo, PAUSA_MODELO_INDISPONIVEL_S // 60)


def modelos_extracao() -> list[str]:
    """Principal e reserva, sem os que estão no disjuntor. Se todos estiverem, tenta todos (melhor que nada)."""
    todos = list(dict.fromkeys([get_settings().pesquisa_modelo_extracao, MODELO_RESERVA_EXTRACAO]))
    return [m for m in todos if _disponivel(m)] or todos


@dataclass
class _Tentativa:
    modelo: str
    ofertas: list[Oferta] = field(default_factory=list)
    alucinadas: int = 0
    usage: object | None = None
    erro: str | None = None
    texto: str = ""


async def _tentar(cliente, modelo: str, produto: str, anuncios: str, resultados: list[ResultadoWeb]) -> _Tentativa:
    """Uma tentativa com um modelo. Nunca levanta exceção (só cancelamento): o erro vira dado."""
    t = time.perf_counter()
    try:
        r = await _chamar(cliente, modelo, produto, anuncios)
    except APIStatusError as exc:
        logger.warning("Extração com %s falhou (HTTP %s); tentando reserva", modelo, exc.status_code)
        if exc.status_code == 400:
            _marcar_indisponivel(modelo)
        erro = f"{modelo}: HTTP {exc.status_code}"
        return _Tentativa(modelo, erro=erro, texto=f"{erro} ({time.perf_counter() - t:.1f}s)")
    except Exception as exc:  # noqa: BLE001 — timeout/rede/resposta vazia
        logger.warning("Extração com %s falhou (%s: %s); tentando reserva", modelo, type(exc).__name__, str(exc)[:100])
        erro = f"{modelo}: {type(exc).__name__}"
        return _Tentativa(modelo, erro=erro, texto=f"{erro} ({time.perf_counter() - t:.1f}s)")
    ofertas, alucinadas = ler_resposta(r.choices[0].message.content or "", resultados)
    return _Tentativa(modelo, ofertas, alucinadas, r.usage, None if ofertas else f"{modelo}: resposta sem linhas válidas",
                      f"{modelo}: {time.perf_counter() - t:.1f}s, {len(ofertas)} linhas válidas")


async def _extrair(produto: str, resultados: list[ResultadoWeb], cliente) -> ResultadoExtracao:
    """Principal primeiro. Se ele FALHAR, a reserva entra na hora; se só DEMORAR mais que `pesquisa_hedge_s`,
    a reserva é disparada EM PARALELO (outra chave do rodízio) e vale a primeira resposta com linhas válidas;
    a outra é cancelada. Medido em 07/11: a mesma extração levou 3,4 s numa rodada e 132 s na seguinte."""
    anuncios = montar_anuncios(resultados)
    t0 = time.perf_counter()
    res = ResultadoExtracao()
    fila = modelos_extracao()
    ativas: dict[asyncio.Task, str] = {}

    def lancar() -> None:
        if fila:
            modelo = fila.pop(0)
            ativas[asyncio.create_task(_tentar(cliente, modelo, produto, anuncios, resultados))] = modelo

    lancar()
    try:
        while ativas:
            prazo = get_settings().pesquisa_hedge_s if fila else None
            feitas, _ = await asyncio.wait(ativas, timeout=prazo, return_when=asyncio.FIRST_COMPLETED)
            if not feitas:   # principal demorando: reserva em paralelo
                logger.info("Extração lenta (> %.0f s): reserva em paralelo", prazo)
                res.tentativas.append(f"{next(iter(ativas.values()))}: lento, reserva em paralelo")
                lancar()
                continue
            for tarefa in feitas:
                ativas.pop(tarefa)
                t = tarefa.result()
                res.tentativas.append(t.texto)
                res.descartadas_alucinacao += t.alucinadas
                if t.usage:
                    res.tokens_entrada += t.usage.prompt_tokens or 0
                    res.tokens_saida += t.usage.completion_tokens or 0
                    res.custo_usd += float(getattr(t.usage, "cost", 0) or 0)
                    _custo.registrar(getattr(t.usage, "cost", 0))
                if t.ofertas and not res.ofertas:
                    res.ofertas, res.modelo, res.erro = t.ofertas, t.modelo, None
                elif not res.ofertas:
                    res.erro = t.erro
            if res.ofertas:
                break
            if not ativas:   # falhou rápido: próxima da fila
                lancar()
    finally:
        for tarefa in ativas:   # a outra (mais lenta) é cancelada e devolve a vaga da chave
            tarefa.cancel()
        if ativas:
            await asyncio.gather(*ativas, return_exceptions=True)
    res.ms = int((time.perf_counter() - t0) * 1000)
    return res
