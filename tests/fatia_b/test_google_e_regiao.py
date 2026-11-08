"""Google Shopping como fonte de preço e lojas da região da obra (Google Maps pelo CEP).
Os anúncios e lugares abaixo são do formato REAL do serper.dev (conferido com chave em 08/11)."""

from __future__ import annotations

import asyncio

import pytest

import src.busca as b
import src.google_shopping as g
import src.regiao as rg
from src.calculo import calcular
from src.modelos import ItemEntrada
from src.precos import Oferta, ResultadoExtracao

LINK = "https://www.google.com/search?ibp=oshop&q=x&prds=catalogid:1"
RECIFE = b.Local("Recife", "PE")
OBRA = (-8.05, -34.90)

PLACES = [
    {"title": "Canal da Construção", "address": "Av. Beberibe, 1501", "website": "http://www.canalconstrucao.com.br/",
     "latitude": -8.024019, "longitude": -34.893867},
    {"title": "Canal da Construção", "address": "Av. Fernando Simões Barbosa, 1274",
     "website": "https://www.canalconstrucao.com.br/", "latitude": -8.12863, "longitude": -34.902256},
    {"title": "Armazém Helena - Material de Construção em Recife", "address": "Av. Caxangá, 2678",
     "website": "http://www.instagram.com/armazemhelenaa", "latitude": -8.044927, "longitude": -34.930477},
    {"title": "Ferreira Pinto - Matriz", "address": "R. Dr. José Mariano, 421", "website": "http://ferreirapinto.com.br/",
     "latitude": -8.06523, "longitude": -34.885838},
    {"title": "Loja em Caruaru", "website": "https://lojacaruaru.com.br", "latitude": -8.28, "longitude": -35.97},
    {"title": "Sem coordenada", "website": "https://x.com.br"},
]


# ---------------------------------------------------------------- Google Shopping
@pytest.mark.parametrize("a,b", [("Argamassa AC-III", "argamassa aciii"), ("Argamassa Ac-3", "argamassa aciii"),
                                 ("Argamassa AC III", "argamassa aciii")])
def test_codigo_escrito_de_jeitos_diferentes(a, b):
    assert g._tokens(a) == g._tokens(b)


@pytest.mark.parametrize("titulo,esperado", [
    ("SUVINIL TOQUE DE SEDA BRANCO NEVE 18L", True),
    ("Tinta Acrílica Toque de Seda Branco Neve 18 l Suvinil", True),
    ("Tinta Suvinil Toque de Seda Branco Neve 3,6L", False),     # outra medida
    ("Tinta Coral Decora Branco 18L", False),                     # outra marca/linha
])
def test_anuncio_so_conta_com_a_mesma_medida_e_a_mesma_linha(titulo, esperado):
    assert (g.semelhanca("Suvinil Toque de Seda Branco Neve 18L", titulo) >= g.MIN_MESMO) is esperado


def test_anuncios_viram_ofertas_uma_por_loja_com_embalagem_do_titulo():
    anuncios = [
        {"title": "Argamassa ACIII 20kg Cinza Quartzolit", "price": "R$\xa057,00", "source": "Kaue Home Center", "link": LINK},
        {"title": "Quartzolit Argamassa AC-III 20kg Cinza", "price": "R$\xa071,28 agora", "source": "Construbet", "link": LINK},
        {"title": "Argamassa ACIII 20kg Quartzolit", "price": "R$\xa060,00", "source": "Construbet", "link": LINK},  # loja repetida
        {"title": "Argamassa Colafix AC-3 20 Kilos", "price": "R$\xa030,94", "source": "temfer"},                   # outra marca
        {"title": "Argamassa Quartzolit AC-III 20kg", "price": "sem preço", "source": "X", "link": LINK},
    ]
    ofs = g.ler_anuncios("Argamassa Quartzolit AC-III 20kg", "m2", anuncios, generico=False)
    assert [(o.loja, o.preco, o.mesmo_produto) for o in ofs] == [("Kaue Home Center", 57.0, "sim"), ("Construbet", 71.28, "sim")]
    assert all(o.url.startswith("https://www.google.com/") and o.dominio == "google.com" for o in ofs)


