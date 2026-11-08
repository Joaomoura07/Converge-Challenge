"""Determinismo das chamadas ao modelo que mexem com preço: temperature 0, top_p 0.1 e prompts com as regras absolutas."""

from __future__ import annotations

from types import SimpleNamespace as NS

from src.agent import Agent
from src.config import PROMPTS_DIR, get_settings
from src.tools import ToolRegistry


def test_padroes_sao_deterministicos():
    s = get_settings()
    assert s.llm_temperature == 0.0 and s.llm_top_p == 0.1


def test_agente_envia_temperature_e_top_p_ao_modelo():
    visto = {}

    def create(**kw):
        visto.update(kw)
        return NS(choices=[], usage=None, model=kw["model"])

    cliente = NS(chat=NS(completions=NS(create=create)))
    Agent(name="t", system_prompt="x", tools=ToolRegistry(), client=cliente)._complete_once("m", [{"role": "user", "content": "oi"}])
    assert visto["temperature"] == 0.0 and visto["top_p"] == 0.1


def test_prompts_de_preco_trazem_as_regras_absolutas():
    extrator = (PROMPTS_DIR / "extrator_precos.md").read_text(encoding="utf-8")
    pesquisador = (PROMPTS_DIR / "pesquisador_precos.md").read_text(encoding="utf-8")
    for texto in (extrator, pesquisador):
        assert "conhecimento interno" in texto.lower() and "nunca" in texto.lower()
    assert "FONTE EXCLUSIVA" in extrator and "PROIBIDO INVENTAR" in extrator
