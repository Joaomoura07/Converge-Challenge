"""Fechamento do backend (07/11, noite), a partir do teste como jurado no site publicado:
- item sem marca também passa pelo agente quando a estimativa tem poucas lojas;
- depois da resposta do arquiteto, o item não volta com a mesma pergunta;
- pesquisa com prazo total e item que falha ao gravar não ficam "buscando" para sempre;
- trace_url e tempo_ms gravados no fim; totais gravados pela Fatia C;
- viabilidade diz quanto da média é estimativa (a tela soma só os definidos);
- POST /agent/run desligado por padrão."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import src.orcamento as o
import src.pesquisa as p
from src.config import get_settings
from src.modelos import Fonte, ItemEntrada, ResultadoItem
from src.rotas_resultado import calcular_resultado
from src.viabilidade import calcular_viabilidade
from test_etapa6_pesquisa import LLMFalso, Mundo, of   # dublês da etapa 6
from test_etapa7_orcamento import BancoFalso

FONTE = Fonte(loja="Loja Tramontina", dominio="tramontina.com.br", url="https://t/liz", preco_embalagem=15.8)


@pytest.fixture
def mundo(monkeypatch):
    def montar(buscas, padrao=None):
        m = Mundo(buscas, None, padrao)
        monkeypatch.setattr(p, "buscar_e_extrair", m.buscar_e_extrair)
        monkeypatch.setattr(p.cache, "ler", m.ler)
        monkeypatch.setattr(p.cache, "gravar", m.gravar)
        return m
    return montar


# ---------------------------------------------------------------- agente também no item sem marca
def test_generico_com_uma_loja_passa_pelo_agente_e_continua_pendente(mundo):
    m = mundo({"tinta acrilica fosca 18l": [of("Telhanorte", 389.9, "lata 18 L", "parecido"),
                                             of("Sertão", 359.9, "lata 18 L", "parecido")]},
              padrao=[of("Loja Suvinil", 290.9, "galão 3,6 L", "parecido")])
    llm = LLMFalso([("buscar", "tinta acrilica fosca 18L"), ("fim", "FIM: simplifiquei")])
    item = ItemEntrada(id="g", descricao="Tinta acrílica fosca vermelha", quantidade=120, unidade="m2",
                       classificacao="pendente_especificacao")
    r = asyncio.run(p.pesquisar_item(item, cliente_llm=llm))
    assert llm.chamadas == 1 and r.iteracoes == 1 and m.consultas[1] == "tinta acrilica fosca 18L"
    assert r.status == "pendente_especificacao" and r.pergunta and r.estimativa   # não chuta marca
    assert len(r.fontes) >= 2


def test_generico_que_ja_tem_lojas_nao_gasta_agente(mundo):
    mundo({}, padrao=[of("Loja Suvinil", 290.9, "galão 3,6 L", "parecido"), of("Leroy Merlin", 89.9, "6 L", "parecido")])
    llm = LLMFalso([])
    item = ItemEntrada(id="g", descricao="Tinta acrílica fosca vermelha", quantidade=12, unidade="m2",
                       classificacao="pendente_especificacao")
    asyncio.run(p.pesquisar_item(item, cliente_llm=llm))
    assert llm.chamadas == 0


def test_resumo_do_agente_no_generico_conta_parecidos():
    c = p.Coleta()
    c.juntar([of("A", 10.0, igual="parecido"), of("B", 12.0, igual="sim"), of("C", 9.0, igual="nao")])
    assert c.lojas_conferidas() == 1 and c.lojas_conferidas(generico=True) == 2
    assert p.resumo_para_agente(c.ofertas, c, generico=True)["lojas_acumuladas"] == 2


# ---------------------------------------------------------------- depois da resposta do arquiteto
def _pendente_com_preco():
    return ResultadoItem(item_id="t", status="pendente_especificacao", estimativa=True, confianca="baixa",
                         pergunta="Não achamos à venda exatamente este produto. Qual marca e modelo exatos?",
                         motivo="só produtos parecidos", embalagem="unidade", qtd_embalagens=6,
                         preco_emb_min=15.8, preco_emb_med=15.8, preco_emb_max=15.8, fontes=[FONTE])


def test_resposta_do_arquiteto_vira_definido_com_aviso():
    r = p.aceitar_mais_proximo(_pendente_com_preco())
    assert r.status == "definido" and r.pergunta is None and r.confianca == "baixa" and r.estimativa
    assert "mais próximo" in r.motivo and r.fontes == [FONTE]


def test_resposta_sem_preco_nao_inventa_definido():
    sem = ResultadoItem(item_id="t", status="pendente_especificacao", pergunta="Qual marca?")
    assert p.aceitar_mais_proximo(sem) is sem


def test_repesquisar_com_resposta_nao_repete_a_pergunta(monkeypatch):
    async def pesquisar_item(item, **kw): return _pendente_com_preco()
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    banco = BancoFalso([ItemEntrada(id="t", descricao="Tomada Liz 20A", quantidade=6, unidade="un",
                                    classificacao="pendente_especificacao")])
    r = asyncio.run(o.repesquisar_item("t", "Tramontina Liz tomada 2P+T 20A branca", banco=banco))
    assert r.status == "definido" and r.pergunta is None and banco.gravados[-1].status == "definido"


def test_usar_a_media_tira_a_pendencia_e_mantem_estimativa_e_fontes():
    r = p.aceitar_media_estimada(_pendente_com_preco())
    assert r.status == "definido" and r.pergunta is None and r.estimativa and r.fontes == [FONTE]
    assert r.preco_emb_med == 15.8 and "média" in r.motivo and "aceita por você" in r.motivo


def test_usar_a_media_sem_preco_nao_inventa_definido():
    sem = ResultadoItem(item_id="t", status="pendente_especificacao", pergunta="Qual marca?")
    assert p.aceitar_media_estimada(sem) is sem


def test_repesquisar_aceitando_a_media_grava_definido_sem_mudar_a_descricao(monkeypatch):
    usou_cache = []
    async def pesquisar_item(item, **kw):
        usou_cache.append(kw["usar_cache"])
        assert item.descricao == "Tomada Liz 20A"   # o pedido do arquiteto não muda
        return _pendente_com_preco()
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    banco = BancoFalso([ItemEntrada(id="t", descricao="Tomada Liz 20A", quantidade=6, unidade="un",
                                    classificacao="pendente_especificacao")])
    r = asyncio.run(o.repesquisar_item("t", banco=banco, aceitar_media=True))
    assert usou_cache == [True]   # a média já pesquisada vale: não gasta busca nem LLM à toa
    assert r.status == "definido" and r.pergunta is None and banco.gravados[-1].status == "definido"


def test_rota_aceita_a_media_e_recusa_pedidos_misturados(monkeypatch):
    from src.main import app
    visto = {}
    async def repesquisar_item(item_id, nova_descricao=None, **kw):
        visto.update(item_id=item_id, nova_descricao=nova_descricao, **kw)
        return _pendente_com_preco()
    monkeypatch.setattr(o, "repesquisar_item", repesquisar_item)
    monkeypatch.setattr(get_settings(), "supabase_url", "http://x", raising=False)
    monkeypatch.setattr(get_settings(), "supabase_key", "k", raising=False)
    c = TestClient(app)
    assert c.post("/orcamento-itens/t/repesquisar", json={"aceitar_media": True}).status_code == 200
    assert visto == {"item_id": "t", "nova_descricao": None, "aceitar_media": True}
    assert c.post("/orcamento-itens/t/repesquisar", json={"aceitar_media": True, "objetivo": "preco"}).status_code == 422
    assert c.post("/orcamento-itens/t/repesquisar", json={"aceitar_media": True, "nova_descricao": "Suvinil"}).status_code == 422


def test_pesquisar_de_novo_sem_resposta_mantem_pendente(monkeypatch):
    async def pesquisar_item(item, **kw): return _pendente_com_preco()
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    banco = BancoFalso([ItemEntrada(id="t", descricao="Tomada Liz 20A", quantidade=6, unidade="un")])
    assert asyncio.run(o.repesquisar_item("t", banco=banco)).status == "pendente_especificacao"


# ---------------------------------------------------------------- estados presos
def test_item_que_passa_do_prazo_vira_erro_e_nao_fica_buscando(monkeypatch):
    async def fase_rapida(item, usar_agente, usar_cache):
        if item.id == "lento":
            await asyncio.sleep(5)
        return p.Rascunho(item, ResultadoItem(item_id=item.id, status="nao_encontrado", motivo="nada"))
    monkeypatch.setattr(p, "_fase_rapida", fase_rapida)
    monkeypatch.setattr(get_settings(), "pesquisa_prazo_total_s", 0.2)
    gravados = []
    async def gravar(r): gravados.append(r)
    itens = [ItemEntrada(id="rapido", descricao="x"), ItemEntrada(id="lento", descricao="y")]
    finais = asyncio.run(p.pesquisar_itens(itens, ao_terminar=gravar))
    assert [f.status for f in finais] == ["nao_encontrado", "erro"]
    assert finais[1].motivo == p.MOTIVO_SEM_TEMPO and {g.item_id for g in gravados} == {"rapido", "lento"}


def test_falha_ao_gravar_grava_erro_no_lugar(monkeypatch):
    async def fase_rapida(item, usar_agente, usar_cache):
        return p.Rascunho(item, ResultadoItem(item_id=item.id, status="nao_encontrado", motivo="nada"))
    monkeypatch.setattr(p, "_fase_rapida", fase_rapida)
    gravados = []
    async def gravar(r):
        if r.status != "erro":
            raise ConnectionError("supabase oscilou")
        gravados.append(r)
    asyncio.run(p.pesquisar_itens([ItemEntrada(id="a", descricao="x")], ao_terminar=gravar))
    assert [(g.item_id, g.status) for g in gravados] == [("a", "erro")]


# ---------------------------------------------------------------- métricas do orçamento
def test_conclusao_grava_tempo_e_link_do_trace(monkeypatch):
    async def fase_rapida(item, usar_agente, usar_cache):
        return p.Rascunho(item, ResultadoItem(item_id=item.id, status="nao_encontrado", motivo="nada"))
    monkeypatch.setattr(p, "_fase_rapida", fase_rapida)
    monkeypatch.setattr(o, "_link_do_trace", lambda: "https://us.cloud.langfuse.com/trace/abc")
    monkeypatch.setattr(o, "GANCHOS_FIM", [])
    banco = BancoFalso([ItemEntrada(id="a", descricao="x")])
    gravadas = {}
    async def metricas(orcamento_id, campos): gravadas.update(campos, orcamento_id=orcamento_id)
    banco.metricas = metricas
    asyncio.run(o.pesquisar_orcamento("orc-1", banco=banco))
    assert gravadas["trace_url"].endswith("/trace/abc") and gravadas["orcamento_id"] == "orc-1"
    assert isinstance(gravadas["tempo_ms"], int) and gravadas["tempo_ms"] >= 0


def test_sem_langfuse_grava_so_o_tempo(monkeypatch):
    monkeypatch.setattr(o, "_link_do_trace", lambda: None)
    banco = BancoFalso([])
    gravadas = {}
    async def metricas(orcamento_id, campos): gravadas.update(campos)
    banco.metricas = metricas
    asyncio.run(o._gravar_metricas(banco, "orc-1", 0.0))
    assert set(gravadas) == {"tempo_ms"}


# ---------------------------------------------------------------- Fatia C: totais e texto da viabilidade
ITENS_C = [
    {"status": "definido", "qtd_embalagens": 2, "preco_emb_min": 90, "preco_emb_med": 100, "preco_emb_max": 110,
     "fontes": [{"loja": "A", "dominio": "a.com.br", "url": "https://a", "preco_embalagem": 100}]},
    {"status": "pendente_especificacao", "estimativa": True, "qtd_embalagens": 1, "preco_emb_min": 40,
     "preco_emb_med": 50, "preco_emb_max": 60,
     "fontes": [{"loja": "B", "dominio": "b.com.br", "url": "https://b", "preco_embalagem": 50}]},
]


def test_viabilidade_explica_a_parte_estimada():
    v = calcular_viabilidade(ITENS_C, 1000)
    assert v.total_med == 250 and v.estimado_med == 50
    assert "inclui R$ 50,00 de estimativa para 1 item pendente" in v.resumo


def test_resultado_da_c_grava_os_totais():
    dados = calcular_resultado({"orcamento_cliente": 1000, "cep": "51020000"}, ITENS_C, [])
    assert (dados["total_min"], dados["total_med"], dados["total_max"]) == (220, 250, 280)
    assert dados["viabilidade"]["total_med"] == dados["total_med"]


# ---------------------------------------------------------------- /agent/run
def test_agent_run_desligado_por_padrao():
    from src.main import app
    r = TestClient(app).post("/agent/run", json={"task": "que horas são?"})
    assert r.status_code == 404


# ---------------------------------------------------------------- gravação com nova tentativa
class _SbFalso:
    """Imita supabase-py: as N primeiras gravações falham (falha passageira do banco)."""

    def __init__(self, falhas):
        self.falhas, self.gravadas = falhas, []

    def table(self, _):
        return self

    def update(self, linha):
        self.linha = linha
        return self

    def eq(self, *_):
        return self

    def execute(self):
        if self.falhas:
            self.falhas -= 1
            raise ConnectionError("Server disconnected")
        self.gravadas.append(self.linha)


def _r():
    return ResultadoItem(item_id="i", status="nao_encontrado", motivo="nada")


def test_gravacao_tenta_de_novo_depois_de_falha_passageira(monkeypatch):
    async def sem_espera(_): return None
    monkeypatch.setattr(o.asyncio, "sleep", sem_espera)
    sb = _SbFalso(falhas=2)
    asyncio.run(o.BancoSupabase(cliente=sb).gravar_item(_r()))
    assert len(sb.gravadas) == 1


def test_gravacao_desiste_depois_das_tentativas(monkeypatch):
    async def sem_espera(_): return None
    monkeypatch.setattr(o.asyncio, "sleep", sem_espera)
    with pytest.raises(ConnectionError):
        asyncio.run(o.BancoSupabase(cliente=_SbFalso(falhas=9)).gravar_item(_r()))
