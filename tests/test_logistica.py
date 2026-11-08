"""Testes da E7 (frete por CEP) — dados falsos, sem rede."""

from src.logistica import Fornecedor, _haversine, calcular_logistica

L = Fornecedor(id="L", nome="Leroy Merlin Recife", dominio="leroymerlin.com.br", cep="51021-040",
               frete_base=30, rs_por_km=1.5, pedido_minimo=100)
C = Fornecedor(id="C", nome="C&C Recife", dominio="cec.com.br", cep="50070-000",
               frete_base=20, rs_por_km=1.0, pedido_minimo=0)
KM = {"L": 10.0, "C": 5.0}   # frete L = 45, frete C = 25


def item(l, c, qtd=1, **extra):
    fontes = []
    if l is not None:
        fontes.append({"loja": "Leroy", "dominio": "www.leroymerlin.com.br", "url": "https://x", "preco_embalagem": l})
    if c is not None:
        fontes.append({"loja": "C&C", "dominio": "cec.com.br", "url": "https://y", "preco_embalagem": c})
    return {"fontes": fontes, "qtd_embalagens": qtd, "status": "definido", **extra}


def test_loja_unica_vence_quando_dividir_so_soma_frete():
    r = calcular_logistica([item(100, 105), item(50, 52)], [L, C], KM)
    assert r.estrategia == "loja_unica"
    assert [l.id for l in r.lojas] == ["C"]
    assert r.total == 182.0 and r.frete_total == 25.0
    assert r.economia_estimada == 13.0     # a alternativa (tudo na Leroy) custaria 195


def test_dividir_vence_quando_cada_loja_e_mais_barata_em_um_item():
    r = calcular_logistica([item(1000, 1500), item(1500, 1000)], [L, C], KM)
    assert r.estrategia == "dividir"
    assert {l.id for l in r.lojas} == {"L", "C"}
    assert r.total == 2070.0
    assert r.economia_estimada == 455.0    # melhor loja única: 2525
    assert r.alternativa == {"loja_unica": 2525.0, "dividir": 2070.0}


def test_fecha_loja_abaixo_do_pedido_minimo():
    r = calcular_logistica([item(20, 21), item(None, 500)], [L, C], KM)
    assert [l.id for l in r.lojas] == ["C"]
    assert not any(l.abaixo_do_minimo for l in r.lojas)


def test_quantidade_de_embalagens_multiplica_o_preco():
    r = calcular_logistica([item(None, 30, qtd=4)], [L, C], KM)
    assert r.total_produtos == 120.0 and r.total == 145.0


def test_ignora_pendentes_e_nao_encontrados_e_marca_sem_loja():
    itens = [item(100, 100),
             {"fontes": [], "status": "pendente_especificacao"},
             {"fontes": [], "status": "nao_encontrado"},
             {"fontes": [{"loja": "Outra", "dominio": "outra.com", "preco_embalagem": 9}],
              "qtd_embalagens": 1, "status": "definido"}]
    r = calcular_logistica(itens, [L, C], KM)
    assert r.itens_sem_loja == [3]
    assert sorted(i for l in r.lojas for i in l.itens) == [0]


def test_sem_nenhum_item_atribuivel_devolve_none():
    assert calcular_logistica([], [L, C], KM) is None
    assert calcular_logistica([{"fontes": [], "status": "definido"}], [L, C], KM) is None


def test_preco_invalido_e_ignorado_e_distancia_padrao():
    r = calcular_logistica([item(-5, 0), item(None, 10)], [L, C], None)  # sem distâncias: 15 km
    assert r.lojas[0].id == "C" and r.lojas[0].distancia_km == 15.0
    assert r.frete_total == 35.0


def test_haversine_recife_olinda():
    assert 4 < _haversine(-8.0476, -34.8770, -8.0089, -34.8553) < 6


# --- geocodificação de CEP (APIs simuladas por URL) --------------------------------------------------
import pytest

from src import logistica as lg_mod