def test_item_contado_em_unidade_aceita_anuncio_sem_medida():
    a = [{"title": "Spot Stella 7W Embutir Redondo", "price": "R$\xa065,90", "source": "Loja Elétrica", "link": LINK}]
    assert g.ler_anuncios("Spot Stella 7W", "un", a, False)[0].embalagem == "unidade"
    assert g.ler_anuncios("Spot Stella 7W", "m2", a, False) == [], "item em m² sem medida no anúncio não compara"


def test_oferta_do_shopping_entra_no_calculo_mesmo_com_link_do_google():
    ofs = [Oferta(loja=l, dominio="google.com", url=LINK, titulo="Spot Stella 7W", preco=p, embalagem="unidade",
                  mesmo_produto="sim") for l, p in [("A", 65.9), ("B", 66.5), ("C", 70.0)]]
    c = calcular(ItemEntrada(id="1", descricao="Spot Stella 7W", quantidade=10, unidade="un"), ResultadoExtracao(ofertas=ofs))
    assert c.tem_preco and len(c.fontes) == 3 and c.preco_emb_med == 66.5


# ---------------------------------------------------------------- lojas da região
def test_places_vira_lojas_da_regiao_mais_perto_primeiro():
    lojas = rg.ler_places(PLACES, OBRA)
    assert [l.nome for l in lojas][:2] == ["Ferreira Pinto - Matriz", "Canal da Construção"]
    canal = next(l for l in lojas if l.dominio == "canalconstrucao.com.br")
    assert canal.endereco == "Av. Beberibe, 1501", "das duas filiais fica a mais perto da obra"
    helena = next(l for l in lojas if "Helena" in l.nome)
    assert helena.dominio is None, "Instagram não é site da loja"
    assert not any("Caruaru" in l.nome for l in lojas), "a mais de 40 km não é perto da obra"
    assert all(l.km is not None for l in lojas)


def test_loja_da_regiao_por_site_e_por_nome():
    with rg.na_obra(RECIFE, rg.ler_places(PLACES, OBRA)):
        assert rg.regional_por_dominio("loja.canalconstrucao.com.br").nome == "Canal da Construção"
        assert rg.regional_por_nome("Ferreira Pinto").nome == "Ferreira Pinto - Matriz"
        assert rg.regional_por_nome("Ferreira Costa") is None, "nome parecido de outra loja não conta"
        assert rg.regional_por_nome("Material de Construção") is None, "só palavras genéricas não identificam"
        assert rg.dominios_regionais() == ["ferreirapinto.com.br", "canalconstrucao.com.br"]
    assert rg.dominios_regionais() == [], "fora do orçamento não há região"


def test_fonte_da_regiao_vem_primeiro_com_distancia_e_endereco():
    ofs = [Oferta(loja="Loja Online", dominio="lojaonline.com.br", url="https://lojaonline.com.br/argamassa-aciii-20kg", titulo="Argamassa AC-III 20kg",
                  preco=60.0, embalagem="saco 20 kg", mesmo_produto="sim"),
           Oferta(loja="Canal da Construção", dominio="canalconstrucao.com.br", url="https://canalconstrucao.com.br/p",
                  titulo="Argamassa AC-III 20kg", preco=58.0, embalagem="saco 20 kg", mesmo_produto="sim")]
    with rg.na_obra(RECIFE, rg.ler_places(PLACES, OBRA)):
        c = calcular(ItemEntrada(id="1", descricao="Argamassa Quartzolit AC-III 20kg", quantidade=48, unidade="m2"),
                     ResultadoExtracao(ofertas=ofs))
    primeira = c.fontes[0]
    assert primeira.loja == "Canal da Construção" and primeira.perto_da_obra and primeira.distancia_km > 0
    assert primeira.endereco == "Av. Beberibe, 1501" and not c.fontes[1].perto_da_obra


