"""Alternativa com várias opções (08/11): a IA sugere até 3, as 3 são pesquisadas e o preço real escolhe."""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest

from src.alternativas import Alternativa, AlternativaIndisponivel, escolher, mesmas_medidas, sugerir_alternativas
from src.modelos import Fonte, ResultadoItem

FONTE = Fonte(loja="Leroy Merlin", dominio="leroymerlin.com.br", url="https://www.leroymerlin.com.br/x", preco_embalagem=1.0)


def res(produto, preco, embalagem="unidade"):
    return ResultadoItem(item_id="1", status="definido", produto_normalizado=produto, embalagem=embalagem, qtd_embalagens=1,
                         preco_emb_min=preco, preco_emb_med=preco, preco_emb_max=preco, confianca="media", fontes=[FONTE])


def cliente(*respostas):
    pedidos = []

    def create(model, messages, **kw):
        pedidos.append(json.loads(messages[-1]["content"]))
        return NS(choices=[NS(message=NS(content=respostas[len(pedidos) - 1]))], usage=None)

    return NS(chat=NS(completions=NS(create=create))), pedidos


def test_mesmas_medidas():
    assert mesmas_medidas("Spot Stella 7W 3000K", "Spot Avant 7W 3000K redondo")
    assert not mesmas_medidas("Spot Stella 7W 3000K", "Spot Stella 10W 3000K Super LED")   # medido em 08/11
    assert mesmas_medidas("Torneira Docol Stilo bica alta", "Torneira Deca Link bica alta")


def test_ate_tres_opcoes_validas_e_a_que_muda_a_especificacao_sai():
    c, pedidos = cliente(json.dumps({"opcoes": [
        {"produto": "Spot Stella 10W 3000K", "por_que": "mais potente"},          # mudou a potência
        {"produto": "Spot Avant 7W 3000K redondo", "por_que": "outra marca"},
        {"produto": "Spot Taschibra 7W 3000K", "por_que": "outra marca"},
        {"produto": "Spot Ledvance 7W 3000K", "por_que": "outra marca"}]}))
    alts = sugerir_alternativas("Spot Stella 7W 3000K", "preco", client=c, model="m", preco_atual=55.6, embalagem="unidade")
    assert [a.produto for a in alts] == ["Spot Avant 7W 3000K redondo", "Spot Taschibra 7W 3000K", "Spot Ledvance 7W 3000K"]
    assert pedidos[0]["quantas_opcoes"] == 3 and pedidos[0]["preco_atual_por_embalagem"] == 55.6


def test_todas_repetidas_pede_de_novo_uma_vez():
    c, pedidos = cliente(json.dumps({"opcoes": [{"produto": "Spot Stella 10W 3000K"}]}),
                         json.dumps({"opcoes": [{"produto": "Spot Avant 7W 3000K"}]}))
    alts = sugerir_alternativas("Spot Stella 7W 3000K", "qualidade", client=c, model="m")
    assert [a.produto for a in alts] == ["Spot Avant 7W 3000K"] and pedidos[1]["nao_sugira"] == ["Spot Stella 10W 3000K"]


def test_sem_nenhuma_opcao_razoavel():
    c, _ = cliente('{"opcoes": []}')
    with pytest.raises(AlternativaIndisponivel):
        sugerir_alternativas("Spot Stella 7W 3000K", "preco", client=c, model="m")


ATUAL = res("Torneira Docol Stilo bica alta", 557.5)
OPCOES = [(Alternativa("Torneira Deca Belle bica alta", ""), res("Torneira Deca Belle bica alta", 1242.37)),
          (Alternativa("Torneira Lorenzetti bica alta", ""), res("Torneira Lorenzetti bica alta", 189.9)),
          (Alternativa("Torneira Fabrimar bica alta", ""), res("Torneira Fabrimar bica alta", 312.0))]


def test_menor_preco_escolhe_a_mais_barata_das_que_sairam_mais_baratas():
    """Medido em 08/11: com 1 sugestão, o Deca Belle (R$ 1.242) "mais barato" que o Docol (R$ 557) fazia o item
    voltar ao que era. Com 3, a mais barata de verdade ganha."""
    final, alt = escolher(OPCOES, ATUAL, "preco", "Torneira Docol Stilo bica alta")
    assert alt.produto == "Torneira Lorenzetti bica alta" and final.preco_emb_med == 189.9


def test_maior_qualidade_fica_com_a_primeira_da_ordem_que_custa_igual_ou_mais():
    final, alt = escolher(OPCOES, ATUAL, "qualidade", "Torneira")
    assert alt.produto == "Torneira Deca Belle bica alta"


def test_outra_marca_fica_com_a_de_preco_mais_perto():
    opcoes = [(Alternativa("A", ""), res("A", 900.0)), (Alternativa("B", ""), res("B", 540.0)), (Alternativa("C", ""), res("C", 420.0))]
    final, alt = escolher(opcoes, ATUAL, "semelhante", "Torneira")
    assert alt.produto == "B"


def test_nenhuma_serve_mantem_o_anterior_e_explica():
    opcoes = [(Alternativa("Torneira Deca Belle bica alta", ""), res("Torneira Deca Belle bica alta", 1242.37))]
    final, alt = escolher(opcoes, ATUAL, "preco", "Torneira")
    assert alt is None and final.produto_normalizado == ATUAL.produto_normalizado
    assert "nenhuma saiu mais barata" in final.motivo and "Deca Belle" in final.motivo



def test_menor_preco_barato_demais_e_qualidade_cara_demais_ficam_de_fora():
    """Medido em 08/11: torneira Tigre de R$ 11,83 como "menor preço" de uma Docol de R$ 557; spot de R$ 237 como
    "maior qualidade" de um de R$ 55,60."""
    opcoes = [(Alternativa("Torneira Tigre Pratika bica alta", ""), res("Torneira Tigre Pratika bica alta", 11.83)),
              (Alternativa("Torneira Lorenzetti Flatt bica alta", ""), res("Torneira Lorenzetti Flatt bica alta", 109.02))]
    final, alt = escolher(opcoes, ATUAL, "preco", "Torneira")
    assert alt.produto == "Torneira Lorenzetti Flatt bica alta"
    spot = res("Spot Stella 7W 3000K", 55.6)
    opcoes = [(Alternativa("Spot Tramontina 7W 3000K alumínio", ""), res("Spot Tramontina 7W 3000K alumínio", 237.0)),
              (Alternativa("Spot Philips 7W 3000K", ""), res("Spot Philips 7W 3000K", 64.9))]
    final, alt = escolher(opcoes, spot, "qualidade", "Spot")
    assert alt.produto == "Spot Philips 7W 3000K"
