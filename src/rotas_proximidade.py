"""GET /lojas-proximas?cep=...: lojas das redes cadastradas perto do CEP, com distância e tempo de carro."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query

from .proximidade import lojas_proximas

router = APIRouter()


@router.get("/lojas-proximas")
async def lojas_proximas_rota(cep: str = Query(..., description="CEP da obra, com ou sem hífen"),
                              por_rede: int = Query(2, ge=1, le=3)) -> dict:
    digitos = re.sub(r"\D", "", cep)
    if len(digitos) != 8:
        raise HTTPException(status_code=422, detail="CEP deve ter 8 dígitos")
    return await lojas_proximas(digitos, por_rede=por_rede)