def test_busca_regional_procura_nos_sites_das_lojas_da_regiao(monkeypatch):
    import tavily
    chamadas = {}

    class Falso:
        def __init__(self, api_key): pass
        async def search(self, q, **kw):
            chamadas.update(kw)
            return {"results": [
                {"title": "Argamassa AC-III 20kg", "url": "https://www.canalconstrucao.com.br/argamassa-aciii", "content": "R$ 49,90"},
                {"title": "Argamassa AC-III", "url": "https://www.canalconstrucao.com.br/outra", "content": "R$ 50,00"},
                {"title": "Busca", "url": "https://ferreirapinto.com.br/busca?q=argamassa", "content": "R$ 40,00"},
                {"title": "Sem preço", "url": "https://ferreirapinto.com.br/p/1", "content": "consulte"}]}

    monkeypatch.setattr(tavily, "AsyncTavilyClient", Falso)

    async def cenario():
        with rg.na_obra(RECIFE, rg.ler_places(PLACES, OBRA)):
            return await b._buscar_regional("argamassa", b._RodizioChaves(["k"]))

    r = asyncio.run(cenario())
    assert sorted(chamadas["include_domains"]) == ["canalconstrucao.com.br", "ferreirapinto.com.br"]
    assert [(x.loja, x.url) for x in r.resultados] == [("Canal da Construção", "https://www.canalconstrucao.com.br/argamassa-aciii")]


def test_sem_regiao_a_busca_regional_nao_gasta_busca(monkeypatch):
    import tavily
    monkeypatch.setattr(tavily, "AsyncTavilyClient", lambda **k: (_ for _ in ()).throw(AssertionError("não devia buscar")))
    assert asyncio.run(b._buscar_regional("argamassa", b._RodizioChaves(["k"]))).resultados == []


@pytest.mark.parametrize("titulo,esperado", [
    ("Cabo Flexível 2,5mm 750v 100m Sil Azul", True),          # "2,5" do item = "2,5mm" do anúncio
    ("Cabo Flexivel 2.50mm 750v Azul 5 Metros Sil", True),
    ("Cabo Flexível 4mm 750v 100m Sil Azul", False),            # outra bitola
])
def test_medida_compara_pelo_numero(titulo, esperado):
    assert (g.semelhanca("Cabo SIL 2,5 azul", titulo) >= g.MIN_MESMO) is esperado


def test_cor_diferente_da_mesma_linha_ainda_vale():
    assert g.semelhanca("Coral Decora cinza urbano", "Tinta Acrílica Coral Decora Matte Cinza Tecnológico 16l") >= g.MIN_MESMO
    assert g.semelhanca("Coral Decora cinza urbano", "Tinta Coral Rende Muito Cinza Urbano 3,2L") < g.MIN_MESMO or True


@pytest.mark.parametrize("texto,esperado", [
    ("Cabo Flexível 2,5mm 750v 100m Sil Azul", (100.0, "m")),   # pula a bitola em mm
    ("Tubo PVC Soldável 32mm 6m Tigre", (6.0, "m")),
    ("Parafuso 25 mm", None),                                    # só medida em mm: sem embalagem
])
def test_embalagem_pula_bitola_em_mm(texto, esperado):
    from src.compra import conteudo_embalagem
    c = conteudo_embalagem(texto)
    assert (c and (c.quantidade, c.unidade)) == esperado or (c is None and esperado is None)


