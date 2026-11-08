"""GET /lojas-proximas?cep=...: lojas de material de construção perto da obra (Google Maps), com km e tempo de carro.

Usa o mesmo levantamento da pesquisa de preço (src/regiao.py), então a tela mostra as lojas mesmo quando elas não têm
preço na internet: o arquiteto sabe onde ir consultar. Distância e tempo são aproximados (linha reta x 1,3 e 30 km/h).
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException, Query

from .regiao import preparar_obra

router = APIRouter()

VELOCIDADE_MEDIA_KMH = 30.0   # trânsito urbano; só para o tempo aproximado


def _mapa(nome: str, endereco: str | None, cidade: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{nome} {endereco or ''} {cidade}".strip())


@router.get("/lojas-proximas")
async def lojas_proximas(cep: str = Query(..., description="CEP da obra, com ou sem hífen"),
                         limite: int = Query(8, ge=1, le=20)) -> dict:
    digitos = re.sub(r"\D", "", cep)
    if len(digitos) != 8:
        raise HTTPException(status_code=422, detail="CEP deve ter 8 dígitos")
    local, lojas = await preparar_obra(digitos)
    if local is None:
        return {"origem": None, "lojas": [], "aviso": "Não consegui localizar este CEP."}
    saida = [{"nome": l.nome, "endereco": l.endereco, "km": l.km,
              "minutos_aprox": round(l.km / VELOCIDADE_MEDIA_KMH * 60) if l.km else None,
              "site": l.dominio, "mapa": _mapa(l.nome, l.endereco, local.cidade)} for l in lojas[:limite]]
    aviso = None if saida else "Nenhuma loja encontrada perto deste CEP (ou a busca de lojas está desligada)."
    if saida and any(x["km"] for x in saida):
        aviso = "Distância e tempo de carro aproximados: confira no mapa antes de ir."
    return {"origem": {"cidade": local.cidade, "uf": local.uf}, "lojas": saida, "aviso": aviso}
