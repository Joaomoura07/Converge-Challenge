"""Leitor mínimo dos CSVs de docs/arquivos-teste no formato da lista de revisão da tela.

Imita o que frontend/src/lib/importar/csv.ts entrega (quantidade só com número, unidade normalizada,
valor não numérico em Quantidade vira vazio); serve apenas aos testes do revisor.
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

import pytest

os.environ["LANGFUSE_ENABLED"] = "false"  # os testes não enviam traces (exceto os marcados `real`)

from src.revisao import _parse_quantidade, normalizar_unidade

RAIZ = Path(__file__).resolve().parents[2]
ACERVO = RAIZ / "docs" / "arquivos-teste"


def _texto(caminho: Path) -> str:
    dados = caminho.read_bytes()
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("cp1252")


def lista_da_tela(caminho: Path) -> list[dict]:
    linhas = list(csv.reader(io.StringIO(_texto(caminho)), delimiter=";"))
    cab = [c.strip().lower() for c in linhas[0]]
    col: dict[str, int] = {}
    for i, nome in enumerate(cab):
        if nome in ("produto", "descricao", "descrição"):
            col["descricao"] = i
        elif nome in ("quantidade", "qtd"):
            col["quantidade"] = i
        elif nome in ("unidade", "un"):
            col["unidade"] = i
        elif nome == "categoria":
            col["categoria"] = i
    itens = []
    for n, cel in enumerate(linhas[1:], start=2):
        def pega(campo: str) -> str:
            i = col.get(campo)
            return cel[i].strip() if i is not None and i < len(cel) else ""
        qtd, un = pega("quantidade"), pega("unidade")
        junto = re.fullmatch(r"([\d.,]+)\s*([^\d\s.,][^\s]*\.?)", qtd)
        if junto:
            qtd, un = junto.group(1), un or junto.group(2)
        numero = _parse_quantidade(qtd)
        un = normalizar_unidade(un) or un
        itens.append({
            "id": f"{caminho.stem}-{n}", "descricao": pega("descricao"),
            "quantidade": "" if numero is None else (str(int(numero)) if numero.is_integer() else str(numero).replace(".", ",")),
            "unidade": un, "categoria": pega("categoria"), "linhaOrigem": n,
        })
    return itens


@pytest.fixture
def carregar():
    def _c(pasta: str, arquivo: str) -> list[dict]:
        return lista_da_tela(ACERVO / pasta / arquivo)
    return _c


def item(desc, qtd="1", un="un", linha=None, cat="", **extra):
    d = {"descricao": desc, "quantidade": str(qtd), "unidade": un, "categoria": cat, **extra}
    if linha:
        d["linhaOrigem"] = linha
    return d