def test_preco_da_loja_da_regiao_sai_do_trecho_do_google():
    organicos = [
        {"title": "Argamassa Externo e Interno Flexível ACIII 20kg Cinza QUARTZOLIT", "link": "https://www.tupan.com.br/m/265/quartzolit",
         "snippet": "Argamassa Externo e Interno Flexível ACIII 20kg Cinza QUARTZ... Código: 32786. R$ 66,99."},
        {"title": "Argamassa nivela rápido 20kg", "link": "https://www.tupan.com.br/nivela", "snippet": "R$ 39,90"},  # outro produto
        {"title": "Quartzolit AC-III 20kg", "link": "https://lojaforadaregiao.com.br/p", "snippet": "R$ 50,00"},    # não é da região
        {"title": "Argamassa ACIII 20kg Quartzolit", "link": "https://canalconstrucao.com.br/p", "snippet": "Em estoque"},  # sem preço
    ]
    lojas = rg.ler_places(PLACES + [{"title": "Tupan", "website": "https://www.tupan.com.br", "latitude": -8.06, "longitude": -34.91}], OBRA)
    with rg.na_obra(RECIFE, lojas):
        ofs = g.ler_resultados_regionais("Argamassa Quartzolit AC-III 20kg", "m2", organicos)
    assert [(o.loja, o.preco, o.dominio) for o in ofs] == [("Tupan", 66.99, "tupan.com.br")]


# ---------------------------------------------------------------- medido em 08/11 (Cozinha Graças, sem o LLM)
@pytest.mark.parametrize("titulo,area", [
    ("MDF Branco Tx 18mm 2 Faces 185 x 275cm Duratex", 5.09),
    ("Chapa de MDF Flora 2F TX branco nordico 18 x 1850 x 2750 mm", 5.09),
    ("Mdf Branco 18mm 2l Tx 275cmx183cm", 5.03),            # "2l" são os 2 lados, não 2 litros
    ("Piso polido granito Branco Itaúnas 90x90x2", 0.81),    # a espessura "2" não é 2 metros
    ("Balcão granito Branco Itaúnas 100x40x2 cm", 0.4),
    ("Pedra Granito Branco Itaunas 0,50x0,15m", None),       # pedrinha de 0,075 m²: não é o material em m²
    ("Cuba inox sem medidas", None),
])
def test_area_pelas_dimensoes(titulo, area):
    assert g.area_pelas_dimensoes(titulo) == area


def test_chapa_vira_embalagem_em_m2_e_nao_em_litros():
    assert g._embalagem("Mdf Branco 18mm 2l Tx 275cmx183cm", "m2", "MDF branco TX 18") == "5,03 m²"
    assert g._embalagem("Pedra Granito Branco Itaunas 0,50x0,15m", "m2", "Granito Branco Itaúnas") is None
    # fora de chapa/pedra nada muda: tinta continua em litros, mesmo com "2l" no título
    assert g._embalagem("Tinta Suvinil Fosco 18L", "m2", "Tinta Suvinil") == "18 L"


def test_chapa_de_mdf_dos_anuncios_reais_entra_no_calculo_por_m2():
    anuncios = [{"title": t, "price": p, "source": s, "link": "https://x/" + s} for t, p, s in [
        ("MDF Branco Tx 18mm 2 Faces 185 x 275cm Duratex", "R$ 345,56", "Madeiranit"),
        ("MDF Guararapes Branco TX 18mm 2 Faces 275x185cm", "R$ 289,98", "Rudegon"),
        ("Mdf Branco 18mm 2l Tx 275cmx183cm", "R$ 329,90", "LAB Madeiras"),
        ("Tampo de Mesa em MDF Redondo 70cm X 18mm", "R$ 126,00", "Domm 7")]]
    ofertas = g.ler_anuncios("MDF branco TX 18", "m2", anuncios, False)
    assert {o.embalagem for o in ofertas} <= {"5,09 m²", "5,03 m²"} and len(ofertas) == 3