VIACEP = {"logradouro": "Rua Amélia", "bairro": "Graças", "localidade": "Recife", "uf": "PE"}


class _Resp:
    def __init__(self, dados, status=200):
        self._d, self.status_code = dados, status

    def json(self):
        return self._d


@pytest.fixture
def api(monkeypatch):
    """Fábrica: api(viacep=..., nominatim=..., brasilapi=...) -> lista de URLs chamadas."""
    chamadas: list[str] = []
    lg_mod.limpar_cache_cep()
    monkeypatch.setattr(lg_mod, "_NOMINATIM_INTERVALO_S", 0)

    def montar(viacep=VIACEP, nominatim=lambda q: [{"lat": "-8.04", "lon": "-34.90"}], brasilapi=None):
        def get(url, timeout=5.0, **kw):
            chamadas.append(url)
            if "viacep" in url:
                if isinstance(viacep, Exception):
                    raise viacep
                return _Resp(viacep)
            if "nominatim" in url:
                dados = nominatim(kw["params"]["q"])
                return _Resp(dados)
            if "brasilapi" in url:
                if isinstance(brasilapi, Exception):
                    raise brasilapi
                return _Resp(brasilapi, 200 if brasilapi else 404)
            raise AssertionError(url)

        monkeypatch.setattr(lg_mod.httpx, "get", get)
        return chamadas

    yield montar
    lg_mod.limpar_cache_cep()


def test_usa_viacep_e_nominatim_com_precisao_de_rua(api):
    chamadas = api()
    assert lg_mod._coordenada("52011-050") == (-8.04, -34.90, "rua")
    assert not any("brasilapi" in u for u in chamadas)


def test_sem_a_rua_cai_para_o_bairro(api):
    api(nominatim=lambda q: [{"lat": "-8.1", "lon": "-34.9"}] if q.startswith("Graças") else [])
    assert lg_mod._coordenada("52011-050") == (-8.1, -34.9, "bairro")


def test_brasilapi_so_como_ultimo_recurso_e_marca_cidade(api):
    api(viacep=TimeoutError("fora"), brasilapi={"location": {"coordinates": {"latitude": "-8.05", "longitude": "-34.88"}}})
    assert lg_mod._coordenada("50070000") == (-8.05, -34.88, "cidade")


def test_coordenada_so_de_cidade_nao_vira_distancia_zero(api):
    api(viacep=TimeoutError("fora"), brasilapi={"location": {"coordinates": {"latitude": "-8.05", "longitude": "-34.88"}}})
    f = Fornecedor(id="L", nome="L", dominio="x.com", cep="51021-040")
    assert lg_mod.distancias_km("52011-050", [f]) == {"L": lg_mod.KM_PADRAO}


def test_distancia_real_entre_dois_ceps_distintos(api):
    pontos = {"Rua Amélia": ("-8.0453", "-34.9029"), "Avenida": ("-8.1226", "-34.8995")}
    api(viacep=VIACEP, nominatim=lambda q: [dict(zip(("lat", "lon"), pontos["Rua Amélia" if q.startswith("Rua") else "Avenida"]))])
    lg_mod.limpar_cache_cep()
    # obra: ViaCEP devolve Rua Amélia; loja tem lat/lon manuais (Boa Viagem)
    f = Fornecedor(id="L", nome="L", dominio="x.com", cep="51021-040", lat=-8.1226, lon=-34.8995)
    km = lg_mod.distancias_km("52011-050", [f])["L"]
    assert 10 < km < 14          # ~ 8,6 km em linha reta × 1,3


def test_loja_com_lat_lon_manual_nao_chama_api(api):
    chamadas = api()
    f = Fornecedor(id="L", nome="L", dominio="x.com", cep="51021-040", lat=-8.12, lon=-34.90)
    lg_mod.distancias_km("52011-050", [f])
    assert len([u for u in chamadas if "viacep" in u]) == 1   # só o CEP da obra


