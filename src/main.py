"""API FastAPI. Rode com:  uvicorn src.main:app --reload"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langfuse import get_client
from pydantic import BaseModel, Field, model_validator

from .agent import Agent, AgentResult
from .config import get_settings
from .database import save_agent_run
from .limite_corpo import LimiteDeCorpo
from .rotas_resultado import router as resultado_router   # Fatia C: sugestões, resultado e exportar
from .tools import registry

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if settings.langfuse_active:
        try:
            get_client().flush()  # garante envio dos traces pendentes ao desligar
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).warning("Falha ao enviar traces pendentes ao Langfuse")


app = FastAPI(title="Converge Agents API", version="0.1.0", lifespan=lifespan)
app.add_middleware(LimiteDeCorpo)   # Fatia A: corpo acima do limite dá 413 antes de ser lido (CORS fica por fora e acompanha a resposta)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(resultado_router)

from .rotas_revisao import router as revisao_router  # noqa: E402  (Fatia A: revisor E1)

app.include_router(revisao_router)

from .rotas_orcamentos import router as orcamentos_router  # noqa: E402  (Fatia A: POST /orcamentos)

app.include_router(orcamentos_router)

from .rotas_proximidade import router as proximidade_router  # noqa: E402  (lojas próximas, distância e tempo)

app.include_router(proximidade_router)


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
        "langfuse": settings.langfuse_active,
        "model": settings.featherless_model,
        "tools": registry.names(),
    }


class RepesquisarRequest(BaseModel):
    """Corpo opcional: vazio = "Pesquisar de novo"; com texto = resposta do arquiteto à pergunta do item;
    com `objetivo` = pesquisar uma alternativa (maior qualidade, menor preço ou semelhante de outra marca)."""
    nova_descricao: str | None = Field(default=None, min_length=3, max_length=300)
    objetivo: Literal["qualidade", "preco", "semelhante"] | None = None

    @model_validator(mode="after")
    def _um_so(self) -> "RepesquisarRequest":
        if self.nova_descricao and self.objetivo:
            raise ValueError("envie a especificação OU o objetivo da alternativa, não os dois")
        return self


@app.post("/orcamento-itens/{item_id}/repesquisar")
async def repesquisar(item_id: str, req: RepesquisarRequest | None = None) -> dict:
    """Fatia B: botões "Pesquisar de novo" (com ou sem objetivo) e "Responder" do ItemRow. Roda na mesma
    requisição (a Vercel encerra o que roda depois da resposta) e grava o item em orcamento_itens: o Realtime
    atualiza a tela sozinho."""
    if not settings.supabase_configured:
        raise HTTPException(status_code=503, detail="Supabase não configurado")
    from .alternativas import AlternativaIndisponivel
    from .orcamento import repesquisar_item   # import tardio: /health não depende da pesquisa
    kw = {"objetivo": req.objetivo} if req and req.objetivo else {}
    try:
        resultado = await repesquisar_item(item_id, req.nova_descricao if req else None, **kw)
    except AlternativaIndisponivel:
        raise HTTPException(status_code=503, detail="Não consegui sugerir uma alternativa para este item agora. "
                                                    "O item ficou como estava; tente de novo em instantes.")
    if resultado is None:
        raise HTTPException(status_code=404, detail="item não encontrado")
    return resultado.model_dump(mode="json")


@app.post("/agent/run", response_model=RunResponse)
def run_agent(req: RunRequest) -> RunResponse:
    # Endpoint síncrono: o FastAPI executa em threadpool, sem bloquear o event loop.
    if not settings.agent_run_ativo:   # o site não usa; aberto, gastaria crédito da Featherless pelo link público
        raise HTTPException(status_code=404, detail="Not Found")
    result = Agent().run(req.task, req.context, session_id=req.session_id, tags=req.tags)
    run_id = save_agent_run(req.task, result) if req.persist and settings.supabase_configured else None
    return RunResponse(**result.model_dump(), run_id=run_id)
