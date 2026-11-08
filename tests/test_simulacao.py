"""Modo gravação de vídeo (src/simulacao.py): reproduz pesquisas reais já feitas, com o protocolo da B."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from src import simulacao as sim
from src.modelos import ItemEntrada

GRAVACAO_TINTA = {
    "id": "velho-1", "orcamento_id": "orc-gravado", "status": "definido",
    "produto_normalizado": "Tinta Suvinil Toque de Seda Branco Neve 18L", "imagem_url": "https://x/tinta.jpg",
    "embalagem": "lata 18 L", "qtd_embalagens": 1, "preco_emb_min": 739.9, "preco_emb_med": 739.9,
    "preco_emb_max": 739.9, "confianca": "baixa", "estimativa": False,
    "fontes": [{"loja": "Telhanorte", "dominio": "telhanorte.com.br", "url": "https://www.telhanorte.com.br/p",
                "preco_embalagem": 739.9}],
    "pesquisa_detalhes": {"custo_usd": 0.0021, "tokens_entrada": 10, "tokens_saida": 5},
    "pergunta": None, "motivo": None, "preco_data": "2026-11-08T07:00:00+00:00",
}


class BancoFalso:
    def __init__(self, itens: list[ItemEntrada], reservar: bool = True):
        self.sb = NS()
        self._itens = itens
        self._reservar = reservar
        self.gravados: list = []
        self.marcados: list = []
        self.concluido: dict | None = None
        self.metricas_gravadas: dict | None = None
        self.custos: list = []

    async def reservar(self, orcamento_id):
        return self._reservar

    async def itens_para_pesquisar(self, orcamento_id):
        return self._itens

    async def item(self, item_id):
        return next((i for i in self._itens if i.id == item_id), None)

    async def gravar_item(self, r):
        self.gravados.append(r)

    async def marcar_item(self, item_id, campos):
        self.marcados.append((item_id, campos))

    async def concluir(self, orcamento_id, erro=None, custo_usd=None):
        self.concluido = {"erro": erro, "custo_usd": custo_usd}

    async def metricas(self, orcamento_id, campos):
        self.metricas_gravadas = campos

    async def orcamento_do_item(self, item_id):
        return "orc-novo"

    async def somar_custo(self, orcamento_id, usd):
        self.custos.append(usd)

    async def cep(self, orcamento_id):
        return None


@pytest.fixture(autouse=True)
def sem_pausa(monkeypatch):
    monkeypatch.setattr(sim, "_ritmo", lambda: 0.0)
    monkeypatch.setattr(sim, "custos_das_origens", lambda sb, ids: {i: 0.0021 for i in ids})
    chamadas = []

    async def fatia_c(orcamento_id):
        chamadas.append(orcamento_id)
        return ["resultado"]
    monkeypatch.setattr(sim, "_chamar_fatia_c", fatia_c)
    return chamadas


def test_reproduz_o_resultado_real_e_roda_a_fatia_c(monkeypatch, sem_pausa):
    tinta = ItemEntrada(id="novo-1", descricao="Tinta Suvinil Toque de Seda Branco Neve 18L", quantidade=18, unidade="l")
    monkeypatch.setattr(sim, "buscar_gravacao", lambda *a, **k: dict(GRAVACAO_TINTA))
    banco = BancoFalso([tinta])
    r = asyncio.run(sim.simular_orcamento("orc-novo", banco))
    assert r["status"] == "concluida" and r["reproduzidos"] == 1 and r["pesquisados"] == 0
    g = banco.gravados[0]
    assert g.item_id == "novo-1" and g.preco_emb_med == 739.9 and g.qtd_embalagens == 1
    assert g.fontes[0].url == "https://www.telhanorte.com.br/p" and g.imagem_url == "https://x/tinta.jpg"
    assert g.preco_data is not None   # preço "chega agora": não conta como reaproveitado no ganho
    assert banco.concluido == {"erro": None, "custo_usd": pytest.approx(0.0021)}
    assert sem_pausa == ["orc-novo"]   # logística, viabilidade e ganho calculados de verdade


def test_item_sem_gravacao_e_pesquisado_de_verdade(monkeypatch):
    a = ItemEntrada(id="a", descricao="Tinta Suvinil Toque de Seda Branco Neve 18L", quantidade=18, unidade="l")
    b = ItemEntrada(id="b", descricao="Item inédito", quantidade=1, unidade="un")
    monkeypatch.setattr(sim, "buscar_gravacao", lambda sb, d, *a, **k: dict(GRAVACAO_TINTA) if d.startswith("Tinta") else None)
    pesquisados = []

    async def pesquisar_itens(itens, ao_terminar=None, **kw):
        pesquisados.extend(i.id for i in itens)
        return []
    monkeypatch.setattr(sim, "pesquisar_itens", pesquisar_itens)
    banco = BancoFalso([a, b])
    r = asyncio.run(sim.simular_orcamento("orc-novo", banco))
    assert r["reproduzidos"] == 1 and r["pesquisados"] == 1 and pesquisados == ["b"]


def test_reserva_negada_nao_reproduz_nada(monkeypatch):
    monkeypatch.setattr(sim, "buscar_gravacao", lambda *a, **k: dict(GRAVACAO_TINTA))
    banco = BancoFalso([ItemEntrada(id="a", descricao="x", quantidade=1, unidade="un")], reservar=False)
    r = asyncio.run(sim.simular_orcamento("orc-novo", banco))
    assert r["status"] == "ja_em_andamento_ou_concluido" and banco.gravados == []


def test_responder_reproduz_a_resposta_gravada(monkeypatch, sem_pausa):
    pendente = ItemEntrada(id="t", descricao="Tinta acrílica fosca branca", quantidade=30, unidade="m2")
    vistas = []

    def buscar(sb, descricao, quantidade, unidade, **k):
        vistas.append((descricao, quantidade, unidade, k))
        return dict(GRAVACAO_TINTA)
    monkeypatch.setattr(sim, "buscar_gravacao", buscar)
    banco = BancoFalso([pendente])
    r = asyncio.run(sim.simular_repesquisa("t", "Tinta Suvinil Toque de Seda Branco Neve 18L", banco))
    assert r is not None and r.status == "definido" and r.pergunta is None
    assert vistas == [("Tinta Suvinil Toque de Seda Branco Neve 18L", 30, "m2", {"excluir_item": "t"})]
    assert banco.marcados[0][1]["status"] == "buscando"
    assert banco.marcados[0][1]["descricao"] == "Tinta Suvinil Toque de Seda Branco Neve 18L"
    assert sem_pausa == ["orc-novo"] and banco.custos == [pytest.approx(0.0021)]


def test_sem_gravacao_a_repesquisa_devolve_none_e_nao_mexe_no_item(monkeypatch):
    monkeypatch.setattr(sim, "buscar_gravacao", lambda *a, **k: None)
    banco = BancoFalso([ItemEntrada(id="t", descricao="x", quantidade=1, unidade="un")])
    assert asyncio.run(sim.simular_repesquisa("t", "outra coisa", banco)) is None
    assert banco.marcados == [] and banco.gravados == []


def test_agenda_um_a_um_e_ritmo_zero_sem_pausa():
    import random
    t = sim.agenda(5, 1.0, random.Random(1))
    assert all(b > a for a, b in zip(t, t[1:])) and t[0] >= sim.PRIMEIRO_ITEM_S
    assert sim.agenda(3, 0.0) == [0.0, 0.0, 0.0]


def test_busca_da_gravacao_filtra_descricao_quantidade_unidade_e_exclui_o_proprio():
    chamadas = []

    class Q:
        def __getattr__(self, nome):
            def f(*a, **k):
                chamadas.append((nome, a, k))
                return self
            return f

        def execute(self):
            return NS(data=[{"id": "1", **GRAVACAO_TINTA}])

    sb = NS(table=lambda t: Q())
    g = sim.buscar_gravacao(sb, " Tinta X ", 18.0, "l", excluir_orcamento="orc-novo")
    assert g is not None
    assert ("eq", ("descricao", "Tinta X"), {}) in chamadas and ("eq", ("quantidade", "18"), {}) in chamadas
    assert ("eq", ("unidade", "l"), {}) in chamadas and ("neq", ("orcamento_id", "orc-novo"), {}) in chamadas
    assert ("in_", ("status", list(sim.STATUS_FINAIS)), {}) in chamadas


def test_rota_simulada_valida_igual_a_real(monkeypatch):
    from src import rotas_orcamentos as ro
    from src.main import app
    monkeypatch.setattr(ro, "_supabase_ok", lambda: True)
    c = TestClient(app)
    assert c.post("/simulacao/orcamentos", json={}).status_code == 422


def test_falha_depois_da_reserva_conclui_como_falhou(monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("coluna não existe")
    monkeypatch.setattr(sim, "buscar_gravacao", quebra)
    banco = BancoFalso([ItemEntrada(id="a", descricao="x", quantidade=1, unidade="un")])
    r = asyncio.run(sim.simular_orcamento("orc-novo", banco))
    assert r["status"] == "falhou" and banco.concluido["erro"].startswith("RuntimeError")
