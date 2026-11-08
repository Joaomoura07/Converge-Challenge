"""Isolamento dos testes offline: recursos opcionais que chamam serviços pagos (Serper e OpenRouteService) ficam
DESLIGADOS mesmo se o .env local tiver as chaves. Sem isso, com SERPER_API_KEYS no .env, a conferência de preço
chamava o Google Shopping de verdade e mudava o resultado dos testes (achado em 08/11).
Testes marcados `real` mantêm as chaves do .env."""

import pytest

from src.config import get_settings


@pytest.fixture(autouse=True)
def _sem_servicos_opcionais(request, monkeypatch):
    if request.node.get_closest_marker("real"):
        return
    s = get_settings()
    monkeypatch.setattr(s, "serper_api_keys", "")
    monkeypatch.setattr(s, "ors_api_key", "")
    monkeypatch.setattr(s, "pesquisa_paginas_por_rodada", 0)



@pytest.fixture(autouse=True)
def _sem_abrir_paginas_das_lojas(monkeypatch):
    """Os testes usam links de mentira: a conferência na loja (src/conferir_links.py) fica desligada.
    tests/fatia_b/test_conferir_links.py liga de novo com páginas falsas."""
    import src.conferir_links as conferir_links
    monkeypatch.setattr(conferir_links, "ATIVO", False)
