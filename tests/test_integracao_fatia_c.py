"""Ponta a ponta da Fatia C com a obra real 03-cozinha-gracas.

Só o que é do Enzo (preços/fontes por item) e o banco são simulados; E2, E7, E8, E10 e E11 rodam de verdade.
"""

import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from src import rotas_resultado as rr
from src.logistica import Fornecedor

ROOT = Path(__file__).resolve().parent.parent
OBRA = json.loads((ROOT / "docs/arquivos-teste/03-cozinha-gracas/orcamento_cozinha-gracas.json").read_text("utf-8"))

LOJAS = [
    Fornecedor(id="leroy", nome="Leroy Merlin", dominio="leroymerlin.com.br", cep="51021-040",
               frete_base=29.9, rs_por_km=1.2, pedido_minimo=150, lat=-8.1226, lon=-34.8995),
    Fornecedor(id="cec", nome="C&C", dominio="cec.com.br", cep="50070-000", frete_base=24, rs_por_km=1.5,
               lat=-8.0616, lon=-34.8866),
    Fornecedor(id="telha", nome="Telhanorte", dominio="telhanorte.com.br", cep="51150-000", frete_base=35,
               rs_por_km=1.0, pedido_minimo=200, lat=-8.11, lon=-34.91),
]
KM = {"leroy": 12.0, "cec": 3.3, "telha": 9.4}
DOM = {"leroy": "leroymerlin.com.br", "cec": "cec.com.br", "telha": "telhanorte.com.br"}


def simula_enzo(itens):
    """Devolve itens como o Enzo gravaria: 2 a 3 lojas por item, preço determinístico; os 3 últimos ficam sem preço."""
    saida = []
    for n, it in enumerate(itens, 1):
        base = 20.0 + (n * 37) % 400
        row = {"id": f"i{n}", "linha": n, "descricao": it["descricao"], "categoria": it["categoria"],
               "quantidade": it["quantidade"], "unidade": it["unidade"], "embalagem": "un",
               "qtd_embalagens": max(1, round(it["quantidade"])), "confianca": "alta", "estimativa": False}
        if n > len(itens) - 3:
            row.update(status="nao_encontrado", fontes=[])
        else:
            lojas = ["leroy", "cec", "telha"][: 2 + n % 2]
            fontes = [{"loja": k, "dominio": DOM[k], "url": f"https://{DOM[k]}/p/{n}",
                       "preco_embalagem": round(base * (1 + 0.04 * i), 2)} for i, k in enumerate(lojas)]
            v = [f["preco_embalagem"] for f in fontes]
            row.update(status="definido", fontes=fontes, preco_emb_min=min(v), preco_emb_med=sorted(v)[len(v) // 2],
                       preco_emb_max=max(v))
        saida.append(row)
    return saida


@pytest.fixture
def api(monkeypatch):
    itens_orig = [{"linha": i + 1, **it} for i, it in enumerate(OBRA["itens"])]
    itens_banco = simula_enzo(OBRA["itens"])
    orc = {"id": "o1", "nome": OBRA["obra"]["nome"], "cep": OBRA["obra"]["cep"], "orcamento_cliente": 80000,
           "iniciado_em": "2026-11-07T14:00:00+00:00", "concluido_em": "2026-11-07T14:00:31+00:00", "custo_usd": 0.06}
    gravado = {}
    monkeypatch.setattr(rr, "_carregar_orcamento", lambda i: orc if i == "o1" else None)
    monkeypatch.setattr(rr, "_carregar_itens", lambda i: itens_banco)
    monkeypatch.setattr(rr, "_carregar_fornecedores", lambda: LOJAS)
    monkeypatch.setattr(rr, "_gravar_resultado", lambda i, d: gravado.update(d))
    monkeypatch.setattr(rr, "distancias_km", lambda cep, f: KM)
    app = FastAPI()
    app.include_router(rr.router)
    c = TestClient(app)
    c.itens_orig, c.itens_banco, c.orc, c.gravado = itens_orig, itens_banco, orc, gravado
    return c


def test_fluxo_completo_da_obra_real(api):
    # 1) Revisão: o arquiteto sobe a lista e recebe sugestões (E2)
    s = api.post("/revisao/sugestoes", json={"itens": api.itens_orig})
    assert s.status_code == 200
    comp = s.json()["complementos"]
    assert comp and all(c["quantidade"] > 0 and c["unidade"] and c["motivo"] for c in comp)
    assert not any("AC-III" in c["descricao"] for c in comp)   # a lista já tem argamassa AC-III

    # 2) Fim da pesquisa: o Enzo chama o resultado (E7 + E8 + E10)
    r = api.post("/orcamentos/o1/resultado")
    assert r.status_code == 200
    d = r.json()
    lg, vi, ga = d["logistica"], d["viabilidade"], d["ganho"]
    assert api.gravado["logistica"] == lg                      # o que a tela lê via Realtime foi gravado

    n_com_preco = sum(1 for i in api.itens_banco if i["status"] == "definido")
    lojas_idx = sorted(i for l in lg["lojas"] for i in l["itens"])
    assert len(lojas_idx) == len(set(lojas_idx)) == n_com_preco   # cada item em UMA loja, nenhum some
    assert all(api.itens_banco[i]["status"] == "definido" for i in lojas_idx)

    # coerência dos números
    assert lg["total"] == pytest.approx(lg["total_produtos"] + lg["frete_total"], abs=0.01)
    assert lg["frete_total"] == pytest.approx(sum(l["frete"] for l in lg["lojas"]), abs=0.01)
    assert vi["total_min"] <= vi["total_med"] <= vi["total_max"]
    assert lg["total_produtos"] <= vi["total_med"]            # menor preço por loja nunca passa da mediana
    assert not vi["completo"] and len(vi["itens_sem_preco"]) == 3   # 3 itens sem preço: não afirma "cabe"
    assert vi["resumo"].startswith("Ainda não dá para afirmar: 3 itens")
    assert ga["segundos_reais"] == 31.0 and "R$ 0,33" in ga["resumo"]

    # 3) Excel: o que a tela mostra bate com o que o arquiteto leva
    x = api.get("/orcamentos/o1/exportar.xlsx")
    assert x.status_code == 200
    wb = load_workbook(BytesIO(x.content))
    plano = [c.value for c in wb["Plano de compra"]["A"] if c.value]
    for i in lojas_idx:
        assert api.itens_banco[i]["descricao"] in plano
    sem_preco = [c.value for c in wb["Pendentes"]["A"] if c.value][1:]
    assert sorted(sem_preco) == sorted(i["descricao"] for i in api.itens_banco if i["status"] != "definido")
    resumo = {r[0].value: r[1].value for r in wb["Resumo"].iter_rows()}
    assert resumo["Frete total"] == lg["frete_total"]


def test_resultado_e_idempotente(api):
    a = api.post("/orcamentos/o1/resultado").json()
    b = api.post("/orcamentos/o1/resultado").json()
    assert a["logistica"] == b["logistica"] and a["viabilidade"] == b["viabilidade"]


def test_orcamento_apertado_diz_que_nao_cabe_e_que_pode_piorar(api):
    api.orc["orcamento_cliente"] = 45000      # total simulado ≈ R$ 52,8 mil + 3 itens ainda sem preço
    vi = api.post("/orcamentos/o1/resultado").json()["viabilidade"]
    assert not vi["cabe"] and vi["resumo"].startswith("Não cabe")
    assert "3 itens ainda sem preço ficaram fora desse total" in vi["resumo"]
    assert 1 <= len(vi["sugestoes"]) <= 3
