"""Etapa 7 — orçamento no banco: reserva (sem pesquisa dupla), lê itens 'buscando', grava cada item
assim que fica pronto, conclui/falha, chama a fatia C e o "Pesquisar de novo"."""

from __future__ import annotations

import asyncio
import json
import sys
import types
import uuid
from types import SimpleNamespace as NS

import pytest

import src.orcamento as o
import src.pesquisa as p
from src.modelos import ItemEntrada, ResultadoItem, Fonte


def resultado(item_id, status="definido"):
    if status == "definido":
        return ResultadoItem(item_id=item_id, status="definido", embalagem="lata 18 L", qtd_embalagens=2,
                             preco_emb_min=739.9, preco_emb_med=794.45, preco_emb_max=849.0, confianca="media",
                             premissa="rendimento ≈ 8 m²/L", fontes=[Fonte(loja="Telhanorte", dominio="telhanorte.com.br",
                                                                          url="https://t/a", preco_embalagem=739.9)])
    return ResultadoItem(item_id=item_id, status="nao_encontrado", motivo="nenhuma loja")


class BancoFalso:
    def __init__(self, itens, livre=True):
        self.itens, self.livre = {i.id: i for i in itens}, livre
        self.gravados: list[ResultadoItem] = []
        self.marcados: list[tuple] = []
        self.conclusao = None

    async def reservar(self, orcamento_id):
        ok, self.livre = self.livre, False
        return ok

    async def itens_para_pesquisar(self, orcamento_id): return list(self.itens.values())
    async def item(self, item_id): return self.itens.get(item_id)
    async def gravar_item(self, r): self.gravados.append(r)
    async def marcar_item(self, item_id, campos): self.marcados.append((item_id, campos))
    async def concluir(self, orcamento_id, erro=None, custo_usd=None):
        self.conclusao = ("falhou", erro) if erro else ("concluida", None)
        self.custo = custo_usd

    async def orcamento_do_item(self, item_id): return "orc-do-item"
    async def somar_custo(self, orcamento_id, usd): self.somado = (orcamento_id, usd)


@pytest.fixture
def pesquisa_falsa(monkeypatch):
    chamadas = []
    async def pesquisar_item(item, **kw):
        chamadas.append((item, kw))
        return resultado(item.id, "nao_encontrado" if "xyz" in item.descricao else "definido")
    async def fase_rapida(item, usar_agente, usar_cache):   # pesquisar_itens (2 fases) usa a fase 1 direto
        r = await pesquisar_item(item, usar_agente=usar_agente, usar_cache=usar_cache)
        return p.Rascunho(item, r)
    monkeypatch.setattr("src.pesquisa.pesquisar_item", pesquisar_item)
    monkeypatch.setattr("src.pesquisa._fase_rapida", fase_rapida)
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    return chamadas


ITENS = [ItemEntrada(id="a", descricao="Tinta Suvinil 18L", quantidade=180, unidade="m2"),
         ItemEntrada(id="b", descricao="produto xyz inexistente", quantidade=1, unidade="un")]


# ---------------------------------------------------------------- fluxo
def test_pesquisa_grava_cada_item_e_conclui(pesquisa_falsa):
    banco = BancoFalso(ITENS)
    r = asyncio.run(o.pesquisar_orcamento("orc-1", banco=banco))
    assert r["status"] == "concluida" and r["por_status"] == {"definido": 1, "nao_encontrado": 1}
    assert sorted(x.item_id for x in banco.gravados) == ["a", "b"] and banco.conclusao == ("concluida", None)


def test_segundo_clique_nao_pesquisa_de_novo(pesquisa_falsa):
    banco = BancoFalso(ITENS, livre=False)
    r = asyncio.run(o.pesquisar_orcamento("orc-1", banco=banco))
    assert r["status"] == "ja_em_andamento_ou_concluido" and pesquisa_falsa == [] and banco.conclusao is None


def test_erro_geral_marca_falhou_para_liberar_novo_clique(pesquisa_falsa):
    banco = BancoFalso(ITENS)
    async def quebra(_): raise ConnectionError("supabase fora")
    banco.itens_para_pesquisar = quebra
    r = asyncio.run(o.pesquisar_orcamento("orc-1", banco=banco))
    assert r["status"] == "falhou" and banco.conclusao[0] == "falhou" and "supabase fora" in banco.conclusao[1]


