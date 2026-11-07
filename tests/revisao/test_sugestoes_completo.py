"""POST /revisao/sugestoes/completo: erros E1 (A) + complementos E2 (C) numa resposta."""

import pytest
from fastapi.testclient import TestClient

from tests.revisao.conftest import item


@pytest.fixture
def api():
    from src.main import app
    return TestClient(app)


def completo(api, itens, **kw):
    r = api.post("/revisao/sugestoes/completo", json={"redigir": False, "itens": itens, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def exemplo_joao():
    return [
        item("Porcelanato 90x90 acetinado", "48", "m2", linha=1, id="p", cat="Revestimentos"),
        item("Tinta acrilica fosca branca", "120", "m2", linha=2, id="t", cat="Pintura"),
    ]


def test_exemplo_do_joao_gera_argamassa_rejunte_e_niveladores(api):
    corpo = completo(api, exemplo_joao())
    por_desc = {c["descricao"]: c for c in corpo["complementos"]}
    assert por_desc["Argamassa colante AC-III 20 kg (saco)"]["quantidade"] == 15
    assert por_desc["Rejunte 5 kg (saco)"]["quantidade"] == 5
    assert por_desc["Espaçador/nivelador de piso (pacote 100 un)"]["quantidade"] == 3
    assert por_desc["Selador acrílico 18 L (lata)"]["quantidade"] == 2
    assert por_desc["Massa corrida 25 kg (lata)"]["quantidade"] == 3
    assert por_desc["Fita crepe 48 mm x 50 m (rolo)"]["quantidade"] == 8
    assert por_desc["Lixa para massa grão 150 (folha)"]["quantidade"] == 60
    arg = por_desc["Argamassa colante AC-III 20 kg (saco)"]
    assert arg["regra"] == "porcelanato" and arg["origem_linhas"] == [1] and arg["origem_item_ids"] == ["p"]
    assert arg["estimativa_consumo"] is True and arg["motivo"] and arg["id"]
    assert corpo["complementos_disponiveis"] is True and corpo["complementos_erro"] is None
    assert corpo["revisao_id"] and corpo["erros"] == []


def test_ids_dos_complementos_sao_estaveis_mesmo_com_quantidade_editada(api):
    a = completo(api, exemplo_joao())
    editada = exemplo_joao()
    editada[0]["quantidade"] = "60,5"
    b = completo(api, editada)
    ids_a = {c["descricao"]: c["id"] for c in a["complementos"]}
    ids_b = {c["descricao"]: c["id"] for c in b["complementos"]}
    assert ids_a == ids_b
    assert {c["descricao"]: c["quantidade"] for c in b["complementos"]}["Argamassa colante AC-III 20 kg (saco)"] == 19


def test_quantidade_em_texto_br_e_convertida_antes_da_c(api):
    corpo = completo(api, [item("Porcelanato 90x90", "1.200,5", "m²", linha=1, id="p")])
    argamassa = next(c for c in corpo["complementos"] if c["regra"] == "porcelanato" and "Argamassa" in c["descricao"])
    assert argamassa["quantidade"] == 361  # ceil(1200,5 × 6 / 20)


def test_quantidade_vazia_ou_invalida_nao_derruba(api):
    corpo = completo(api, [item("Porcelanato 90x90", "", "m2", linha=1), item("Tinta branca", "abc", "m2", linha=2)])
    assert corpo["complementos"] == [] and corpo["complementos_disponiveis"] is True


def test_erros_e_complementos_juntos_na_casa_terrea(api, carregar):
    itens = carregar("02-casa-terrea-aldeia", "lista_materiais_casa-terrea-aldeia.csv")
    corpo = completo(api, itens)
    erros = [e for e in corpo["erros"] if e["regra"] == "unidade"]
    assert {e["valor_atual"] for e in erros} == {"sc", "br"} and len(erros) == 4
    assert all(e["correcao"]["alteracoes"][0]["para"] == "un" for e in erros)
    assert corpo["complementos_disponiveis"] is True
    assert all(c["origem_item_ids"] for c in corpo["complementos"])


def test_c_indisponivel_devolve_os_erros_e1(api, monkeypatch):
    def quebra(_itens):
        raise RuntimeError("C fora do ar")
    monkeypatch.setattr("src.rotas_revisao.sugerir_complementos", quebra)
    corpo = completo(api, [item("Cimento Votoran", "180", "sc", linha=2, id="c")])
    assert len(corpo["erros"]) == 1 and corpo["erros"][0]["valor_atual"] == "sc"
    assert corpo["complementos"] == [] and corpo["complementos_disponiveis"] is False
    assert corpo["complementos_erro"] and "RuntimeError" not in corpo["complementos_erro"]


def test_lista_vazia_e_corpo_invalido(api):
    corpo = completo(api, [])
    assert corpo["erros"] == [] and corpo["complementos"] == [] and corpo["complementos_disponiveis"] is True
    assert api.post("/revisao/sugestoes/completo", json={"itens": "x"}).status_code == 422


def test_rota_do_joao_continua_intacta(api):
    r = api.post("/revisao/sugestoes", json={"itens": [
        {"linha": 1, "categoria": "Revestimentos", "descricao": "Porcelanato 90x90", "quantidade": 48, "unidade": "m2"}]})
    assert r.status_code == 200 and set(r.json()) == {"complementos"}
