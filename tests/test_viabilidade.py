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