def test_chama_a_fatia_c_no_fim_quando_ela_existe(pesquisa_falsa, monkeypatch):
    chamados = []
    mod = types.ModuleType("src.rotas_resultado")
    def resultado_c(orcamento_id): chamados.append(("resultado", orcamento_id))   # síncrona, como a da fatia C
    mod.resultado = resultado_c
    monkeypatch.setitem(sys.modules, "src.rotas_resultado", mod)
    r = asyncio.run(o.pesquisar_orcamento("orc-9", banco=BancoFalso(ITENS)))
    assert chamados == [("resultado", "orc-9")] and r["fatia_c"] == ["resultado"]


def test_falha_da_fatia_c_nao_derruba_a_pesquisa(pesquisa_falsa, monkeypatch):
    mod = types.ModuleType("src.rotas_resultado")
    def resultado_c(orcamento_id): raise ValueError("bug da C")
    mod.resultado = resultado_c
    monkeypatch.setitem(sys.modules, "src.rotas_resultado", mod)
    r = asyncio.run(o.pesquisar_orcamento("orc-9", banco=BancoFalso(ITENS)))
    assert r["status"] == "concluida" and r["fatia_c"] == []


def test_custo_do_llm_e_somado_e_gravado_ao_concluir(monkeypatch):
    from src import custo
    async def pesquisar_itens(itens, ao_terminar=None, **kw):   # não usa a rede
        custo.registrar(0.01)       # extração
        custo.registrar("0.005")    # agente (a Featherless devolve número ou texto)
        custo.registrar(None)       # sem custo informado
        return [resultado(i.id) for i in itens]
    monkeypatch.setattr(o, "pesquisar_itens", pesquisar_itens)
    banco = BancoFalso(ITENS[:1])
    asyncio.run(o.pesquisar_orcamento("orc-1", banco=banco))
    assert banco.custo == pytest.approx(0.015)


def test_repesquisar_soma_custo_e_recalcula_o_resultado(monkeypatch):
    from src import custo
    chamados = []
    mod = types.ModuleType("src.rotas_resultado")
    mod.resultado = lambda oid: chamados.append(oid)
    monkeypatch.setitem(sys.modules, "src.rotas_resultado", mod)
    async def pesquisar_item(item, **kw):
        custo.registrar(0.02)
        return resultado(item.id)
    monkeypatch.setattr(o, "pesquisar_item", pesquisar_item)
    banco = BancoFalso(ITENS[:1])
    asyncio.run(o.repesquisar_item("a", banco=banco))
    assert banco.somado == ("orc-do-item", pytest.approx(0.02)) and chamados == ["orc-do-item"]


def test_registrar_fora_de_um_orcamento_nao_faz_nada():
    from src import custo
    custo.registrar(1.0)   # sem acumulador ativo: não levanta nem acumula


def test_repesquisar_com_a_resposta_do_arquiteto(pesquisa_falsa):
    banco = BancoFalso([ItemEntrada(id="t", descricao="Tinta acrílica fosca vermelha", quantidade=12, unidade="m2",
                                    classificacao="pendente_especificacao")])
    r = asyncio.run(o.repesquisar_item("t", nova_descricao="Tinta Suvinil Fosco Completo Vermelho Cardinal 3,6L", banco=banco))
    item, kw = pesquisa_falsa[0]
    assert item.descricao.startswith("Tinta Suvinil Fosco") and item.classificacao == "definido" and kw["usar_cache"] is False
    assert banco.marcados[0][1]["status"] == "buscando" and banco.gravados[0] == r


# ---------------------------------------------------------------- serialização e SQL do Supabase
def _cliente_api(monkeypatch, repesquisar, supabase=True):
    from fastapi.testclient import TestClient
    import src.main as m
    monkeypatch.setattr(o, "repesquisar_item", repesquisar)
    monkeypatch.setattr(type(m.settings), "supabase_configured", property(lambda self: supabase))
    return TestClient(m.app)


def test_rota_repesquisar_com_e_sem_resposta_do_arquiteto(monkeypatch):
    chamadas = []
    async def repesquisar(item_id, nova_descricao=None, **kw):
        chamadas.append((item_id, nova_descricao))
        return resultado(item_id) if item_id != "nao-existe" else None
    api = _cliente_api(monkeypatch, repesquisar)

    r = api.post("/orcamento-itens/a/repesquisar")                       # "Pesquisar de novo" (sem corpo)
    assert r.status_code == 200 and r.json()["status"] == "definido" and r.json()["fontes"]
    r = api.post("/orcamento-itens/a/repesquisar", json={"nova_descricao": "Tinta Suvinil fosco vermelho 3,6L"})
    assert r.status_code == 200 and chamadas[-1] == ("a", "Tinta Suvinil fosco vermelho 3,6L")
    assert api.post("/orcamento-itens/nao-existe/repesquisar").status_code == 404
    assert api.post("/orcamento-itens/a/repesquisar", json={"nova_descricao": "x"}).status_code == 422
    assert api.post("/orcamento-itens/a/repesquisar", json={"outra": 1}).status_code == 200   # campo extra ignorado


