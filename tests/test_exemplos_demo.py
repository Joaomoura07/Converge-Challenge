"""Os arquivos de teste da /demo (frontend/public/exemplos/demo/teste_*) precisam MOSTRAR a IA trabalhando: cada um traz
de propósito um erro típico que o revisor aponta com correção em um clique, um material que puxa complementos e um item
genérico que vira pergunta ao arquiteto. Os itens vêm do leitor REAL do site (fixture gerada e conferida em
frontend/src/lib/demo/exemplos.test.ts); aqui eles passam pelas regras REAIS do revisor (A) e dos complementos (C)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.complementos import sugerir_complementos
from src.revisao import classificar_item, revisar_itens

FIXTURE = Path(__file__).resolve().parents[1] / "frontend/src/lib/demo/fixtures/itens-exemplos.json"
EXEMPLOS = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _itens(nome: str) -> list[dict]:
    return [{"id": f"i{n}", "linha": n + 1, "descricao": i["descricao"] or "", "quantidade": i["quantidade"],
             "unidade": i["unidade"] or "", "categoria": i["categoria"] or ""} for n, i in enumerate(EXEMPLOS[nome])]


def test_todos_os_testes_da_demo_estao_na_fixture():
    assert len(EXEMPLOS) == 14 and all(k.startswith("teste_") for k in EXEMPLOS)


@pytest.mark.parametrize("nome", sorted(EXEMPLOS))
def test_cada_teste_mostra_erro_complemento_e_pergunta(nome):
    itens = _itens(nome)
    erros = revisar_itens(itens)
    assert any(e.correcao is not None for e in erros), f"{nome}: nenhum erro com correção em um clique"
    assert sugerir_complementos([{**i, "quantidade": i["quantidade"] or 0} for i in itens]), f"{nome}: sem complemento"
    assert any(classificar_item(i["descricao"]) != "definido" for i in itens), f"{nome}: nenhum item genérico"


@pytest.mark.parametrize("nome", sorted(EXEMPLOS))
def test_correcao_nao_estraga_o_porcelanato(nome):
    """Falso alarme achado em 08/11: 'Porcelanato Portobello Cimento' era lido como cimento (m2 -> un)."""
    for e in revisar_itens(_itens(nome)):
        if e.regra == "unidade":
            assert not any("porcelanato" in (i["descricao"] or "").lower() for i in _itens(nome) if i["id"] in e.item_ids)
