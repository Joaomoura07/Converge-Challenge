"""O seed de fornecedores (Fatia C) tem que casar com as lojas que a busca da Fatia B reconhece."""

import re
from pathlib import Path

from src.busca import LOJAS
from src.logistica import Fornecedor

SQL = (Path(__file__).resolve().parent.parent / "sql" / "004_fornecedores_seed.sql").read_text(encoding="utf-8")
LINHAS = re.findall(r"^\s*\('([^']+)', '((?:[^']|'')+)', '([^']+)', ([\d.]+), ([\d.]+), ([\d.]+)\)", SQL, re.M)


def test_seed_tem_exatamente_as_lojas_da_busca():
    assert {d for _, _, d, *_ in LINHAS} == set(LOJAS)               # nenhum domínio a mais ou a menos
    assert {d: n.replace("''", "'") for _, n, d, *_ in LINHAS} == LOJAS


def test_ids_unicos_e_viram_fornecedor_valido():
    ids = [i for i, *_ in LINHAS]
    assert len(ids) == len(set(ids)) == len(LOJAS)
    for i, nome, dom, frete, rskm, minimo in LINHAS:
        f = Fornecedor(id=i, nome=nome, dominio=dom, frete_base=float(frete), rs_por_km=float(rskm),
                       pedido_minimo=float(minimo))
        assert f.cep is None and f.frete_base > 0 and f.rs_por_km == 0 and f.pedido_minimo == 0


def test_seed_e_idempotente_e_documenta_que_o_frete_e_estimado():
    assert "on conflict (id)" in SQL and "ESTIMADOS" in SQL
