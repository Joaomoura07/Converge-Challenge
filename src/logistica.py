"""E7 — Frete por CEP: loja única × dividir entre lojas.

Núcleo puro e testável (``calcular_logistica``) + resolução de distância (``distancias_km``,
BrasilAPI/ViaCEP com cache e plano B). Entrada por item vem da Fatia B:
``fontes: [{loja, dominio, url, preco_embalagem}]`` e ``qtd_embalagens``.

Saída: ``{estrategia: loja_unica|dividir, lojas, frete_total, total_produtos, total,
economia_estimada, itens_sem_loja}``. Nunca inventa preço: item sem fonte numa loja
cadastrada vai para ``itens_sem_loja``.
"""

from __future__ import annotations

import logging
import math
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

KM_PADRAO = 15.0  # plano B quando não dá para geolocalizar um CEP (região metropolitana do Recife)


class Fornecedor(BaseModel):
    """Linha da tabela ``fornecedores`` (loja física/entrega cadastrada)."""

    id: str
    nome: str
    dominio: str                       # mesmo domínio que a busca encontra (ex.: leroymerlin.com.br)
    cep: str
    frete_base: float = 0.0            # R$ fixo por entrega
    rs_por_km: float = 0.0             # R$ por km de distância
    pedido_minimo: float = 0.0         # R$ mínimo de produtos para entregar
    lat: float | None = None
    lon: float | None = None


class LojaPlano(BaseModel):
    id: str
    nome: str
    distancia_km: float
    itens: list[int]                   # índices (ordem da lista de entrada)
    subtotal: float
    frete: float
    pedido_minimo: float = 0.0
    abaixo_do_minimo: bool = False


class Logistica(BaseModel):
    estrategia: str                    # loja_unica | dividir
    lojas: list[LojaPlano]
    frete_total: float
    total_produtos: float
    total: float
    economia_estimada: float
    itens_sem_loja: list[int] = Field(default_factory=list)
    alternativa: dict[str, float] = Field(default_factory=dict)  # totais de cada estratégia, p/ a tela


def _dominio(d: str | None) -> str:
    d = (d or "").lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def _frete(f: Fornecedor, km: float) -> float:
    return round(f.frete_base + f.rs_por_km * km, 2)


def _precos_por_loja(item: dict[str, Any], fornecedores: dict[str, Fornecedor]) -> dict[str, float]:
    """{id_fornecedor: custo do item nessa loja} usando o menor preço de cada loja."""
    qtd = item.get("qtd_embalagens") or 0
    if not qtd:
        return {}
    por_dom = {_dominio(f.dominio): f.id for f in fornecedores.values()}
    melhor: dict[str, float] = {}
    for fonte in item.get("fontes") or []:
        fid = por_dom.get(_dominio(fonte.get("dominio") or fonte.get("url")))
        preco = fonte.get("preco_embalagem")
        if fid is None or not isinstance(preco, (int, float)) or preco <= 0:
            continue
        custo = round(float(preco) * float(qtd), 2)
        melhor[fid] = min(custo, melhor.get(fid, math.inf))
    return melhor


def _montar(estrategia: str, atrib: dict[int, str], custos: dict[int, dict[str, float]],
            fornecedores: dict[str, Fornecedor], km: dict[str, float],
            sem_loja: list[int]) -> Logistica:
    por_loja: dict[str, list[int]] = {}
    for i, fid in atrib.items():
        por_loja.setdefault(fid, []).append(i)
    lojas, frete_total, produtos = [], 0.0, 0.0
    for fid, idxs in sorted(por_loja.items()):
        f = fornecedores[fid]
        sub = round(sum(custos[i][fid] for i in idxs), 2)
        d = km.get(fid, KM_PADRAO)
        fr = _frete(f, d)
        lojas.append(LojaPlano(id=fid, nome=f.nome, distancia_km=round(d, 1), itens=sorted(idxs),
                               subtotal=sub, frete=fr, pedido_minimo=f.pedido_minimo,
                               abaixo_do_minimo=sub < f.pedido_minimo))
        frete_total += fr
        produtos += sub
    return Logistica(estrategia=estrategia, lojas=lojas, frete_total=round(frete_total, 2),
                     total_produtos=round(produtos, 2), total=round(produtos + frete_total, 2),
                     economia_estimada=0.0, itens_sem_loja=sorted(sem_loja))


def _custo(plano: Logistica) -> float:
    """Custo para comparar: total + penalidade por pedido mínimo não atingido (plano inviável)."""
    penal = sum(max(0.0, l.pedido_minimo - l.subtotal) for l in plano.lojas if l.abaixo_do_minimo)
    return plano.total + penal * 10


def _dividir(custos: dict[int, dict[str, float]], fornecedores: dict[str, Fornecedor],
             km: dict[str, float], sem_loja: list[int]) -> Logistica:
    atrib = {i: min(c, key=c.get) for i, c in custos.items()}

    def plano(a: dict[int, str]) -> Logistica:
        return _montar("dividir", a, custos, fornecedores, km, sem_loja)

    melhor = plano(atrib)
    # Tenta fechar lojas que ficaram abaixo do pedido mínimo (ou cujo frete não compensa).
    mudou = True
    while mudou:
        mudou = False
        for loja in sorted(melhor.lojas, key=lambda l: l.subtotal):
            if len(melhor.lojas) == 1:
                break
            nova = dict(atrib)
            ok = True
            for i in loja.itens:
                alternativas = {f: c for f, c in custos[i].items() if f != loja.id}
                if not alternativas:
                    ok = False
                    break
                # prefere loja já usada (evita abrir frete novo)
                usadas = {f: c for f, c in alternativas.items() if f in {l.id for l in melhor.lojas}}
                pool = usadas or alternativas
                nova[i] = min(pool, key=pool.get)
            if not ok:
                continue
            candidato = plano(nova)
            if _custo(candidato) < _custo(melhor) - 1e-9:
                atrib, melhor, mudou = nova, candidato, True
                break
    return melhor


