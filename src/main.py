"""API FastAPI. Rode com:  uvicorn src.main:app --reload"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langfuse import get_client
from pydantic import BaseModel

from .agent import Agent, AgentResult
from .config import get_settings
from .database import save_agent_run
from .tools import registry

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    get_client().flush()  # garante envio dos traces pendentes ao desligar


app = FastAPI(title="Converge Agents API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RunRequest(BaseModel):
    task: str
    context: dict | None = None
    session_id: str | None = None   # agrupa execuções no Langfuse (ex.: uma conversa/caso)
    tags: list[str] | None = None   # ex.: ["demo"] para filtrar no Demo Day
    persist: bool = True


class RunResponse(AgentResult):
    run_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "env": settings.app_env,
        "llm": settings.llm_configured,
        "supabase": settings.supabase_configured,
        "langfuse": settings.langfuse_configured,
        "model": settings.featherless_model,
        "tools": registry.names(),
    }


@app.post("/agent/run", response_model=RunResponse)
def run_agent(req: RunRequest) -> RunResponse:
    # Endpoint síncrono: o FastAPI executa em threadpool, sem bloquear o event loop.
    result = Agent().run(req.task, req.context, session_id=req.session_id, tags=req.tags)
    run_id = save_agent_run(req.task, result) if req.persist and settings.supabase_configured else None
    return RunResponse(**result.model_dump(), run_id=run_id)
