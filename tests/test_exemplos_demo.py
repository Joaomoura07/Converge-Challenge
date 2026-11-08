"""Exemplos reais de arquivo, dados sintéticos: pesquisa no teste 1 e revisão no teste 2.
O leitor do site confere a fixture; aqui validamos os resultados observáveis, sem serviços externos.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.complementos import sugerir_complementos
from src.revisao import classificar_item, revisar_itens
from src.calculo import calcular
from src.google_shopping import ler_anuncios
from src.modelos import ItemEntrada
from src.precos import ResultadoExtracao

FIXTURE = Path(__file__).resolve().parents[1] / "frontend/src/lib/demo/fixtures/itens-exemplos.json"
EXEMPLOS = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _itens(nome: str) -> list[dict]:
    return [{"id": f"i{n}", "linha": n + 1, "descricao": i["descricao"] or "", "quantidade": i["quantidade"],
             "unidade": i["unidade"] or "", "categoria": i["categoria"] or ""} for n, i in enumerate(EXEMPLOS[nome])]


def test_todos_os_testes_da_demo_estao_na_fixture():
    assert len(EXEMPLOS) == 14 and all(k.startswith("teste_") for k in EXEMPLOS)


@pytest.mark.parametrize("nome", sorted(k for k in EXEMPLOS if k.startswith("teste_1")))
def test_pesquisa_comeca_com_material_especificado_sem_correcao(nome):
    itens = _itens(nome)
    assert 3 <= len(itens) <= 5
    assert not any(e.correcao for e in revisar_itens(itens))
    assert all(classificar_item(i["descricao"]) == "definido" for i in itens)


@pytest.mark.parametrize("nome", sorted(k for k in EXEMPLOS if k.startswith("teste_2")))
def test_revisao_mostra_complemento_e_pergunta(nome):
    itens = _itens(nome)
    assert len(itens) <= 5
    if nome == "teste_2.skp":
        assert itens[0]["quantidade"] is None
        # Passo documentado no roteiro: o arquiteto informa a área que a contagem SKP não fornece.
        itens[0].update(quantidade=18, unidade="m2")
    if nome.rsplit(".", 1)[-1] in {"csv", "xlsx", "txt", "pdf"}:
        correcoes = [e for e in revisar_itens(itens) if e.correcao]
        assert len(correcoes) == 1 and correcoes[0].regra == "unidade"
        assert correcoes[0].correcao.alteracoes[0].para == "un"
        itens[1]["unidade"] = "un"
        assert not any(e.correcao for e in revisar_itens(itens))
    assert sugerir_complementos([{**i, "quantidade": i["quantidade"] or 0} for i in itens]), f"{nome}: sem complemento"
    assert any(classificar_item(i["descricao"]) != "definido" for i in itens), f"{nome}: nenhum item genérico"


@pytest.mark.parametrize("nome", sorted(k for k in EXEMPLOS if k.startswith("teste_1")))
def test_exemplos_especificados_geram_fontes_e_embalagens_com_ofertas_simuladas(nome):
    # Valores arbitrários APENAS no teste. Não estão nos arquivos entregues aos jurados.
    for i in _itens(nome):
        anuncios = [{"title": i["descricao"], "source": f"Loja simulada {n}", "price": preco,
                     "link": f"https://loja{n}.example/produto"} for n, preco in enumerate([87.9, 91.9])]
        ofertas = ler_anuncios(i["descricao"], i["unidade"], anuncios, False)
        calc = calcular(ItemEntrada(id=i["id"], descricao=i["descricao"], quantidade=i["quantidade"], unidade=i["unidade"]),
                        ResultadoExtracao(ofertas=ofertas), generico=False)
        assert calc.tem_preco and not calc.estimativa, (nome, i["descricao"], calc.descartadas)
        assert len(calc.fontes) == 2 and calc.qtd_embalagens > 0
        assert calc.preco_emb_min <= calc.preco_emb_med <= calc.preco_emb_max


@pytest.mark.parametrize("nome", sorted(EXEMPLOS))
def test_correcao_nao_estraga_o_porcelanato(nome):
    """Falso alarme achado em 08/11: 'Porcelanato Portobello Cimento' era lido como cimento (m2 -> un)."""
    for e in revisar_itens(_itens(nome)):
        if e.regra == "unidade":
            for i in _itens(nome):
                if i["id"] in e.item_ids and "porcelanato" in (i["descricao"] or "").lower():
                    assert not i["unidade"]  # só completar unidade ausente, nunca trocar m² por un
                    assert all(a.para == "m2" for a in e.correcao.alteracoes if a.item_id == i["id"])
