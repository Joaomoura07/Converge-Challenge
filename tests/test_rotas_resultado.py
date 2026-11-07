"""Testes das rotas da Fatia C com banco e CEP simulados (sem rede, sem Supabase)."""

from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from src import rotas_resultado as rr
from src.logistica import Fornecedor

L = Fornecedor(id="L", nome="Leroy Merlin", dominio="leroymerlin.com.br", cep="51021-040",
               frete_base=30, rs_por_km=1.5, pedido_minimo=100)
C = Fornecedor(id="C", nome="C&C", dominio="cec.com.br", cep="50070-000", frete_base=20, rs_por_km=1.0)


def _item(linha, desc, l, c, qtd=1):
    fontes = [{"loja": "Leroy", "dominio": "leroymerlin.com.br", "url": "https://l/x", "preco_embalagem": l},
              {"loja": "C&C", "dominio": "cec.com.br", "url": "https://c/y", "preco_embalagem": c}]
    return {"id": f"i{linha}", "linha": linha, "descricao": desc, "qtd_embalagens": qtd, "status": "definido",
            "embalagem": "un", "confianca": "alta", "fontes": fontes, "preco_emb_min": min(l, c),
            "preco_emb_med": (l + c) / 2, "preco_emb_max": max(l, c)}


@pytest.fixture
def api(monkeypatch):
    gravado = {}
    monkeypatch.setenv("FRETE_ATIVO", "true")   # estes testes cobrem o cálculo de frete (pausado por padrão)
    itens = [_item(2, "Porcelanato", 1500, 1000), _item(1, "Tinta", 1000, 1500)]   # fora de ordem de propósito
    orc = {"id": "o1", "nome": "Cozinha", "cep": "52011-050", "orcamento_cliente": 5000,
           "pesquisa_iniciada_em": "2026-11-07T10:00:00+00:00", "pesquisa_concluida_em": "2026-11-07T10:00:28+00:00", "custo_usd": 0.0545}
    monkeypatch.setattr(rr, "_carregar_orcamento", lambda i: orc if i == "o1" else None)
    monkeypatch.setattr(rr, "_carregar_itens", lambda i: sorted(itens, key=lambda x: x["linha"]))
    monkeypatch.setattr(rr, "_carregar_fornecedores", lambda: [L, C])
    monkeypatch.setattr(rr, "_gravar_resultado", lambda i, d: gravado.update(id=i, dados=d))
    monkeypatch.setattr(rr, "distancias_km", lambda cep, f: {"L": 10.0, "C": 5.0})
    app = FastAPI()
    app.include_router(rr.router)
    cli = TestClient(app)
    cli.gravado, cli.orc, cli.itens = gravado, orc, itens
    return cli


def test_sugestoes_devolve_complementos(api):
    r = api.post("/revisao/sugestoes", json={"itens": [
        {"linha": 3, "categoria": "Revestimentos", "descricao": "Porcelanato 90x90", "quantidade": 48, "unidade": "m2"}]})
    assert r.status_code == 200
    comp = {c["descricao"]: c for c in r.json()["complementos"]}
    assert comp["Argamassa colante AC-III 20 kg (saco)"]["quantidade"] == 15
    assert comp["Rejunte 5 kg (saco)"]["origem_linhas"] == [3]


def test_sugestoes_sem_itens_e_corpo_invalido(api):
    assert api.post("/revisao/sugestoes", json={"itens": []}).json() == {"complementos": []}
    assert api.post("/revisao/sugestoes", json={}).status_code == 422


def test_resultado_calcula_e_grava(api):
    r = api.post("/orcamentos/o1/resultado")
    assert r.status_code == 200
    d = r.json()
    assert d["logistica"]["estrategia"] == "dividir" and d["logistica"]["frete_total"] == 70.0
    assert d["viabilidade"]["cabe"] and d["viabilidade"]["completo"]
    assert d["ganho"]["resumo"].startswith("À mão:") and d["ganho"]["segundos_reais"] == 28.0
    assert api.gravado["id"] == "o1" and api.gravado["dados"]["logistica"]["total"] == d["logistica"]["total"]


def test_resultado_sem_orcamento_do_cliente_nao_calcula_viabilidade(api):
    api.orc["orcamento_cliente"] = None
    d = api.post("/orcamentos/o1/resultado").json()
    assert d["viabilidade"] is None and d["logistica"] is not None


def test_resultado_sem_itens_ou_lojas(api, monkeypatch):
    monkeypatch.setattr(rr, "_carregar_itens", lambda i: [])
    d = api.post("/orcamentos/o1/resultado").json()
    assert d["logistica"] is None and d["viabilidade"]["total_med"] == 0


def test_orcamento_inexistente_da_404(api):
    assert api.post("/orcamentos/nao-existe/resultado").status_code == 404
    assert api.get("/orcamentos/nao-existe/exportar.xlsx").status_code == 404


def test_falha_ao_gravar_da_502_com_mensagem(api, monkeypatch):
    def quebra(i, d):
        raise RuntimeError("supabase fora")

    monkeypatch.setattr(rr, "_gravar_resultado", quebra)
    r = api.post("/orcamentos/o1/resultado")
    assert r.status_code == 502 and "não consegui salvar" in r.json()["detail"]


