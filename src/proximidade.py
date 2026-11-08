"""Lojas físicas perto da obra, com distância e tempo de carro.

Duas peças, ambas opcionais (sem chave, o resultado é só mais simples; nada quebra):
- `lojas_proximas`: Serper /places ("Leroy Merlin Recife PE") para as redes da lista fixa que têm loja física.
- `rota_matriz`: OpenRouteService (rota de carro: km e minutos). Sem chave ou com falha, cai na estimativa
  `linha reta x 1,3` que a logística já usa, com minutos por velocidade média, marcada `aproximado=True`.

ATENÇÃO: os formatos de resposta do Serper /places e do OpenRouteService vêm da documentação pública resumida e ainda
NÃO foram conferidos com chave real; a leitura é defensiva. O cache de lojas é em memória (some quando a função da
Vercel reinicia): para guardar de verdade falta uma tabela, a combinar com o Samuel.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass

import httpx

from .busca import local_do_cep
from .config import get_settings
from .logistica import _coordenada, _haversine

logger = logging.getLogger(__name__)

URL_PLACES = "https://google.serper.dev/places"
URL_ORS = "https://api.openrouteservice.org/v2/matrix/driving-car"
TIMEOUT_S = 8.0
FATOR_ROTA = 1.3            # linha reta -> rota (mesmo fator de src/logistica.py)
VELOCIDADE_MEDIA_KMH = 30.0   # trânsito urbano: só para a estimativa quando não há rota real
CACHE_LOJAS_S = 24 * 3600.0
SIMULTANEAS = 4

# Redes da lista fixa de busca (src/busca.py: LOJAS) que têm loja física. Marketplaces ficam de fora.
REDES_FISICAS: dict[str, tuple[str, str]] = {   # domínio -> (nome para buscar, palavra que o título da loja precisa ter)
    "leroymerlin.com.br": ("Leroy Merlin", "leroy"),
    "cec.com.br": ("C&C", "c&c"),
    "telhanorte.com.br": ("Telhanorte", "telhanorte"),
    "obramax.com.br": ("Obramax", "obramax"),
    "ferreiracosta.com": ("Ferreira Costa", "ferreira costa"),
    "tumelero.com.br": ("Tumelero", "tumelero"),
    "sertao.com.br": ("Sertão", "sert"),
    "padovani.com.br": ("Padovani", "padovani"),
}


@dataclass
class Rota:
    km: float
    minutos: float | None
    aproximado: bool


@dataclass
class LojaProxima:
    rede: str
    dominio: str
    nome: str
    endereco: str | None
    lat: float
    lon: float
    km: float
    minutos: float | None
    aproximado: bool


def _rota_aproximada(origem: tuple[float, float], destino: tuple[float, float]) -> Rota:
    km = _haversine(origem[0], origem[1], destino[0], destino[1]) * FATOR_ROTA
    return Rota(km=round(km, 1), minutos=round(km / VELOCIDADE_MEDIA_KMH * 60), aproximado=True)


async def rota_matriz(origem: tuple[float, float], destinos: list[tuple[float, float]],
                      cliente: httpx.AsyncClient | None = None) -> list[Rota]:
    """Uma Rota por destino, na ordem de `destinos`. Nunca levanta: qualquer falha vira estimativa aproximada."""
    if not destinos:
        return []
    aproximadas = [_rota_aproximada(origem, d) for d in destinos]
    chave = get_settings().ors_api_key.strip()
    if not chave:
        return aproximadas
    corpo = {"locations": [[origem[1], origem[0]]] + [[d[1], d[0]] for d in destinos],   # ORS usa [lon, lat]
             "sources": [0], "destinations": list(range(1, len(destinos) + 1)),
             "metrics": ["distance", "duration"], "units": "km"}
    proprio = cliente is None
    cli = cliente or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        r = await cli.post(URL_ORS, headers={"Authorization": chave, "Content-Type": "application/json"}, json=corpo)
        if r.status_code != 200:
            logger.warning("OpenRouteService respondeu HTTP %s: usando a estimativa", r.status_code)
            return aproximadas
        j = r.json()
        distancias, duracoes = j["distances"][0], j["durations"][0]
        saida = []
        for i, base in enumerate(aproximadas):
            km, seg = distancias[i], duracoes[i]
            saida.append(base if km is None or seg is None
                         else Rota(km=round(float(km), 1), minutos=round(float(seg) / 60), aproximado=False))
        return saida
    except Exception as exc:  # noqa: BLE001 — rede, formato inesperado
        logger.warning("OpenRouteService falhou (%s): usando a estimativa", type(exc).__name__)
        return aproximadas
    finally:
        if proprio:
            await cli.aclose()


_cache_lojas: dict[str, tuple[float, list[dict]]] = {}


async def _places(consulta: str, cliente: httpx.AsyncClient | None = None) -> list[dict]:
    guardado = _cache_lojas.get(consulta)
    if guardado and time.monotonic() - guardado[0] < CACHE_LOJAS_S:
        return guardado[1]
    proprio = cliente is None
    cli = cliente or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        for chave in get_settings().serper_keys:
            r = await cli.post(URL_PLACES, headers={"X-API-KEY": chave, "Content-Type": "application/json"},
                               json={"q": consulta, "gl": "br", "hl": "pt-br"})
            if r.status_code in (401, 403, 429):
                continue
            if r.status_code != 200:
                return []
            lista = [p for p in (r.json().get("places") or []) if isinstance(p, dict)]
            _cache_lojas[consulta] = (time.monotonic(), lista)
            return lista
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Serper /places falhou (%s)", type(exc).__name__)
        return []
    finally:
        if proprio:
            await cli.aclose()


def _numero(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def lojas_proximas(cep: str, por_rede: int = 2, cliente: httpx.AsyncClient | None = None,
                         redes: dict[str, tuple[str, str]] | None = None) -> dict:
    """Lojas físicas das redes da lista fixa perto do CEP, da mais rápida para a mais lenta de chegar.

    Devolve {"origem": {...}, "lojas": [...], "aviso": str | None}. `aviso` explica por que a lista pode estar
    vazia (sem chave, CEP sem coordenada, nenhuma loja achada)."""
    redes = redes or REDES_FISICAS
    coord = await asyncio.to_thread(_coordenada, cep)
    local = await local_do_cep(cep)
    if coord is None or local is None:
        return {"origem": None, "lojas": [], "aviso": "Não consegui localizar este CEP."}
    origem = (coord[0], coord[1])
    info = {"cep": cep, "cidade": local.cidade, "uf": local.uf, "lat": origem[0], "lon": origem[1],
            "precisao": coord[2]}
    if not get_settings().serper_keys:
        return {"origem": info, "lojas": [], "aviso": "Busca de lojas desligada (sem SERPER_API_KEYS)."}

    vaga = asyncio.Semaphore(SIMULTANEAS)

    async def da_rede(dominio: str, nome: str, palavra: str) -> list[tuple[str, str, dict]]:
        async with vaga:
            lista = await _places(f"{nome} {local.cidade} {local.uf}", cliente)
        achadas = []
        for p in lista:
            lat, lon = _numero(p.get("latitude")), _numero(p.get("longitude"))
            if lat is None or lon is None or palavra not in str(p.get("title") or "").lower():
                continue
            achadas.append((dominio, nome, p))
        achadas.sort(key=lambda t: _haversine(origem[0], origem[1], float(t[2]["latitude"]), float(t[2]["longitude"])))
        return achadas[:por_rede]

    por_rede_lista = await asyncio.gather(*(da_rede(d, n, w) for d, (n, w) in redes.items()))
    candidatas = [t for lista in por_rede_lista for t in lista]
    if not candidatas:
        return {"origem": info, "lojas": [], "aviso": "Nenhuma loja das redes cadastradas encontrada perto deste CEP."}

    rotas = await rota_matriz(origem, [(float(p["latitude"]), float(p["longitude"])) for _, _, p in candidatas], cliente)
    lojas = [LojaProxima(rede=nome, dominio=dominio, nome=str(p.get("title")), endereco=p.get("address"),
                         lat=float(p["latitude"]), lon=float(p["longitude"]), km=rota.km, minutos=rota.minutos,
                         aproximado=rota.aproximado)
             for (dominio, nome, p), rota in zip(candidatas, rotas)]
    lojas.sort(key=lambda x: (x.minutos if x.minutos is not None else 1e9, x.km))
    aviso = None
    if any(x.aproximado for x in lojas):
        aviso = "Tempo e distância estimados (sem rota real): confira no mapa antes de ir."
    return {"origem": info, "lojas": [asdict(x) for x in lojas], "aviso": aviso}
