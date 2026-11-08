"""Conferências da oferta antes da conta (sem IA). Casos REAIS do teste como jurado no site publicado em 07/11:
selador com o código do produto lido como preço, tinta de 21,5 kg rotulada "lata 18 L", alicate no lugar do
espaçador nivelador e interruptor com fonte num edital de leilão da Justiça Federal."""

from __future__ import annotations

import pytest

from src.busca import _filtra_aberto, fonte_nao_e_loja
from src.calculo import (calcular, e_outro_tipo_de_produto, embalagem_confere_com_titulo, motivo_descarte,
                         preco_e_codigo_do_titulo)
from src.modelos import ItemEntrada
from src.precos import Oferta, ResultadoExtracao, preco_no_texto


def of(loja, preco, emb, titulo, url=None, dominio=None, igual="sim"):
    dominio = dominio or f"{loja.lower().replace(' ', '')}.com.br"
    return Oferta(loja=loja, dominio=dominio, url=url or f"https://www.{dominio}/{preco}", titulo=titulo,
                  preco=preco, embalagem=emb, mesmo_produto=igual)


# Ofertas exatamente como estão no cache_precos do Supabase (07/11, chave "coral selador")
SELADOR = [
    of("Ferreira Costa", 1470, "galão 3,6 L", "Selador Acrílico Interno e Externo 3,6L 1470 - Coral - Ferreira Costa"),
    of("Canalconstrucao", 239.9, "lata 18 L", "Selador Acrílico Interno e Externo 18l - Coral"),
    of("Armazemcoral", 69.9, "galão 3,6 L", "Selador Acrilico Coral 5202615 3,6l"),
]


# ---------------------------------------------------------------- preço que é código
def test_codigo_do_titulo_nao_e_preco():
    assert preco_e_codigo_do_titulo(SELADOR[0])
    assert not preco_e_codigo_do_titulo(SELADOR[1])          # 239,90 tem centavos
    assert not preco_e_codigo_do_titulo(SELADOR[2])


@pytest.mark.parametrize("preco,titulo,codigo", [
    (189.0, "Tinta Suvinil Toque De Seda 3,6L", False),      # 189 não está no título
    (189.0, "Tinta Coral 3,6L por R$ 189", False),            # com R$ antes é preço
    (1470.0, "Selador 3,6L cód. 1.470", True),               # milhar com ponto também é código
    (18.0, "Tinta 18L", True),                                # preço igual à medida: leitura errada
    (10.0, "10 Metros Fita Led Smd Dimerizável 7500 Lúmens", True),   # caso real do cache
    (2090.0, "Fita crepe 3M 2090 azul", True),
])
def test_preco_redondo_solto_no_titulo(preco, titulo, codigo):
    assert preco_e_codigo_do_titulo(of("X", preco, "unidade", titulo)) is codigo


def test_trava_de_preco_exige_rs_para_numero_redondo():
    """A trava anti-alucinação aceitava '1470' só porque estava escrito no título."""
    assert not preco_no_texto(1470.0, "Selador Acrílico Interno e Externo 3,6L 1470 - Coral — Ferreira Costa")
    assert preco_no_texto(1470.0, "Selador 3,6L 1470 — R$ 1.470,00 à vista")
    assert preco_no_texto(1470.0, "Selador — R$ 1.470 no Pix")
    assert preco_no_texto(189.0, "R$ 189 em 12x R$ 15,75")


def test_selador_real_nao_vira_galao_de_1470():
    """Antes: 5 galões de 3,6 L a R$ 864–1.470 (o 1470 falso ainda fazia a lata de 18 L virar preço por litro)."""
    item = ItemEntrada(id="1", descricao="Selador Coral", quantidade=180, unidade="m2")
    c = calcular(item, ResultadoExtracao(ofertas=SELADOR))
    assert c.descartadas.get("preço é código do título") == 1
    assert c.embalagem == "lata 18 L"                          # 180 m² / 11 m²/L ≈ 17 L: uma lata de 18 L
    assert (c.preco_emb_min, c.preco_emb_max) == (239.9, 349.5)  # o galão de R$ 69,90 convertido para 18 L
    assert {f.loja for f in c.fontes} == {"Canalconstrucao", "Armazemcoral"}
    total = c.qtd_embalagens * c.preco_emb_med
    assert total < 400                                         # 180 m² de selador: era ~R$ 5,8 mil