def test_exportar_devolve_xlsx_por_loja(api):
    r = api.get("/orcamentos/o1/exportar.xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "plano-de-compra.xlsx" in r.headers["content-disposition"]
    wb = load_workbook(BytesIO(r.content))
    col = [c.value for c in wb["Plano de compra"]["A"] if c.value]
    assert "Tinta" in col and "Porcelanato" in col and any("Leroy" in str(v) for v in col)


def test_segundos_invalidos_nao_quebram():
    assert rr._segundos(None, None) is None
    assert rr._segundos("2026-11-07T10:00:00Z", "2026-11-07T10:01:00Z") == 60.0


def test_resultado_nao_grava_colunas_que_nao_existem(api):
    """Só grava logistica/viabilidade/ganho: uma coluna inexistente no SQL faria o update falhar (502)."""
    api.post("/orcamentos/o1/resultado")
    assert set(api.gravado["dados"]) == {"logistica", "viabilidade", "ganho"}


# --- frete em pausa (padrão): sempre R$ 0, sem CEP/API/fornecedores ------------------------------------------
def test_frete_pausado_por_padrao_e_zero_e_nao_usa_cep_nem_fornecedores(api, monkeypatch):
    monkeypatch.delenv("FRETE_ATIVO", raising=False)
    monkeypatch.setattr(rr, "distancias_km", lambda *a: pytest.fail("não deve consultar CEP"))
    monkeypatch.setattr(rr, "_carregar_fornecedores", lambda: pytest.fail("não deve ler fornecedores"))
    d = api.post("/orcamentos/o1/resultado").json()
    lg = d["logistica"]
    assert lg["frete_total"] == 0.0 and lg["total"] == lg["total_produtos"]
    assert all(l["frete"] == 0.0 and not l["abaixo_do_minimo"] for l in lg["lojas"])
    # cada item na loja mais barata (Tinta: Leroy 1000 < C&C 1500; Porcelanato: C&C 1000 < Leroy 1500)
    por_loja = {l["id"]: sorted(l["itens"]) for l in lg["lojas"]}
    assert por_loja == {"leroymerlin.com.br": [0], "cec.com.br": [1]}
    assert d["viabilidade"]["frete"] == 0.0 and d["viabilidade"]["total_med"] == 2500.0
    assert api.gravado["dados"]["logistica"]["frete_total"] == 0.0


def test_exportar_com_frete_pausado_agrupa_por_loja_sem_frete(api, monkeypatch):
    monkeypatch.delenv("FRETE_ATIVO", raising=False)
    monkeypatch.setattr(rr, "_carregar_fornecedores", lambda: pytest.fail("não deve ler fornecedores"))
    wb = load_workbook(BytesIO(api.get("/orcamentos/o1/exportar.xlsx").content))
    col = [str(c.value) for c in wb["Plano de compra"]["A"] if c.value]
    assert any("Leroy" in v for v in col) and any("C&C" in v for v in col) and "Tinta" in col
    resumo = {r[0].value: r[1].value for r in wb["Resumo"].iter_rows()}
    assert resumo["Frete total"] == 0.0


def test_frete_ativo_so_com_a_variavel(monkeypatch):
    monkeypatch.delenv("FRETE_ATIVO", raising=False)
    assert rr._frete_ativo() is False
    for v in ("true", "TRUE", "1", "sim"):
        monkeypatch.setenv("FRETE_ATIVO", v)
        assert rr._frete_ativo() is True
    monkeypatch.setenv("FRETE_ATIVO", "false")
    assert rr._frete_ativo() is False


# --- leitura do banco (supabase simulado): complementos não aceitos e fornecedores inativos ------------------
class _Q:
    def __init__(self, dados):
        self.dados, self.filtros = dados, []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filtros.append((col, val))
        return self

    def execute(self):
        class R:  # noqa: D401
            pass

        r = R()
        r.data = [d for d in self.dados if all(d.get(c) == v for c, v in self.filtros if c != "orcamento_id")]
        return r


class _SB:
    def __init__(self, tabelas):
        self.tabelas = tabelas

    def table(self, nome):
        return _Q(self.tabelas[nome])


def test_complemento_nao_aceito_nao_entra_nos_itens(monkeypatch):
    linhas = [
        {"id": "a", "linha": 1, "descricao": "Tinta", "sugerido": False, "aceito": None},
        {"id": "b", "linha": 2, "descricao": "Selador", "sugerido": True, "aceito": True},
        {"id": "c", "linha": 3, "descricao": "Massa", "sugerido": True, "aceito": False},
        {"id": "d", "linha": 4, "descricao": "Fita", "sugerido": True, "aceito": None},
    ]
    monkeypatch.setattr(rr, "get_supabase", lambda: _SB({"orcamento_itens": linhas}))
    assert [i["descricao"] for i in rr._carregar_itens("o1")] == ["Tinta", "Selador"]


def test_so_fornecedores_ativos(monkeypatch):
    forn = [{"id": "1", "nome": "Ativa", "dominio": "a.com", "cep": "50000000", "ativo": True},
            {"id": "2", "nome": "Inativa", "dominio": "b.com", "cep": "50000000", "ativo": False}]
    monkeypatch.setattr(rr, "get_supabase", lambda: _SB({"fornecedores": forn}))
    assert [f.nome for f in rr._carregar_fornecedores()] == ["Ativa"]
