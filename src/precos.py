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
from dataclasses import dataclass, field
from typing import Literal

from langfuse import get_client, observe
from openai import APIStatusError, AsyncOpenAI
from pydantic import BaseModel

from .busca import ResultadoWeb
from .config import get_settings, load_prompt
from .modelos import Fonte

logger = logging.getLogger(__name__)

MODELO_RESERVA_EXTRACAO = "google/gemma-4-31B-it"   # 5/5 na avaliação; usado se o principal falhar
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
def _variantes_preco(p: float) -> set[str]:
    """739.9 -> {'739,90', '739.90', '739,9'}; 1599.0 -> {'1.599,00', '1599,00', '1.599', '1599'}."""
    br = f"{p:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    v = {br, br.replace(".", ""), f"{p:.2f}", f"{p:.2f}".replace(".", ","), f"{p:,.2f}"}
    if br.endswith(",00"):
        v |= {br[:-3], br[:-3].replace(".", "")}
    if br.endswith("0"):
        v.add(br[:-1])
    return v


def preco_no_texto(preco: float, texto: str) -> bool:
    t = re.sub(r"(?<=R\$)\s+", "", texto)
    return any(re.search(rf"(?<![\d.,]){re.escape(x)}(?![\d])", t) for x in _variantes_preco(preco))


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
_semaforos: dict[int, asyncio.Semaphore] = {}


def _porteiro() -> asyncio.Semaphore:
    """No máximo N chamadas simultâneas à Featherless (evita erro 429). Um por event loop."""
    loop = id(asyncio.get_running_loop())
    if loop not in _semaforos:
        _semaforos[loop] = asyncio.Semaphore(get_settings().pesquisa_concorrencia_llm)
    return _semaforos[loop]


def _cliente() -> AsyncOpenAI:
    s = get_settings()
    # Tempo curto + 1 nova tentativa: se o modelo principal travar, a reserva assume rápido (demo de ~30 s).
    return AsyncOpenAI(api_key=s.featherless_api_key or "missing", base_url=s.featherless_base_url,
                       timeout=TIMEOUT_EXTRACAO_S, max_retries=1)


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
    for tentativa in range(TENTATIVAS_RESPOSTA_VAZIA):
        async with _porteiro():
            r = await cliente.chat.completions.create(model=modelo, messages=mensagens, temperature=0, max_tokens=400)
        try:
            conferir_resposta(r)
            break
        except RespostaVazia:
            if tentativa == TENTATIVAS_RESPOSTA_VAZIA - 1:
                raise
            logger.info("Featherless devolveu resposta vazia (%s); tentando de novo", modelo)
            await asyncio.sleep(1.0 + random.random())   # espalha as novas tentativas
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
    proprio = cliente is None
    cliente = cliente or _cliente()
    try:
        return await _extrair(produto, resultados, cliente)
    finally:
        if proprio:
            await cliente.close()   # sem isso o httpx reclama "Event loop is closed" ao sair


async def _extrair(produto: str, resultados: list[ResultadoWeb], cliente) -> ResultadoExtracao:
    anuncios = montar_anuncios(resultados)
    t0 = time.perf_counter()
    res = ResultadoExtracao()
    for modelo in (get_settings().pesquisa_modelo_extracao, MODELO_RESERVA_EXTRACAO):
        t_modelo = time.perf_counter()
        try:
            r = await _chamar(cliente, modelo, produto, anuncios)
        except APIStatusError as exc:
            res.erro = f"{modelo}: HTTP {exc.status_code}"
            res.tentativas.append(f"{res.erro} ({time.perf_counter() - t_modelo:.1f}s)")
            logger.warning("Extração com %s falhou (HTTP %s); tentando reserva", modelo, exc.status_code)
            continue
        except Exception as exc:  # noqa: BLE001 — timeout/rede/resposta vazia
            res.erro = f"{modelo}: {type(exc).__name__}"
            res.tentativas.append(f"{res.erro} ({time.perf_counter() - t_modelo:.1f}s)")
            logger.warning("Extração com %s falhou (%s: %s); tentando reserva", modelo, type(exc).__name__, str(exc)[:100])
            continue
        if r.usage:
            res.tokens_entrada += r.usage.prompt_tokens or 0
            res.tokens_saida += r.usage.completion_tokens or 0
            res.custo_usd += float(getattr(r.usage, "cost", 0) or 0)
        ofertas, alucinadas = ler_resposta(r.choices[0].message.content or "", resultados)
        res.descartadas_alucinacao += alucinadas
        res.tentativas.append(f"{modelo}: {time.perf_counter() - t_modelo:.1f}s, {len(ofertas)} linhas válidas")
        if ofertas:
            res.ofertas, res.modelo, res.erro = ofertas, modelo, None
            break
        res.erro = f"{modelo}: resposta sem linhas válidas"
    res.ms = int((time.perf_counter() - t0) * 1000)
    return res
