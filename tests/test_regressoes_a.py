"""Etapa 13: regressões da Fatia A que cruzam fronteiras (front × servidor × B × contrato da importação).

Cada teste protege uma divergência que, se voltar, passa despercebida pelos testes de uma fatia só:
  - tabela de apelidos de unidade do front (csv.ts) e do servidor (revisao.py);
  - classificação única da A entendida pela B;
  - números brasileiros (importador × revisor);
  - os casos de API 094–099 do acervo (tests/importacao) contra o POST /orcamentos;
  - limite de tamanho do corpo (TC-098: um milhão de itens).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

os.environ.setdefault("LANGFUSE_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient

import src.main as principal
from src import orcamento as b
from src import rotas_orcamentos as ro
from src.limite_corpo import LIMITE_CORPO_BYTES
from src.revisao import _ALIAS_UNIDADE, _parse_quantidade, classificar_item

RAIZ = Path(__file__).resolve().parent.parent
FIX = RAIZ / "tests/importacao/fixtures"


# ------------------------------------------------------------------ apelidos de unidade: front × servidor


def _alias_do_front() -> dict[str, str]:
    texto = (RAIZ / "frontend/src/lib/importar/csv.ts").read_text("utf-8")
    bloco = re.search(r"const ALIAS_UNIDADE: Record<string, string> = \{(.*?)\n\};", texto, re.S)
    assert bloco, "não achei ALIAS_UNIDADE em csv.ts (mudou de formato?)"
    pares = re.findall(r'(?:"([^"]+)"|\b([a-z0-9_]+)\b):\s*"([^"]+)"', bloco.group(1))
    return {(a or b_): v for a, b_, v in pares}


def test_apelidos_de_unidade_do_front_e_do_servidor_sao_os_mesmos():
    front = _alias_do_front()
    assert len(front) > 25
    assert front == _ALIAS_UNIDADE, {
        "so_no_front": {k: v for k, v in front.items() if _ALIAS_UNIDADE.get(k) != v},
        "so_no_servidor": {k: v for k, v in _ALIAS_UNIDADE.items() if front.get(k) != v},
    }


# ------------------------------------------------------------------ classificação única da A, lida pela B


@pytest.mark.parametrize("descricao,esperada", [
    ("Tinta acrílica Suvinil Toque de Seda Branco Neve 18L", "definido"),
    ("Porcelanato Portobello Cimento Queimado acetinado 90x90", "definido"),
    ("tinta branca", "pendente"),
    ("Tinta cor coral", "pendente"),      # "coral" aqui é cor, não a marca
    ("cimento", "pendente"),
])
def test_a_classifica_e_a_b_entende_o_mesmo_valor(descricao, esperada):
    assert classificar_item(descricao) == esperada
    # a B lê o que a A gravou em orcamento_itens.classificacao e a converte para o seu vocabulário
    item = b.item_da_linha({"id": "x", "descricao": descricao, "quantidade": 1, "unidade": "un", "classificacao": esperada})
    assert item.classificacao == ("definido" if esperada == "definido" else "pendente_especificacao")


def test_o_servidor_grava_a_classificacao_da_a_e_ignora_a_do_cliente():
    item = ro.ItemIn.model_validate({"id": "a", "linha": 1, "descricao": "tinta branca", "quantidade": 1, "unidade": "un"})
    assert ro._item_para_banco(item)["classificacao"] == "pendente"
    assert "classificacao" not in ro.ItemIn.model_fields   # o corpo do cliente nem aceita o campo


# ------------------------------------------------------------------ números brasileiros


@pytest.mark.parametrize("texto,esperado", [
    ("12,5", 12.5), ("12,50", 12.5), ("1.234,56", 1234.56), ("3.000", 3000.0), ("48,2", 48.2),
    ("12.5", 12.5), ("180", 180.0), ("0,3", 0.3), ("1,5", 1.5), (12.5, 12.5), (7, 7.0),
])
def test_numero_brasileiro_do_revisor(texto, esperado):
    assert _parse_quantidade(texto) == pytest.approx(esperado)


@pytest.mark.parametrize("texto", ["", "abc", "12,5,3", None, True])
def test_numero_invalido_do_revisor_vira_none(texto):
    assert _parse_quantidade(texto) is None


# ------------------------------------------------------------------ casos de API 094–099 do acervo × POST /orcamentos


@pytest.fixture
def api(monkeypatch):
    chamadas = []
    monkeypatch.setattr(ro, "_supabase_ok", lambda: True)

    def criar(orcamento_id, hash_conteudo, obra, origem, itens):
        chamadas.append((orcamento_id, hash_conteudo))
        vistos = [h for i, h in chamadas[:-1] if i == orcamento_id]
        return {"resultado": ("existente" if hash_conteudo in vistos else "criado"), "orcamento_id": orcamento_id}

    async def pesquisar(orcamento_id):
        return {"status": "concluida"}

    monkeypatch.setattr(ro, "_criar_no_banco", criar)
    monkeypatch.setattr(ro, "_pesquisar", pesquisar)
    return TestClient(principal.app), chamadas


def do_contrato(arquivo: str, **sobrescrever) -> dict:
    """JSON do contrato da importação (origem/itens/avisos) -> corpo do POST /orcamentos (obra + itens com id)."""
    c = json.loads((FIX / arquivo).read_text("utf-8"))
    corpo = {
        "orcamento_id": "11111111-1111-4111-8111-111111111111",
        "obra": {"nome": "Obra de teste", "cep": "51020000", "orcamento_cliente": 1000.0},
    }
    if "origem" in c:
        corpo["origem"] = {"tipo": "arquivo", "arquivo": c["origem"].get("arquivo")}
    if "itens" in c:
        corpo["itens"] = [
            {"id": f"l{i['linha']}" if isinstance(i.get("linha"), int) else "x", "linha": i["linha"], "categoria": i.get("categoria"),
             "descricao": i["descricao"], "quantidade": i["quantidade"], "unidade": i["unidade"], "nivel": i.get("nivel"),
             "extras": i.get("extras") or {}, "origem_item": "arquivo"}
            for i in c["itens"]
        ]
    corpo.update(sobrescrever)
    return corpo


def test_tc094_json_valido_passa(api):
    cliente, _ = api
    assert cliente.post("/orcamentos", json=do_contrato("TC-094.json")).status_code == 200


@pytest.mark.parametrize("arquivo", ["TC-095-a-sem-itens.json", "TC-095-b-sem-origem.json"])
def test_tc095_sem_itens_ou_sem_origem_da_422(api, arquivo):
    cliente, chamadas = api
    r = cliente.post("/orcamentos", json=do_contrato(arquivo))
    assert r.status_code == 422 and chamadas == []


def test_tc096_quantidade_como_texto_da_422(api):
    cliente, chamadas = api
    corpo = do_contrato("TC-094.json")
    corpo["itens"][0]["quantidade"] = "12,5"
    assert cliente.post("/orcamentos", json=corpo).status_code == 422 and chamadas == []


def test_tc097_lista_vazia_nunca_da_500(api):
    # o importador devolve "sem dados" (aviso SEM_DADOS); na hora de ENVIAR, lista vazia é 422 (decisão da A)
    cliente, chamadas = api
    r = cliente.post("/orcamentos", json=do_contrato("TC-097.json", itens=[]))
    assert r.status_code == 422 and chamadas == []


def test_tc098a_tipos_errados_da_422(api):
    cliente, chamadas = api
    corpo = do_contrato("TC-094.json")
    corpo["itens"][0]["linha"] = "dois"
    corpo["itens"][1]["quantidade"] = None
    corpo["itens"][2]["unidade"] = 7
    assert cliente.post("/orcamentos", json=corpo).status_code == 422 and chamadas == []


def test_tc098b_muitos_itens_nao_trava(api):
    cliente, chamadas = api
    base = do_contrato("TC-094.json")
    um = base["itens"][0]
    base["itens"] = [{**um, "id": f"i{n}", "linha": n + 1} for n in range(ro.LIMITE_ITENS + 1)]
    r = cliente.post("/orcamentos", json=base)
    assert r.status_code in (413, 422) and chamadas == []


def test_tc099_o_mesmo_arquivo_duas_vezes_nao_cria_duas_vezes(api):
    cliente, chamadas = api
    corpo = do_contrato("TC-094.json")
    primeira = cliente.post("/orcamentos", json=corpo).json()
    segunda = cliente.post("/orcamentos", json=corpo).json()
    assert primeira["resultado"] == "criado" and segunda["resultado"] == "existente"
    assert chamadas[0] == chamadas[1]   # mesmo id e mesmo hash de conteúdo


# ------------------------------------------------------------------ limite do corpo (TC-098: ~140 MB)


def test_corpo_acima_do_limite_da_413_antes_de_ler(api):
    cliente, chamadas = api
    enorme = b'{"orcamento_id": "x", "lixo": "' + b"a" * (LIMITE_CORPO_BYTES + 10) + b'"}'
    r = cliente.post("/orcamentos", content=enorme, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert "grande demais" in r.json()["detail"]["mensagem"]
    assert chamadas == []


def test_corpo_sem_content_length_tambem_e_cortado(api):
    cliente, chamadas = api

    def pedacos():
        for _ in range(LIMITE_CORPO_BYTES // (1024 * 1024) + 2):
            yield b"a" * (1024 * 1024)

    r = cliente.post("/orcamentos", content=pedacos(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and chamadas == []


def test_corpo_normal_passa_pelo_limite(api):
    cliente, _ = api
    assert cliente.post("/orcamentos", json=do_contrato("TC-094.json")).status_code == 200


def test_o_limite_vale_para_a_revisao_mas_nao_para_as_outras_rotas(api):
    cliente, _ = api
    enorme = b"a" * (LIMITE_CORPO_BYTES + 10)
    assert cliente.post("/revisao/erros", content=enorme).status_code == 413
    # /health e outras não têm corpo grande e não passam pelo limite
    assert cliente.get("/health").status_code == 200


def test_413_acompanha_os_cabecalhos_de_cors(api):
    cliente, _ = api
    enorme = b"a" * (LIMITE_CORPO_BYTES + 10)
    r = cliente.post("/orcamentos", content=enorme, headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 413 and r.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


# ------------------------------------------------------------------ limite de itens: front × servidor


def test_limite_de_itens_por_orcamento_e_o_mesmo_no_front_e_no_servidor():
    tipos = (RAIZ / "frontend/src/lib/importar/tipos.ts").read_text("utf-8")
    front = int(re.search(r"export const LIMITE_ITENS_ORCAMENTO = ([\d_]+);", tipos).group(1).replace("_", ""))
    assert front == ro.LIMITE_ITENS