# ---------------------------------------------------------------- embalagem do título
@pytest.mark.parametrize("emb,titulo,confere", [
    ("lata 18 L", "Tinta Parede E Teto Rendimento Total Decor Colors 21,5kg Cor Poseidon", False),  # caso real
    ("latão 18 L", "Tinta Acrílica Branco Neve Acetinado Premium 3,6L Toque de Seda Suvinil", False),
    ("galão 3,6 L", "Selador Acrílico Interno e Externo 3,6L 1470 - Coral", True),
    ("kit 2 latas 18 L", "Kit 2 latas Suvinil Toque de Seda 18L", True),
    ("m²", "Porcelanato Eliane Munari 60x60 caixa 1,80m²", True),       # preço por m² de piso em caixa
    ("unidade", "Caixa d'água Fortlev 1000L", True),                    # un × litros não se compara
    ("unidade", "Espaçador Nivelador Slim 1,0mm Cortag 100 Pçs", False),  # 1 × 100 peças
    ("100 unidades", "Espaçador Nivelador 1,5 mm - Cortag 100 un", True),
    ("10 Metros", "Fita LED Ledvance 5m 12V", False),
    ("galão", "Tinta Suvinil 3,6L", True),                               # "galão" sozinho não diz quanto
    (None, "Tinta Suvinil 18L", True),
])
def test_embalagem_lida_bate_com_o_titulo(emb, titulo, confere):
    assert embalagem_confere_com_titulo(of("X", 100.0, emb, titulo)) is confere


# ---------------------------------------------------------------- ferramenta no lugar do material
def test_alicate_nao_e_o_espacador_nivelador():
    alicate = of("Sertão", 82.6, "unidade", "Alicate Nivelador de Piso CORTAGSertão")
    assert e_outro_tipo_de_produto(alicate, "Nivelador Cortag")
    assert not e_outro_tipo_de_produto(alicate, "Alicate nivelador Cortag")       # se pediu o alicate, vale
    assert not e_outro_tipo_de_produto(of("T", 15.1, "100 peças", "Espaçador Nivelador Slim 1,0mm Cortag 100 Pçs"),
                                       "Nivelador Cortag")


# ---------------------------------------------------------------- fonte que não é loja
def test_edital_da_justica_federal_nao_e_loja():
    url = ("https://www.jfpe.jus.br/JFPE/Leiloes%20%20Petrolina/Leiloes__Petrolina/2021/02/25/"
           "20210225Edital_de_Leilao_e_Intimacao_n_EDL00170000040.PDF")
    assert fonte_nao_e_loja("jfpe.jus.br", url)
    assert fonte_nao_e_loja("loja.com.br", "https://loja.com.br/tabela-precos.pdf")
    assert fonte_nao_e_loja("compras.recife.pe.gov.br", "https://compras.recife.pe.gov.br/x")
    assert not fonte_nao_e_loja("sertao.com.br", "https://www.sertao.com.br/lixa-150/p")
    oferta = of("Jfpe", 5.5, "unidade", "Edital de Leilão", url=url, dominio="jfpe.jus.br")
    assert motivo_descarte(oferta, "Interruptor Pial Plus+") == "fonte não é loja (órgão público ou arquivo)"


def test_busca_aberta_ignora_edital_e_pdf():
    brutos = [("Edital de Leilão", "https://www.jfpe.jus.br/edital.PDF", "Interruptor R$ 5,50"),
              ("Tabela", "https://lojax.com.br/precos.pdf", "Interruptor R$ 9,90"),
              ("Interruptor Pial Plus", "https://lojay.com.br/interruptor-pial/p", "R$ 19,90")]
    assert [r.dominio for r in _filtra_aberto(brutos, 5, None)] == ["lojay.com.br"]


def test_descartes_aparecem_no_calculo_e_sobra_o_que_presta():
    item = ItemEntrada(id="1", descricao="Tinta Decor Colors vermelho cardinal", quantidade=12, unidade="m2")
    ext = ResultadoExtracao(ofertas=[
        of("Mercado Livre", 513.9, "lata 18 L", "Tinta Parede E Teto Rendimento Total Decor Colors 21,5kg Cor ..."),
        of("Telhanorte", 489.9, "lata 18 L", "Tinta Decor Colors Vermelho Cardinal 18L")])
    c = calcular(item, ext)
    assert c.descartadas == {"embalagem não confere com o título": 1}
    assert [f.loja for f in c.fontes] == ["Telhanorte"]


