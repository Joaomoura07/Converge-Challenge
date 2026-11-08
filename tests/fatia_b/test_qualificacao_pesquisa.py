"""Dez materiais sintéticos: oferta correta e variante incompatível, sem rede/LLM real."""
import asyncio
from types import SimpleNamespace as NS

import pytest

from src.calculo import calcular
from src.config import get_settings
from src.modelos import ItemEntrada
from src.precos import Oferta, ResultadoExtracao
from test_etapa6_pesquisa import LLMFalso, mundo  # reutiliza busca/cache em memória


# id, pedido, anúncio correto, anúncio incompatível, embalagem anunciada
CASOS = [
    ("classe", "Argamassa Quartzolit AC-III cinza 20kg", "Argamassa Quartzolit AC-3 cinza 20kg", "Argamassa Quartzolit AC-II cinza 20kg", "20 kg"),
    ("cor", "Tomada Tramontina Liz branca 20A", "Tomada Tramontina Liz branco 20A", "Tomada Tramontina Liz preta 20A", "unidade"),
    ("material", "Cabo flexível SIL cobre 2,5mm² 750V", "Cabo flexível SIL cobre 2.5mm2 750V", "Cabo flexível SIL alumínio 2,5mm² 750V", "1 m"),
    ("conexao", "Joelho Tigre soldável 25mm", "Joelho Tigre soldavel 25mm", "Joelho Tigre roscável 25mm", "unidade"),
    ("referencia", "Spot Stella ref. STH123 7W 3000K", "Spot Stella STH123 7W 3000K", "Spot Stella STH124 7W 3000K", "unidade"),
    ("dimensao", "Porcelanato Portobello 60x60cm polido", "Porcelanato Portobello 600x600mm polido", "Porcelanato Portobello 60x60mm polido", "1 m²"),
    ("acessorio", "Bacia Deca Vogue Plus branca", "Bacia Deca Vogue Plus branco", "Assento para bacia Deca Vogue Plus branca", "unidade"),
    ("aplicacao", "Tinta Suvinil fosca uso externo 18L", "Tinta Suvinil fosca para exterior 18L", "Tinta Suvinil fosca uso interno 18L", "18 L"),
    ("marca_explicita", "Torneira marca TesteFlux modelo AX100 cromada", "Torneira TesteFlux AX100 cromada", "Torneira OutraFlux AX100 cromada", "unidade"),
    ("tensao", "Chuveiro Lorenzetti 220V 7500W", "Chuveiro Lorenzetti 220 V 7500 W", "Chuveiro Lorenzetti 127V 7500W", "unidade"),
]


def oferta(titulo, embalagem, **kw):
    return Oferta(loja="Loja sintética", dominio="loja.example", url="https://loja.example/produto",
                  titulo=titulo, preco=87.9, embalagem=embalagem, mesmo_produto="sim", **kw)


@pytest.mark.parametrize("caso,pedido,certo,errado,emb", CASOS, ids=[c[0] for c in CASOS])
def test_produto_correto_nao_e_descartado(caso, pedido, certo, errado, emb):
    item = ItemEntrada(id=caso, descricao=pedido, quantidade=1, unidade="un")
    assert calcular(item, ResultadoExtracao(ofertas=[oferta(certo, emb)]), generico=False).tem_preco


@pytest.mark.parametrize("caso,pedido,certo,errado,emb", CASOS, ids=[c[0] for c in CASOS])
def test_sim_incorreto_do_modelo_ou_cache_nao_confirma_variante(caso, pedido, certo, errado, emb):
    item = ItemEntrada(id=caso, descricao=pedido, quantidade=1, unidade="un")
    assert not calcular(item, ResultadoExtracao(ofertas=[oferta(errado, emb)]), generico=False).tem_preco


def test_cor_de_produto_relacionado_nao_corrige_titulo_incompativel():
    item = ItemEntrada(id="cor", descricao=CASOS[1][1], quantidade=1, unidade="un")
    o = oferta(CASOS[1][3], "unidade", evidencia="R$ 87,90. Veja também: Tomada Tramontina Liz branca 20A.")
    assert not calcular(item, ResultadoExtracao(ofertas=[o]), generico=False).tem_preco


@pytest.mark.parametrize("caso,pedido,certo,errado,emb", CASOS, ids=[c[0] for c in CASOS])
def test_shopping_aceita_equivalentes_e_rejeita_variantes(caso, pedido, certo, errado, emb):
    from src.google_shopping import MIN_MESMO, semelhanca
    assert semelhanca(pedido, certo) >= MIN_MESMO
    assert semelhanca(pedido, errado) < MIN_MESMO


