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
from pydantic import BaseModel, Field, model_serializer

from .config import get_settings

logger = logging.getLogger(__name__)

KM_PADRAO = 15.0  # plano B quando não dá para geolocalizar um CEP (região metropolitana do Recife)

# Marketplaces e e-commerces sem filial física de material de construção: nunca consultam Serper Maps nem ORS
# e ficam sem distância/tempo (None) mesmo quando vencem pelo menor preço.
SOMENTE_ONLINE: frozenset[str] = frozenset({
    "amazon.com.br",
    "mercadolivre.com.br",
    "magazineluiza.com.br",
    "casasbahia.com.br",
    "americanas.com.br",
    "madeiramadeira.com.br",
    "loja.suvinil.com.br",
    "lojadexco.com.br",
    "tramontina.com.br",
    "shopee.com.br",
    "aliexpress.com",
})

# Redes com loja física (material de construção). SÓ elas consultam Serper Maps/ORS. Qualquer outro domínio que a
# busca (Tavily/Google) traga é tratado como online: sem chamada de rede e sem distância/tempo.
LOJAS_FISICAS: frozenset[str] = frozenset({
    "leroymerlin.com.br",
    "cec.com.br",
    "telhanorte.com.br",
    "obramax.com.br",
    "ferreiracosta.com",
    "dicico.com.br",
    "sertao.com.br",
    "padovani.com.br",
    "tumelero.com.br",
})


def _somente_online(dominio: str | None) -> bool:
    """True para tudo que não é rede física conhecida (inclui a lista SOMENTE_ONLINE e domínios desconhecidos)."""
    d = _dominio(dominio)
    if not d or d in SOMENTE_ONLINE:
        return True
    return not any(d == f or d.endswith("." + f) for f in LOJAS_FISICAS)


class Fornecedor(BaseModel):
    """Linha da tabela ``fornecedores`` (loja física/entrega cadastrada)."""

    id: str
    nome: str
    dominio: str                       # mesmo domínio que a busca encontra (ex.: leroymerlin.com.br)
    cep: str | None = None              # None em e-commerce (sem loja física): distância não entra no frete
    frete_base: float = 0.0            # R$ fixo por entrega
    rs_por_km: float = 0.0             # R$ por km de distância
    pedido_minimo: float = 0.0         # R$ mínimo de produtos para entregar
    lat: float | None = None
    lon: float | None = None
    endereco: str | None = None


class LojaPlano(BaseModel):
    id: str
    nome: str
    distancia_km: float | None = None
    tempo_min: int | None = None       # minutos até a obra (ORS ou estimativa a partir da filial física)
    endereco: str | None = None        # endereço da filial mais próxima encontrada no Serper Maps
    itens: list[int]                   # índices (ordem da lista de entrada)
    subtotal: float
    frete: float
    pedido_minimo: float = 0.0
    abaixo_do_minimo: bool = False

    @model_serializer(mode="wrap")
    def _serializar(self, handler: Any) -> dict[str, Any]:
        d = handler(self)
        if d.get("tempo_min") is None:
            d.pop("tempo_min", None)
        if d.get("endereco") is None:
            d.pop("endereco", None)
        return d


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


# precisão da coordenada: "rua" > "bairro" > "cidade" (BrasilAPI cai no centro da cidade quando não tem a rua)
_CACHE_OK: dict[str, tuple[float, float, str]] = {}   # CEP -> (lat, lon, precisão); acertos: para sempre
_CACHE_CIDADE: dict[str, tuple[str, str]] = {}         # CEP -> (cidade, UF)
_CACHE_FILIAL: dict[tuple[str, str, str], list[dict[str, Any]]] = {}  # (dominio, cidade, uf) -> places do Serper Maps
_CACHE_FALHA: dict[str, float] = {}                    # CEP -> instante da falha (só evita repetir timeout)
FALHA_TTL_S = 60.0
_UA = {"User-Agent": "orcamentista-hackathon/0.1"}      # exigido pelo Nominatim (nome genérico, sem dados pessoais)
_NOMINATIM_INTERVALO_S = 1.1                            # política de uso do Nominatim: no máx. 1 req/s
_ultimo_nominatim = 0.0


def _get_json(url: str, **kw: Any) -> Any:
    r = httpx.get(url, timeout=5.0, **kw)
    return r.json() if r.status_code == 200 else None


