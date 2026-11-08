"""Conferência do preço no Google Shopping (Serper): conversão, comparação, regras e falhas. Sem rede."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import httpx
import pytest

from src import validacao_serper as v
from src.modelos import Fonte, ResultadoItem

PRODUTO = "Tinta Suvinil Fosco Completo Branco 18L"


def resultado(preco=800.0, **kw):
    base = dict(item_id="a", status="definido", produto_normalizado=PRODUTO, embalagem="lata 18 L", qtd_embalagens=2,
                preco_emb_min=preco, preco_emb_med=preco, preco_emb_max=preco, confianca="alta",
                fontes=[Fonte(loja="Leroy Merlin", dominio="leroymerlin.com.br", url="https://l/a", preco_embalagem=preco)])
    base.update(kw)
    return ResultadoItem(**base)


def anuncios(*precos, titulo="Tinta Suvinil Fosco Completo Branco 18L"):
    return [{"title": titulo, "price": p, "source": "Loja", "link": "https://x"} for p in precos]


@pytest.mark.parametrize("entrada,esperado", [("R$ 1.234,56", 1234.56), ("739,90", 739.9), (739.9, 739.9), ("R$ 5", 5.0),
                                              ("consulte", None), (None, None), (0, None), (True, None)])
def test_converter_preco(entrada, esperado):
    assert v.converter_preco(entrada) == esperado


def test_confirmado_quando_o_preco_bate():
    r = v.comparar(PRODUTO, "lata 18 L", 800.0, anuncios("R$ 790,00", "R$ 820,00", "R$ 805,00"))
    assert r.status == "confirmado" and r.n == 3 and r.mediana == 805.0 and r.diferenca_pct < 5


def test_divergente_leve_e_divergente():
    assert v.comparar(PRODUTO, "lata 18 L", 1000.0, anuncios("R$ 700,00", "R$ 720,00")).status == "divergente_leve"
    assert v.comparar(PRODUTO, "lata 18 L", 1000.0, anuncios("R$ 400,00", "R$ 420,00")).status == "divergente"


def test_converte_pelo_conteudo_da_embalagem():
    # anúncios de lata 3,6 L a R$ 180 (R$ 50/L) comparados com a nossa lata de 18 L a R$ 900
    r = v.comparar(PRODUTO, "lata 18 L", 900.0, anuncios("R$ 180,00", "R$ 185,00", titulo=PRODUTO.replace("18L", "3,6L")))
    assert r.status == "confirmado" and r.mediana == pytest.approx(912.5, abs=0.1)


def test_sem_dados_com_poucos_anuncios_ou_de_outro_produto():
    assert v.comparar(PRODUTO, "lata 18 L", 800.0, anuncios("R$ 790,00")).status == "sem_dados"
    outro = anuncios("R$ 100,00", "R$ 110,00", titulo="Cimento CP II 50kg")
    assert v.comparar(PRODUTO, "lata 18 L", 800.0, outro).status == "sem_dados"
    assert v.comparar(PRODUTO, "lata 18 L", 800.0, anuncios("sob consulta", "R$ ?")).status == "sem_dados"


def test_sem_embalagem_conhecida_nao_afirma_nada():
    assert v.comparar(PRODUTO, None, 800.0, anuncios("R$ 800,00", "R$ 810,00")).status == "sem_dados"


def _cliente(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _limpa(monkeypatch):
    v._cache.clear()
    monkeypatch.setattr(v, "get_settings", lambda: NS(serper_keys=["k1"]))


def test_validar_confirma_e_manda_a_chave_e_o_pais():
    vistos = {}

    def handler(req: httpx.Request):
        vistos["chave"] = req.headers["X-API-KEY"]
        vistos["corpo"] = req.read().decode()
        return httpx.Response(200, json={"shopping": anuncios("R$ 790,00", "R$ 810,00")})

    async def rodar():
        async with _cliente(handler) as c:
            return await v.validar(resultado(800.0), c)

    r = asyncio.run(rodar())
    assert r.validacao.status == "confirmado" and r.confianca == "alta" and r.preco_emb_med == 800.0
    assert vistos["chave"] == "k1" and '"gl":"br"' in vistos["corpo"].replace(" ", "")


def test_divergente_rebaixa_a_confianca_mas_nao_troca_o_preco_nem_as_fontes():
    handler = lambda req: httpx.Response(200, json={"shopping": anuncios("R$ 300,00", "R$ 310,00")})

    async def rodar():
        async with _cliente(handler) as c:
            return await v.validar(resultado(800.0), c)

    r = asyncio.run(rodar())
    assert r.validacao.status == "divergente" and r.confianca == "baixa"
    assert r.preco_emb_med == 800.0 and r.fontes[0].dominio == "leroymerlin.com.br" and len(r.fontes) == 1


@pytest.mark.parametrize("resposta", [httpx.Response(500), httpx.Response(200, text="não é json"),
                                      httpx.Response(200, json={"outra_coisa": 1}), httpx.Response(401)])
def test_falhas_nao_derrubam_nem_mudam_o_resultado(resposta):
    async def rodar():
        async with _cliente(lambda req: resposta) as c:
            return await v.validar(resultado(), c)

    r = asyncio.run(rodar())
    assert r.confianca == "alta" and (r.validacao is None or r.validacao.status == "sem_dados")


def test_rede_fora_do_ar_devolve_o_resultado_intacto():
    def handler(req):
        raise httpx.ConnectError("sem rede")

    async def rodar():
        async with _cliente(handler) as c:
            return await v.validar(resultado(), c)

    r = asyncio.run(rodar())
    assert r.confianca == "alta" and r.validacao.status == "sem_dados"


def test_chave_recusada_tenta_a_proxima(monkeypatch):
    monkeypatch.setattr(v, "get_settings", lambda: NS(serper_keys=["ruim", "boa"]))
    usadas = []

    def handler(req):
        usadas.append(req.headers["X-API-KEY"])
        return httpx.Response(429) if req.headers["X-API-KEY"] == "ruim" else httpx.Response(
            200, json={"shopping": anuncios("R$ 790,00", "R$ 810,00")})

    async def rodar():
        async with _cliente(handler) as c:
            return await v.validar(resultado(800.0), c)

    assert asyncio.run(rodar()).validacao.status == "confirmado" and usadas == ["ruim", "boa"]


def test_so_valida_item_com_preco_de_verdade(monkeypatch):
    chamadas = []

    def handler(req):
        chamadas.append(1)
        return httpx.Response(200, json={"shopping": []})

    async def rodar(item):
        async with _cliente(handler) as c:
            return await v.validar(item, c)

    asyncio.run(rodar(resultado(estimativa=True)))
    asyncio.run(rodar(ResultadoItem(item_id="b", status="nao_encontrado", motivo="sem loja")))
    assert chamadas == []
    monkeypatch.setattr(v, "get_settings", lambda: NS(serper_keys=[]))
    asyncio.run(rodar(resultado()))
    assert chamadas == []


def test_mesma_consulta_nao_gasta_credito_duas_vezes():
    chamadas = []

    def handler(req):
        chamadas.append(1)
        return httpx.Response(200, json={"shopping": anuncios("R$ 790,00", "R$ 810,00")})

    async def rodar():
        async with _cliente(handler) as c:
            await v.validar(resultado(800.0), c)
            await v.validar(resultado(800.0), c)

    asyncio.run(rodar())
    assert len(chamadas) == 1


def test_chave_sem_credito_http_400_tenta_a_proxima():
    # medido em 08/11: a 1ª chave com saldo negativo respondia 400 "Not enough credits" e Shopping, Maps e fotos
    # de reserva ficavam vazios, embora as outras chaves tivessem crédito
    from src import serper
    serper._sem_credito.clear()
    usadas = []

    def handler(req):
        usadas.append(req.headers["X-API-KEY"])
        if req.headers["X-API-KEY"] == "sem":
            return httpx.Response(400, json={"message": "Not enough credits", "statusCode": 400})
        return httpx.Response(200, json={"ok": 1})

    async def rodar():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            a = await serper.post(c, "https://google.serper.dev/images", {"q": "x"}, ["sem", "boa"])
            b = await serper.post(c, "https://google.serper.dev/images", {"q": "x"}, ["sem", "boa"])
            return a, b

    a, b = asyncio.run(rodar())
    assert a == {"ok": 1} and b == {"ok": 1}
    assert usadas == ["sem", "boa", "boa"]   # na 2ª chamada a chave sem crédito já vai para o fim da fila
    serper._sem_credito.clear()


def test_http_400_de_consulta_invalida_nao_troca_de_chave():
    from src import serper
    serper._sem_credito.clear()
    usadas = []

    def handler(req):
        usadas.append(req.headers["X-API-KEY"])
        return httpx.Response(400, json={"message": "Query is required", "statusCode": 400})

    async def rodar():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await serper.post(c, "https://google.serper.dev/images", {"q": ""}, ["a", "b"])

    assert asyncio.run(rodar()) is None and usadas == ["a"]