@pytest.mark.parametrize("pedido,evidencia,confirma", [
    ("Produto ref:AB123", "Produto AB123", True),
    ("Produto ref. AB123", "Produto AB1234", False),
    ("Produto ref. AB123", "Produto AB123.4", False),
    ("Produto código 7", "Produto 7", True),
    ("Peça 2,5cm x 25mm", "Peça 25x25mm", True),
    ("Peça 25x25mm", "Peça 25x25cm", False),
    ("Peça 25x25mm", "Peça 25x25", False),
    ("Produto marca TesteFlux", "Produto TesteFluxx", False),
    ("Tinta fosca 18L", "Tinta acetinada 18L. Veja também tinta fosca 18L", False),
    ("Tomada branca 20A", "Tomada branca ou preta 20A", False),
])
def test_limites_de_referencia_dimensao_e_acabamento(pedido, evidencia, confirma):
    from src.especificacao import nao_confirmados
    titulo = evidencia.split(". Veja também")[0]
    assert (not nao_confirmados(pedido, evidencia, titulo=titulo)) is confirma


@pytest.mark.parametrize("caso,pedido,certo,errado,emb", CASOS, ids=[c[0] for c in CASOS])
def test_pesquisa_completa_qualifica_fontes_sem_servicos(caso, pedido, certo, errado, emb, monkeypatch):
    from src import pesquisa
    from src.busca import RespostaBusca, ResultadoWeb
    from src.precos import extrair_e_conferir

    monkeypatch.setattr(get_settings(), "pesquisa_hedge_ativo", False)
    async def criar(**kwargs):
        # Um modelo excessivamente otimista confirma as duas variantes: a guarda deve corrigir.
        return NS(usage=NS(prompt_tokens=100, completion_tokens=20, cost=0.0001),
                  choices=[NS(message=NS(content=f"0|87.90|{emb}|SIM\n1|87.90|{emb}|SIM"))])
    cliente = NS(chat=NS(completions=NS(create=criar)))
    async def buscar(consulta, produto):
        resultados = [ResultadoWeb(t, f"https://loja{i}.example/produto", f"loja{i}.example", f"Loja {i}", "R$ 87,90")
                      for i, t in enumerate([certo, errado])]
        return RespostaBusca(consulta, "sintetico"), await extrair_e_conferir(produto, resultados, cliente)
    async def vazio(*args, **kwargs):
        return []
    async def gravar(*args, **kwargs):
        pass
    monkeypatch.setattr(pesquisa, "buscar_e_extrair", buscar)
    monkeypatch.setattr(pesquisa, "ofertas_google", vazio)
    monkeypatch.setattr(pesquisa, "ofertas_regionais", vazio)
    monkeypatch.setattr(pesquisa.cache, "gravar", gravar)
    item = ItemEntrada(id=caso, descricao=pedido, quantidade=1, unidade="un")
    r = asyncio.run(pesquisa.pesquisar_item(item, usar_cache=False, usar_agente=False))
    assert r.status == "definido"
    assert [f.url for f in r.fontes] == ["https://loja0.example/produto"]
    assert r.pesquisa_detalhes["chamadas"] == 1


def test_so_similares_pede_especificacao_sem_confirmar(mundo):
    from src import pesquisa
    _, pedido, _, errado, emb = CASOS[0]
    mundo({}, padrao=[oferta(errado, emb)])
    item = ItemEntrada(id="classe", descricao=pedido, quantidade=1, unidade="un")
    r = asyncio.run(pesquisa.pesquisar_item(item, usar_cache=False, usar_agente=False))
    assert r.status == "pendente_especificacao" and r.estimativa
    assert r.pergunta and "classe" in r.pergunta


def test_agente_nao_para_por_lojas_que_o_calculo_rejeita(mundo, monkeypatch):
    from src import pesquisa
    monkeypatch.setattr(get_settings(), "featherless_api_keys", "chave-sintetica-teste")
    monkeypatch.setattr(get_settings(), "pesquisa_min_lojas", 2)
    monkeypatch.setattr(get_settings(), "pesquisa_max_refazer", 2)
    _, pedido, certo, _, emb = CASOS[1]
    # O modelo confirma produtos, mas os links abrem o buscador e não podem ser fontes.
    invalidas = [oferta(certo, emb).model_copy(update={"loja": f"Inválida {i}", "dominio": "google.com",
                 "url": f"https://www.google.com/search?q=tomada{i}"}) for i in range(3)]
    validas = [oferta(certo, emb).model_copy(update={"loja": f"Válida {i}", "dominio": f"loja{i}.example",
               "url": f"https://loja{i}.example/tomada"}) for i in range(2)]
    mundo({"refinar": invalidas, "diretas": validas})
    llm = LLMFalso([("buscar", pedido + " refinar"), ("buscar", pedido + " diretas")])
    item = ItemEntrada(id="tomada", descricao=pedido, quantidade=1, unidade="un")
    r = asyncio.run(pesquisa.pesquisar_item(item, usar_cache=False, cliente_llm=llm))
    assert r.status == "definido" and len(r.fontes) == 2
    assert r.iteracoes == 2 and llm.chamadas == 2