def test_falha_de_rede_nao_fica_para_sempre(api, monkeypatch):
    estado = {"fora": True}

    def nominatim(q):
        if estado["fora"]:
            raise TimeoutError("oscilou")
        return [{"lat": "-8.04", "lon": "-34.90"}]

    chamadas = api(nominatim=nominatim, brasilapi={})
    assert lg_mod._coordenada("52011-050") is None
    n = len(chamadas)
    assert lg_mod._coordenada("52011-050") is None and len(chamadas) == n   # dentro do TTL: não tenta
    estado["fora"] = False
    t = lg_mod.time.monotonic()
    monkeypatch.setattr(lg_mod.time, "monotonic", lambda: t + lg_mod.FALHA_TTL_S + 1)
    assert lg_mod._coordenada("52011-050") == (-8.04, -34.90, "rua")


def test_acerto_fica_em_cache_e_ignora_formatacao(api):
    chamadas = api()
    assert lg_mod.coordenadas_cep("52011050") == lg_mod.coordenadas_cep("52011-050") == (-8.04, -34.90)
    assert len([u for u in chamadas if "viacep" in u]) == 1


def test_cep_invalido_nao_chama_api(api):
    chamadas = api()
    assert lg_mod.coordenadas_cep("123") is None and lg_mod.coordenadas_cep("") is None
    assert chamadas == []


# --- e-commerce: sem CEP/coordenadas, frete fixo por loja -----------------------------------------------
def test_ecommerce_sem_cep_nao_consulta_api_e_usa_frete_fixo(api):
    chamadas = api()
    lojas = [Fornecedor(id=d, nome=d, dominio=d, frete_base=35) for d in ("leroymerlin.com.br", "cec.com.br")]
    assert lojas[0].cep is None
    km = lg_mod.distancias_km("52011-050", lojas)
    assert all(v == lg_mod.KM_PADRAO for v in km.values())                 # sem coordenada: padrão, sem 0 km falso
    assert len([u for u in chamadas if "viacep" in u]) == 1                # só a obra é geocodificada
    itens = [item(100, 105), item(50, 52)]
    r = calcular_logistica(itens, [Fornecedor(id="L", nome="L", dominio="leroymerlin.com.br", frete_base=35),
                                   Fornecedor(id="C", nome="C", dominio="cec.com.br", frete_base=35)], km)
    assert r.frete_total in (35.0, 70.0) and r.lojas[0].distancia_km == lg_mod.KM_PADRAO
    assert r.estrategia == "loja_unica" and r.total == 185.0               # L: 150 + 35 (dividir custaria +35 de frete)


# --- Filial física (Serper Maps) + rota/tempo (ORS) ----------------------------------------------------


def test_buscar_filial_serper_escolhe_a_mais_proxima_e_ignora_concorrente_e_online(monkeypatch):
    lg_mod.limpar_cache_cep()
    posts: list[tuple[str, dict]] = []

    def fake_post(url, **kw):
        posts.append((url, kw.get("json") or {}))
        return {
            "places": [
                # Concorrente que apareceu no Maps: deve ser ignorado
                {"title": "Armazém Coral Graças", "latitude": -8.0450, "longitude": -34.9020, "address": "Rua Perto, 10"},
                # Filial Imbiribeira (longe das Graças ~8,5 km)
                {"title": "Ferreira Costa - Imbiribeira", "latitude": -8.1180, "longitude": -34.9140,
                 "address": "Av. Mal. Mascarenhas de Morais, 2967"},
                # Filial Tamarineira (perto das Graças ~2,2 km)
                {"title": "Ferreira Costa - Tamarineira", "latitude": -8.0285, "longitude": -34.9065,
                 "address": "Rua Cônego Barata, 275 - Tamarineira"},
            ]
        }

    monkeypatch.setattr(lg_mod, "_post_json", fake_post)

    # Loja somente online (Amazon): nunca chama Serper Maps e devolve None
    assert lg_mod.buscar_filial_serper(
        "Amazon", "amazon.com.br", "Recife", "PE", -8.0453, -34.9029, chaves_serper=["k1"]
    ) is None
    assert posts == []

    # Obra nas Graças (-8.0453, -34.9029) -> escolhe Ferreira Costa Tamarineira
    filial = lg_mod.buscar_filial_serper(
        "Ferreira Costa", "ferreiracosta.com", "Recife", "PE", -8.0453, -34.9029, chaves_serper=["k1"]
    )
    assert filial is not None
    assert "Tamarineira" in filial["titulo"] and "Cônego Barata" in (filial["endereco"] or "")
    assert len(posts) == 1

    # Obra em Boa Viagem (-8.1226, -34.8995) -> usa o cache da cidade (sem nova requisição) e escolhe Imbiribeira
    filial_sul = lg_mod.buscar_filial_serper(
        "Ferreira Costa", "ferreiracosta.com", "Recife", "PE", -8.1226, -34.8995, chaves_serper=["k1"]
    )
    assert filial_sul is not None and "Imbiribeira" in filial_sul["titulo"]
    assert len(posts) == 1


