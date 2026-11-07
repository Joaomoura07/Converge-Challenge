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
