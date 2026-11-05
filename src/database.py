"""Acesso ao Supabase (cliente singleton + helpers de persistência)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from supabase import Client, create_client

from .config import get_settings

if TYPE_CHECKING:
    from .agent import AgentResult

logger = logging.getLogger(__name__)


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    if not s.supabase_configured:
        raise RuntimeError("SUPABASE_URL/SUPABASE_KEY não configurados no .env")
    return create_client(s.supabase_url, s.supabase_key)


def save_agent_run(task: str, result: AgentResult) -> str | None:
    """Grava a execução em `agent_runs` (ver sql/001_agent_runs.sql).
    Falha de persistência não derruba a resposta da API: só registra no log."""
    try:
        row = {
            "task": task,
            **result.model_dump(include={"status", "output", "model", "prompt_tokens",
                                         "completion_tokens", "latency_ms", "trace_id"}),
            "steps": [step.model_dump(mode="json") for step in result.steps],
        }
        response = get_supabase().table("agent_runs").insert(row).execute()
        return response.data[0]["id"] if response.data else None
    except Exception:  # noqa: BLE001
        logger.exception("Não foi possível salvar agent_run no Supabase")
        return None
