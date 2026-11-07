"""Rota do revisor E1 (Fatia A). O POST /revisao/sugestoes que junta erros e complementos é a etapa 06."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .revisao import ErroRevisao, ItemRevisao, revisar_e_redigir

router = APIRouter(prefix="/revisao", tags=["revisao"])


class RevisaoRequest(BaseModel):
    itens: list[ItemRevisao] = Field(max_length=5000)
    redigir: bool = True   # False = só texto fixo (sem LLM)


class RevisaoResponse(BaseModel):
    revisao_id: str
    erros: list[ErroRevisao]


@router.post("/erros", response_model=RevisaoResponse)
def revisar(req: RevisaoRequest) -> RevisaoResponse:
    """Propõe correções E1. Não altera nada: a tela só aplica o que o arquiteto aceitar."""
    # Endpoint síncrono: o FastAPI o executa em threadpool, então a chamada ao LLM não bloqueia o event loop.
    rid, erros = revisar_e_redigir(req.itens, redigir=req.redigir)
    return RevisaoResponse(revisao_id=rid, erros=erros)
