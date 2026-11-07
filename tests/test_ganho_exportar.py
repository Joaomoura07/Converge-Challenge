"""Testes de E10 (ganho) e E11 (exportar xlsx) — dados falsos."""

from io import BytesIO

from openpyxl import load_workbook

from src.exportar import gerar_xlsx
from src.ganho import calcular_ganho
from src.logistica import Fornecedor, calcular_logistica
from src.viabilidade import calcular_viabilidade


def test_ganho_20_itens_28s():
    g = calcular_ganho(20, 28, custo_usd=0.0545)
    assert g.minutos_a_mao == 360.0
    assert g.resumo == "À mão: ~6 h. Aqui: 28 s. Custo de IA: R$ 0,30"
    assert g.reducao_pct > 99.8


def test_ganho_duracoes_e_zeros():
    assert calcular_ganho(0, 5).reducao_pct == 0.0
    assert calcular_ganho(1, 90).texto_real == "1 min 30 s"
    assert calcular_ganho(-3, -1, -2).custo_ia_brl == 0.0


L = Fornecedor(id="L", nome="Leroy Merlin Recife", dominio="leroymerlin.com.br", cep="51021-040",
               frete_base=30, rs_por_km=1.5)
C = Fornecedor(id="C", nome="C&C Recife", dominio="cec.com.br", cep="50070-000", frete_base=20, rs_por_km=1.0)


def _item(desc, l, c, qtd=1, **x):
    f = []
    if l:
        f.append({"loja": "Leroy", "dominio": "leroymerlin.com.br", "url": "https://leroy/x", "preco_embalagem": l})
    if c:
        f.append({"loja": "C&C", "dominio": "cec.com.br", "url": "https://cec/y", "preco_embalagem": c})
    return {"descricao": desc, "fontes": f, "qtd_embalagens": qtd, "status": "definido", "embalagem": "un",
            "confianca": "alta", "preco_emb_min": min(p for p in (l, c) if p),
            "preco_emb_med": min(p for p in (l, c) if p), "preco_emb_max": max(p for p in (l, c) if p), **x}


def test_xlsx_agrupa_por_loja_e_lista_pendentes():
    itens = [_item("Tinta 18 L", 1000, 1500), _item("Porcelanato 90x90", 1500, 1000, qtd=2),
             {"descricao": "Tinta vermelha", "status": "pendente_especificacao",
              "pergunta": "Qual acabamento e litragem?", "fontes": []}]
    forn = [L, C]
    lg = calcular_logistica(itens, forn, {"L": 10, "C": 5})
    vi = calcular_viabilidade(itens, 5000, lg.frete_total)
    raw = gerar_xlsx({"nome": "Cozinha Graças", "cep": "52011-050"}, itens, forn, lg, vi, calcular_ganho(3, 20))
    wb = load_workbook(BytesIO(raw))
    assert wb.sheetnames == ["Plano de compra", "Pendentes", "Resumo"]
    col_a = [c.value for c in wb["Plano de compra"]["A"] if c.value]
    assert any("Leroy" in str(v) for v in col_a) and any("C&C" in str(v) for v in col_a)
    assert "Tinta 18 L" in col_a and "Porcelanato 90x90" in col_a
    assert wb["Pendentes"]["A2"].value == "Tinta vermelha"
    assert "Qual acabamento" in wb["Pendentes"]["C2"].value
    resumo = {r[0].value: r[1].value for r in wb["Resumo"].iter_rows()}
    assert resumo["Frete total"] == lg.frete_total and "À mão" in resumo["Ganho de tempo"]


def test_xlsx_sem_logistica_nao_quebra():
    raw = gerar_xlsx({"nome": "X"}, [{"descricao": "Item", "status": "buscando"}], [])
    assert load_workbook(BytesIO(raw))["Pendentes"]["A2"].value == "Item"
