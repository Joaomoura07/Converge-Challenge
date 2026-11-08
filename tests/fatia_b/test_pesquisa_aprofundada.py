"""Especificações, páginas e consumo: testes offline com dados sintéticos."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from types import SimpleNamespace as NS

import pytest

from src import custo
from src.busca import ResultadoWeb
from src.calculo import calcular
from src.config import get_settings
from src.especificacao import nao_confirmados, orientacao
from src.modelos import ItemEntrada
from src.paginas_produto import aprofundar, recortar, url_publica
from src.precos import Oferta, ResultadoExtracao, extrair_e_conferir


@pytest.mark.parametrize("pedido,titulo,campo", [
    ("Tomada Tramontina Liz branca 20A", "Tomada Tramontina Liz preta 20A", "cor"),
    ("Spot Stella 7W 3000K", "Spot Stella 7W 4000K", "medida"),
    ("Tinta Suvinil fosca 18L", "Tinta Suvinil acetinada 18L", "acabamento"),
    ("Tubo Tigre 25mm", "Tubo Amanco 25mm", "marca/linha"),
    ("Produto referência AB123", "Produto referência AB124", "referência"),
    ("Porcelanato 60x60", "Porcelanato 60x120", "dimensão"),
    ("Tomada 20A", "Tomada 20W", "medida"),
])
def test_especificacao_diferente_ou_ausente_nao_confirma(pedido, titulo, campo):
    assert any(x.startswith(campo) for x in nao_confirmados(pedido, titulo))


def test_normaliza_unidade_cor_e_decimal_sem_confundir_grandezas():
    assert not nao_confirmados("Peça branca 25mm", "Peça branco 2,5 cm")
    assert not nao_confirmados("Tinta 3,6 litros", "Tinta 3600 ml")


def test_cache_antigo_nao_confirma_produto_de_outra_cor():
    item = ItemEntrada(id="sintetico", descricao="Tomada Tramontina Liz branca 20A", quantidade=1, unidade="un")
    o = Oferta(loja="Loja teste", dominio="loja.example", url="https://loja.example/tomada", titulo="Tomada Tramontina Liz preta 20A",
               preco=25.9, embalagem="unidade", mesmo_produto="sim")
    assert not calcular(item, ResultadoExtracao(ofertas=[o])).tem_preco
    assert calcular(item, ResultadoExtracao(ofertas=[o]), generico=True).estimativa


def test_pergunta_tecnica_nao_inventa_especificacao():
    assert "tensão" in orientacao("Chuveiro")
    assert "classe" in orientacao("Argamassa")
    assert "espessura" in orientacao("Porcelanato")


def test_consumo_aninhado_inclui_resposta_invalida_e_custo_ausente():
    with custo.acumular() as total:
        with custo.acumular(item=True) as item:
            reserva = custo.reservar("abc", 400)
            custo.registrar_resposta(reserva, NS(prompt_tokens=40, completion_tokens=12, cost=0.001))
            reserva = custo.reservar("def", 400)
            custo.registrar_resposta(reserva, NS(prompt_tokens=30, completion_tokens=0))
            custo.registrar_paginas(2)
    assert total.entrada == item.entrada == 70
    assert total.usd == item.usd == 0.001
    assert total.paginas == item.paginas == 2
    assert item.resumo()["consumo_incompleto"]


def test_limite_compartilhado_reserva_antes_da_chamada_em_threads():
    acc = custo.Acumulador(limite_chamadas=2)
    with custo.acumular(acc):
        def tentar():
            try:
                custo.reservar("x", 400)
                return True
            except custo.LimitePesquisa:
                return False
        contextos = [copy_context() for _ in range(10)]
        with ThreadPoolExecutor(max_workers=5) as pool:
            resultados = list(pool.map(lambda ctx: ctx.run(tentar), contextos))
    assert sum(resultados) == 2
    assert acc.chamadas == acc.sem_usage == 2
    assert acc.resumo()["limite_atingido"]


def test_limite_tokens_e_custo():
    with custo.acumular(custo.Acumulador(limite_tokens=10)):
        with pytest.raises(custo.LimitePesquisa):
            custo.reservar("abc", 400)
    with custo.acumular(custo.Acumulador(usd=0.03, limite_usd=0.03)):
        with pytest.raises(custo.LimitePesquisa):
            custo.reservar("abc", 400)


def test_paginas_lidas_limitadas_e_falha_preserva_snippet(monkeypatch):
    monkeypatch.setattr(get_settings(), "pesquisa_paginas_por_rodada", 2)
    rs = [ResultadoWeb("Tomada branca", f"https://loja.example/produto-{i}", "loja.example", "Loja", "R$ 25,90") for i in range(4)]
    class Cliente:
        async def extract(self, **kw):
            assert len(kw["urls"]) == 2
            return {"results": [{"url": rs[0].url, "raw_content": "Tomada branca\n20A\nR$ 25,90"}],
                    "failed_results": [{"url": rs[1].url}]}
    with custo.acumular(item=True) as acc:
        saida = asyncio.run(aprofundar("Tomada branca 20A", rs, Cliente()))
    assert saida[0].pagina_lida and "20A" in saida[0].trecho
    assert saida[1:] == rs[1:] and acc.paginas == 1


def test_timeout_pagina_preserva_resultados(monkeypatch):
    monkeypatch.setattr(get_settings(), "pesquisa_paginas_por_rodada", 2)
    class Cliente:
        async def extract(self, **kw):
            raise TimeoutError()
    rs = [ResultadoWeb("Produto", "https://loja.example/produto", "loja.example", "Loja", "R$ 20,90")]
    assert asyncio.run(aprofundar("Produto", rs, Cliente())) == rs
    assert len(recortar("marca: produto\n" * 2000, "produto")) <= 1400
    assert not url_publica("https://127.0.0.1/produto")
    assert not url_publica("https://localhost/produto")
    assert not url_publica("https://usuario:senha@loja.example/produto")


def test_extracao_contabiliza_todas_respostas_e_rejeita_falso_sim(monkeypatch):
    monkeypatch.setattr(get_settings(), "pesquisa_hedge_ativo", False)
    class Cliente:
        def __init__(self):
            self.n = 0
            self.chat = NS(completions=NS(create=self.create))
        async def create(self, **kw):
            self.n += 1
            return NS(usage=NS(prompt_tokens=80, completion_tokens=10, cost=0.0001),
                      choices=[NS(message=NS(content="inválida" if self.n == 1 else "0|25.90|unidade|SIM"))])
    rs = [ResultadoWeb("Tomada Tramontina preta 20A", "https://loja.example/tomada", "loja.example", "Loja", "R$ 25,90")]
    with custo.acumular(item=True) as acc:
        ext = asyncio.run(extrair_e_conferir("Tomada Tramontina branca 20A", rs, Cliente()))
    assert acc.chamadas == 2 and acc.entrada == 160 and acc.usd == 0.0002
    assert ext.ofertas[0].mesmo_produto == "parecido"


def test_cancelamento_preserva_consumo_conhecido_e_chamada_sem_resposta(monkeypatch):
    from src import pesquisa
    async def demorada(*args):
        custo.registrar_resposta(custo.reservar("primeira", 400),
                                NS(prompt_tokens=80, completion_tokens=10, cost=0.0001))
        custo.reservar("segunda", 400)
        raise asyncio.CancelledError()
    monkeypatch.setattr(pesquisa, "_fase_rapida_impl", demorada)
    item = ItemEntrada(id="sintetico", descricao="Tomada branca 20A", quantidade=1, unidade="un")
    resultado = asyncio.run(pesquisa.pesquisar_item(item))
    assert resultado.status == "erro"
    assert resultado.pesquisa_detalhes["tokens_entrada"] == 80
    assert resultado.pesquisa_detalhes["chamadas"] == 2
    assert resultado.pesquisa_detalhes["consumo_incompleto"]


def test_busca_link_direto_usa_preco_da_mesma_oferta(monkeypatch):
    from src import google_shopping as shopping
    monkeypatch.setattr(get_settings(), "serper_api_keys", "sintetica")
    async def anuncios(*args):
        return [{"title": "Tomada Tramontina Liz branca 20A", "source": "Loja teste",
                 "price": "R$ 9,90", "link": "https://www.google.com/shopping/product/123"}]
    async def organicos(*args, **kwargs):
        return {"organic": [{"title": "Tomada Tramontina Liz branca 20A",
                             "snippet": "Em estoque por R$ 25,90",
                             "link": "https://loja.example/produto/tomada-liz-branca-20a"},
                            {"title": "Tomada Tramontina Liz preta 20A", "snippet": "R$ 19,90",
                             "link": "https://loja.example/produto/preta"}]}
    monkeypatch.setattr(shopping, "_buscar", anuncios)
    monkeypatch.setattr(shopping.serper, "post", organicos)
    ofertas = asyncio.run(shopping.ofertas_google("Tomada Tramontina Liz branca 20A", "un"))
    assert len(ofertas) == 1
    assert ofertas[0].preco == 25.9
    assert ofertas[0].url == "https://loja.example/produto/tomada-liz-branca-20a"
