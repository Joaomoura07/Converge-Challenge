"""Conferência dos links na página da loja (08/11). Casos tirados da auditoria dos 4 casos da demo (95 links)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

import src.conferir_links as cl
from src.precos import Oferta


def of(url, titulo="", preco=10.0, emb="unidade", loja="Loja"):
    return Oferta(loja=loja, dominio="loja.com.br", url=url, titulo=titulo, preco=preco, embalagem=emb, mesmo_produto="sim")


def pagina(nome, precos=(), produto=True, esgotado=False, http=200):
    return cl.Pagina(http=http, final="", nome=nome, produto=produto, precos=list(precos), esgotado=esgotado, texto="x")


@pytest.mark.parametrize("pedido,url,nome,preco,precos,motivo", [
    ("Tinta acrílica fosca branca", "https://www.telhanorte.com.br/tinta-acrilica",
     "Tinta acrílica para paredes | Telhanorte", 379.9, (), "categoria"),
    ("Tomada", "https://www.ferreiracosta.com/Categoria/tomadas-interruptores", "Tomadas e interruptores", 8.9, (), "categoria"),
    ("Tinta Suvinil Toque de Seda 18L", "https://www.google.com/search?tbm=shop&q=x", "Google Search", 799.9, (), "buscador"),
    ("Tomada Tramontina Liz branca 20A", "https://www.amazon.com.br/Conj-4X2-interruptor-Tramontina/dp/B0X",
     "Conjunto 4x2 Tramontina 1 Interruptor Simples e 2 Tomadas 2P+T", 14.83, (), "outro produto"),
    ("Tinta Suvinil Toque de Seda Branco Neve 18L", "https://www.copafer.com.br/tinta-acrilica-toque-fosco-branco-neve",
     "Tinta Acrílica Toque Fosco Branco Neve 18 Litros", 607.9, (607.9,), "outra linha"),
    ("Porcelanato Portobello 60x60cm polido", "https://www.telhanorte.com.br/porcelanato-marmore-bianco-60x60-natural",
     "Porcelanato Marmore Bianco 60X60 Natural Bold Caixa 1,83M2", 72.85, (104.9,), "acabamento"),
    ("Argamassa Quartzolit AC-III cinza 20kg", "https://www.cazanovaconstrucao.com.br/argamassa-quartz-flexivel-branca",
     "Argamassa Quartz Flexivel Branca Aciii 20kg", 114.9, (114.9,), "cor"),
    ("Argamassa Quartzolit AC-III cinza 20kg", "https://www.loja.com.br/argamassa-aciii-cinza-quartzolit-20kg",
     "Argamassa ACIII Cinza 20kg Quartzolit", 46.9, (64.9,), "preço"),
])
def test_links_errados_da_demo_saem(pedido, url, nome, preco, precos, motivo):
    v = cl.julgar(pedido, of(url, nome, preco), pagina(nome, precos, produto=bool(precos)))
    assert v.errado and motivo in v.errado, v


def test_kit_de_10_em_loja_que_bloqueia_robo_sai_pelo_endereco():
    v = cl.julgar("Tomada Tramontina Liz branca 20A",
                  of("https://www.leroymerlin.com.br/kit-c--10-tomada-dupla-20a-2p-t-branca_1567008061", "Tomada 20A Tramontina", 7.6),
                  cl.Pagina(http=403, final=""))
    assert v.errado and "kit de 10" in v.errado


@pytest.mark.parametrize("pedido,nome,preco,precos", [
    ("Argamassa Quartzolit AC-III cinza 20kg", "Argamassa ACIII Porcelanato Interno e Externo Cinza 20kg Quartzolit", 46.9, (46.9,)),
    ("Tinta Suvinil Toque de Seda Branco Neve 18L", "SUVINIL TOQUE DE SEDA BRANCO NEVE 18L", 851.6, (851.6,)),
    ("Joelho Tigre soldável 25mm", "Joelho 90° Soldável 25Mm Tigre", 1.5, (1.35,)),        # preço no Pix: até 15%
    ("Spot Stella 7W 3000K", "Spot de Led Embutir Stella Easy Par 20 Quadrado 7W", 55.6, (55.6,)),
])
def test_links_certos_sao_confirmados(pedido, nome, preco, precos):
    v = cl.julgar(pedido, of("https://www.loja.com.br/" + "-".join(nome.lower().split()[:6]), nome, preco),
                  pagina(nome, precos))
    assert v.confirmado and not v.errado, v


def test_bloqueio_sem_pista_fica_sem_confirmar():
    v = cl.julgar("Spot Stella 7W 3000K", of("https://www.magazineluiza.com.br/spot-de-led-de-embutir-recuado-stella/p/1"),
                  cl.Pagina(http=403, final=""))
    assert not v.errado and not v.confirmado


def test_sem_resposta_da_loja_nao_vira_categoria():
    v = cl.julgar("Joelho Tigre 25mm", of("https://loja.com.br/a"), cl.Pagina(http=None, final=""))
    assert not v.errado


def test_esgotado_e_404_saem():
    assert cl.julgar("Joelho Tigre 25mm", of("https://loja.com.br/joelho-tigre-25mm-soldavel"),
                     pagina("Joelho Tigre 25mm", (2.0,), esgotado=True)).errado
    assert cl.julgar("Joelho Tigre 25mm", of("https://loja.com.br/joelho-tigre-25mm-soldavel"),
                     cl.Pagina(http=404, final="")).errado


def test_le_produto_do_json_ld():
    dados = {"@context": "https://schema.org", "@graph": [{"@type": "Product", "name": "Tinta Toque de Seda 18L",
             "offers": {"@type": "Offer", "price": "739.90", "availability": "https://schema.org/InStock"}}]}
    corpo = ('<html><head><title>Loja</title><script type="application/ld+json">' + json.dumps(dados)
             + "</script></head><body>R$ 739,90</body></html>")
    p = cl.ler_html(200, "https://x", corpo)
    assert p.produto and p.nome == "Tinta Toque de Seda 18L" and p.precos == [739.9] and not p.esgotado


def _ld(nome, preco):
    return '<script type="application/ld+json">' + json.dumps({"@type": "Product", "name": nome, "offers": {"price": preco}}) + "</script>"


def test_conferir_tira_os_errados_e_confirma_os_certos(monkeypatch):
    monkeypatch.setattr(cl, "ATIVO", True)
    monkeypatch.setattr(cl, "_cache", {})
    paginas = {"/tinta-toque-de-seda-18l-suvinil-branco": _ld("Tinta Suvinil Toque de Seda 18L", 739.9),
               "/tinta-toque-fosco-18l-suvinil-branco": _ld("Tinta Suvinil Toque Fosco 18L", 607.9),
               "/tinta-acrilica": "<title>Tintas</title>"}

    def responder(req):
        if req.url.path in paginas:
            return httpx.Response(200, text=paginas[req.url.path])
        return httpx.Response(403)

    ofertas = [of("https://loja.com.br/tinta-toque-de-seda-18l-suvinil-branco", "Tinta Toque de Seda 18L", 739.9, loja="A"),
               of("https://loja.com.br/tinta-toque-fosco-18l-suvinil-branco", "Tinta Toque Fosco 18L", 607.9, loja="B"),
               of("https://loja.com.br/tinta-acrilica", "Tinta", 379.9, loja="C"),
               of("https://bloqueia.com.br/tinta-toque-de-seda-suvinil-18l-branco-neve", "Tinta Toque de Seda", 799.9, loja="D")]

    async def rodar():
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cli:
            return await cl.conferir("Tinta Suvinil Toque de Seda Branco Neve 18L", ofertas, cliente=cli)

    saida = asyncio.run(rodar())
    # "Toque Fosco" (outra linha) fica como PARECIDO: sem link e fora da conta do produto exato
    assert [(o.loja, o.link_verificado, o.mesmo_produto) for o in saida] == [
        ("A", True, "sim"), ("B", False, "parecido"), ("D", False, "sim")]


def test_falha_geral_nao_derruba_a_pesquisa(monkeypatch):
    monkeypatch.setattr(cl, "ATIVO", True)

    async def quebra(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(cl, "_abrir", quebra)
    saida = asyncio.run(cl.conferir("Tinta", [of("https://loja.com.br/tinta-x-y-z-w", "Tinta", 10.0)]))
    assert len(saida) == 1 and not saida[0].link_verificado


def test_oferta_sem_preco_nao_vai_para_a_ia_e_falha_da_ia_nao_traz_errado_de_volta(monkeypatch):
    """Achado na 2ª auditoria (08/11): oferta sem preço (só a foto) ia para a IA, dava TypeError e a reserva devolvia
    a lista ORIGINAL, com os links "Toque Fosco" que já tinham sido tirados."""
    monkeypatch.setattr(cl, "ATIVO", True)
    monkeypatch.setattr(cl, "_cache", {})
    sem_preco_html = "<title>Tinta Acrílica Toque de Seda 18 L Suvinil</title><body>Comprar</body>"
    paginas = {"/tinta-toque-fosco-18l-suvinil-branco": _ld("Tinta Suvinil Toque Fosco 18L", 607.9),
               "/tinta-toque-de-seda-18l-suvinil-branco-neve": sem_preco_html}

    async def quebra(*a, **k):
        raise RuntimeError("IA fora")

    monkeypatch.setattr(cl, "_ler_com_ia", quebra)
    ofertas = [of("https://loja.com.br/tinta-toque-fosco-18l-suvinil-branco", "Tinta Toque Fosco 18L", 607.9, loja="B"),
               of("https://loja.com.br/tinta-toque-de-seda-18l-suvinil-branco-neve", "Tinta Toque de Seda 18L", 799.9, loja="H"),
               Oferta(loja="F", dominio="f.com.br", url="https://f.com.br/tinta-toque-de-seda-suvinil-18l-x", titulo="Tinta",
                      preco=None, embalagem=None, mesmo_produto="sim")]

    def responder(req):
        return httpx.Response(200, text=paginas.get(req.url.path, "<title>Tinta Toque de Seda Suvinil 18L</title>"))

    async def rodar():
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cli:
            return await cl.conferir("Tinta Suvinil Toque de Seda Branco Neve 18L", ofertas, cliente=cli)

    saida = asyncio.run(rodar())
    assert [(o.loja, o.mesmo_produto) for o in saida] == [("B", "parecido"), ("H", "sim"), ("F", "sim")]
    assert not any(o.link_verificado for o in saida)



def test_kit_do_link_diferente_do_kit_do_anuncio_sai():
    url = "https://www.mercadolivre.com.br/kit-5-spot-embutido-led-easy-stella-7w/p/MLB1"
    assert "kit de 5" in cl.julgar("Spot Stella 7W 3000K", of(url, "Kit 2 Spot Stella Easy 7W", 122.56),
                                   cl.Pagina(http=200, final="", nome="Mercado Libre")).errado
    assert not cl.julgar("Spot Stella 7W 3000K", of(url, "Kit 5 Spot Stella Easy 7W", 122.56),
                         cl.Pagina(http=200, final="", nome="Mercado Libre")).errado



def test_so_links_confirmados_entram_na_conta_quando_ha_algum():
    from src.calculo import calcular
    from src.modelos import ItemEntrada
    from src.precos import ResultadoExtracao
    oks = [of(f"https://l{i}.com.br/tinta-toque-de-seda-18l", "Tinta Toque de Seda 18L", p, "lata 18 L", f"L{i}")
           for i, p in enumerate([739.9, 799.9])]
    oks = [o.model_copy(update={"link_verificado": True}) for o in oks]
    sem = of("https://x.com.br/tinta-toque-de-seda-18l", "Tinta Toque de Seda 18L", 760.0, "lata 18 L", "X")
    c = calcular(ItemEntrada(id="1", descricao="Tinta Suvinil Toque de Seda 18L", quantidade=1, unidade="un"),
                 ResultadoExtracao(ofertas=[*oks, sem]))
    assert {f.loja for f in c.fontes} == {"L0", "L1"} and c.descartadas.get("link não confirmado") == 1


def test_pagina_aberta_na_busca_extra_vira_oferta_confirmada():
    from src.outras_lojas import consulta_sem, oferta_da_pagina
    assert consulta_sem("Spot Stella 7W", {"leroymerlin.com.br", "google.com"}) == "Spot Stella 7W preço -site:leroymerlin.com.br"
    pg = pagina("Spot de Embutir LED Stella 7W 3000K", (54.9, 59.9))
    o = oferta_da_pagina("Spot Stella 7W 3000K", "un", "https://loja.com.br/spot-stella-7w-3000k", "loja.com.br", "Loja", pg)
    assert o and o.preco == 54.9 and o.link_verificado and o.embalagem == "unidade"
    outro = pagina("Kit 10 Spot de Embutir LED Stella 7W", (99.0,))
    assert oferta_da_pagina("Spot Stella 7W 3000K", "un", "https://loja.com.br/kit-10-spot-stella", "loja.com.br", "L", outro) is None
    assert oferta_da_pagina("Spot Stella 7W 3000K", "un", "https://loja.com.br/a-b-c-d", "loja.com.br", "L",
                            cl.Pagina(http=403, final="")) is None



def test_busca_extra_nao_aceita_produto_fora_da_faixa_ja_vista():
    """Medido em 08/11: o spot de TRILHO (R$ 239) entrou no lugar do de embutir (R$ 55) na busca extra."""
    from src.outras_lojas import na_faixa, referencia_de
    vistos = [of("https://a.com.br/x", "Spot Stella 7W", 55.6, loja="A"), of("https://b.com.br/x", "Spot Stella 7W", 53.5, loja="B")]
    ref = referencia_de(vistos)
    assert not na_faixa(of("https://c.com.br/x", "Spot para Trilho Stella 7W", 239.1), ref)
    assert na_faixa(of("https://d.com.br/x", "Spot Stella 7W", 59.9), ref)
    assert na_faixa(of("https://e.com.br/x", "Spot", 239.1), None)



def test_generico_aceita_a_mesma_peca_em_outra_medida_como_parecido_confirmado():
    """Medido em 08/11: "Azulejo português azul 60x60" (fora dos exemplos) ficava sem nenhum preço real; as lojas de
    azulejo vendem em 15x15/20x20 e a medida barrava todas."""
    from src.outras_lojas import oferta_da_pagina, sem_medidas
    assert sem_medidas("Azulejo português azul 60x60") == "Azulejo português azul"
    pg = pagina("Azulejo Português Azul Escuro - Port 018", (245.0,))
    url = "https://www.taiazulejos.com.br/azulejo-portugues-azul-escuro-port-018"
    o = oferta_da_pagina("Azulejo português azul 60x60", "m2", url, "taiazulejos.com.br", "Taiazulejos", pg, generico=True)
    assert o and o.mesmo_produto == "parecido" and o.link_verificado and o.preco == 245.0
    # item ESPECIFICADO continua exigindo a medida
    assert oferta_da_pagina("Azulejo português azul 60x60", "m2", url, "taiazulejos.com.br", "T", pg) is None
