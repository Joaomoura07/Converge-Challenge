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
    async def concluir(self, orcamento_id, erro=None): self.conclusao = ("falhou", erro) if erro else ("concluida", None)


@pytest.fixture
def pesquisa_falsa(monkeypatch):
    chamadas = []
    async def pesquisar_item(item, **kw):
        chamadas.append((item, kw))
        return resultado(item.id, "nao_encontrado" if "xyz" in item.descricao else "definido")
    monkeypatch.setattr("src.pesquisa.pesquisar_item", pesquisar_item)
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
    mod = types.ModuleType("src.logistica")
    async def calcular_logistica(orcamento_id): chamados.append(("logistica", orcamento_id))
    mod.calcular_logistica = calcular_logistica
    monkeypatch.setitem(sys.modules, "src.logistica", mod)
    r = asyncio.run(o.pesquisar_orcamento("orc-9", banco=BancoFalso(ITENS)))
    assert chamados == [("logistica", "orc-9")] and r["fatia_c"] == ["calcular_logistica"]


def test_falha_da_fatia_c_nao_derruba_a_pesquisa(pesquisa_falsa, monkeypatch):
    mod = types.ModuleType("src.viabilidade")
    def calcular_viabilidade(orcamento_id): raise ValueError("bug da C")
    mod.calcular_viabilidade = calcular_viabilidade
    monkeypatch.setitem(sys.modules, "src.viabilidade", mod)
    r = asyncio.run(o.pesquisar_orcamento("orc-9", banco=BancoFalso(ITENS)))
    assert r["status"] == "concluida" and "calcular_viabilidade" not in r["fatia_c"]


def test_repesquisar_com_a_resposta_do_arquiteto(pesquisa_falsa):
    banco = BancoFalso([ItemEntrada(id="t", descricao="Tinta acrílica fosca vermelha", quantidade=12, unidade="m2",
                                    classificacao="pendente_especificacao")])
    r = asyncio.run(o.repesquisar_item("t", nova_descricao="Tinta Suvinil Fosco Completo Vermelho Cardinal 3,6L", banco=banco))
    item, kw = pesquisa_falsa[0]
    assert item.descricao.startswith("Tinta Suvinil Fosco") and item.classificacao == "definido" and kw["usar_cache"] is False
    assert banco.marcados[0][1]["status"] == "buscando" and banco.gravados[0] == r


# ---------------------------------------------------------------- serialização e SQL do Supabase
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
    assert novas == {"premissa"}, f"coluna nova precisa ser avisada ao Samuel: {novas}"


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
    try:
        sb.table("orcamento_itens").select(",".join(o.COLUNAS_LIDAS + o.COLUNAS_GRAVADAS)).limit(1).execute()
        sb.table("orcamentos").select("id,status_pesquisa,pesquisa_iniciada_em,pesquisa_concluida_em,pesquisa_erro").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"tabelas/colunas da fatia A ainda não existem: {str(exc)[:160]}")
    orc = sb.table("orcamentos").insert({}).execute().data[0]
    try:
        sb.table("orcamento_itens").insert([
            {"orcamento_id": orc["id"], "descricao": "Argamassa Quartzolit AC-III cinza 20kg", "quantidade": 48, "unidade": "m2"},
            {"orcamento_id": orc["id"], "descricao": "Tinta acrílica fosca vermelha", "quantidade": 12, "unidade": "m2",
             "classificacao": "pendente_especificacao"}]).execute()
        r = asyncio.run(o.pesquisar_orcamento(orc["id"]))
        assert r["status"] == "concluida" and r["itens"] == 2, r
        linhas = sb.table("orcamento_itens").select("*").eq("orcamento_id", orc["id"]).execute().data
        assert {x["status"] for x in linhas} <= {"definido", "pendente_especificacao"}, linhas
        assert all(x["fontes"] for x in linhas if x["preco_emb_med"] is not None)
        assert asyncio.run(o.pesquisar_orcamento(orc["id"]))["status"] == "ja_em_andamento_ou_concluido"
    finally:
        sb.table("orcamento_itens").delete().eq("orcamento_id", orc["id"]).execute()
        sb.table("orcamentos").delete().eq("id", orc["id"]).execute()
