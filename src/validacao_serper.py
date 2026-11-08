"""Segunda fonte para o preço: Google Shopping via serper.dev.

Só VALIDA. Nunca troca o preço do item nem entra em `fontes` (a Fatia C casa `fontes[].dominio` com a tabela
`fornecedores`). O que ela faz: compara o nosso preço com a mediana de anúncios do Google que parecem o mesmo produto
e, se a diferença for grande, avisa (`validacao`) e rebaixa a confiança para "baixa".

Desligada sem `SERPER_API_KEYS`. Falha, timeout ou resposta estranha = `sem_dados`; nunca derruba a pesquisa.

ATENÇÃO: o formato exato da resposta do endpoint /shopping (campos title, price, link, source) vem da documentação
pública resumida por terceiros e AINDA NÃO foi conferido com uma chave real. A leitura é defensiva (aceita preço
texto ou número) e o teste com chave real está no plano (docs/VALIDACAO-E-LOJAS-PROXIMAS.md).
"""

from __future__ import annotations

import asyncio
import logging
import re
import statistics
import time

import httpx
from langfuse import observe

from .cache import chave_cache
from .compra import Conteudo, conteudo_embalagem
from .config import get_settings
from .modelos import ResultadoItem, Validacao

logger = logging.getLogger(__name__)

URL_SHOPPING = "https://google.serper.dev/shopping"
TIMEOUT_S = 5.0
LIMITE_CONFIRMADO = 0.25      # até 25% de diferença: confirmado
LIMITE_LEVE = 0.50            # até 50%: divergente leve; acima, divergente (a confiança cai para "baixa")
MIN_COMPARAVEIS = 2           # com menos anúncios comparáveis não se afirma nada
MIN_PARECIDO = 0.6            # fração das palavras do item que precisa aparecer no título do anúncio
CACHE_S = 3600.0
ERROS_DA_CHAVE = {401, 403, 429}   # chave inválida, sem crédito ou limite: vale tentar a próxima

_cache: dict[str, tuple[float, list[dict]]] = {}
_PRECO = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{1,2}|\d+,\d{1,2}|\d+\.\d{1,2}|\d+")


def ativo() -> bool:
    return bool(get_settings().serper_keys)


def converter_preco(valor) -> float | None:
    """'R$ 1.234,56' -> 1234.56 · '739,90' -> 739.9 · 739.9 -> 739.9. Texto sem número = None."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor) if valor > 0 else None
    achou = _PRECO.search(str(valor or "").replace("R$", " "))
    if not achou:
        return None
    t = achou.group(0)
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if v > 0 else None


def _parecido(descricao: str, titulo: str) -> bool:
    """O título do anúncio contém a maior parte das palavras do item (marca, linha, medida)."""
    item = set(chave_cache(descricao).split())
    anuncio = set(chave_cache(titulo).split())
    if len(item) < 2:
        return False
    return len(item & anuncio) / len(item) >= MIN_PARECIDO


async def _buscar(consulta: str, cliente: httpx.AsyncClient | None = None) -> list[dict]:
    """Anúncios do Google Shopping para a consulta (em cache por 1 h). Falha = lista vazia."""
    agora = time.monotonic()
    guardado = _cache.get(consulta)
    if guardado and agora - guardado[0] < CACHE_S:
        return guardado[1]
    chaves = get_settings().serper_keys
    proprio = cliente is None
    cli = cliente or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        for chave in chaves:
            try:
                r = await cli.post(URL_SHOPPING, headers={"X-API-KEY": chave, "Content-Type": "application/json"},
                                   json={"q": consulta, "gl": "br", "hl": "pt-br", "num": 10})
            except Exception as exc:  # noqa: BLE001 — rede, timeout
                logger.warning("Serper falhou (%s): sem conferência neste item", type(exc).__name__)
                return []
            if r.status_code in ERROS_DA_CHAVE:
                logger.warning("Serper: chave recusada (HTTP %s); tentando a próxima", r.status_code)
                continue
            if r.status_code != 200:
                logger.warning("Serper respondeu HTTP %s: sem conferência neste item", r.status_code)
                return []
            try:
                lista = r.json().get("shopping") or []
            except Exception:  # noqa: BLE001
                return []
            lista = [a for a in lista if isinstance(a, dict)]
            _cache[consulta] = (agora, lista)
            return lista
        return []
    finally:
        if proprio:
            await cli.aclose()


def comparar(descricao: str, embalagem: str | None, nosso_preco: float, anuncios: list[dict]) -> Validacao:
    """Núcleo puro: compara o preço por unidade base (R$/L, R$/m², R$/un...) dos anúncios parecidos com o nosso."""
    nosso = conteudo_embalagem(embalagem)
    if nosso is None or nosso.quantidade <= 0:
        return Validacao(status="sem_dados")
    unitarios = []
    for a in anuncios:
        preco = converter_preco(a.get("price"))
        titulo = str(a.get("title") or "")
        if preco is None or not _parecido(descricao, titulo):
            continue
        c = conteudo_embalagem(titulo)
        if c is None and nosso.unidade == "un":
            c = Conteudo(1.0, "un")     # anúncio de uma peça só, sem medida no título
        if c is None or c.unidade != nosso.unidade or c.quantidade <= 0:
            continue
        unitarios.append(preco / c.quantidade)
    if len(unitarios) < MIN_COMPARAVEIS:
        return Validacao(status="sem_dados", n=len(unitarios))
    mediana = statistics.median(unitarios) * nosso.quantidade
    dif = abs(nosso_preco - mediana) / mediana
    status = "confirmado" if dif <= LIMITE_CONFIRMADO else "divergente_leve" if dif <= LIMITE_LEVE else "divergente"
    return Validacao(status=status, mediana=round(mediana, 2), diferenca_pct=round(dif * 100, 1), n=len(unitarios))


@observe(name="validacao.serper")
async def validar(r: ResultadoItem, cliente: httpx.AsyncClient | None = None) -> ResultadoItem:
    """Devolve o resultado com `validacao` preenchida. Só itens com preço de verdade (não estimativa)."""
    if (not ativo() or r.status != "definido" or r.estimativa or r.preco_emb_med is None
            or not r.produto_normalizado or r.validacao is not None):
        return r
    try:
        anuncios = await asyncio.wait_for(_buscar(r.produto_normalizado, cliente), timeout=TIMEOUT_S + 2)
        v = comparar(r.produto_normalizado, r.embalagem, r.preco_emb_med, anuncios)
    except Exception as exc:  # noqa: BLE001 — a conferência nunca derruba a pesquisa
        logger.warning("Conferência no Serper falhou para '%s' (%s)", r.produto_normalizado, type(exc).__name__)
        return r
    mudanca: dict = {"validacao": v}
    if v.status == "divergente":
        mudanca["confianca"] = "baixa"
    return r.model_copy(update=mudanca)