def _post_json(url: str, **kw: Any) -> Any:
    r = httpx.post(url, timeout=6.0, **kw)
    return r.json() if r.status_code == 200 else None


def _nominatim(consulta: str) -> tuple[float, float] | None:
    global _ultimo_nominatim
    # nunca espera mais que o intervalo (mesmo se o relógio andar para trás)
    espera = min(_NOMINATIM_INTERVALO_S, _NOMINATIM_INTERVALO_S - (time.monotonic() - _ultimo_nominatim))
    if espera > 0:
        time.sleep(espera)
    _ultimo_nominatim = time.monotonic()
    dados = _get_json("https://nominatim.openstreetmap.org/search",
                      params={"q": consulta, "format": "json", "limit": 1}, headers=_UA)
    return (float(dados[0]["lat"]), float(dados[0]["lon"])) if dados else None


def _geocodificar(cep: str) -> tuple[float, float, str] | None:
    """ViaCEP (endereço) -> Nominatim (rua, depois bairro) -> BrasilAPI (só cidade). Qualquer etapa pode falhar."""
    try:
        v = _get_json(f"https://viacep.com.br/ws/{cep}/json/") or {}
        if not v.get("erro") and v.get("localidade"):
            _CACHE_CIDADE[cep] = (str(v.get("localidade") or ""), str(v.get("uf") or ""))
            fim = f"{v.get('localidade')}, {v.get('uf')}, Brasil"
            tentativas = []
            if v.get("logradouro") and v.get("bairro"):
                tentativas.append((f"{v['logradouro']}, {v['bairro']}, {fim}", "rua"))
            if v.get("bairro"):
                tentativas.append((f"{v['bairro']}, {fim}", "bairro"))
            for consulta, precisao in tentativas:
                ponto = _nominatim(consulta)
                if ponto:
                    return (*ponto, precisao)
    except Exception:  # noqa: BLE001
        logger.warning("ViaCEP/Nominatim falharam para o CEP %s", cep)
    try:
        c = ((_get_json(f"https://brasilapi.com.br/api/cep/v2/{cep}") or {}).get("location") or {}).get("coordinates") or {}
        if c.get("latitude") and c.get("longitude"):
            return float(c["latitude"]), float(c["longitude"]), "cidade"
    except Exception:  # noqa: BLE001
        logger.warning("BrasilAPI falhou para o CEP %s", cep)
    return None


def _coordenada(cep: str) -> tuple[float, float, str] | None:
    cep = re.sub(r"\D", "", cep or "")
    if len(cep) != 8:
        return None
    if cep in _CACHE_OK:
        return _CACHE_OK[cep]
    falhou_em = _CACHE_FALHA.get(cep)
    if falhou_em is not None and time.monotonic() - falhou_em < FALHA_TTL_S:
        return None
    achou = _geocodificar(cep)
    if achou:
        _CACHE_FALHA.pop(cep, None)
        _CACHE_OK[cep] = achou
        return achou
    _CACHE_FALHA[cep] = time.monotonic()   # falha NÃO fica para sempre: retenta após FALHA_TTL_S
    return None


def coordenadas_cep(cep: str) -> tuple[float, float] | None:
    """(lat, lon) do CEP ou ``None`` se indisponível (o chamador usa ``KM_PADRAO``)."""
    c = _coordenada(cep)
    return (c[0], c[1]) if c else None


def cidade_uf_cep(cep: str) -> tuple[str, str] | None:
    """(cidade, UF) do CEP via ViaCEP (reaproveita o cache de ``_geocodificar``)."""
    limpo = re.sub(r"\D", "", cep or "")
    if len(limpo) != 8:
        return None
    if limpo in _CACHE_CIDADE:
        cid, uf = _CACHE_CIDADE[limpo]
        return (cid, uf) if cid and uf else None
    try:
        v = _get_json(f"https://viacep.com.br/ws/{limpo}/json/") or {}
        if not v.get("erro") and v.get("localidade") and v.get("uf"):
            par = (str(v["localidade"]), str(v["uf"]))
            _CACHE_CIDADE[limpo] = par
            return par
    except Exception:  # noqa: BLE001
        logger.warning("ViaCEP falhou ao buscar cidade/UF para %s", limpo)
    return None


def limpar_cache_cep() -> None:
    """Esvazia os caches (usado nos testes)."""
    global _ultimo_nominatim
    _ultimo_nominatim = 0.0
    _CACHE_OK.clear()
    _CACHE_CIDADE.clear()
    _CACHE_FILIAL.clear()
    _CACHE_FALHA.clear()


