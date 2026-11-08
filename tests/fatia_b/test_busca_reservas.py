"""Reservas da busca: Tavily -> Serper -> DuckDuckGo (brave e depois auto). Tudo offline, sem rede."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

import src.busca as b


BUSCAR_ABERTA_REAL = b._buscar_aberta


def rodar(coro):
    return asyncio.run(coro)


def _ok(provedor, n=2):
    return b.RespostaBusca("q", provedor, [b.ResultadoWeb("t", f"https://cec.com.br/{i}", "cec.com.br", "C&C", "R$ 1")
                                           for i in range(n)], [b.ImagemWeb("https://img/1.jpg")])


@pytest.fixture(autouse=True)
def sem_busca_aberta(monkeypatch):
    async def vazia(consulta, *a):
        return b.RespostaBusca(consulta, "nenhum")
    monkeypatch.setattr(b, "_buscar_aberta", vazia)


# ------------------------------------------------------------------ cadeia da busca fixa
def test_tavily_vazio_usa_serper_antes_do_duckduckgo(monkeypatch):
    async def tav(*a): return b.RespostaBusca("q", "tavily", [], [b.ImagemWeb("https://img/tavily.jpg")])
    async def ser(*a): return _ok("serper");
    async def ddg(*a): raise AssertionError("o Serper já resolveu")
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_serper_busca", ser)
    monkeypatch.setattr(b, "_duckduckgo", ddg)
    r = rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"])))
    assert r.provedor == "serper" and r.resultados and r.erro is None


def test_serper_vazio_cai_no_duckduckgo(monkeypatch):
    async def tav(*a): raise TimeoutError("lento")
    async def ser(*a): return b.RespostaBusca("q", "serper")
    async def ddg(*a): return _ok("duckduckgo")
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_serper_busca", ser)
    monkeypatch.setattr(b, "_duckduckgo", ddg)
    assert rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"]))).provedor == "duckduckgo"


def test_serper_que_levanta_erro_nao_derruba_a_busca(monkeypatch):
    async def tav(*a): raise TimeoutError("lento")
    async def ser(*a): raise RuntimeError("serper fora")
    async def ddg(*a): return _ok("duckduckgo")
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_serper_busca", ser)
    monkeypatch.setattr(b, "_duckduckgo", ddg)
    assert rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"]))).provedor == "duckduckgo"


def test_tavily_ok_nao_gasta_serper(monkeypatch):
    async def tav(*a): return _ok("tavily")
    async def ser(*a): raise AssertionError("não devia gastar crédito do Serper")
    monkeypatch.setattr(b, "_tavily", tav); monkeypatch.setattr(b, "_serper_busca", ser)
    assert rodar(b.buscar("q", rodizio=b._RodizioChaves(["k"]))).provedor == "tavily"


def test_serper_sem_chave_devolve_vazio_sem_rede():
    # o conftest desliga SERPER_API_KEYS nos testes; sem chave nem abre conexão
    assert rodar(b._serper_texto("tinta suvinil")) == []


# ------------------------------------------------------------------ cadeia da busca aberta
def test_aberta_tavily_vazio_usa_serper(monkeypatch):
    async def tav(*a): return b.RespostaBusca("q", "tavily")
    async def ser(*a): return b.RespostaBusca("q", "serper", [b.ResultadoWeb("t", "https://x.com.br/1", "x.com.br", "X", "R$ 1")])
    async def ddg(*a): raise AssertionError("o Serper já resolveu")
    monkeypatch.setattr(b, "_tavily_aberto", tav); monkeypatch.setattr(b, "_serper_aberto", ser)
    monkeypatch.setattr(b, "_duckduckgo_aberto", ddg)
    r = rodar(BUSCAR_ABERTA_REAL("q", 3, b._RodizioChaves(["k"]), None))
    assert r.provedor == "serper"


# ------------------------------------------------------------------ ddgs: brave primeiro, auto depois
def _falso_ddgs(monkeypatch, por_backend):
    chamados = []

    class DDGS:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def text(self, q, region=None, max_results=None, backend=None):
            chamados.append(backend)
            r = por_backend[backend]
            if isinstance(r, Exception):
                raise r
            return r

    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=DDGS))
    return chamados


def test_ddg_brave_funciona_e_auto_nem_e_chamado(monkeypatch):
    chamados = _falso_ddgs(monkeypatch, {"brave": [{"title": "t", "href": "https://cec.com.br/a", "body": "R$ 1"}],
                                         "auto": AssertionError("não devia chamar")})
    assert rodar(b._ddg_texto("q"))[0]["href"] == "https://cec.com.br/a"
    assert chamados == ["brave"]


@pytest.mark.parametrize("brave", [TimeoutError("bloqueado"), []])
def test_ddg_brave_falha_ou_vazio_tenta_auto(monkeypatch, brave):
    chamados = _falso_ddgs(monkeypatch, {"brave": brave,
                                         "auto": [{"title": "t", "href": "https://cec.com.br/a", "body": "R$ 1"}]})
    assert rodar(b._ddg_texto("q"))
    assert chamados == ["brave", "auto"]


def test_ddg_todos_falham_levanta_o_ultimo_erro(monkeypatch):
    _falso_ddgs(monkeypatch, {"brave": RuntimeError("a"), "auto": ValueError("b")})
    with pytest.raises(ValueError):
        rodar(b._ddg_texto("q"))
