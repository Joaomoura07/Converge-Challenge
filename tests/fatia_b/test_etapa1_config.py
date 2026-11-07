"""Etapa 1 — configuração: chaves do Tavily, Langfuse fora do Docker, parâmetros da pesquisa."""

from __future__ import annotations

import os

import pytest

from src.config import Settings, get_settings


def _s(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


# ---------------------------------------------------------------- offline
def test_tavily_keys_lista_limpa():
    s = _s(tavily_api_keys=' tvly-aaa , "tvly-bbb",, \'tvly-ccc\' ,')
    assert s.tavily_keys == ["tvly-aaa", "tvly-bbb", "tvly-ccc"]


def test_tavily_keys_vazio():
    assert _s(tavily_api_keys="").tavily_keys == []
    assert _s(tavily_api_keys=' , "" ').tavily_keys == []


def test_langfuse_base_url_tem_prioridade_sobre_host(monkeypatch):
    # Isola do ambiente: src/__init__ exporta LANGFUSE_BASE_URL ao importar, e o Settings também lê o ambiente.
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    assert _s(langfuse_base_url="https://us.cloud.langfuse.com").langfuse_url == "https://us.cloud.langfuse.com"
    assert _s(langfuse_host="https://cloud.langfuse.com").langfuse_url == "https://cloud.langfuse.com"


@pytest.fixture
def sem_chaves_no_ambiente(monkeypatch):
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    monkeypatch.delenv("FEATHERLESS_API_KEYS", raising=False)


@pytest.mark.parametrize("keys,key,esperado", [
    ('fw-a, "fw-b",, \'fw-c\' ,', "", ["fw-a", "fw-b", "fw-c"]),   # nova, limpa como a do Tavily
    ("", "fw-velha", ["fw-velha"]),                                 # só a antiga: continua funcionando
    ("fw-a,fw-b", "fw-a", ["fw-a", "fw-b"]),                        # as duas, sem repetir
    ("", "", []),
])
def test_chaves_featherless_nova_e_antiga(sem_chaves_no_ambiente, keys, key, esperado):
    """O Enzo trocou FEATHERLESS_API_KEY por FEATHERLESS_API_KEYS no .env e na Vercel: nada pode quebrar."""
    s = _s(featherless_api_keys=keys, featherless_api_key=key)
    assert s.featherless_keys == esperado
    assert s.featherless_key == (esperado[0] if esperado else "") and s.llm_configured is bool(esperado)


def test_parametros_da_pesquisa_batem_com_o_plano():
    s = _s()
    # 3 LLM simultâneos (era 4): medido na etapa 9, 6 chamadas ao Qwen3-32B ao mesmo tempo → 3 respostas vazias
    assert (s.pesquisa_concorrencia_llm, s.pesquisa_max_lojas, s.pesquisa_cache_dias) == (3, 5, 7)
    assert s.pesquisa_modelo_extracao == "Qwen/Qwen3-32B"


# ---------------------------------------------------------------- real (gasta créditos)
@pytest.mark.real
def test_etapa1_tavily_todas_as_chaves_funcionam():
    chaves = get_settings().tavily_keys
    assert chaves, "TAVILY_API_KEYS vazio no .env"
    from tavily import TavilyClient
    for chave in chaves:
        r = TavilyClient(api_key=chave).search("argamassa Quartzolit AC-III preço", max_results=2, include_images=True)
        assert r.get("results"), f"chave {chave[:9]}… não trouxe resultados"


@pytest.mark.real
def test_etapa1_duckduckgo_reserva_funciona():
    from ddgs import DDGS
    r = DDGS().text("porcelanato Portobello 90x90 preço", region="br-pt", max_results=3)
    assert r, "DuckDuckGo não retornou resultados"


@pytest.mark.real
def test_etapa1_langfuse_funciona_fora_do_docker():
    s = get_settings()
    assert s.langfuse_active, "chaves do Langfuse ausentes/placeholder no .env"
    assert os.environ.get("LANGFUSE_BASE_URL") == s.langfuse_url, "config não exportou LANGFUSE_BASE_URL"
    from langfuse import get_client
    assert get_client().auth_check()
