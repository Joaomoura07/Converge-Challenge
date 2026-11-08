"""Alternativa (08/11): nunca o mesmo produto, outra marca no "semelhante" e preço na faixa pedida."""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest

from src.alternativas import (Alternativa, AlternativaIndisponivel, decidir, mesma_marca, mesmo_produto, razao_de_preco,
                              sugerir_alternativa)
from src.modelos import Fonte, ResultadoItem

FONTE = Fonte(loja="Leroy Merlin", dominio="leroymerlin.com.br", url="https://www.leroymerlin.com.br/x", preco_embalagem=100.0)


def tinta(produto="Tinta Suvinil Toque de Seda Branco Neve 18L", emb=800.0, embalagem="18 L"):
    return ResultadoItem(item_id="1", status="definido", produto_normalizado=produto, embalagem=embalagem, qtd_embalagens=1,
                         preco_emb_min=emb, preco_emb_med=emb, preco_emb_max=emb, confianca="media", fontes=[FONTE])


def cliente(*respostas):
    pedidos = []

    def create(model, messages, **kw):
        pedidos.append(json.loads(messages[-1]["content"]))
        conteudo = respostas[len(pedidos) - 1]
        return NS(choices=[NS(message=NS(content=conteudo))], usage=None)

    return NS(chat=NS(completions=NS(create=create))), pedidos


def test_mesmo_produto_em_outra_ordem_e_reconhecido():
    assert mesmo_produto("Tinta Suvinil Toque de Seda Branco Neve 18L", "Suvinil Toque de Seda Branco Neve tinta 18 L")
    assert not mesmo_produto("Tinta Suvinil", "Tinta Suvinil Premium 18 L")
    assert mesma_marca("Tinta Suvinil Toque de Seda 18L", "Tinta Suvinil Fosco Completo 18L")
    assert not mesma_marca("Tinta Suvinil Toque de Seda 18L", "Tinta Coral Rende Muito 18L")


def test_repetiu_pede_de_novo_dizendo_o_que_evitar():
    c, pedidos = cliente('{"produto": "Suvinil Toque de Seda Branco Neve tinta 18 L", "por_que": "x"}',
                         '{"produto": "Tinta Coral Pinta Piso fosco branco 18 L", "por_que": "outra marca"}')
    alt = sugerir_alternativa("Tinta Suvinil Toque de Seda Branco Neve 18L", "semelhante", client=c, model="m",
                              preco_atual=800.0, embalagem="18 L")
    assert alt.produto.startswith("Tinta Coral")
    assert pedidos[0]["preco_atual_por_embalagem"] == 800.0 and pedidos[0]["faixa_de_preco"].startswith("na mesma faixa")
    assert pedidos[1]["nao_sugira"] == ["Suvinil Toque de Seda Branco Neve tinta 18 L"]


def test_semelhante_da_mesma_marca_duas_vezes_desiste():
    c, _ = cliente('{"produto": "Tinta Suvinil Fosco Completo 18 L"}', '{"produto": "Tinta Suvinil Premium Fosco 18 L"}')
    with pytest.raises(AlternativaIndisponivel):
        sugerir_alternativa("Tinta Suvinil Toque de Seda Branco Neve 18L", "semelhante", client=c, model="m")


@pytest.mark.parametrize("objetivo,novo,trocou", [
    ("qualidade", 950.0, True), ("qualidade", 500.0, False),        # linha superior não pode sair mais barata
    ("semelhante", 760.0, True), ("semelhante", 300.0, False), ("semelhante", 1400.0, False),
    ("preco", 600.0, True), ("preco", 900.0, False),
])
def test_resultado_precisa_ficar_na_faixa_do_objetivo(objetivo, novo, trocou):
    alt = Alternativa("Tinta Coral Rende Muito branco 18 L", "")
    final, t = decidir(tinta("Tinta Coral Rende Muito branco 18 L", novo), tinta(), alt, objetivo, "Tinta")
    assert t is trocou
    if not trocou:
        assert final.produto_normalizado.startswith("Tinta Suvinil") and "mantive" in final.motivo


def test_mesmo_produto_devolvido_pela_pesquisa_nao_troca():
    alt = Alternativa("Suvinil Toque de Seda Branco Neve 18L tinta", "")
    final, t = decidir(tinta(alt.produto, 700.0), tinta(), alt, "preco", "Tinta")
    assert not t and "mesmo produto" in final.motivo


def test_razao_compara_por_litro_quando_a_lata_muda():
    assert razao_de_preco(tinta(emb=200.0, embalagem="3,6 L"), tinta(emb=800.0, embalagem="18 L")) == pytest.approx(1.25)
