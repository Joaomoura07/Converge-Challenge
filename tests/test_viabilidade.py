"""Testes da E8 (viabilidade) — dados falsos."""

from src.viabilidade import calcular_viabilidade


def it(qtd, mn, md, mx, **extra):
    return {"qtd_embalagens": qtd, "preco_emb_min": mn, "preco_emb_med": md, "preco_emb_max": mx,
            "status": "definido", **extra}


def test_cabe_com_sobra():
    r = calcular_viabilidade([it(10, 90, 100, 110)], 2000, frete_total=50)
    assert (r.total_min, r.total_med, r.total_max) == (950.0, 1050.0, 1150.0)
    assert r.cabe and r.cabe_no_minimo and r.diferenca == -950.0
    assert r.resumo.startswith("Cabe") and "R$ 950,00" in r.resumo


def test_nao_cabe_e_da_ate_3_sugestoes_com_economia():
    itens = [it(10, 80, 100, 120), it(5, 180, 200, 220), it(2, 400, 500, 600), it(1, 90, 100, 110)]
    r = calcular_viabilidade(itens, 2000, frete_total=300)
    assert not r.cabe and not r.cabe_no_minimo and r.diferenca == r.total_med - 2000
    assert r.resumo.startswith("Não cabe")
    assert 1 <= len(r.sugestoes) <= 3
    tipos = {s.tipo for s in r.sugestoes}
    assert "preco_minimo" in tipos and "frete" in tipos
    eco = [s.economia for s in r.sugestoes if s.economia is not None]
    assert eco == sorted(eco, reverse=True)


def test_cabe_so_no_menor_preco():
    r = calcular_viabilidade([it(10, 90, 100, 110)], 950)
    assert not r.cabe and r.cabe_no_minimo and r.resumo.startswith("Cabe só no menor preço")


def test_similar_mais_barato_vira_sugestao_com_economia_real():
    itens = [it(4, 90, 100, 110, similar={"descricao": "Votomassa AC-II", "preco_emb_med": 82})]
    r = calcular_viabilidade(itens, 100)
    s = next(s for s in r.sugestoes if s.tipo == "similar")
    assert s.economia == 72.0 and "Votomassa" in s.texto


def test_pendentes_e_sem_preco_nao_inventam_valor():
    itens = [it(1, 10, 10, 10),
             {"status": "nao_encontrado", "qtd_embalagens": 3},
             {"status": "buscando"},
             {"status": "pendente_especificacao", "qtd_embalagens": 2, "preco_emb_min": 40,
              "preco_emb_med": 50, "preco_emb_max": 60, "estimativa": True}]
    r = calcular_viabilidade(itens, 1000)
    assert r.itens_sem_preco == [1, 2]
    assert r.total_med == 110.0 and r.inclui_estimativas
    assert any(s.tipo == "pendencias" for s in r.sugestoes) or r.cabe


def test_lista_vazia():
    r = calcular_viabilidade([], 500)
    assert r.total_med == 0 and r.cabe and r.sugestoes == []


def test_cabe_nao_e_afirmado_quando_ha_itens_sem_preco():
    """15 de 20 itens sem preço + orçamento folgado: não pode dizer 'Cabe ... sobram'."""
    itens = [it(1, 200, 200, 200)] * 5 + [{"status": "nao_encontrado", "qtd_embalagens": 1}] * 15
    r = calcular_viabilidade(itens, 5000)
    assert r.cabe and not r.completo and len(r.itens_sem_preco) == 15
    assert r.resumo.startswith("Ainda não dá para afirmar: 15 itens ainda sem preço ficaram fora do total")
    assert "Até agora cabe:" in r.resumo and "Cabe:" not in r.resumo


def test_um_item_sem_preco_usa_singular():
    r = calcular_viabilidade([it(1, 10, 10, 10), {"status": "erro"}], 1000)
    assert "1 item ainda sem preço ficou fora do total" in r.resumo


def test_nao_cabe_com_itens_sem_preco_avisa_que_pode_ser_pior():
    r = calcular_viabilidade([it(10, 90, 100, 110), {"status": "nao_encontrado"}], 500)
    assert not r.cabe and not r.completo
    assert r.resumo.startswith("Não cabe") and "tende a ser maior" in r.resumo


def test_cabe_so_no_minimo_com_itens_sem_preco_tambem_avisa():
    r = calcular_viabilidade([it(10, 90, 100, 110), {"status": "buscando"}], 950)
    assert r.cabe_no_minimo and not r.cabe
    assert "Até agora cabe só no menor preço" in r.resumo and r.resumo.startswith("Ainda não dá")


def test_lista_completa_nao_muda_o_texto():
    r = calcular_viabilidade([it(10, 90, 100, 110)], 2000)
    assert r.completo and r.resumo.startswith("Cabe:") and "ainda sem preço" not in r.resumo