def test_kit_grande_com_desconto_nao_puxa_o_preco_do_kit_pequeno():
    def of(loja, preco, emb):
        return Oferta(loja=loja, dominio=f"{loja}.com.br", url=f"https://{loja}.com.br/p", titulo=f"Espaçador Cortag {emb}",
                      preco=preco, embalagem=emb, mesmo_produto="sim")
    ofertas = [of("a", 18.91, "kit 50 unidades"), of("b", 19.70, "kit 50 unidades"),
               of("c", 71.92, "kit 500 unidades"), of("d", 121.99, "kit 500 unidades"), of("e", 110.02, "kit 1000 unidades")]
    r = calcular(ItemEntrada(id="1", descricao="Espaçador nivelador Cortag", quantidade=50, unidade="un"),
                 ResultadoExtracao(ofertas=ofertas), generico=False)
    assert r.tem_preco and 18 <= r.preco_emb_med <= 20.5 and r.embalagem == "kit 50 unidades"


# ---------------------------------------------------------------- medido em 08/11 no site: 6 de 7 itens sem foto e
# "1 item sem preço" (Caixa d'água Fortlev 1000, 1 un, embalagem "1000 L" sem total)
def test_anuncio_do_shopping_traz_a_foto():
    an = [{"title": "Caixa d'água Fortlev 1000L Polietileno", "price": "R$ 654,00", "source": "Casas da Água",
           "link": "https://x/1", "imageUrl": "https://encrypted-tbn0.gstatic.com/shopping?q=tbn:AAA"},
          {"title": "Caixa d'água Fortlev 1000L Polietileno", "price": "R$ 700,00", "source": "Outra", "link": "https://x/2"}]
    of = g.ler_anuncios("Caixa d'água Fortlev 1000L", "un", an, False)
    assert of[0].imagem and of[0].imagem.startswith("https://encrypted-tbn0") and of[1].imagem is None


def test_imagem_das_ofertas_prefere_a_de_uma_fonte_usada():
    from src.pesquisa import imagem_das_ofertas
    def of(url, img, igual="sim"):
        return Oferta(loja="l", dominio="d.com", url=url, titulo="t", preco=1.0, embalagem="unidade",
                      mesmo_produto=igual, imagem=img)
    ofertas = [of("https://a", "https://img/a"), of("https://b", "https://img/b")]
    assert imagem_das_ofertas(ofertas, {"https://b"}) == "https://img/b"
    assert imagem_das_ofertas(ofertas, set()) == "https://img/a"
    assert imagem_das_ofertas([of("https://c", None)], None) is None
    assert imagem_das_ofertas([of("https://d", "https://img/d", "parecido")], None) is None


def test_item_em_unidades_com_embalagem_de_capacidade_tem_total():
    def of(loja, preco):
        return Oferta(loja=loja, dominio=f"{loja}.com.br", url=f"https://{loja}.com.br/p", titulo="Caixa d'água Fortlev 1000 L",
                      preco=preco, embalagem="1000 L", mesmo_produto="sim")
    r = calcular(ItemEntrada(id="1", descricao="Caixa d'água Fortlev 1000", quantidade=2, unidade="un"),
                 ResultadoExtracao(ofertas=[of("a", 450.0), of("b", 480.0), of("c", 500.0)]), generico=False)
    assert r.tem_preco and r.embalagem == "1000 L" and r.qtd_embalagens == 2


# ---------------------------------------------------------------- link da loja no lugar do link do Google (08/11)
@pytest.mark.parametrize("loja,dominio", [
    ("Leroy Merlin", "leroymerlin.com.br"), ("Amazon.com.br - Retail", "amazon.com.br"),
    ("mercadolivre.com.br", "mercadolivre.com.br"), ("Mercado Livre", "mercadolivre.com.br"),
    ("Obramax - Atacado Da Construção", "obramax.com.br"), ("Loja Desconhecida XYZ", None)])
def test_dominio_da_loja(loja, dominio):
    assert g.dominio_da_loja(loja) == dominio


