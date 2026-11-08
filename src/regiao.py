"""Lojas de material de construção PERTO DA OBRA (o diferencial do Orça: comprar perto de quem compra).

Pelo CEP da obra: Google Maps (serper.dev /places) acha as lojas da cidade, com endereço, coordenadas e site.
Medido em 07/11 (Recife): Canal da Construção, Armazém Casa Amarela, Atacado da Construção, CEMAFEL, Ferreira Pinto...
Essas lojas entram de três jeitos na pesquisa:
1. a busca procura o produto DENTRO dos sites delas (src/busca.py, busca regional);
2. anúncio do Google Shopping de uma loja com o mesmo nome conta como loja da região (src/google_shopping.py);
3. a fonte do preço sai marcada `perto_da_obra`, com distância e endereço, e vem primeiro na tela (src/calculo.py).

Vale para o orçamento inteiro por um ContextVar (`na_obra`), sem mudar assinaturas nem o contrato com A/C.
Sem SERPER_API_KEYS, ou com falha, a lista fica vazia e tudo segue como antes.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
import unicodedata
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .busca import LOCAL_DA_OBRA, Local, local_do_cep
from .config import get_settings

logger = logging.getLogger(__name__)

URL_PLACES = "https://google.serper.dev/places"
TIMEOUT_S = 6.0
CACHE_S = 12 * 3600.0
FATOR_ROTA = 1.3            # linha reta -> caminho de carro (mesmo fator da logística)
MAX_KM = 40.0               # mais longe que isso não é "perto da obra"
CONSULTAS = ["loja de material de construção", "home center materiais de construção", "loja de tintas",
             "loja de pisos e revestimentos", "loja de material elétrico e hidráulico"]
# site que não é a loja (rede social, agregador): a loja continua valendo pelo nome, sem busca no site
SITES_QUE_NAO_SAO_LOJA = re.compile(r"instagram|facebook|wa\.me|whatsapp|linktr|google\.|goo\.gl|bit\.ly|"
                                    r"linkedin|youtube|tiktok|ifood|ubereats|wix(site)?\.com|negocio\.site", re.I)
# Nome genérico demais para casar loja do Shopping com loja do Maps
PALAVRAS_GENERICAS = {"loja", "lojas", "material", "materiais", "construcao", "de", "da", "do", "e", "home", "center",
                      "ltda", "me", "eireli", "comercio", "deposito", "armazem", "matriz", "filial", "recife",
                      "acabamentos", "tintas", "eletrica", "hidraulica", "atacado"}


@dataclass(frozen=True)
class LojaRegional:
    nome: str
    dominio: str | None        # site próprio da loja (None = só rede social)
    endereco: str | None
    lat: float
    lon: float
    km: float | None           # distância de carro aproximada até a obra


LOJAS_DA_REGIAO: ContextVar[tuple[LojaRegional, ...]] = ContextVar("lojas_da_regiao", default=())


@contextmanager
def na_obra(local: Local | None, lojas: tuple[LojaRegional, ...] | list[LojaRegional]):
    """Local (cidade/UF) e lojas da região valem para toda a pesquisa feita dentro do `with`."""
    t1, t2 = LOCAL_DA_OBRA.set(local), LOJAS_DA_REGIAO.set(tuple(lojas))
    try:
        yield
    finally:
        LOJAS_DA_REGIAO.reset(t2)
        LOCAL_DA_OBRA.reset(t1)


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def _palavras(nome: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _sem_acento(nome)) if len(w) >= 3} - PALAVRAS_GENERICAS


def _dominio(site: str | None) -> str | None:
    if not site or SITES_QUE_NAO_SAO_LOJA.search(site):
        return None
    host = (urlparse(site if "://" in site else f"https://{site}").hostname or "").lower()
    return host[4:] if host.startswith("www.") else (host or None)


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def ler_places(lista: list[dict], obra: tuple[float, float] | None) -> list[LojaRegional]:
    """Núcleo puro: resposta do /places -> lojas (sem repetir), mais perto primeiro."""
    saida: dict[str, LojaRegional] = {}
    for p in lista:
        if not isinstance(p, dict):
            continue
        nome, lat, lon = (p.get("title") or "").strip(), p.get("latitude"), p.get("longitude")
        if not nome or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        km = round(_haversine(obra, (lat, lon)) * FATOR_ROTA, 1) if obra else None
        if km is not None and km > MAX_KM:
            continue
        dom = _dominio(p.get("website"))
        chave = dom or _sem_acento(nome)
        atual = saida.get(chave)
        if atual is None or (km is not None and (atual.km is None or km < atual.km)):   # filial mais perto vence
            saida[chave] = LojaRegional(nome=nome, dominio=dom, endereco=p.get("address"), lat=lat, lon=lon, km=km)
    return sorted(saida.values(), key=lambda l: (l.km is None, l.km or 0))


_cache: dict[str, tuple[float, list[LojaRegional]]] = {}


async def lojas_da_regiao(local: Local | None, obra: tuple[float, float] | None = None,
                          cliente: httpx.AsyncClient | None = None) -> list[LojaRegional]:
    """Lojas da cidade da obra pelo Google Maps (várias consultas em paralelo, cache de 12 h). Falha = []."""
    chaves = get_settings().serper_keys
    if not local or not chaves:
        return []
    chave_cache = f"{_sem_acento(local.cidade)}/{local.uf.upper()}/{obra}"
    guardado = _cache.get(chave_cache)
    if guardado and time.monotonic() - guardado[0] < CACHE_S:
        return guardado[1]
    proprio = cliente is None
    cli = cliente or httpx.AsyncClient(timeout=TIMEOUT_S)

    async def uma(consulta: str) -> list[dict]:
        for k in chaves:
            try:
                r = await cli.post(URL_PLACES, headers={"X-API-KEY": k, "Content-Type": "application/json"},
                                   json={"q": f"{consulta} {local.cidade} {local.uf}", "gl": "br", "hl": "pt-br"})
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google Maps (Serper) falhou (%s)", type(exc).__name__)
                return []
            if r.status_code in (401, 403, 429):
                continue
            if r.status_code != 200:
                return []
            try:
                return [p for p in (r.json().get("places") or []) if isinstance(p, dict)]
            except Exception:  # noqa: BLE001
                return []
        return []

    try:
        respostas = await asyncio.gather(*(uma(c) for c in CONSULTAS))
    finally:
        if proprio:
            await cli.aclose()
    lojas = ler_places([p for r in respostas for p in r], obra)
    if lojas:
        _cache[chave_cache] = (time.monotonic(), lojas)
    logger.info("Lojas da região (%s/%s): %d, %d com site", local.cidade, local.uf, len(lojas),
                sum(1 for l in lojas if l.dominio))
    return lojas


async def preparar_obra(cep: str | None) -> tuple[Local | None, list[LojaRegional]]:
    """CEP -> (cidade/UF, lojas da região com distância). Nunca levanta: sem dado, a pesquisa segue sem região."""
    try:
        local = await local_do_cep(cep)
        if not local:
            return None, []
        obra = None
        try:
            from .logistica import coordenadas_cep   # ViaCEP + Nominatim (já usado pela logística da C)
            obra = await asyncio.wait_for(asyncio.to_thread(coordenadas_cep, re.sub(r"\D", "", cep or "")), 8)
        except Exception:  # noqa: BLE001 — sem coordenada: lojas da cidade sem distância
            obra = None
        return local, await lojas_da_regiao(local, obra)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Não deu para preparar a região da obra (%s)", type(exc).__name__)
        return None, []


# ------------------------------------------------------------------ consultas usadas na busca e no cálculo
def dominios_regionais() -> list[str]:
    return [l.dominio for l in LOJAS_DA_REGIAO.get() if l.dominio]


def regional_por_dominio(dominio: str | None) -> LojaRegional | None:
    if not dominio:
        return None
    return next((l for l in LOJAS_DA_REGIAO.get()
                 if l.dominio and (dominio == l.dominio or dominio.endswith("." + l.dominio))), None)


def regional_por_nome(nome: str | None) -> LojaRegional | None:
    """'Ferreira Pinto' (Shopping) casa com 'Ferreira Pinto - Matriz' (Maps). Precisa de 1+ palavra própria em comum
    e de TODAS as palavras próprias do nome mais curto."""
    alvo = _palavras(nome or "")
    if not alvo:
        return None
    for l in LOJAS_DA_REGIAO.get():
        p = _palavras(l.nome)
        if p and (alvo <= p or p <= alvo):
            return l
    return None
