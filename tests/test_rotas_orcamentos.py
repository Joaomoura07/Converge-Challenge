"""POST /orcamentos (Fatia A, etapa 08). Banco e pesquisa são simulados: nenhum teste toca no Supabase real nem no LLM."""

from __future__ import annotations

import copy
import os

os.environ.setdefault("LANGFUSE_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient

from src import rotas_orcamentos as ro
from src.main import app

ID = "11111111-1111-4111-8111-111111111111"


def corpo(**mudancas):
    base = {
        "orcamento_id": ID,
        "obra": {"nome": "Reforma Apto Boa Viagem", "cep": "51020-000", "orcamento_cliente": 20000.0},
        "origem": {"tipo": "arquivo", "arquivo": "lista.csv", "formato": "csv"},
        "itens": [
            {"id": "a1", "linha": 2, "categoria": "Pintura", "descricao": "Tinta acrílica Suvinil Toque de Seda 18L",
             "quantidade": 180, "unidade": "m2", "origem_item": "arquivo"},
            {"id": "a2", "linha": 3, "descricao": "tinta branca", "quantidade": 2, "unidade": "un"},
        ],
    }
    base.update(mudancas)
    return base


class Falso:
    """Banco e pesquisa de mentira, com registro das chamadas."""

    def __init__(self, resultado="criado", erro_banco=None, erro_pesquisa=None):
        self.resultado, self.erro_banco, self.erro_pesquisa = resultado, erro_banco, erro_pesquisa
        self.gravacoes: list[dict] = []
        self.pesquisas: list[str] = []

    def criar(self, orcamento_id, hash_conteudo, obra, origem, itens):
        self.gravacoes.append({"id": orcamento_id, "hash": hash_conteudo, "obra": obra, "origem": origem, "itens": itens})
        if self.erro_banco:
            raise self.erro_banco
        return {"resultado": self.resultado, "orcamento_id": orcamento_id, "status_pesquisa": "pendente"}

    async def pesquisar(self, orcamento_id):
        self.pesquisas.append(orcamento_id)
        if self.erro_pesquisa:
            raise self.erro_pesquisa
        return {"orcamento_id": orcamento_id, "status": "concluida", "itens": 2}


@pytest.fixture
def falso(monkeypatch):
    f = Falso()
    monkeypatch.setattr(ro, "_supabase_ok", lambda: True)
    monkeypatch.setattr(ro, "_criar_no_banco", f.criar)
    monkeypatch.setattr(ro, "_pesquisar", f.pesquisar)
    return f


@pytest.fixture
def cliente():
    return TestClient(app)


# ------------------------------------------------------------------ caminho feliz


def test_grava_e_pesquisa_na_mesma_requisicao(falso, cliente):
    r = cliente.post("/orcamentos", json=corpo())
    assert r.status_code == 200
    j = r.json()
    assert j["orcamento_id"] == ID and j["resultado"] == "criado" and j["itens"] == 2
    assert j["pesquisa"]["status"] == "concluida"
    assert falso.pesquisas == [ID]                      # a pesquisa roda UMA vez, depois de gravar
    (g,) = falso.gravacoes
    assert g["obra"] == {"nome": "Reforma Apto Boa Viagem", "cep": "51020000", "orcamento_cliente": 20000.0}
    assert g["origem"]["arquivo"] == "lista.csv"


def test_itens_vao_ao_banco_com_a_classificacao_unica_e_o_id_da_tela(falso, cliente):
    cliente.post("/orcamentos", json=corpo())
    itens = falso.gravacoes[0]["itens"]
    assert [i["id_linha"] for i in itens] == ["a1", "a2"]                 # ID estável da tela
    assert [i["classificacao"] for i in itens] == ["definido", "pendente"]   # classificar_item da etapa 05
    assert all("status" not in i for i in itens)         # o status 'buscando' é do SQL (criar_orcamento)
    assert itens[0]["descricao_original"] == itens[0]["descricao"]
    assert itens[0]["linha"] == 2 and itens[0]["categoria"] == "Pintura"


def test_cep_com_mascara_vira_oito_digitos_e_preserva_zero(falso, cliente):
    c = corpo(obra={"nome": "Casa", "cep": "01310-100", "orcamento_cliente": 1234.56})
    assert cliente.post("/orcamentos", json=c).status_code == 200
    assert falso.gravacoes[0]["obra"]["cep"] == "01310100"
    assert falso.gravacoes[0]["obra"]["orcamento_cliente"] == 1234.56


# ------------------------------------------------------------------ reenvio e conflito


def test_reenvio_equivalente_usa_o_mesmo_hash_e_recupera(falso, cliente):
    r1 = cliente.post("/orcamentos", json=corpo())
    falso.resultado = "existente"
    r2 = cliente.post("/orcamentos", json=corpo())
    assert r1.status_code == r2.status_code == 200
    assert r2.json()["resultado"] == "existente"
    assert falso.gravacoes[0]["hash"] == falso.gravacoes[1]["hash"]       # o banco decide 'existente' por este hash
    assert falso.pesquisas == [ID, ID]   # a B decide pela reserva se pesquisa; a rota não duplica itens


def test_hash_ignora_origem_e_ordem_das_chaves_mas_muda_com_o_conteudo(falso, cliente):
    cliente.post("/orcamentos", json=corpo())
    outra_origem = corpo(origem={"tipo": "arquivo", "arquivo": "outro-nome.csv"})
    cliente.post("/orcamentos", json=outra_origem)
    mudou = corpo()
    mudou["itens"][0]["quantidade"] = 181
    cliente.post("/orcamentos", json=mudou)
    h = [g["hash"] for g in falso.gravacoes]
    assert h[0] == h[1] and h[0] != h[2]


def test_conflito_devolve_409_e_nao_pesquisa(falso, cliente):
    falso.resultado = "conflito"
    r = cliente.post("/orcamentos", json=corpo())
    assert r.status_code == 409
    assert r.json()["detail"]["orcamento_id"] == ID
    assert falso.pesquisas == []


# ------------------------------------------------------------------ falhas e recuperação


def test_falha_da_pesquisa_mantem_o_orcamento_e_diz_como_recuperar(falso, cliente):
    falso.erro_pesquisa = RuntimeError("Tavily fora do ar")
    r = cliente.post("/orcamentos", json=corpo())
    assert r.status_code == 502
    d = r.json()["detail"]
    assert d["orcamento_id"] == ID and d["recuperavel"] is True
    assert len(falso.gravacoes) == 1   # o orçamento ficou gravado; reenviar o mesmo corpo é seguro


def test_erro_generico_do_banco_vira_502_e_nao_pesquisa(falso, cliente):
    falso.erro_banco = RuntimeError("conexão perdida")
    r = cliente.post("/orcamentos", json=corpo())
    assert r.status_code == 502 and falso.pesquisas == []


def test_regra_do_banco_violada_vira_422(falso, cliente):
    class Violacao(Exception):
        code = "23514"

    falso.erro_banco = Violacao("itens_quantidade_ck")
    r = cliente.post("/orcamentos", json=corpo())
    assert r.status_code == 422 and falso.pesquisas == []


def test_sem_supabase_devolve_503(monkeypatch, cliente):
    monkeypatch.setattr(ro, "_supabase_ok", lambda: False)
    assert cliente.post("/orcamentos", json=corpo()).status_code == 503


# ------------------------------------------------------------------ validação do contrato (422, nada é gravado)


def _muda(caminho, valor):
    c = copy.deepcopy(corpo())
    alvo = c
    for k in caminho[:-1]:
        alvo = alvo[k]
    alvo[caminho[-1]] = valor
    return c


@pytest.mark.parametrize("motivo,c", [
    ("quantidade em texto (D7)", _muda(["itens", 0, "quantidade"], "12,5")),
    ("quantidade zero", _muda(["itens", 0, "quantidade"], 0)),
    ("quantidade negativa", _muda(["itens", 0, "quantidade"], -3)),
    ("unidade fora da lista", _muda(["itens", 0, "unidade"], "sc")),
    ("unidade vazia", _muda(["itens", 0, "unidade"], "")),
    ("descrição vazia", _muda(["itens", 0, "descricao"], "   ")),
    ("CEP curto", _muda(["obra", "cep"], "123")),
    ("orçamento do cliente zero", _muda(["obra", "orcamento_cliente"], 0)),
    ("orçamento do cliente em texto", _muda(["obra", "orcamento_cliente"], "20.000,00")),
    ("nome vazio", _muda(["obra", "nome"], " ")),
    ("sem itens", _muda(["itens"], [])),
    ("UUID inválido", _muda(["orcamento_id"], "nao-e-uuid")),
    ("campo desconhecido no item", _muda(["itens", 0, "preco"], 10)),
    ("id repetido", {**corpo(), "itens": [corpo()["itens"][0], {**corpo()["itens"][1], "id": "a1"}]}),
    ("complemento sem origem_linhas", _muda(["itens", 1], {
        "id": "c1", "linha": 3, "descricao": "Argamassa", "quantidade": 3, "unidade": "un",
        "sugerido": True, "sugestao_regra": "porcelanato", "aceito": True})),
    ("complemento sem decisão", _muda(["itens", 1], {
        "id": "c1", "linha": 3, "descricao": "Argamassa", "quantidade": 3, "unidade": "un",
        "sugerido": True, "sugestao_regra": "porcelanato", "origem_linhas": [1]})),
])
def test_corpo_invalido_e_recusado_sem_gravar(falso, cliente, motivo, c):
    r = cliente.post("/orcamentos", json=c)
    assert r.status_code == 422, motivo
    assert falso.gravacoes == [] and falso.pesquisas == []


def test_corpo_sem_obra_ou_sem_itens(falso, cliente):
    assert cliente.post("/orcamentos", json={"orcamento_id": ID}).status_code == 422
    assert cliente.post("/orcamentos", json=[1, 2]).status_code == 422
    assert falso.gravacoes == []


# ------------------------------------------------------------------ complementos (E2)


def _complemento(aceito):
    return {"id": "c1", "linha": 4, "categoria": "Revestimentos e argamassas",
            "descricao": "Argamassa colante AC-III 20 kg (saco)", "quantidade": 15, "unidade": "un",
            "origem_item": "manual", "sugerido": True, "sugestao_regra": "porcelanato",
            "sugestao_motivo": "Para 48 m² de piso costumam faltar argamassa.", "origem_linhas": [1],
            "aceito": aceito, "estimativa_consumo": True}


def test_complemento_aceito_vai_com_regra_motivo_origem_e_estimativa_de_consumo(falso, cliente):
    c = corpo()
    c["itens"].append(_complemento(True))
    assert cliente.post("/orcamentos", json=c).status_code == 200
    comp = next(i for i in falso.gravacoes[0]["itens"] if i["id_linha"] == "c1")
    assert comp["sugerido"] is True and comp["aceito"] is True
    assert comp["sugestao_regra"] == "porcelanato" and comp["origem_linhas"] == [1]
    assert comp["estimativa_consumo"] is True      # consumo estimado pela C, diferente de estimativa de preço
    assert "estimativa" not in comp                # a estimativa de PREÇO é da B


def test_complemento_recusado_nao_e_gravado_nem_pesquisado(falso, cliente):
    c = corpo()
    c["itens"].append(_complemento(False))
    r = cliente.post("/orcamentos", json=c)
    assert r.status_code == 200
    assert r.json()["itens"] == 2 and r.json()["complementos_recusados_ignorados"] == ["c1"]
    assert {i["id_linha"] for i in falso.gravacoes[0]["itens"]} == {"a1", "a2"}


def test_so_complementos_recusados_nao_envia(falso, cliente):
    c = corpo(itens=[_complemento(False)])
    assert cliente.post("/orcamentos", json=c).status_code == 422
    assert falso.gravacoes == []


# ------------------------------------------------------------------ paridade com o contrato publicado


def test_campos_do_item_cobrem_o_contrato_da_importacao():
    from tests.importacao.contrato import Item as ItemContrato

    do_contrato = set(ItemContrato.model_fields)          # linha, categoria, descricao, quantidade, unidade, nivel, extras
    nossos = set(ro.ItemIn.model_fields)
    assert do_contrato <= nossos, do_contrato - nossos
    from tests.importacao.contrato import UNIDADES as _U
    assert set(ro.UNIDADES) <= set(_U.__args__)


def test_rota_registrada_no_app():
    assert "post" in app.openapi()["paths"].get("/orcamentos", {})