def test_rotas_ors_converte_metros_e_segundos_e_faz_fallback_sem_chave(monkeypatch):
    def fake_post(url, **kw):
        assert "openrouteservice.org/v2/matrix/driving-car" in url
        # ORS exige [lon, lat]
        assert kw["json"]["locations"][0] == [-34.9029, -8.0453]
        return {"distances": [[3420.0, 9850.0]], "durations": [[540.0, 1320.0]]}

    monkeypatch.setattr(lg_mod, "_post_json", fake_post)
    destinos = {"fc": (-8.0285, -34.9065), "leroy": (-8.1226, -34.8995)}
    r = lg_mod.rotas_ors((-8.0453, -34.9029), destinos, chave_ors="ors-key")
    assert r == {"fc": (3.4, 9), "leroy": (9.8, 22)}

    # Sem chave ORS: fallback Haversine × 1,3 e velocidade 30 km/h
    r_fb = lg_mod.rotas_ors((-8.0453, -34.9029), {"fc": (-8.0285, -34.9065)}, chave_ors="")
    km, mins = r_fb["fc"]
    assert 2.0 <= km <= 3.5 and mins >= 4


def test_enriquecer_rotas_lojas_so_preenche_loja_fisica_vencedora_e_zera_amazon(api, monkeypatch):
    api()  # ViaCEP + Nominatim simulados para 52011-050 -> (-8.04, -34.90, "rua"), Recife/PE
    posts: list[str] = []

    def fake_post(url, **kw):
        posts.append(url)
        if "serper.dev/maps" in url:
            q = kw["json"]["q"]
            assert "Amazon" not in q
            return {"places": [{"title": "Leroy Merlin Boa Viagem", "latitude": -8.1226, "longitude": -34.8995,
                                "address": "Av. Antônio Falcão, 1000"}]}
        if "openrouteservice" in url:
            return {"distances": [[6200.0]], "durations": [[840.0]]}
        raise AssertionError(url)

    monkeypatch.setattr(lg_mod, "_post_json", fake_post)
    lojas = [
        lg_mod.LojaPlano(id="amazon.com.br", nome="Amazon", distancia_km=15.0, itens=[0], subtotal=120.0, frete=0.0),
        lg_mod.LojaPlano(id="leroymerlin.com.br", nome="Leroy Merlin", distancia_km=15.0, itens=[1], subtotal=350.0, frete=0.0),
    ]
    lg_mod.enriquecer_rotas_lojas(lojas, "52011-050", chaves_serper=["serper-1"], chave_ors="ors-1")

    # Amazon ganhou no item 0, mas é somente online: sem distância e sem tempo
    assert lojas[0].distancia_km is None and lojas[0].tempo_min is None and lojas[0].endereco is None
    # Leroy Merlin ganhou no item 1 e tem filial física: recebe km, minutos e endereço
    assert lojas[1].distancia_km == 6.2 and lojas[1].tempo_min == 14
    assert lojas[1].endereco == "Av. Antônio Falcão, 1000"