# ---------------------------------------------------------------- listagem da loja e bases de licitação (07/11 noite)
def test_listagem_da_leroy_vale_so_para_estimativa():
    from src.busca import eh_pagina_de_listagem
    lst = "https://www.leroymerlin.com.br/pedra-britada/peso-do-produto-na-embalagem/1400_Kg_a_1410_Kg"
    prod = "https://www.leroymerlin.com.br/rodape-de-poliestireno-457-branco-240x10cm-santa-luzia_87635415"
    assert eh_pagina_de_listagem("leroymerlin.com.br", lst) and not eh_pagina_de_listagem("leroymerlin.com.br", prod)
    assert not eh_pagina_de_listagem("telhanorte.com.br", "https://www.telhanorte.com.br/qualquer")
    brita = of("Leroy Merlin", 1450.0, "1 m³", "Pedra Britada | Leroy Merlin", url=lst, dominio="leroymerlin.com.br")
    exato = calcular(ItemEntrada(id="1", descricao="Brita 1", quantidade=14, unidade="m3"), ResultadoExtracao(ofertas=[brita]))
    assert not exato.tem_preco and exato.descartadas == {"página de listagem (vale só para estimativa)": 1}
    estim = calcular(ItemEntrada(id="1", descricao="Brita 1", quantidade=14, unidade="m3"),
                     ResultadoExtracao(ofertas=[brita]), generico=True)
    assert estim.tem_preco and estim.estimativa


def test_base_de_preco_de_licitacao_nao_e_loja():
    assert fonte_nao_e_loja("bancodeprecos.com.br", "https://www.bancodeprecos.com.br/CertificadoAutenticidade?to=1")
    assert fonte_nao_e_loja("buscadorsinapi.com.br", "https://buscadorsinapi.com.br/x")
    assert fonte_nao_e_loja("static.tre-al.jus.br", "https://static.tre-al.jus.br/cotacao")


# ---------------------------------------------------------------- preço do anúncio e loja perto da obra (07/11 noite)
def test_fonte_guarda_o_preco_e_a_embalagem_do_anuncio():
    """No site, o galão de 3,6 L a R$ 69,90 aparecia como R$ 349,50 (equivalente em 18 L) e o link 'não batia'."""
    c = calcular(ItemEntrada(id="1", descricao="Selador Coral", quantidade=180, unidade="m2"),
                 ResultadoExtracao(ofertas=SELADOR[1:]))
    armazem = next(f for f in c.fontes if f.loja == "Armazemcoral")
    assert (armazem.preco_anunciado, armazem.embalagem_anunciada) == (69.9, "galão 3,6 L")
    assert armazem.preco_embalagem == 349.5 and armazem.embalagem == "lata 18 L"   # a conta continua comparável


def test_loja_com_unidade_no_estado_da_obra_vem_primeiro_e_marcada():
    from src.busca import Local, na_regiao, perto_da_obra
    recife = Local("Recife", "PE")
    assert perto_da_obra("ferreiracosta.com", recife) and not perto_da_obra("ferreiracosta.com", Local("Curitiba", "PR"))
    assert not perto_da_obra("leroymerlin.com.br", recife) and not perto_da_obra("ferreiracosta.com", None)
    ofertas = [of("Telhanorte", 239.9, "lata 18 L", "Selador 18L", dominio="telhanorte.com.br"),
               of("Ferreira Costa", 259.9, "lata 18 L", "Selador 18L", dominio="ferreiracosta.com")]
    item = ItemEntrada(id="1", descricao="Selador Coral", quantidade=180, unidade="m2")
    with na_regiao(recife):
        c = calcular(item, ResultadoExtracao(ofertas=ofertas))
    assert [f.loja for f in c.fontes] == ["Ferreira Costa", "Telhanorte"] and c.fontes[0].perto_da_obra
    sem_local = calcular(item, ResultadoExtracao(ofertas=ofertas))
    assert not any(f.perto_da_obra for f in sem_local.fontes)


def test_busca_fixa_poe_a_loja_da_regiao_antes():
    from src.busca import Local, _filtra, na_regiao
    brutos = [("Selador 18L", "https://www.telhanorte.com.br/selador/p", "R$ 239,90"),
              ("Selador 18L", "https://www.ferreiracosta.com/produto/1/selador", "R$ 259,90")]
    with na_regiao(Local("Recife", "PE")):
        assert [r.loja for r in _filtra(brutos, 5)] == ["Ferreira Costa", "Telhanorte"]
    assert [r.loja for r in _filtra(brutos, 5)] == ["Telhanorte", "Ferreira Costa"]