def distancias_km(cep_obra: str, fornecedores: list[Fornecedor]) -> dict[str, float]:
    """{id_fornecedor: km (linha reta ×1,3 para aproximar a rota)}.

    Usa ``KM_PADRAO`` quando falta coordenada OU quando uma das pontas só tem precisão de cidade
    (todas as coordenadas iguais dariam 0 km, o que seria uma distância falsa).
    Dica: preencha ``lat``/``lon`` das lojas em ``fornecedores`` (precisão máxima, sem depender de API).
    """
    obra = _coordenada(cep_obra)
    saida: dict[str, float] = {}
    for f in fornecedores:
        if f.lat is not None and f.lon is not None:
            loja = (f.lat, f.lon, "manual")
        else:
            loja = _coordenada(f.cep)
        if not obra or not loja or "cidade" in (obra[2], loja[2]):
            saida[f.id] = KM_PADRAO
        else:
            saida[f.id] = round(_haversine(obra[0], obra[1], loja[0], loja[1]) * 1.3, 1)
    return saida


# --- Filial física mais próxima (Serper Maps) + rota e tempo (OpenRouteService) ------------------


def _norm_simples(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def _casa_nome_loja(titulo_place: str, nome_loja: str, dominio: str) -> bool:
    """Garante que o lugar retornado pelo Google Maps é realmente da rede pesquisada (e não anúncio concorrente)."""
    t = re.sub(r"[^a-z0-9]+", " ", _norm_simples(titulo_place)).strip()
    if not t:
        return False
    base_dom = _dominio(dominio).split(".")[0]
    for cand in (_norm_simples(nome_loja), base_dom):
        limpo = re.sub(r"[^a-z0-9]+", " ", cand).strip()
        if limpo and (limpo in t or t in limpo):
            return True
        # primeira palavra forte (>= 3 letras), ex.: "Leroy Merlin" -> "leroy", "Ferreira Costa" -> "ferreira"
        partes = [p for p in limpo.split() if len(p) >= 3 and p not in ("loja", "lojas", "home", "center")]
        if partes and partes[0] in t.split():
            return True
    return False


def buscar_filial_serper(
    nome_loja: str,
    dominio: str,
    cidade: str,
    uf: str,
    obra_lat: float,
    obra_lon: float,
    chaves_serper: list[str] | None = None,
) -> dict[str, Any] | None:
    """Busca no Serper Maps (`POST /maps`) a filial física mais próxima da obra.

    Devolve ``{"lat": float, "lon": float, "endereco": str | None, "titulo": str}`` ou ``None``
    se a loja for somente online, se não houver chave Serper ou se não existir filial na região.
    """
    dom = _dominio(dominio)
    if _somente_online(dom) or not cidade or not uf:
        return None
    chaves = chaves_serper if chaves_serper is not None else get_settings().serper_keys
    if not chaves:
        return None

    chave_cache = (dom, cidade.strip().lower(), uf.strip().lower())
    places = _CACHE_FILIAL.get(chave_cache)
    if places is None:
        consulta = f"{nome_loja} {cidade} {uf}"
        for k in chaves:
            try:
                resp = _post_json(
                    "https://google.serper.dev/maps",
                    headers={"X-API-KEY": k, "Content-Type": "application/json"},
                    json={"q": consulta, "gl": "br", "hl": "pt-br"},
                )
                if isinstance(resp, dict) and isinstance(resp.get("places"), list):
                    places = resp["places"]
                    _CACHE_FILIAL[chave_cache] = places
                    break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Serper Maps falhou para %s (%s)", consulta, type(exc).__name__)
        if places is None:
            return None

    candidatas: list[tuple[float, dict[str, Any]]] = []
    for p in places:
        lat, lon = p.get("latitude"), p.get("longitude")
        titulo = str(p.get("title") or "")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if not _casa_nome_loja(titulo, nome_loja, dom):
            continue
        dist_reta = _haversine(obra_lat, obra_lon, float(lat), float(lon))
        # Descarta filial em outra região muito distante (> 80 km em linha reta da obra)
        if dist_reta <= 80.0:
            candidatas.append((dist_reta, p))

    if not candidatas:
        return None
    _, melhor = min(candidatas, key=lambda x: x[0])
    return {
        "lat": float(melhor["latitude"]),
        "lon": float(melhor["longitude"]),
        "endereco": str(melhor.get("address")).strip() if melhor.get("address") else None,
        "titulo": str(melhor.get("title") or nome_loja).strip(),
    }


def rotas_ors(
    obra: tuple[float, float],
    destinos: dict[str, tuple[float, float]],
    chave_ors: str | None = None,
) -> dict[str, tuple[float, int]]:
    """Calcula ``{id_loja: (distancia_km, tempo_min)}`` via OpenRouteService Matrix API.

    Se ``ORS_API_KEY`` não estiver configurada ou se a chamada falhar, usa fallback determinístico
    (Haversine × 1,3 e velocidade média urbana de 30 km/h) para as filiais físicas encontradas.
    """
    if not destinos:
        return {}
    chave = chave_ors if chave_ors is not None else get_settings().ors_key
    ids = list(destinos.keys())
    saida: dict[str, tuple[float, int]] = {}

    if chave:
        try:
            locs = [[obra[1], obra[0]]] + [[destinos[k][1], destinos[k][0]] for k in ids]
            resp = _post_json(
                "https://api.openrouteservice.org/v2/matrix/driving-car",
                headers={"Authorization": chave, "Content-Type": "application/json"},
                json={
                    "locations": locs,
                    "sources": [0],
                    "destinations": list(range(1, len(locs))),
                    "metrics": ["distance", "duration"],
                },
            )
            if isinstance(resp, dict):
                dists = (resp.get("distances") or [[]])[0]
                durs = (resp.get("durations") or [[]])[0]
                for idx, fid in enumerate(ids):
                    dm = dists[idx] if idx < len(dists) else None
                    ds = durs[idx] if idx < len(durs) else None
                    if isinstance(dm, (int, float)) and isinstance(ds, (int, float)) and dm > 0 and ds >= 0:
                        km = round(float(dm) / 1000.0, 1)
                        minutos = max(1, round(float(ds) / 60.0))
                        saida[fid] = (km, minutos)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenRouteService falhou (%s); usando estimativa Haversine", type(exc).__name__)

    for fid, (lat_l, lon_l) in destinos.items():
        if fid not in saida:
            km = round(_haversine(obra[0], obra[1], lat_l, lon_l) * 1.3, 1)
            minutos = max(1, round((km / 30.0) * 60.0))
            saida[fid] = (km, minutos)
    return saida


def enriquecer_rotas_lojas(
    lojas: list[LojaPlano],
    cep_obra: str,
    chaves_serper: list[str] | None = None,
    chave_ors: str | None = None,
) -> None:
    """Preenche ``distancia_km``, ``tempo_min`` e ``endereco`` SÓ nas lojas vencedoras que têm filial física.

    Lojas somente online (Amazon, Mercado Livre, etc.) ou sem filial na região ficam com
    ``distancia_km = None`` e ``tempo_min = None``. Sem ``SERPER_API_KEYS``, não faz chamadas de rede.
    """
    if not lojas:
        return
    chaves = chaves_serper if chaves_serper is not None else get_settings().serper_keys
    if not chaves:
        return

    for loja in lojas:
        if _somente_online(loja.id):
            loja.distancia_km = None
            loja.tempo_min = None
            loja.endereco = None

    fisicas = [l for l in lojas if not _somente_online(l.id)]
    if not fisicas:
        return

    obra = _coordenada(cep_obra)
    cid_uf = cidade_uf_cep(cep_obra)
    if not obra or obra[2] == "cidade" or not cid_uf:
        for loja in fisicas:
            loja.distancia_km = None
            loja.tempo_min = None
        return

    destinos: dict[str, tuple[float, float]] = {}
    for loja in fisicas:
        filial = buscar_filial_serper(
            loja.nome, loja.id, cid_uf[0], cid_uf[1], obra[0], obra[1], chaves_serper=chaves
        )
        if filial:
            destinos[loja.id] = (filial["lat"], filial["lon"])
            loja.endereco = filial.get("endereco")
        else:
            loja.distancia_km = None
            loja.tempo_min = None
            loja.endereco = None

    if destinos:
        rotas = rotas_ors((obra[0], obra[1]), destinos, chave_ors=chave_ors)
        for loja in fisicas:
            if loja.id in rotas:
                loja.distancia_km, loja.tempo_min = rotas[loja.id]
