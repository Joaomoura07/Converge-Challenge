"""Etapa 12: o encaixe das três fatias, do clique ao Excel, com dados sintéticos e o código REAL de cada fatia.

  A  POST /orcamentos      src/rotas_orcamentos.py  grava orçamento e itens e chama a pesquisa na MESMA requisição
  B  pesquisar_orcamento   src/orcamento.py         reserva, pesquisa cada item, grava, conclui e chama a C no fim
  C  resultado / exportar  src/rotas_resultado.py   frete, viabilidade, ganho (gravados em `orcamentos`) e o Excel

O que é simulado: o banco (um Supabase em memória que as três fatias leem e escrevem) e a busca de preços na internet
(uma tabela de preços sintéticos). A.criar_orcamento (SQL), B (`pesquisar_orcamento`, `repesquisar_item`) e C
(`resultado`, `exportar`) rodam de verdade; só o adaptador `BancoSupabase` da B é trocado por um equivalente em memória.
"""

from __future__ import annotations

import copy
import inspect
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

os.environ.setdefault("LANGFUSE_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import src.main as principal
from src import orcamento as b
from src import rotas_orcamentos as a
from src import rotas_resultado as c
from src.modelos import Fonte, ItemEntrada, ResultadoItem

ID = "11111111-1111-4111-8111-111111111111"
AGORA = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ banco em memória (Supabase de mentira)


class BD:
    def __init__(self):
        self.tabelas: dict[str, list[dict]] = {"orcamentos": [], "orcamento_itens": [], "fornecedores": []}
        self.ordem: list[str] = []   # quem fez o quê, na ordem


class _Consulta:
    def __init__(self, bd: BD, tabela: str):
        self.bd, self.tabela, self.op, self.dados, self.filtros, self.n = bd, tabela, "select", None, [], None

    def select(self, *_):
        self.op = "select"
        return self

    def update(self, dados):
        self.op, self.dados = "update", dados
        return self

    def eq(self, col, val):
        self.filtros.append((col, val))
        return self

    def limit(self, n):
        self.n = n
        return self

    def execute(self):
        linhas = [r for r in self.bd.tabelas[self.tabela] if all(r.get(k) == v for k, v in self.filtros)]
        if self.op == "update":
            for r in linhas:
                r.update(copy.deepcopy(self.dados))
        saida = copy.deepcopy(linhas if self.n is None else linhas[: self.n])
        return SimpleNamespace(data=saida)


class SupabaseMemoria:
    """O que a Fatia C usa (`get_supabase().table(...)`)."""

    def __init__(self, bd: BD):
        self.bd = bd

    def table(self, nome: str):
        return _Consulta(self.bd, nome)


class BancoMemoria:
    """Equivalente em memória do `BancoSupabase` da Fatia B (mesmo protocolo `Banco`)."""

    def __init__(self, bd: BD):
        self.bd = bd

    def _orc(self, orcamento_id):
        return next(r for r in self.bd.tabelas["orcamentos"] if r["id"] == orcamento_id)

    def _item(self, item_id):
        return next((r for r in self.bd.tabelas["orcamento_itens"] if r["id"] == item_id), None)

    async def reservar(self, orcamento_id):
        o = self._orc(orcamento_id)
        if o["status_pesquisa"] in ("pendente", "falhou"):
            o["status_pesquisa"] = "pesquisando"
            o["pesquisa_iniciada_em"] = AGORA.isoformat()
            self.bd.ordem.append("B:reservar")
            return True
        self.bd.ordem.append("B:reserva_negada")
        return False

    async def itens_para_pesquisar(self, orcamento_id):
        return [b.item_da_linha(r) for r in self.bd.tabelas["orcamento_itens"]
                if r["orcamento_id"] == orcamento_id and r["status"] == "buscando"]

    async def item(self, item_id):
        r = self._item(item_id)
        return b.item_da_linha(r) if r else None

    async def gravar_item(self, resultado):
        self._item(resultado.item_id).update(b.linha_do_resultado(resultado))
        self.bd.ordem.append("B:gravar_item")

    async def marcar_item(self, item_id, campos):
        self._item(item_id).update(campos)
        self.bd.ordem.append("B:marcar_item")

    async def concluir(self, orcamento_id, erro=None, custo_usd=None):
        o = self._orc(orcamento_id)
        o["status_pesquisa"] = "falhou" if erro else "concluida"
        o["pesquisa_erro"] = erro
        o["pesquisa_concluida_em"] = AGORA.isoformat()
        if custo_usd is not None:
            o["custo_usd"] = custo_usd
        self.bd.ordem.append("B:concluir")

    async def orcamento_do_item(self, item_id):
        return self._item(item_id)["orcamento_id"]

    async def somar_custo(self, orcamento_id, usd):
        o = self._orc(orcamento_id)
        o["custo_usd"] = round(float(o.get("custo_usd") or 0) + usd, 6)


# ------------------------------------------------------------------ pesquisa de preços sintética (no lugar da internet)

LEROY = Fonte(loja="Leroy Merlin", dominio="leroymerlin.com.br", url="https://www.leroymerlin.com.br/p/1", preco_embalagem=455.9, embalagem="lata 18 L")
CEC = Fonte(loja="C&C", dominio="cec.com.br", url="https://www.cec.com.br/p/2", preco_embalagem=98.5, embalagem="barrica 25 kg")


def _definido(item_id, produto, emb, n, mn, med, mx, fonte):
    return ResultadoItem(
        item_id=item_id, status="definido", produto_normalizado=produto, embalagem=emb, qtd_embalagens=n,
        preco_emb_min=mn, preco_emb_med=med, preco_emb_max=mx, confianca="alta",
        fontes=[fonte.model_copy(update={"preco_embalagem": med})], preco_data=AGORA,
    )


def preco_sintetico(item: ItemEntrada) -> ResultadoItem:
    d = item.descricao.lower()
    if "toque de seda" in d:
        return _definido(item.id, "Suvinil Toque de Seda 18L", "lata 18 L", 2, 420.0, 455.9, 489.9, LEROY)
    if "massa corrida" in d:
        return _definido(item.id, "Massa corrida PVA Suvinil 25 kg", "barrica 25 kg", 3, 90.0, 98.5, 110.0, CEC)
    if "argamassa" in d:
        return _definido(item.id, "Argamassa colante AC-III 20 kg", "saco 20 kg", 15, 34.0, 38.0, 42.0, LEROY)
    if "rende muito" in d:  # a resposta do arquiteto à pergunta ("tinta branca")
        return _definido(item.id, "Coral Rende Muito Branco 18L", "lata 18 L", 1, 270.0, 289.9, 310.0, CEC)
    if "porcelanato" in d:
        return ResultadoItem(item_id=item.id, status="nao_encontrado", motivo="Nenhuma loja devolveu esse porcelanato.")
    return ResultadoItem(item_id=item.id, status="pendente_especificacao", pergunta="Qual acabamento e litragem?")


# ------------------------------------------------------------------ montagem: A + B + C sobre o mesmo banco


@pytest.fixture
def mundo(monkeypatch):
    bd = BD()

    # A: o SQL criar_orcamento (aqui em memória) e a chamada à pesquisa da B na mesma requisição
    def criar_no_banco(orcamento_id, hash_conteudo, obra, origem, itens):
        bd.ordem.append("A:criar_orcamento")
        if any(o["id"] == orcamento_id for o in bd.tabelas["orcamentos"]):
            existente = next(o for o in bd.tabelas["orcamentos"] if o["id"] == orcamento_id)
            mesmo = existente["hash_conteudo"] == hash_conteudo
            return {"resultado": "existente" if mesmo else "conflito", "orcamento_id": orcamento_id}
        bd.tabelas["orcamentos"].append({
            "id": orcamento_id, "nome": obra["nome"], "cep": obra["cep"], "orcamento_cliente": obra["orcamento_cliente"],
            "hash_conteudo": hash_conteudo, "status_pesquisa": "pendente", "origem": origem,
            "qtd_itens": len(itens), "tentativa_pesquisa": 0,   # como o SQL criar_orcamento deixa
            "created_at": AGORA.isoformat(), "atualizado_em": AGORA.isoformat(),
            "logistica": None, "viabilidade": None, "ganho": None, "custo_usd": None,
            "pesquisa_iniciada_em": None, "pesquisa_concluida_em": None, "pesquisa_erro": None,
        })
        for i in itens:
            bd.tabelas["orcamento_itens"].append({
                **{k: v for k, v in i.items() if k != "id_linha"}, "id": str(uuid.uuid4()), "id_linha": i["id_linha"],
                "orcamento_id": orcamento_id, "status": "buscando", "fontes": [], "estimativa": False,
            })
        return {"resultado": "criado", "orcamento_id": orcamento_id}

    async def pesquisar(orcamento_id):
        return await b.pesquisar_orcamento(orcamento_id, banco=BancoMemoria(bd))

    # B: a pesquisa de preços (internet) é sintética; o fluxo da B é o real
    async def pesquisar_itens(itens, ao_terminar=None, **kw):
        saida = []
        for item in itens:
            r = preco_sintetico(item)
            if ao_terminar:
                await ao_terminar(r)
            saida.append(r)
        return saida

    async def pesquisar_item(item, **kw):
        return preco_sintetico(item)

    # C: o código real lê e grava por get_supabase(); o gancho da B chama rotas_resultado.resultado
    original = c.resultado

    def resultado_com_registro(orcamento_id):
        bd.ordem.append("C:resultado")
        return original(orcamento_id)

    monkeypatch.setattr(a, "_supabase_ok", lambda: True)
    monkeypatch.setattr(a, "_criar_no_banco", criar_no_banco)
    monkeypatch.setattr(a, "_pesquisar", pesquisar)
    monkeypatch.setattr(b, "pesquisar_itens", pesquisar_itens)
    monkeypatch.setattr(b, "pesquisar_item", pesquisar_item)
    monkeypatch.setattr(b, "BancoSupabase", lambda *args, **kw: BancoMemoria(bd))
    monkeypatch.setattr(c, "get_supabase", lambda: SupabaseMemoria(bd))
    monkeypatch.setattr(c, "resultado", resultado_com_registro)
    monkeypatch.delenv("FRETE_ATIVO", raising=False)  # frete em pausa: sempre R$ 0
    monkeypatch.setattr(type(principal.settings), "supabase_configured", property(lambda self: True))
    return SimpleNamespace(bd=bd, api=TestClient(principal.app))


def corpo(**mudancas):
    base = {
        "orcamento_id": ID,
        "obra": {"nome": "Reforma Apto Boa Viagem", "cep": "51020-000", "orcamento_cliente": 4000.0},
        "origem": {"tipo": "arquivo", "modo": "csv"},
        "itens": [
            {"id": "t1", "linha": 2, "categoria": "Pintura", "descricao": "Tinta acrílica Suvinil Toque de Seda Branco Neve 18L",
             "quantidade": 180, "unidade": "m2", "origem_item": "arquivo"},
            {"id": "t2", "linha": 3, "categoria": "Pintura", "descricao": "Massa corrida PVA Suvinil",
             "quantidade": 180, "unidade": "m2", "origem_item": "arquivo"},
            {"id": "t3", "linha": 4, "descricao": "tinta branca", "quantidade": 2, "unidade": "un", "origem_item": "manual"},
            {"id": "t4", "linha": 5, "categoria": "Revestimentos", "descricao": "Porcelanato 90x90 acetinado",
             "quantidade": 48, "unidade": "m2", "origem_item": "manual"},
            # complemento da C, aceito pelo arquiteto
            {"id": "c1", "linha": 6, "categoria": "Revestimentos e argamassas", "descricao": "Argamassa colante AC-III 20 kg (saco)",
             "quantidade": 15, "unidade": "un", "origem_item": "manual", "sugerido": True, "sugestao_regra": "porcelanato",
             "sugestao_motivo": "Para 48 m² de piso costumam faltar argamassa.", "origem_linhas": [5], "aceito": True,
             "estimativa_consumo": True},
            # complemento RECUSADO: não pode virar linha nem entrar na conta
            {"id": "c2", "linha": 7, "descricao": "Rejunte flexível 5 kg", "quantidade": 5, "unidade": "un", "origem_item": "manual",
             "sugerido": True, "sugestao_regra": "porcelanato", "origem_linhas": [5], "aceito": False},
        ],
    }
    base.update(mudancas)
    return base


def itens_do(bd: BD) -> dict[str, dict]:
    return {r["id_linha"]: r for r in bd.tabelas["orcamento_itens"]}


# ------------------------------------------------------------------ o fluxo


def test_a_chama_b_na_mesma_requisicao_e_b_chama_c_no_fim(mundo):
    r = mundo.api.post("/orcamentos", json=corpo())
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["orcamento_id"] == ID and j["resultado"] == "criado"
    assert j["complementos_recusados_ignorados"] == ["c2"]
    assert j["pesquisa"]["status"] == "concluida"          # veio da B, dentro da resposta do A
    # quem chamou quem, na ordem: A grava, B reserva/pesquisa/conclui, e SÓ DEPOIS a C calcula (gancho da B)
    ordem = mundo.bd.ordem
    assert ordem[0] == "A:criar_orcamento" and ordem[1] == "B:reservar"
    assert ordem.count("B:gravar_item") == 5                # 4 itens + o complemento aceito; o recusado nem existe
    assert ordem.index("B:concluir") < ordem.index("C:resultado") == len(ordem) - 1
    assert ordem.count("C:resultado") == 1


def test_a_nao_calcula_nada_de_b_nem_de_c(mundo):
    fonte = inspect.getsource(a)
    for dono_de_outro in ("rotas_resultado", "calcular_logistica", "calcular_viabilidade", "calcular_ganho", "gerar_xlsx",
                          "pesquisar_item(", "preco_emb"):
        assert dono_de_outro not in fonte, f"a rota da A não pode conter {dono_de_outro!r}"


def test_o_banco_fica_como_cada_fatia_deveria_deixar(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    itens = itens_do(mundo.bd)
    assert set(itens) == {"t1", "t2", "t3", "t4", "c1"}     # o complemento recusado não foi gravado
    # A: classificação única; B: status e preço com FONTE; pergunta ao arquiteto; motivo do não encontrado
    assert itens["t1"]["classificacao"] == "definido" and itens["t3"]["classificacao"] == "pendente"
    assert itens["t1"]["status"] == "definido" and itens["t1"]["preco_emb_med"] == 455.9
    assert itens["t1"]["fontes"][0]["dominio"] == "leroymerlin.com.br" and itens["t1"]["fontes"][0]["url"].startswith("https://")
    assert itens["t3"]["status"] == "pendente_especificacao" and itens["t3"]["pergunta"]
    assert itens["t4"]["status"] == "nao_encontrado" and itens["t4"]["motivo"]
    # nenhum preço sem fonte
    for it in itens.values():
        if it.get("preco_emb_med") is not None:
            assert it["fontes"], f"{it['id_linha']}: preço sem fonte"
    # complemento aceito mantém regra, motivo, origem e a estimativa de CONSUMO (não a de preço)
    c1 = itens["c1"]
    assert (c1["sugerido"], c1["aceito"], c1["sugestao_regra"], c1["origem_linhas"], c1["estimativa_consumo"]) == (True, True, "porcelanato", [5], True)
    assert c1["estimativa"] is False and c1["status"] == "definido"
    o = mundo.bd.tabelas["orcamentos"][0]
    assert o["status_pesquisa"] == "concluida" and o["pesquisa_concluida_em"]


def test_c_calcula_viabilidade_frete_e_ganho_sobre_o_que_a_b_gravou(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    o = mundo.bd.tabelas["orcamentos"][0]
    assert o["logistica"] and o["viabilidade"] and o["ganho"]
    itens = itens_do(mundo.bd)
    esperado = sum(i["preco_emb_med"] * i["qtd_embalagens"] for i in itens.values() if i.get("preco_emb_med") is not None)
    # 911,80 (tinta) + 295,50 (massa) + 570,00 (argamassa do complemento ACEITO)
    assert esperado == pytest.approx(1777.30)
    v = o["viabilidade"]
    assert v["total_med"] == pytest.approx(esperado)
    assert v["orcamento_cliente"] == 4000.0 and v["cabe"] is True
    # dois itens sem preço (pendente e não encontrado): o total é só um piso e a tela precisa avisar
    assert v["completo"] is False and len(v["itens_sem_preco"]) == 2
    # frete em pausa: R$ 0 e nenhuma consulta de CEP
    lg = o["logistica"]
    assert lg["frete_total"] == 0 and lg["total"] == pytest.approx(esperado)
    assert {l["nome"] for l in lg["lojas"]} == {"Leroy Merlin", "C&C"}
    assert all(l["frete"] == 0 for l in lg["lojas"])
    assert o["ganho"]["resumo"]


def test_as_posicoes_da_logistica_apontam_para_a_lista_ordenada_por_linha(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    o = mundo.bd.tabelas["orcamentos"][0]
    ordenados = sorted(itens_do(mundo.bd).values(), key=lambda i: i["linha"])  # a mesma ordem que a tela usa (useOrcamento)
    por_loja = {l["nome"]: [ordenados[p]["id_linha"] for p in l["itens"]] for l in o["logistica"]["lojas"]}
    assert por_loja == {"Leroy Merlin": ["t1", "c1"], "C&C": ["t2"]}
    assert [ordenados[p]["id_linha"] for p in o["viabilidade"]["itens_sem_preco"]] == ["t3", "t4"]


def test_complemento_nao_aceito_nunca_entra_na_conta_da_c(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    # mesmo que alguém grave um complemento sem decisão, a C o ignora (regra do João) e o total não muda
    antes = mundo.bd.tabelas["orcamentos"][0]["viabilidade"]["total_med"]
    mundo.bd.tabelas["orcamento_itens"].append({
        "id": "x", "orcamento_id": ID, "id_linha": "c9", "linha": 9, "descricao": "Rejunte", "quantidade": 5, "unidade": "un",
        "status": "definido", "preco_emb_med": 999.0, "preco_emb_min": 999.0, "preco_emb_max": 999.0, "qtd_embalagens": 9,
        "fontes": [LEROY.model_dump()], "sugerido": True, "aceito": None, "estimativa": False,
    })
    r = mundo.api.post(f"/orcamentos/{ID}/resultado")
    assert r.status_code == 200
    assert r.json()["viabilidade"]["total_med"] == pytest.approx(antes)


def test_exportar_excel_pela_c_com_o_plano_de_compra(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    r = mundo.api.get(f"/orcamentos/{ID}/exportar.xlsx")
    assert r.status_code == 200 and r.headers["content-type"] == c.XLSX
    wb = load_workbook(BytesIO(r.content))
    tudo = " | ".join(str(cel.value) for ws in wb for linha in ws.iter_rows() for cel in linha if cel.value is not None)
    assert "Argamassa colante" in tudo                       # o complemento aceito entra no plano
    assert "Rejunte" not in tudo                             # o recusado não existe
    assert "tinta branca" in tudo.lower()                    # o pendente aparece (na lista de pendentes)
    assert "leroymerlin.com.br" in tudo or "Leroy Merlin" in tudo


def test_responder_a_pergunta_aciona_a_b_e_a_c_recalcula(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    pendente = itens_do(mundo.bd)["t3"]
    antes = mundo.bd.tabelas["orcamentos"][0]["viabilidade"]
    mundo.bd.ordem.clear()
    r = mundo.api.post(f"/orcamento-itens/{pendente['id']}/repesquisar",
                       json={"nova_descricao": "Tinta acrílica fosca Coral Rende Muito Branco 18L"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "definido"
    # quem fez o quê: a B marca, pesquisa e grava o item; DEPOIS a C recalcula
    assert mundo.bd.ordem == ["B:marcar_item", "B:gravar_item", "C:resultado"]
    item = itens_do(mundo.bd)["t3"]
    assert item["status"] == "definido" and item["classificacao"] == "definido" and item["descricao"].startswith("Tinta acrílica fosca Coral")
    assert item["fontes"][0]["dominio"] == "cec.com.br"
    depois = mundo.bd.tabelas["orcamentos"][0]["viabilidade"]
    assert len(depois["itens_sem_preco"]) == len(antes["itens_sem_preco"]) - 1
    assert depois["total_med"] == pytest.approx(antes["total_med"] + 289.9)


def test_pesquisar_de_novo_sem_resposta_repete_a_busca_de_um_item(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    naoachado = itens_do(mundo.bd)["t4"]
    mundo.bd.ordem.clear()
    r = mundo.api.post(f"/orcamento-itens/{naoachado['id']}/repesquisar")
    assert r.status_code == 200
    assert mundo.bd.ordem == ["B:marcar_item", "B:gravar_item", "C:resultado"]


def test_reenvio_do_mesmo_pedido_nao_duplica_itens_nem_repete_a_pesquisa(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    mundo.bd.ordem.clear()
    custo = mundo.bd.tabelas["orcamentos"][0]["custo_usd"]
    r = mundo.api.post("/orcamentos", json=corpo())            # a resposta se perdeu e a tela reenviou
    assert r.status_code == 200 and r.json()["resultado"] == "existente"
    assert len(mundo.bd.tabelas["orcamento_itens"]) == 5
    # a reserva da B nega: orçamento já concluído não pesquisa de novo, e a C não recalcula à toa
    assert mundo.bd.ordem == ["A:criar_orcamento", "B:reserva_negada"]
    assert mundo.bd.tabelas["orcamentos"][0]["custo_usd"] == custo


def test_mesmo_codigo_com_conteudo_diferente_da_conflito_e_nao_pesquisa(mundo):
    mundo.api.post("/orcamentos", json=corpo())
    mundo.bd.ordem.clear()
    outro = corpo()
    outro["itens"][0]["quantidade"] = 181
    r = mundo.api.post("/orcamentos", json=outro)
    assert r.status_code == 409
    assert mundo.bd.ordem == ["A:criar_orcamento"]             # nada de B, nada de C


# ------------------------------------------------------------------ fixture para o frontend

def test_fixture_do_frontend_vem_do_fluxo_real(mundo):
    """Com ATUALIZAR_FIXTURE_FLUXO=1 regrava o snapshot que o frontend usa em fluxo.test.ts (linhas EXATAS que o banco
    guarda depois de A, B e C rodarem). Sem a variável, só confere que o arquivo versionado ainda é igual ao fluxo."""
    import json
    from pathlib import Path

    mundo.api.post("/orcamentos", json=corpo())
    snapshot = {
        "orcamento": mundo.bd.tabelas["orcamentos"][0],
        "itens": sorted(mundo.bd.tabelas["orcamento_itens"], key=lambda i: i["linha"]),
    }
    # ids aleatórios do banco viram estáveis, para o arquivo não mudar a cada execução
    for n, item in enumerate(snapshot["itens"], start=1):
        item["id"] = f"00000000-0000-4000-8000-{n:012d}"
        item["atualizado_em"] = AGORA.isoformat()   # a B grava a hora real; fixa para o arquivo não mudar a cada execução
    alvo = Path(__file__).resolve().parent.parent / "frontend/src/lib/orcamento/fixtures/fluxo-a-b-c.json"
    texto = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
    if os.getenv("ATUALIZAR_FIXTURE_FLUXO") == "1":
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8")
    assert alvo.exists(), "gere com ATUALIZAR_FIXTURE_FLUXO=1"
    assert json.loads(alvo.read_text("utf-8")) == json.loads(texto), "fixture desatualizada: rode com ATUALIZAR_FIXTURE_FLUXO=1"
