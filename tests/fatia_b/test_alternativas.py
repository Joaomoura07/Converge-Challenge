"""Pesquisar de novo com objetivo: maior qualidade, menor preço ou semelhante de outra marca.
O LLM só sugere o nome; a pesquisa confere nas lojas; o código decide se troca ou devolve o anterior."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from types import SimpleNamespace as NS

import pytest

import src.orcamento as o
from src import custo
from src.alternativas import Alternativa, AlternativaIndisponivel, decidir, sugerir_alternativa
from src.modelos import Fonte, ItemEntrada, ResultadoItem

from test_etapa7_orcamento import BancoFalso, _cliente_api, resultado


def cliente(conteudo: str | Exception, custo_usd=0.001):
    chamadas = []
    def create(**kw):
        chamadas.append(kw)
        if isinstance(conteudo, Exception):
            raise conteudo
        return NS(choices=[NS(message=NS(content=conteudo))],
                  usage=NS(prompt_tokens=10, completion_tokens=5, cost=custo_usd))
    c = NS(chat=NS(completions=NS(create=create)))
    c.chamadas = chamadas
    return c


def tinta(item_id="a", produto="Tinta Suvinil Toque de Seda branco 18 L", un=4.5, emb=740.0):
    return ResultadoItem(item_id=item_id, status="definido", produto_normalizado=produto, embalagem="lata 18 L",
                         qtd_embalagens=2, preco_emb_min=emb, preco_emb_med=emb, preco_emb_max=emb,
                         preco_un_min=un, preco_un_med=un, preco_un_max=un, unidade_preco="m2", confianca="media",
                         fontes=[Fonte(loja="Leroy Merlin", dominio="leroymerlin.com.br", url=f"https://l/{produto}",
                                       preco_embalagem=emb)])


# ---------------------------------------------------------------- sugestão do LLM
def test_sugere_produto_e_manda_o_objetivo_ao_modelo():
    c = cliente('{"produto": "Tinta Coral Rende Muito fosco branco 18 L", "por_que": "Linha de entrada da Coral."}')
    alt = sugerir_alternativa("Tinta Suvinil Toque de Seda branco 18 L", "preco", categoria="Pintura", client=c, model="m")
    assert alt == Alternativa("Tinta Coral Rende Muito fosco branco 18 L", "Linha de entrada da Coral.")
    pedido = json.loads(c.chamadas[0]["messages"][1]["content"])
    assert pedido == {"produto_atual": "Tinta Suvinil Toque de Seda branco 18 L", "objetivo": "preco", "categoria": "Pintura",
                      "faixa_de_preco": "mais barata que a atual"}
    assert c.chamadas[0]["max_tokens"] >= 2000   # GLM pensa antes: limite baixo devolve vazio


@pytest.mark.parametrize("conteudo", [
    '{"produto": null}',                                             # modelo diz que não há alternativa
    '{"produto": "Tinta Suvinil Toque de Seda branco 18 L"}',        # repetiu o atual
    '{"produto": "Tinta X por R$ 199"}',                             # preço inventado
    "não sei",                                                       # sem JSON
    "",                                                              # resposta vazia
    TimeoutError("featherless"),                                     # rede
])
def test_qualquer_falha_vira_indisponivel(conteudo):
    with pytest.raises(AlternativaIndisponivel):
        sugerir_alternativa("Tinta Suvinil Toque de Seda branco 18 L", "semelhante", client=cliente(conteudo), model="m")


def test_frase_com_numero_e_descartada():
    c = cliente('{"produto": "Tinta Coral Rende Muito branco 18 L", "por_que": "Sai 30% mais barata."}')
    assert sugerir_alternativa("Tinta Suvinil", "preco", client=c, model="m").por_que == ""


def test_custo_do_llm_entra_no_acumulador():
    with custo.acumular() as acc:
        sugerir_alternativa("Tinta Suvinil", "qualidade", client=cliente('{"produto": "Tinta Suvinil Premium 18 L"}', 0.003), model="m")
    assert acc.usd == pytest.approx(0.003)


# ---------------------------------------------------------------- decisão (código, não LLM)
ALT = Alternativa("Tinta Coral Rende Muito branco 18 L", "Linha de entrada da Coral.")


def test_menor_preco_que_saiu_mais_barata_troca_e_explica():
    final, trocou = decidir(tinta(produto=ALT.produto, un=3.2, emb=520.0), tinta(), ALT, "preco", "Tinta branca 18 L")
    assert trocou and final.produto_normalizado == ALT.produto
    assert final.motivo.startswith('Alternativa de menor preço ao pedido "Tinta branca 18 L".')
    assert "R$ 3,20/m² contra R$ 4,50/m² do anterior" in final.motivo


def test_menor_preco_que_saiu_mais_cara_devolve_o_anterior():
    anterior = tinta()
    final, trocou = decidir(tinta(produto=ALT.produto, un=5.0, emb=820.0), anterior, ALT, "preco", "x")
    assert not trocou and final.produto_normalizado == anterior.produto_normalizado
    assert final.preco_emb_med == anterior.preco_emb_med and "não saiu mais barata" in final.motivo


def test_alternativa_nao_encontrada_devolve_o_anterior():
    final, trocou = decidir(resultado("a", "nao_encontrado"), tinta(), ALT, "qualidade", "x")
    assert not trocou and final.status == "definido" and "não foi encontrada à venda" in final.motivo


def test_sem_resultado_anterior_fica_com_o_que_a_pesquisa_achou():
    nao = resultado("a", "nao_encontrado")
    assert decidir(nao, None, ALT, "semelhante", "x") == (nao, True)


def test_qualidade_troca_mesmo_mais_cara():
    final, trocou = decidir(tinta(produto="Suvinil Premium", un=6.0), tinta(), ALT, "qualidade", "x")
    assert trocou and "maior qualidade" in final.motivo


# ---------------------------------------------------------------- repesquisar_item com objetivo
class BancoComResultado(BancoFalso):
    def __init__(self, itens, atual):
        super().__init__(itens)
        self.atual = atual

    async def resultado_atual(self, item_id): return self.atual


@pytest.fixture
def sem_fatia_c(monkeypatch):
    mod = types.ModuleType("src.rotas_resultado")
    mod.resultado = lambda oid: None
    monkeypatch.setitem(sys.modules, "src.rotas_resultado", mod)


ITEM = ItemEntrada(id="a", descricao="Tinta acrílica branca 18 L", quantidade=180, unidade="m2", categoria="Pintura",
                   classificacao="pendente_especificacao")


def test_repesquisar_pesquisa_a_alternativa_sem_mudar_a_descricao_do_arquiteto(monkeypatch, sem_fatia_c):
    pedidos, buscas = [], []
    def sugerir(atual, objetivo, categoria=None, **_):
        pedidos.append((atual, objetivo, categoria))
        return ALT
    async def pesquisar_item(item, **kw):
        buscas.append((item, kw))
        return tinta(item.id, produto=item.descricao, un=3.0)
    monkeypatch.setattr(o, "sugerir_alternativa", sugerir)
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    banco = BancoComResultado([ITEM], tinta())
    r = asyncio.run(o.repesquisar_item("a", banco=banco, objetivo="preco"))
    assert pedidos == [("Tinta Suvinil Toque de Seda branco 18 L", "preco", "Pintura")]   # parte do que a tela mostra
    item, kw = buscas[0]
    assert item.descricao == ALT.produto and item.classificacao == "definido" and kw["usar_cache"] is False
    assert "descricao" not in banco.marcados[0][1]          # a descrição do arquiteto fica no banco como estava
    assert r.produto_normalizado == ALT.produto and banco.gravados == [r] and "menor preço" in r.motivo


def test_llm_fora_nao_toca_no_item(monkeypatch, sem_fatia_c):
    def sugerir(*a, **k): raise AlternativaIndisponivel("fora")
    async def pesquisar_item(item, **kw): raise AssertionError("não deveria pesquisar")
    monkeypatch.setattr(o, "sugerir_alternativa", sugerir)
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    banco = BancoComResultado([ITEM], tinta())
    with pytest.raises(AlternativaIndisponivel):
        asyncio.run(o.repesquisar_item("a", banco=banco, objetivo="semelhante"))
    assert banco.marcados == [] and banco.gravados == []


def test_banco_sem_resultado_atual_usa_a_descricao(monkeypatch, sem_fatia_c):
    pedidos = []
    monkeypatch.setattr(o, "sugerir_alternativa", lambda atual, objetivo, categoria=None, **_: pedidos.append(atual) or ALT)
    async def pesquisar_item(item, **kw): return tinta(item.id, produto=item.descricao)
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    asyncio.run(o.repesquisar_item("a", banco=BancoFalso([ITEM]), objetivo="qualidade"))
    assert pedidos == ["Tinta acrílica branca 18 L"]


# ---------------------------------------------------------------- rota
def test_rota_aceita_objetivo_e_recusa_combinacoes_invalidas(monkeypatch):
    chamadas = []
    async def repesquisar(item_id, nova_descricao=None, **kw):
        chamadas.append((item_id, nova_descricao, kw))
        return resultado(item_id)
    api = _cliente_api(monkeypatch, repesquisar)
    for objetivo in ("qualidade", "preco", "semelhante"):
        assert api.post("/orcamento-itens/a/repesquisar", json={"objetivo": objetivo}).status_code == 200
        assert chamadas[-1] == ("a", None, {"objetivo": objetivo})
    assert api.post("/orcamento-itens/a/repesquisar", json={"objetivo": "barato"}).status_code == 422
    assert api.post("/orcamento-itens/a/repesquisar",
                    json={"objetivo": "preco", "nova_descricao": "Tinta Coral 18 L"}).status_code == 422
    api.post("/orcamento-itens/a/repesquisar")
    assert chamadas[-1] == ("a", None, {})   # sem objetivo: igual a antes


def test_rota_responde_503_quando_a_ia_nao_sugere(monkeypatch):
    async def repesquisar(*a, **k): raise AlternativaIndisponivel("fora")
    r = _cliente_api(monkeypatch, repesquisar).post("/orcamento-itens/a/repesquisar", json={"objetivo": "preco"})
    assert r.status_code == 503 and "ficou como estava" in r.json()["detail"]


# ---------------------------------------------------------------- leitura do resultado atual no Supabase
def test_banco_supabase_le_o_resultado_atual_do_item():
    from test_etapa7_orcamento import SupabaseGravador
    linha = {"id": "a", **o.linha_do_resultado(tinta())}
    linha.pop("atualizado_em")
    linha["pergunta"] = None
    sb = SupabaseGravador([linha])
    r = asyncio.run(o.BancoSupabase(sb).resultado_atual("a"))
    assert r == tinta()
    colunas = sb.chamadas[1][1][0].split(",")
    assert colunas[0] == "id" and "atualizado_em" not in colunas and "fontes" in colunas


@pytest.mark.parametrize("dados", [[], [{"id": "a", "status": "buscando"}], [{"id": "a", "status": "definido"}]])
def test_resultado_atual_invalido_ou_ausente_e_none(dados):
    """'buscando' ou 'definido' sem preço não formam um ResultadoItem válido: nada para devolver."""
    from test_etapa7_orcamento import SupabaseGravador
    assert asyncio.run(o.BancoSupabase(SupabaseGravador(dados)).resultado_atual("a")) is None


def test_modelo_frio_cai_no_reserva_uma_vez():
    modelos = []
    def create(**kw):
        modelos.append(kw["model"])
        if len(modelos) == 1:
            raise RuntimeError("400 model is loading")
        return NS(choices=[NS(message=NS(content='{"produto": "Argamassa Votoran AC-III cinza 20 kg"}'))], usage=None)
    c = NS(chat=NS(completions=NS(create=create)))
    alt = sugerir_alternativa("Argamassa Quartzolit AC-III cinza 20 kg", "semelhante", client=c)
    assert alt.produto == "Argamassa Votoran AC-III cinza 20 kg"
    assert len(modelos) == 2 and modelos[0] != modelos[1]


def test_sem_alternativa_razoavel_nao_tenta_outro_modelo():
    modelos = []
    def create(**kw):
        modelos.append(kw["model"])
        return NS(choices=[NS(message=NS(content='{"produto": null}'))], usage=None)
    with pytest.raises(AlternativaIndisponivel):
        sugerir_alternativa("Argamassa", "preco", client=NS(chat=NS(completions=NS(create=create))))
    assert len(modelos) == 1
