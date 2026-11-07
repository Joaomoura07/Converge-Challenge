"""Etapa 2 — escolha de UMA imagem por produto (regra fixa, sem variantes de cor erradas)."""

from __future__ import annotations

import asyncio

import pytest

from src.busca import ImagemWeb as I, buscar, escolher_imagem, montar_consulta, nota_imagem
from src.modelos import ItemEntrada

LORENZETTI = [
    I("https://telhanorte.vtexassets.com/arquivos/ids/1282636-290-290",
      "The Lorenzetti Acqua Duo Ultra 220V electronic shower features a sleek copper-colored rectangular panel"),
    I("https://cdn.leroymerlin.com.br/products/chuveiro_lorenzetti_acqua_duo_ultra_eletronico_preto_220v.jpg",
      "The Lorenzetti Acqua Duo Ultra 220V electronic shower features a black and silver design"),
    I("https://telhanorte.vtexassets.com/arquivos/ids/1282635-290-290",
      "The Lorenzetti Acqua Duo Ultra 220V electronic shower features a rose gold exterior"),
]


def test_escolhe_a_cor_pedida():
    assert "preto" in escolher_imagem(LORENZETTI, "Ducha Lorenzetti Acqua Duo Ultra 220 V preta")


def test_cor_errada_perde_para_cor_certa():
    cobre, preto = LORENZETTI[0], LORENZETTI[1]
    produto = "Ducha Lorenzetti Acqua Duo Ultra preta"
    assert nota_imagem(preto, produto) > nota_imagem(cobre, produto)


def test_medida_errada_perde_para_medida_certa():
    """Caso real da avaliação: pediu cuba 56x34 e a escolhida era de uma 69x49."""
    produto = "Cuba de embutir inox Tramontina Morgana 56x34 cm"
    errada = I("https://cdn.leroymerlin.com.br/products/cuba_inox_69x49_mor_60fx_undermount_tramontina_600x600.jpg",
               "A stainless steel kitchen sink with faucet installed in a countertop")
    certa = I("https://cdn.leroymerlin.com.br/products/cuba_inox_morgana_56x34_tramontina.jpg",
              "A stainless steel Tramontina Morgana sink, 56x34 cm, displayed on white background")
    assert escolher_imagem([errada, certa], produto) == certa.url
    assert escolher_imagem([errada], produto) is None, "só a de medida errada → melhor não mostrar (hachura)"


def test_url_manda_quando_descricao_do_tavily_alucina_a_medida():
    """Caso real: o Tavily descreveu a foto de uma cuba 69x49 como '56x34' (ecoando a busca)."""
    produto = "Cuba de embutir inox Tramontina Morgana 56x34 cm"
    alucinada = I("https://cdn.leroymerlin.com.br/products/cuba_inox_69x49_mor_60fx_undermount_tramontina_600x600.jpg",
                  "A sleek, stainless steel Tramontina Morgana undermount sink ... showcasing its 56x34 cm dimensions.")
    generica = I("https://http2.mlstatic.com/D_NQ_NP_982862-MLB91939444812_092025-O.webp",
                 "A Tramontina Morgana stainless steel sink 56x34 cm displayed on white background")
    assert nota_imagem(alucinada, produto) < nota_imagem(generica, produto)
    assert escolher_imagem([alucinada], produto) is None


def test_tamanho_de_miniatura_nao_conta_como_medida():
    from src.busca import _medidas_em
    assert _medidas_em("https://a-static.mlcdn.com.br/420x420/chuveiro.jpg") == set()
    assert _medidas_em("Porcelanato 60X60 e chapa 1200 x 2400") == {(60, 60), (1200, 2400)}


def test_foto_do_produto_ganha_de_foto_de_ambiente():
    produto = "Porcelanato Eliane Munari Cimento acetinado 60x60"
    peca = I("https://telhanorte.vtexassets.com/arquivos/ids/337874/Porcelanato-Munari-Cimento-acetinado.jpg",
             "Two square tiles of Porcelanato Eliane Munari Cimento acetinado 60x60 are displayed")
    sala = I("https://tumelerosaintgobain.vtexassets.com/arquivos/ids/222722-800-800",
             "A modern living room features Porcelanato Eliane Munari Cimento acetinado 60x60 flooring")
    assert escolher_imagem([sala, peca], produto) == peca.url


@pytest.mark.parametrize("url", ["https://i.ytimg.com/vi/x/maxresdefault.jpg", "https://loja.com.br/logo-loja.png",
                                 "https://cdn.leroymerlin.com.br/banner-black-friday.jpg", "https://x.com.br/selo.svg"])
def test_descarta_youtube_logo_banner_svg(url):
    assert nota_imagem(I(url, "Porcelanato Eliane Munari"), "Porcelanato Eliane Munari") < 0


def test_sem_imagem_boa_devolve_none_para_tela_usar_hachura():
    assert escolher_imagem([I("https://x.com/foto.jpg", "a cat")], "Cuba Tramontina Morgana") is None
    assert escolher_imagem([], "qualquer") is None


def test_mesma_entrada_sempre_mesma_escolha_mesmo_em_outra_ordem():
    produto = "Ducha Lorenzetti Acqua Duo Ultra 220 V"
    a = escolher_imagem(LORENZETTI, produto)
    assert all(escolher_imagem(ordem, produto) == a for ordem in (LORENZETTI[::-1], LORENZETTI[1:] + LORENZETTI[:1]))


def test_pula_imagem_que_nao_carrega():
    """Caso real: a URL do Magazine Luiza devolvia uma página HTML em vez da imagem."""
    from src.busca import escolher_imagem_verificada
    produto = "Ducha Lorenzetti Acqua Duo Ultra 220 V preta"
    melhor, segunda = LORENZETTI[1].url, None

    async def checar(url):
        return url != melhor  # a melhor "não carrega"

    escolhida = asyncio.run(escolher_imagem_verificada(LORENZETTI, produto, checar=checar))
    assert escolhida and escolhida != melhor


def test_nenhuma_carrega_devolve_none():
    from src.busca import escolher_imagem_verificada

    async def nunca(url): return False
    assert asyncio.run(escolher_imagem_verificada(LORENZETTI, "Lorenzetti Acqua Duo Ultra", checar=nunca)) is None


@pytest.mark.real
def test_etapa2_detector_reconhece_html_disfarcado_de_imagem():
    from src.busca import imagem_carrega
    assert not asyncio.run(imagem_carrega("https://www.leroymerlin.com.br/"))   # página HTML
    assert not asyncio.run(imagem_carrega("https://exemplo.invalido/x.jpg"))     # nem existe


@pytest.mark.real
@pytest.mark.parametrize("descricao", ["Ducha eletrônica Lorenzetti Acqua Duo Ultra 220 V",
                                       "Porcelanato Eliane Munari Cimento acetinado 60x60"])
def test_etapa2_imagem_real_escolhe_uma(descricao):
    r = asyncio.run(buscar(montar_consulta(ItemEntrada(id="1", descricao=descricao))))
    assert r.imagem, f"nenhuma imagem passou da nota mínima: {[(i.url[:60], round(nota_imagem(i, descricao), 1)) for i in r.imagens]}"
    assert any(i.url == r.imagem for i in r.imagens)
    from src.busca import imagem_carrega
    assert asyncio.run(imagem_carrega(r.imagem)), f"a imagem escolhida não carrega: {r.imagem}"