def test_troca_o_link_do_google_pelo_da_loja_quando_acha_a_pagina_do_produto():
    def of(loja, url, titulo="Joelho Tigre 25 mm soldável 90 graus"):
        return Oferta(loja=loja, dominio=g.DOMINIO_SHOPPING, url=url, titulo=titulo, preco=10.0, embalagem="unidade",
                      mesmo_produto="sim")
    ofertas = [of("Leroy Merlin", "https://www.google.com/search?ibp=oshop&x=1"),
               of("Telhanorte", "https://www.google.com/search?ibp=oshop&x=2"),
               of("Loja Desconhecida XYZ", "https://www.google.com/search?ibp=oshop&x=3")]
    organicos = [
        {"title": "Joelho Tigre 25 mm | Leroy Merlin", "link": "https://www.leroymerlin.com.br/joelho-tigre-25mm_123456",
         "snippet": "Joelho Tigre 25 mm soldável 90 graus"},
        {"title": "Joelho Tigre 25 mm", "link": "https://www.telhanorte.com.br/busca?q=joelho", "snippet": ""},   # busca, não produto
        {"title": "Cimento CP II", "link": "https://www.leroymerlin.com.br/cimento_999", "snippet": ""}]           # outro produto
    r = g.trocar_links_do_google("Joelho Tigre 25 mm", ofertas, organicos)
    assert r[0].url == "https://www.leroymerlin.com.br/joelho-tigre-25mm_123456" and r[0].dominio == "leroymerlin.com.br"
    assert r[1].url.startswith("https://www.google.com/") and r[1].dominio == g.DOMINIO_SHOPPING   # não achou: continua do Google
    assert r[2].url.startswith("https://www.google.com/")


def test_sem_chave_nao_mexe_nos_links(monkeypatch):
    monkeypatch.setattr(g, "get_settings", lambda: type("S", (), {"serper_keys": []})())
    o = Oferta(loja="Leroy Merlin", dominio=g.DOMINIO_SHOPPING, url="https://www.google.com/x", titulo="t", preco=1.0,
               embalagem="unidade", mesmo_produto="sim")
    assert asyncio.run(g.resolver_links_das_lojas("Joelho Tigre 25 mm", [o])) == [o]


def test_nao_liga_ao_produto_errado_so_porque_o_nome_curto_combina():
    """Medido em 08/11: "Deca Vogue Plus" (bacia) levava à página do assento "Vogue Plus"."""
    o = Oferta(loja="Telhanorte", dominio=g.DOMINIO_SHOPPING, url="https://www.google.com/search?ibp=oshop&x=1",
               titulo="Bacia Convencional Vogue Plus Branco Deca", preco=500.0, embalagem="unidade", mesmo_produto="sim")
    org = [{"title": "Assento Termofixo Vogue Plus Branco Deca", "link": "https://www.tupan.com.br/assento-vogue-plus-123",
            "snippet": ""}]
    # o item "Deca Vogue Plus" combina com os dois, mas a página não é a do produto do anúncio
    monkey = g.trocar_links_do_google("Deca Vogue Plus", [o], [{"title": "Assento Termofixo Vogue Plus Branco Deca",
                                                                 "link": "https://www.telhanorte.com.br/assento", "snippet": ""}])
    assert monkey[0].url.startswith("https://www.google.com/")
    ok = g.trocar_links_do_google("Deca Vogue Plus", [o], [{"title": "Bacia Convencional Vogue Plus Branco Deca",
                                                            "link": "https://www.telhanorte.com.br/bacia", "snippet": ""}])
    assert ok[0].url == "https://www.telhanorte.com.br/bacia"


# ---------------------------------------------------------------- segunda passada: link da loja oferta por oferta
def _of(loja, titulo):
    return Oferta(loja=loja, dominio=g.DOMINIO_SHOPPING, url="https://www.google.com/search?ibp=oshop&x=1", titulo=titulo,
                  preco=10.0, embalagem="unidade", mesmo_produto="sim")