def calcular_logistica(itens: list[dict[str, Any]], fornecedores: list[Fornecedor],
                       distancias: dict[str, float] | None = None) -> Logistica | None:
    """Escolhe loja única × dividir. ``distancias``: {id_fornecedor: km até a obra}.

    Considera só itens com ``fontes`` e ``qtd_embalagens`` (pendentes/não encontrados ficam fora).
    Devolve ``None`` se nenhum item pôde ser atribuído a uma loja cadastrada.
    """
    forn = {f.id: f for f in fornecedores}
    km = distancias or {}
    custos: dict[int, dict[str, float]] = {}
    sem_loja: list[int] = []
    for i, it in enumerate(itens):
        if it.get("status") in ("pendente_especificacao", "nao_encontrado", "erro", "buscando"):
            continue
        c = _precos_por_loja(it, forn)
        if c:
            custos[i] = c
        elif it.get("fontes"):
            sem_loja.append(i)
    if not custos:
        return None

    candidatos: list[Logistica] = []
    # loja única: lojas que cobrem tudo; se nenhuma cobre, a que cobre mais (resto vai a sem_loja)
    cobertura = {fid: [i for i, c in custos.items() if fid in c] for fid in forn}
    max_cob = max(len(v) for v in cobertura.values())
    for fid, cobre in cobertura.items():
        if len(cobre) != max_cob or not cobre:
            continue
        faltam = sorted(set(custos) - set(cobre)) + sem_loja
        candidatos.append(_montar("loja_unica", {i: fid for i in cobre}, custos, forn, km, faltam))
    unica = min(candidatos, key=_custo)
    dividido = _dividir(custos, forn, km, sem_loja)

    # só divide se cobrir mais itens ou ficar claramente mais barato
    escolhido = dividido if (
        len(dividido.itens_sem_loja) < len(unica.itens_sem_loja) or _custo(dividido) < _custo(unica) - 0.005
    ) else unica
    outro = unica if escolhido is dividido else dividido
    escolhido.economia_estimada = round(max(0.0, outro.total - escolhido.total), 2)
    escolhido.alternativa = {"loja_unica": unica.total, "dividir": dividido.total}
    return escolhido


# --- Distância (rede) ---------------------------------------------------------------------------


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


_CACHE_OK: dict[str, tuple[float, float]] = {}   # CEP -> coordenadas (respostas que deram certo: para sempre)
_CACHE_FALHA: dict[str, float] = {}               # CEP -> instante da falha (só evita repetir timeout)
FALHA_TTL_S = 60.0


def coordenadas_cep(cep: str) -> tuple[float, float] | None:
    """(lat, lon) do CEP via BrasilAPI v2. ``None`` se indisponível (o chamador usa ``KM_PADRAO``).

    Só acertos ficam em cache permanente. Falhas (timeout, erro HTTP) são lembradas por
    ``FALHA_TTL_S`` segundos e depois tentadas de novo: uma oscilação de rede não pode fixar 15 km
    para sempre.
    """
    cep = re.sub(r"\D", "", cep or "")
    if len(cep) != 8:
        return None
    if cep in _CACHE_OK:
        return _CACHE_OK[cep]
    falhou_em = _CACHE_FALHA.get(cep)
    if falhou_em is not None and time.monotonic() - falhou_em < FALHA_TTL_S:
        return None
    try:
        r = httpx.get(f"https://brasilapi.com.br/api/cep/v2/{cep}", timeout=5.0)
        if r.status_code == 200:
            c = (r.json().get("location") or {}).get("coordinates") or {}
            lat, lon = c.get("latitude"), c.get("longitude")
            if lat and lon:
                _CACHE_FALHA.pop(cep, None)
                _CACHE_OK[cep] = (float(lat), float(lon))
                return _CACHE_OK[cep]
    except Exception:  # noqa: BLE001
        logger.warning("Falha ao geolocalizar CEP %s", cep)
    _CACHE_FALHA[cep] = time.monotonic()
    return None


def limpar_cache_cep() -> None:
    """Esvazia os caches (usado nos testes)."""
    _CACHE_OK.clear()
    _CACHE_FALHA.clear()


def distancias_km(cep_obra: str, fornecedores: list[Fornecedor]) -> dict[str, float]:
    """{id_fornecedor: km (linha reta ×1,3 para aproximar a rota)}; ``KM_PADRAO`` se faltar coordenada."""
    obra = coordenadas_cep(cep_obra)
    saida: dict[str, float] = {}
    for f in fornecedores:
        loja = (f.lat, f.lon) if f.lat is not None and f.lon is not None else coordenadas_cep(f.cep)
        saida[f.id] = round(_haversine(*obra, *loja) * 1.3, 1) if obra and loja else KM_PADRAO
    return saida
