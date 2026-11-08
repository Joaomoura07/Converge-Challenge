"""GET /lojas-proximas: lojas do Google Maps perto do CEP, com km e tempo aproximado. Sem rede."""

from __future__ import annotations

from fastapi.testclient import TestClient

import src.rotas_proximidade as rp
from src.busca import Local
from src.main import app
from src.regiao import LojaRegional


def test_cep_invalido_da_422():
    assert TestClient(app).get("/lojas-proximas?cep=123").status_code == 422


def test_lista_lojas_com_km_minutos_e_mapa(monkeypatch):
    async def preparar(cep):
        return Local("Recife", "PE"), [
            LojaRegional("CEMAFEL", "cemafel.com.br", "Av. João de Barros, 1904", -8.0, -34.9, 1.5),
            LojaRegional("Pinte Mais Tintas", None, "Estr. Velha de Água Fria, 571", -8.0, -34.9, None)]
    monkeypatch.setattr(rp, "preparar_obra", preparar)
    j = TestClient(app).get("/lojas-proximas?cep=52011-050").json()
    assert j["origem"] == {"cidade": "Recife", "uf": "PE"}
    a, b = j["lojas"]
    assert a["km"] == 1.5 and a["minutos_aprox"] == 3 and a["site"] == "cemafel.com.br"
    assert a["mapa"].startswith("https://www.google.com/maps/search/?api=1&query=CEMAFEL")
    assert b["minutos_aprox"] is None and b["site"] is None
    assert "aproximados" in j["aviso"]


def test_cep_que_nao_localiza_explica(monkeypatch):
    async def preparar(cep):
        return None, []
    monkeypatch.setattr(rp, "preparar_obra", preparar)
    j = TestClient(app).get("/lojas-proximas?cep=00000000").json()
    assert j["lojas"] == [] and "localizar" in j["aviso"]
