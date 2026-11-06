"""Testes Python da importação.

    pytest tests/importacao                                   # integridade das fixtures (sempre roda)
    IMPORTACAO_URL=http://localhost:8000/importacao pytest tests/importacao   # + casos da API (094–099)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest

AQUI = Path(__file__).resolve().parent
FIX = AQUI / "fixtures"
sys.path.insert(0, str(AQUI))
from contrato import Importacao, RespostaErro  # noqa: E402

MANIFEST = json.loads((FIX / "manifest.json").read_text(encoding="utf-8")) if (FIX / "manifest.json").exists() else None
pytestmark = pytest.mark.skipif(MANIFEST is None, reason="rode: python tests/importacao/gerar_fixtures.py")
CASOS = MANIFEST["casos"] if MANIFEST else []
URL = os.getenv("IMPORTACAO_URL")


def variantes(tipo: str | None = None):
    for c in CASOS:
        if tipo and c["tipo"] != tipo:
            continue
        for v in c["variantes"]:
            yield pytest.param(c, v, id=f'{c["id"]}:{(v["entrada"] or "-").split("/")[-1]}')


# ------------------------------------------------------------- integridade das fixtures

def test_sao_100_casos_em_ordem():
    assert [c["id"] for c in CASOS] == [f"TC-{i:03d}" for i in range(1, 101)]


@pytest.mark.parametrize("caso,var", list(variantes()))
def test_entrada_existe(caso, var):
    if var["entrada"] is None or caso["tipo"] == "manual":
        pytest.skip("caso sem arquivo de entrada")
    if var["grande"] and not (FIX / var["entrada"]).exists():
        pytest.skip("arquivo grande: gere com --grandes")
    assert (FIX / var["entrada"]).exists()


@pytest.mark.parametrize("caso,var", [p for p in variantes() if p.values[1]["esperado"]])
def test_esperado_segue_contrato(caso, var):
    esp = json.loads((FIX / var["esperado"]).read_text(encoding="utf-8"))
    if "resumo" in esp:
        assert esp["resumo"]["total_itens"] > 0
    elif "erro" in esp:
        RespostaErro.model_validate(esp)
    else:
        Importacao.model_validate(esp)
        assert esp["origem"]["arquivo"] == var["entrada"].split("/")[-1]


# ------------------------------------------------------------------------- API (094–099)

api = pytest.mark.skipif(not URL, reason="defina IMPORTACAO_URL para testar a API")


@api
@pytest.mark.parametrize("caso,var", [p for p in variantes("api") if p.values[1]["entrada"]])
def test_api_status(caso, var):
    arquivo = FIX / var["entrada"]
    if not arquivo.exists():
        pytest.skip("arquivo grande: gere com --grandes")
    corpo = arquivo.read_bytes()
    try:
        r = httpx.post(URL, content=corpo, headers={"Content-Type": "application/json"}, timeout=120)
    except httpx.HTTPError as exc:  # corpo gigante pode derrubar a conexão: isso também é falha
        pytest.fail(f"servidor não respondeu: {exc}")
    aceitos = {var["status_http"]} | ({413} if caso["id"] == "TC-098" and var["grande"] else set())
    assert r.status_code in aceitos, f"{caso['id']}: esperado {aceitos}, veio {r.status_code}: {r.text[:300]}"
    assert r.status_code != 500


@api
def test_api_idempotencia_tc099():
    corpo = (FIX / "TC-094.json").read_bytes()
    h = {"Content-Type": "application/json"}
    r1, r2 = httpx.post(URL, content=corpo, headers=h), httpx.post(URL, content=corpo, headers=h)
    assert r1.status_code == r2.status_code == 200
    j1, j2 = r1.json(), r2.json()
    chave = next((k for k in ("id", "importacao_id", "hash") if k in j1), None)
    assert chave, f"resposta deve trazer id/hash para provar idempotência: {list(j1)}"
    assert j1[chave] == j2[chave], "segundo envio criou um registro novo"