def test_rota_repesquisar_sem_supabase_responde_503(monkeypatch):
    async def repesquisar(*a, **k): raise AssertionError("não deveria pesquisar")
    api = _cliente_api(monkeypatch, repesquisar, supabase=False)
    assert api.post("/orcamento-itens/a/repesquisar").status_code == 503


def test_linha_do_resultado_e_json_valido_para_o_banco():
    linha = o.linha_do_resultado(resultado("a"))
    json.dumps(linha)   # jsonb/timestamptz: tudo serializável
    assert "item_id" not in linha and linha["fontes"][0]["dominio"] == "telhanorte.com.br"
    assert set(linha) == set(o.COLUNAS_GRAVADAS)


def test_colunas_combinadas_com_a_fatia_a():
    combinadas = {"status", "produto_normalizado", "imagem_url", "embalagem", "unidade_preco", "pergunta", "motivo",
                  "qtd_embalagens", "iteracoes", "preco_emb_min", "preco_emb_med", "preco_emb_max", "preco_un_min",
                  "preco_un_med", "preco_un_max", "confianca", "estimativa", "fontes", "preco_data", "atualizado_em"}
    novas = set(o.COLUNAS_GRAVADAS) - combinadas
    assert novas == {"premissa", "validacao"}, f"coluna nova precisa ser avisada ao Samuel: {novas}"


class SupabaseGravador:
    """Grava a cadeia de chamadas do supabase-py para conferir o SQL que vai para o PostgREST."""
    def __init__(self, dados): self.chamadas, self.dados = [], dados
    def table(self, nome): self.chamadas.append(("table", nome)); return self
    def __getattr__(self, nome):
        def metodo(*a, **k):
            self.chamadas.append((nome, a))
            return NS(data=self.dados) if nome == "execute" else self
        return metodo


def test_reserva_e_um_update_condicional_atomico():
    sb = SupabaseGravador([{"id": "orc-1"}])
    assert asyncio.run(o.BancoSupabase(sb).reservar("orc-1"))
    nomes = [c[0] for c in sb.chamadas]
    assert nomes == ["table", "update", "eq", "or_", "execute"]
    filtro = sb.chamadas[3][1][0]
    assert filtro.startswith("status_pesquisa.in.(pendente,falhou),and(status_pesquisa.eq.pesquisando,pesquisa_iniciada_em.lt.")
    assert not asyncio.run(o.BancoSupabase(SupabaseGravador([])).reservar("orc-1"))


def test_pesquisa_viva_nao_e_reassumida_antes_do_fim_da_funcao():
    """A janela que libera um orçamento 'pesquisando' precisa passar do tempo máximo da função na Vercel (300 s).
    Antes era 3 min: uma pesquisa viva de 200 s podia ser reassumida por outro clique e as duas gravariam."""
    from datetime import datetime, timezone
    assert o.JANELA_TRAVADO > o.TEMPO_MAXIMO_FUNCAO
    sb = SupabaseGravador([{"id": "orc-1"}])
    antes = datetime.now(timezone.utc)
    asyncio.run(o.BancoSupabase(sb).reservar("orc-1"))
    corte = datetime.fromisoformat(sb.chamadas[3][1][0].rsplit("pesquisa_iniciada_em.lt.", 1)[1].rstrip(")"))
    assert (antes - corte).total_seconds() >= 300, "pesquisa iniciada há 200 s ainda está viva e não pode ser liberada"


@pytest.mark.parametrize("da_a,na_b", [("pendente", "pendente_especificacao"), ("definido", "definido"),
                                       ("pendente_especificacao", "pendente_especificacao"), ("outra", None), (None, None)])
def test_classificacao_do_banco_da_fatia_a(da_a, na_b):
    """Achado real (07/11): o SQL da A grava 'pendente' (itens_classificacao_ck); antes virava None e o item
    genérico era pesquisado como definido, sem a pergunta ao arquiteto."""
    linha = {"id": 1, "descricao": "Tinta vermelha", "quantidade": 12, "unidade": "m2", "classificacao": da_a}
    assert o.item_da_linha(linha).classificacao == na_b


