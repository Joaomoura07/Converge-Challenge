"""Lojas próximas, distância e tempo (OpenRouteService e Serper /places). Sem rede."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace as NS

import httpx
import pytest

from src import proximidade as p

RECIFE = (-8.0476, -34.8770)
LOJA_PERTO = (-8.0600, -34.8800)
LOJA_LONGE = (-8.1500, -34.9200)


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    p._cache_lojas.clear()
    monkeypatch.setattr(p, "get_settings", lambda: NS(ors_api_key="ors", serper_keys=["k"]))


def _cli(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_rota_real_do_openrouteservice_usa_lon_lat_e_converte_segundos():
    corpo = {}

    def handler(req):
        corpo.update(json.loads(req.read()))
        return httpx.Response(200, json={"distances": [[4.2, 15.0]], "durations": [[600, 1800]]})

    async def rodar():
        async with _cli(handler) as c:
            return await p.rota_matriz(RECIFE, [LOJA_PERTO, LOJA_LONGE], c)

    rotas = asyncio.run(rodar())
    assert [(r.km, r.minutos, r.aproximado) for r in rotas] == [(4.2, 10, False), (15.0, 30, False)]
    assert corpo["locations"][0] == [RECIFE[1], RECIFE[0]] and corpo["destinations"] == [1, 2]


@pytest.mark.parametrize("resposta", [httpx.Response(500), httpx.Response(200, json={"x": 1}), httpx.Response(403)])
def test_falha_da_rota_cai_na_estimativa_marcada(resposta):
    async def rodar():
        async with _cli(lambda req: resposta) as c:
            return await p.rota_matriz(RECIFE, [LOJA_PERTO], c)

    r = asyncio.run(rodar())[0]
    assert r.aproximado and r.km > 0 and r.minutos > 0


def test_sem_chave_nem_chama_o_servico(monkeypatch):
    monkeypatch.setattr(p, "get_settings", lambda: NS(ors_api_key="", serper_keys=[]))

    def handler(req):
        raise AssertionError("não deveria chamar a rede")

    async def rodar():
        async with _cli(handler) as c:
            return await p.rota_matriz(RECIFE, [LOJA_PERTO], c)

    assert asyncio.run(rodar())[0].aproximado


def test_lojas_proximas_filtra_a_rede_ordena_por_tempo_e_limita_por_rede(monkeypatch):
    async def local(cep):
        return NS(cidade="Recife", uf="PE")

    monkeypatch.setattr(p, "local_do_cep", local)
    monkeypatch.setattr(p, "_coordenada", lambda cep: (*RECIFE, "rua"))

    def handler(req: httpx.Request):
        if "serper" in str(req.url):
            q = json.loads(req.read())["q"]
            lista = [{"title": "Leroy Merlin Boa Viagem", "address": "Av. A, 1", "latitude": LOJA_PERTO[0], "longitude": LOJA_PERTO[1]},
                     {"title": "Leroy Merlin Prazeres", "address": "Rod. B", "latitude": LOJA_LONGE[0], "longitude": LOJA_LONGE[1]},
                     {"title": "Padaria do Zé", "address": "Rua C", "latitude": -8.05, "longitude": -34.88},   # não é da rede
                     {"title": "Leroy sem coordenada", "address": "?"}]
            return httpx.Response(200, json={"places": lista if q.startswith("Leroy") else []})
        return httpx.Response(200, json={"distances": [[3.0, 20.0]], "durations": [[480, 2400]]})

    async def rodar():
        async with _cli(handler) as c:
            return await p.lojas_proximas("50030000", por_rede=2, cliente=c)

    r = asyncio.run(rodar())
    nomes = [x["nome"] for x in r["lojas"]]
    assert nomes == ["Leroy Merlin Boa Viagem", "Leroy Merlin Prazeres"]
    assert r["lojas"][0]["minutos"] == 8 and r["lojas"][0]["aproximado"] is False and r["aviso"] is None
    assert r["origem"]["cidade"] == "Recife"


def test_cep_que_nao_localiza_e_sem_chave_explicam_o_motivo(monkeypatch):
    async def sem_local(cep):
        return None

    monkeypatch.setattr(p, "local_do_cep", sem_local)
    monkeypatch.setattr(p, "_coordenada", lambda cep: None)
    r = asyncio.run(p.lojas_proximas("00000000"))
    assert r["lojas"] == [] and "localizar" in r["aviso"]

    async def local(cep):
        return NS(cidade="Recife", uf="PE")

    monkeypatch.setattr(p, "local_do_cep", local)
    monkeypatch.setattr(p, "_coordenada", lambda cep: (*RECIFE, "rua"))
    monkeypatch.setattr(p, "get_settings", lambda: NS(ors_api_key="", serper_keys=[]))
    r = asyncio.run(p.lojas_proximas("50030000"))
    assert r["lojas"] == [] and "SERPER_API_KEYS" in r["aviso"]


def test_rota_http_valida_o_cep():
    from fastapi.testclient import TestClient
    from src.main import app

    assert TestClient(app).get("/lojas-proximas?cep=123").status_code == 422
