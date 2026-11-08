"""Valores do exemplo da demo (08/11): quantidade de compra, tipo e marca do produto, kit e cache de 1 loja."""

from __future__ import annotations

import pytest

from src.calculo import calcular, e_tipo_diferente, marca_ausente, pecas_do_kit
from src.compra import conteudo_embalagem, qtd_embalagens
from src.modelos import ItemEntrada
from src.precos import Oferta, ResultadoExtracao


def of(titulo, preco=10.0, emb="unidade", loja="Loja", url=None):
    return Oferta(loja=loja, dominio=f"{loja.lower()}.com.br", url=url or f"https://{loja.lower()}.com.br/{preco}",
                  titulo=titulo, preco=preco, embalagem=emb, mesmo_produto="sim")


@pytest.mark.parametrize("produto,qtd,un,emb,n", [
    ("Tinta Suvinil Toque de Seda Branco Neve 18L", 18, "l", "lata 18 L", 1),        # era 2 (perda de 5% em cima)
    ("Argamassa Quartzolit AC-III cinza 20kg", 40, "kg", "saco 20 kg", 2),           # era 3
    ("Tinta Suvinil Toque de Seda Branco Neve 18L", 180, "m2", "lata 18 L", 2),      # da área: a perda continua
    ("Porcelanato Eliane Munari 60x60", 48, "m2", "caixa 1,8 m²", 30),
])
def test_quantidade_em_unidade_de_compra_nao_ganha_perda(produto, qtd, un, emb, n):
    assert qtd_embalagens(produto, qtd, un, conteudo_embalagem(emb))[0] == n


def test_tomada_nao_aceita_interruptor_da_mesma_linha():
    pedido = "Tomada Tramontina Liz branca 20A"
    assert e_tipo_diferente(of("Conjunto 4x2 com 1 Interruptor Simples Tramontina Liz"), pedido)
    assert not e_tipo_diferente(of("Tomada 2P+T 20A Tramontina Liz Branca"), pedido)
    assert not e_tipo_diferente(of("Tomadas 20A Liz Tramontina"), pedido)
    assert not e_tipo_diferente(of("SUVINIL TOQUE DE SEDA 18L"), "Tinta Suvinil Toque de Seda 18L")   # título sem tipo


def test_marca_de_outra_empresa_sai_e_titulo_sem_marca_fica():
    pedido = "Argamassa Quartzolit AC-III cinza 20kg"
    assert marca_ausente(of("Argamassa Votorantim AC3 Flexível 20kg"), pedido) == "votorantim"
    assert marca_ausente(of("Argamassa Cimentocola ACIII 20Kg Quartzolit"), pedido) is None
    assert marca_ausente(of("Argamassa AC-III 20kg"), pedido) is None


def test_kit_de_pecas_vira_preco_por_peca():
    assert [pecas_do_kit(t) for t in ["Kit 5 Spot Embutido Led", "Conjunto 4x2 com 1 interruptor", "Kit com 10 unidades",
                                       "Caixa 2,16 m2"]] == [5, None, 10, None]
    ext = ResultadoExtracao(ofertas=[of("Spot Stella 7W 3000K", 55.0, loja="A"), of("Spot Stella 7W 3000K", 57.0, loja="B"),
                                     of("Kit 5 Spot Stella 7W 3000K", 280.0, loja="C")])
    c = calcular(ItemEntrada(id="1", descricao="Spot Stella 7W 3000K", quantidade=4, unidade="un"), ext)
    assert c.qtd_embalagens == 4 and c.preco_emb_med == 56.0 and c.preco_emb_max == 57.0


def test_interruptor_e_votorantim_ficam_fora_da_conta():
    ext = ResultadoExtracao(ofertas=[of("Tomada 20A Tramontina Liz", 21.5, loja="A"), of("Tomada Liz 20A Tramontina", 22.9, loja="B"),
                                     of("Conjunto 1 Interruptor Tramontina Liz", 9.5, loja="C")])
    c = calcular(ItemEntrada(id="1", descricao="Tomada Tramontina Liz branca 20A", quantidade=6, unidade="un"), ext)
    assert {f.loja for f in c.fontes} == {"A", "B"} and c.descartadas == {"outro tipo de produto da mesma linha": 1}


def test_porcelanato_com_padrao_marmore_e_preco_por_m2_e_nao_por_peca():
    """Medido em 08/11: 'Porcelanato Portobello Mármore Bianco 60x60' virou '0,36 m²' por peça (regra da pedra) e
    18 m² custaram R$ 5.853. O pedido decide se é chapa/pedra; piso sem caixa no título é preço por m²."""
    from src.google_shopping import _embalagem
    pedido = "Porcelanato Portobello 60x60cm polido"
    assert _embalagem("Porcelanato Portobello Marmore Bianco 60x60cm Bold", "m2", pedido) == "m²"
    assert _embalagem("Porcelanato Eliane 60x60 caixa 1,44 m2", "m2", pedido) == "1,44 m²"
    assert _embalagem("Mdf Branco 18mm 2l Tx 275cmx183cm", "m2", "MDF branco 18mm") == "5,03 m²"   # chapa continua


def test_palavra_acentuada_depois_do_numero_nao_vira_unidade():
    assert conteudo_embalagem("Kit 2 Módulos Tomada 20A") is None   # era "2 m"
    assert conteudo_embalagem("2 metros") == conteudo_embalagem("2 m")