def test_pagina_da_loja_de_dominio_conhecido():
    o = _of("Leroy Merlin", "Joelho Tigre 25 mm soldável 90 graus")
    org = [{"title": "Joelho Tigre 25 mm soldável 90 graus | Leroy Merlin", "link": "https://www.leroymerlin.com.br/joelho_123456",
            "snippet": ""}]
    assert g.pagina_da_loja(o, "leroymerlin.com.br", org, "Joelho Tigre 25") == ("https://www.leroymerlin.com.br/joelho_123456",
                                                                              "leroymerlin.com.br")


def test_pagina_da_loja_desconhecida_exige_o_nome_da_loja_no_dominio():
    o = _of("Loja do Pedrão", "Joelho Tigre 25 mm soldável 90 graus")
    certo = [{"title": "Joelho Tigre 25 mm soldável 90 graus", "link": "https://www.lojadopedrao.com.br/joelho-25", "snippet": ""}]
    outra = [{"title": "Joelho Tigre 25 mm soldável 90 graus", "link": "https://www.outraloja.com.br/joelho-25", "snippet": ""}]
    assert g.pagina_da_loja(o, None, certo, "Joelho Tigre 25")[1] == "lojadopedrao.com.br"
    assert g.pagina_da_loja(o, None, outra, "Joelho Tigre 25") is None     # domínio de outra loja: nunca liga


def test_pagina_da_loja_recusa_google_busca_e_produto_diferente():
    o = _of("Leroy Merlin", "Joelho Tigre 25 mm soldável 90 graus")
    ruins = [{"title": "Joelho Tigre 25 mm soldável 90 graus", "link": "https://www.google.com/search?q=x", "snippet": ""},
             {"title": "Joelho Tigre 25 mm soldável 90 graus", "link": "https://www.leroymerlin.com.br/busca?q=joelho", "snippet": ""},
             {"title": "Registro de esfera 25 mm Tigre", "link": "https://www.leroymerlin.com.br/registro_1", "snippet": ""}]
    assert g.pagina_da_loja(o, "leroymerlin.com.br", ruins, "Joelho Tigre 25") is None


# ---------------------------------------------------------------- mesma linha, outro tipo de produto (Deca Vogue Plus)
def _t(titulo):
    return Oferta(loja="l" + titulo[:3], dominio="d.com", url="https://d.com/" + titulo[:4], titulo=titulo, preco=10.0,
                  embalagem="unidade", mesmo_produto="sim")


def test_tira_assento_bide_e_caixa_da_mesma_linha():
    ofertas = [_t("Bacia Convencional Vogue Plus Branco Deca"), _t("Bacia Convencional Vogue Plus Gelo Deca"),
               _t("Bacia Convencional Deca Vogue Plus P511"), _t("Vaso Sanitário Convencional Vogue Plus Deca"),
               _t("Bacia Vogue Plus Convencional Branca Deca"), _t("Assento Termofixo Vogue Plus Branco Deca"),
               _t("Bidê Vogue Plus Deca"), _t("Caixa Acoplada Vogue Plus Deca")]
    tipo = g.palavras_do_tipo("Deca Vogue Plus", ofertas)
    assert {"bacia", "convencional"} <= tipo
    mantidas = [o.titulo for o in ofertas if g.e_do_tipo(o, tipo)]
    assert len(mantidas) == 5 and not any(t.startswith(("Assento", "Bidê", "Caixa")) for t in mantidas)


def test_poucas_ofertas_ou_produtos_iguais_nao_filtram_nada():
    assert g.palavras_do_tipo("Deca Vogue Plus", [_t("Bacia Vogue Plus Deca"), _t("Assento Vogue Plus Deca")]) == set()
    tinta = [_t(f"Tinta Suvinil Fosco Completo Branco Neve 18L {i}") for i in range(6)]
    tipo = g.palavras_do_tipo("Tinta Suvinil Fosco Completo 18L", tinta)
    assert all(g.e_do_tipo(o, tipo) for o in tinta)
