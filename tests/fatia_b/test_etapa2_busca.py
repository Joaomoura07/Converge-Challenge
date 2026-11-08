"""Etapa 2 — busca: consulta, lista fixa de lojas, Tavily com rodízio de chaves, reserva DuckDuckGo."""

from __future__ import annotations

import asyncio
import time

import pytest

import src.busca as b
from src.modelos import ItemEntrada


def rodar(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def sem_busca_aberta_de_verdade(monkeypatch, request):
    """Os testes offline desta etapa tratam da busca FIXA; a aberta (testada em test_busca_aberta.py) não pode ir à rede."""
    if "real" in request.keywords:
        return
    async def vazia(consulta, *a):
        return b.RespostaBusca(consulta, "nenhum")
    monkeypatch.setattr(b, "_buscar_aberta", vazia)


# ---------------------------------------------------------------- offline: consulta e filtro
def test_consulta_tira_quantidade_e_pede_preco():
    item = ItemEntrada(id="1", descricao="Porcelanato Portobello Cimento Queimado 90x90 48 m²")
    assert b.montar_consulta(item) == "Porcelanato Portobello Cimento Queimado 90x90 preço"
    assert b.montar_consulta(item, "acetinado") == "Porcelanato Portobello Cimento Queimado 90x90 acetinado preço"


def test_dominio_e_loja_incluindo_subdominio():
    assert b.dominio_de("https://www.leroymerlin.com.br/x") == "leroymerlin.com.br"
    assert b.loja_de("produto.mercadolivre.com.br") == "Mercado Livre"
    assert b.loja_de("blogdaobra.com.br") is None


def test_filtro_so_lojas_da_lista_sem_repetir_e_com_limite():
    brutos = [("A", "https://www.leroymerlin.com.br/a", "R$ 10"),
              ("Blog", "https://blogdaobra.com.br/b", "R$ 1"),
              ("A de novo", "https://www.leroymerlin.com.br/a", "R$ 10"),
              ("C", "https://www.cec.com.br/c", "R$ 12"),
              ("D", "https://www.telhanorte.com.br/d", "R$ 13")]
    r = b._filtra(brutos, limite=2)
    assert [x.loja for x in r] == ["Leroy Merlin", "C&C"]


@pytest.mark.parametrize("url,busca", [
    ("https://www.magazineluiza.com.br/busca/porcelanato+portobello/", True),   # caso da passagem
    ("https://www.amazon.com.br/s?k=argamassa+ac3", True),
    ("https://lista.mercadolivre.com.br/cuba-tramontina-morgana", True),
    ("https://www.telhanorte.com.br/busca?ft=tinta%20suvinil", True),
    ("https://www.leroymerlin.com.br/search?term=misturador", True),
    ("https://www.leroymerlin.com.br/porcelanato-cimento-90x90-portobello_89393833", False),
    ("https://produto.mercadolivre.com.br/MLB-123-cuba-tramontina-morgana-56x34-_JM", False),
    ("https://www.amazon.com.br/Argamassa-Quartzolit/dp/B07XYZ", False),
    ("https://www.telhanorte.com.br/tinta-suvinil-toque-de-seda-18l/p?skuId=1", False),
])
def test_descarta_pagina_de_busca_da_loja(url, busca):
    assert b.eh_pagina_de_busca(url) is busca
    assert (b._filtra([("X", url, "R$ 10")], limite=5) == []) is busca


def test_no_maximo_2_resultados_por_loja():
    brutos = [(f"ML {i}", f"https://www.mercadolivre.com.br/{i}", "R$ 1") for i in range(5)]
    brutos.append(("Leroy", "https://www.leroymerlin.com.br/x", "R$ 2"))
    r = b._filtra(brutos, limite=5)
    assert [x.loja for x in r] == ["Mercado Livre", "Mercado Livre", "Leroy Merlin"]


def test_tavily_vazio_na_1a_tentativa_tenta_de_novo_antes_da_reserva(monkeypatch):
    chamadas = []
    async def tav(*a):
        chamadas.append(1)
        return b.RespostaBusca("q", "tavily") if len(chamadas) == 1 else _ok("tavily")
    async def ddg(*a): raise AssertionError("não devia chamar a reserva")
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_duckduckgo", ddg)
    r = rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"])))
    assert len(chamadas) == 2 and r.provedor == "tavily"


# ---------------------------------------------------------------- offline: caminhos de falha
def _ok(provedor, n=2):
    return b.RespostaBusca("q", provedor, [b.ResultadoWeb("t", f"https://cec.com.br/{i}", "cec.com.br", "C&C", "R$ 1")
                                           for i in range(n)], [b.ImagemWeb("https://img/1.jpg")])


def test_tavily_ok_nao_chama_reserva(monkeypatch):
    async def tav(*a): return _ok("tavily")
    async def ddg(*a): raise AssertionError("não devia chamar a reserva")
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_duckduckgo", ddg)
    assert rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"]))).provedor == "tavily"


@pytest.mark.parametrize("falha", ["excecao", "vazio"])
def test_tavily_falha_ou_vazio_cai_no_duckduckgo(monkeypatch, falha):
    async def tav(*a):
        if falha == "excecao":
            raise TimeoutError("lento")
        return b.RespostaBusca("q", "tavily")
    async def ddg(*a): return _ok("duckduckgo")
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_duckduckgo", ddg)
    r = rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"])))
    assert r.provedor == "duckduckgo" and r.resultados and r.erro is None


def test_reserva_aproveita_imagens_do_tavily(monkeypatch):
    async def tav(*a): return b.RespostaBusca("q", "tavily", [], [b.ImagemWeb("https://img/tavily.jpg")])
    async def ddg(*a):
        r = _ok("duckduckgo"); r.imagens = []; return r
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_duckduckgo", ddg)
    r = rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"])))
    assert r.provedor == "duckduckgo" and [i.url for i in r.imagens] == ["https://img/tavily.jpg"]


def test_nao_usa_country_com_lista_de_lojas():
    """Regressão: country='brazil' + include_domains zera os resultados do Tavily."""
    import inspect
    assert "country=" not in inspect.getsource(b._tavily).split("# NÃO usar")[0]


def test_tudo_falha_traz_motivo(monkeypatch):
    async def tav(*a): raise TimeoutError()
    async def ddg(*a): raise ConnectionError()
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_duckduckgo", ddg)
    r = rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"])))
    assert r.provedor == "nenhum" and not r.resultados
    assert "tavily" in r.erro and "duckduckgo" in r.erro


def test_rodizio_pula_chave_esgotada(monkeypatch):
    import tavily
    from tavily.errors import UsageLimitExceededError
    usadas = []

    class Falso:
        def __init__(self, api_key): self.k = api_key
        async def search(self, *a, **kw):
            usadas.append(self.k)
            if self.k == "esgotada":
                raise UsageLimitExceededError("limite")
            return {"results": [{"title": "t", "url": "https://www.cec.com.br/x", "content": "R$ 9"}], "images": []}

    monkeypatch.setattr(tavily, "AsyncTavilyClient", Falso)
    rod = b._RodizioChaves(["esgotada", "boa"])
    r = rodar(b._tavily("q", 5, rod))
    assert usadas == ["esgotada", "boa"] and r.provedor == "tavily" and rod.atual == "boa"


# ---------------------------------------------------------------- real (gasta 1–2 créditos)
@pytest.mark.real
@pytest.mark.parametrize("descricao", [
    "Porcelanato Portobello Cimento Queimado acetinado 90x90 retificado",
    "Argamassa colante Quartzolit AC-III cinza 20kg",
])
def test_etapa2_busca_real_traz_lojas_da_lista_e_imagem(descricao):
    t0 = time.perf_counter()
    r = rodar(b.buscar(b.montar_consulta(ItemEntrada(id="1", descricao=descricao))))
    dur = time.perf_counter() - t0
    assert r.provedor in ("tavily", "duckduckgo"), r.erro
    assert len(r.resultados) >= 2, f"poucas lojas: {[x.loja for x in r.resultados]} ({r.erro})"
    # loja da lista fixa OU loja da busca aberta, que só entra com preço escrito no anúncio
    assert all(b.loja_de(x.dominio) or b.tem_preco(x.titulo, x.trecho) for x in r.resultados)
    assert r.imagens, "sem imagens candidatas"
    assert r.imagem is None or r.imagem.startswith("http")
    assert dur < 15, f"busca lenta: {dur:.1f}s"


@pytest.mark.real
def test_etapa2_reserva_real_com_chave_invalida():
    r = rodar(b.buscar("Tinta Suvinil Toque de Seda Branco Neve 18L preço", rodizio=b._RodizioChaves(["tvly-invalida"])))
    assert r.provedor == "duckduckgo", f"esperava cair no DuckDuckGo: {r.provedor} {r.erro}"



def test_uma_chave_esgotada_nao_derruba_as_outras_em_buscas_simultaneas(monkeypatch):
    """Medido em 08/11: 16 buscas ao mesmo tempo falhavam na chave 1 (esgotada) e cada uma descartava "a atual",
    que já era a 2, a 3...: as 8 chaves saíam e o Tavily desligava. Só a chave 1 pode sair."""
    import asyncio
    from types import SimpleNamespace as NS

    import tavily
    from tavily.errors import ForbiddenError

    import src.busca as b

    class Cliente:
        def __init__(self, api_key): self.k = api_key

        async def search(self, *a, **kw):
            await asyncio.sleep(0.01)
            if self.k == "k1":
                raise ForbiddenError("This request exceeds your plan's set usage limit")
            return {"results": [], "images": []}

    monkeypatch.setattr(tavily, "AsyncTavilyClient", Cliente)
    rod = b._RodizioChaves(["k1", "k2", "k3", "k4"])

    async def rajada():
        return await asyncio.gather(*(b._tavily(f"consulta {i}", 5, rod) for i in range(16)))

    respostas = asyncio.run(rajada())
    assert all(r.provedor == "tavily" for r in respostas)
    assert rod._ate.get(0) == float("inf") and all(rod._ate.get(i, 0.0) != float("inf") for i in (1, 2, 3))
