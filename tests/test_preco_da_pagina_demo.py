"""Demo: o preço gravado junto ao link vem da página, sem usar cotações antigas."""
import pytest

from src import orcamento, pesquisa
from src.busca import RespostaBusca, ResultadoWeb
from src.config import get_settings
from src.orcamento import BancoSupabase
from src.paginas_produto import aprofundar, preco_claro_da_pagina
from src.precos import Oferta, ResultadoExtracao, ler_resposta
from test_fluxo_a_b_c import BancoMemoria, SupabaseMemoria, corpo, itens_do, mundo


@pytest.mark.parametrize(("pagina", "preco"), [
    ("De R$ 1.299,90 por R$ 999,90.\n10x de R$ 99,99\nR$ 949,90 no Pix", 999.9),
    ("Por R$ 90,00\nProdutos relacionados\nOutro item por R$ 12,99", 90),
    ("R$ 25,90\nR$ 29,90", None),
    ("10x de R$ 12,50\nCupom: R$ 95,90", None),
    ("No Pix\n\nR$ 95,90", None),
    ("De: R$ 130,00\nProduto indisponível", None),
    ("De: R$ 130,00", None),
    ("Produtos relacionados\nR$ 90,00", None),
])
def test_preco_claro_desconsidera_outras_condicoes(pagina, preco):
    assert preco_claro_da_pagina(pagina)[1] == preco


def test_demo_confere_pagina_e_repesquisa_sem_cache(mundo, monkeypatch):
    produto = "Tomada Tramontina Liz branca 20A"
    url = "https://loja.example/produto/tomada"
    url_shopping = "https://outraloja.example/produto/tomada"
    valor = 59.9
    paginas = []

    async def modo_demo(self, id_):
        return await BancoSupabase(SupabaseMemoria(self.bd)).modo_demo(id_)

    async def busca(consulta):
        return RespostaBusca(consulta, "simulado", [ResultadoWeb(f"{produto} R$ 19,90", url, "loja.example", "Loja", "R$ 19,90")])

    async def shopping(*args):
        return [Oferta(titulo=produto, url=url_shopping, dominio="outraloja.example", loja="Outra loja",
                       preco=29.9, embalagem="unidade", mesmo_produto="sim")]

    class Leitor:
        async def extract(self, urls, **kwargs):
            paginas.append(urls)
            venda = f"{valor:.2f}".replace(".", ",") if valor is not None else None
            texto = f"{produto}\nDe R$ 89,90 por R$ {venda}" if venda else f"{produto}\n10x de R$ 6,49"
            return {"results": [{"url": url, "raw_content": texto}]}

    async def ler(produto, resultados):
        return await aprofundar(produto, resultados, Leitor())

    async def extrair(produto, resultados):
        if valor is None:
            assert not resultados
            return ResultadoExtracao()
        assert [r.url for r in resultados] == [url]  # Shopping não respondeu à leitura
        ofertas, _ = ler_resposta(f"0|{valor:.2f}|unidade|SIM", resultados)
        velhas, _ = ler_resposta("0|89.90|unidade|SIM", resultados)
        assert velhas[0].preco is None  # preço antigo está escrito na página, mas não é o de venda
        return ResultadoExtracao(ofertas=ofertas)

    async def sem_regiao(*args):
        return []

    async def indevido(*args, **kwargs):
        pytest.fail("Demo não deve consultar o cache ou publicar preço da comparação do Shopping")

    monkeypatch.setattr(BancoMemoria, "modo_demo", modo_demo, raising=False)
    monkeypatch.setattr(orcamento, "pesquisar_itens", pesquisa.pesquisar_itens)
    monkeypatch.setattr(orcamento, "pesquisar_item", pesquisa.pesquisar_item)
    monkeypatch.setattr(orcamento, "validar_preco", indevido)
    monkeypatch.setattr(pesquisa, "buscar", busca)
    monkeypatch.setattr(pesquisa, "ofertas_google", shopping)
    monkeypatch.setattr(pesquisa, "ofertas_regionais", sem_regiao)
    monkeypatch.setattr(pesquisa, "aprofundar", ler)
    monkeypatch.setattr(pesquisa, "extrair_e_conferir", extrair)
    monkeypatch.setattr(pesquisa.cache, "ler", indevido)
    monkeypatch.setattr(pesquisa.cache, "gravar", indevido)
    monkeypatch.setattr(get_settings(), "pesquisa_paginas_por_rodada", 2)
    monkeypatch.setattr(get_settings(), "pesquisa_min_lojas", 1)
    monkeypatch.setattr(type(get_settings()), "llm_configured", property(lambda self: False))

    pedido = corpo(origem={"tipo": "manual", "modo": "manual", "demo": True}, itens=[
        {"id": "i", "linha": 1, "descricao": produto, "quantidade": 2, "unidade": "un"},
    ])
    resp = mundo.api.post("/orcamentos", json=pedido)
    assert resp.status_code == 200, resp.text
    item = itens_do(mundo.bd)["i"]
    assert [(f["url"], f["preco_anunciado"]) for f in item["fontes"]] == [(url, 59.9)]

    valor = 64.9
    resp = mundo.api.post(f"/orcamento-itens/{item['id']}/repesquisar")
    assert resp.status_code == 200, resp.text
    assert itens_do(mundo.bd)["i"]["fontes"][0]["preco_anunciado"] == 64.9
    valor = None
    resp = mundo.api.post(f"/orcamento-itens/{item['id']}/repesquisar")
    assert resp.status_code == 200, resp.text
    item = itens_do(mundo.bd)["i"]
    assert item["status"] == "nao_encontrado" and item["fontes"] == []
    assert item["preco_emb_med"] is None
    assert paginas == [[url, url_shopping]] * 3