def test_gravar_item_tira_coluna_que_o_banco_nao_tem():
    """Achado real (07/11): orcamento_itens veio sem `premissa`; sem a reserva, o item ficava 'buscando' para sempre."""
    class Sb(SupabaseGravador):
        def __getattr__(self, nome):
            if nome == "update":
                def update(linha):
                    self.chamadas.append(("update", (dict(linha),)))
                    self.recusar = "premissa" in linha
                    return self
                return update
            if nome == "execute" and getattr(self, "recusar", False):
                def falha():
                    raise Exception({"message": "Could not find the 'premissa' column of 'orcamento_itens' in the schema cache",
                                     "code": "PGRST204"})
                return falha
            return super().__getattr__(nome)
    sb = Sb([])
    banco = o.BancoSupabase(sb)
    asyncio.run(banco.gravar_item(resultado("a")))
    asyncio.run(banco.gravar_item(resultado("b")))
    updates = [c[1][0] for c in sb.chamadas if c[0] == "update"]
    assert "premissa" in updates[0] and "premissa" not in updates[1] and updates[1]["preco_emb_med"] == 794.45
    assert len(updates) == 3, "o 2º item já sai sem a coluna (não tenta de novo)"


def test_le_so_itens_buscando_do_orcamento():
    sb = SupabaseGravador([{"id": 7, "orcamento_id": "o", "descricao": "Cuba 56x34", "quantidade": "1", "unidade": "un",
                            "categoria": None, "classificacao": "qualquer", "status": "buscando"}])
    itens = asyncio.run(o.BancoSupabase(sb).itens_para_pesquisar("o"))
    assert ("eq", ("status", "buscando")) in sb.chamadas and ("eq", ("orcamento_id", "o")) in sb.chamadas
    assert itens[0].id == "7" and itens[0].quantidade == 1.0 and itens[0].classificacao is None


# ---------------------------------------------------------------- real (Supabase, tabelas da fatia A)
@pytest.mark.real
def test_etapa7_orcamento_real_no_supabase():
    from src.database import get_supabase
    sb = get_supabase()
    # `premissa` é a coluna nova avisada à fatia A: sem ela o item é gravado sem a premissa (BancoSupabase.gravar_item)
    exigidas = o.COLUNAS_LIDAS + [c for c in o.COLUNAS_GRAVADAS if c != "premissa"]
    try:
        sb.table("orcamento_itens").select(",".join(exigidas)).limit(1).execute()
        sb.table("orcamentos").select("id,status_pesquisa,pesquisa_iniciada_em,pesquisa_concluida_em,pesquisa_erro").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"tabelas/colunas da fatia A ainda não existem: {str(exc)[:160]}")
    # Orçamento sintético com as colunas obrigatórias do SQL da fatia A (medido em 07/11)
    orc_id = str(uuid.uuid4())
    sb.table("orcamentos").insert({"id": orc_id, "nome": "TESTE etapa7 (sintético)", "cep": "50030230",   # orcamentos_cep_ck: só dígitos
                                   "orcamento_cliente": 10000, "origem": {"teste": "etapa7"},
                                   "hash_conteudo": f"teste-{orc_id}", "qtd_itens": 2}).execute()
    orc = {"id": orc_id}
    def item(n, descricao, qtd, classificacao):
        return {"orcamento_id": orc_id, "id_linha": str(n), "linha": n, "descricao_original": descricao,
                "descricao": descricao, "quantidade": qtd, "unidade": "m2", "extras": {}, "classificacao": classificacao,
                "fontes": []}
    try:
        sb.table("orcamento_itens").insert([
            item(1, "Argamassa Quartzolit AC-III cinza 20kg", 48, "definido"),
            item(2, "Tinta acrílica fosca vermelha", 12, "pendente")]).execute()   # itens_classificacao_ck
        r = asyncio.run(o.pesquisar_orcamento(orc["id"]))
        assert r["status"] == "concluida" and r["itens"] == 2, r
        linhas = sb.table("orcamento_itens").select("*").eq("orcamento_id", orc["id"]).execute().data
        assert {x["status"] for x in linhas} <= {"definido", "pendente_especificacao"}, linhas
        assert all(x["fontes"] for x in linhas if x["preco_emb_med"] is not None)
        assert any(x["preco_emb_med"] is not None for x in linhas), "nenhum item gravou preço"
        pendente = next(x for x in linhas if x["classificacao"] == "pendente")
        assert pendente["status"] == "pendente_especificacao", pendente
        assert pendente["pergunta"], "item genérico precisa da pergunta ao arquiteto"
        cab = sb.table("orcamentos").select("status_pesquisa,pesquisa_concluida_em").eq("id", orc_id).execute().data[0]
        assert cab["status_pesquisa"] == "concluida" and cab["pesquisa_concluida_em"]
        assert asyncio.run(o.pesquisar_orcamento(orc["id"]))["status"] == "ja_em_andamento_ou_concluido"
    finally:
        sb.table("orcamento_itens").delete().eq("orcamento_id", orc["id"]).execute()
        sb.table("orcamentos").delete().eq("id", orc["id"]).execute()
