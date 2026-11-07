"""Rotas da revisão (Fatia A): erros E1 e, na etapa 06, erros E1 + complementos E2 numa só resposta.

`POST /revisao/sugestoes` pertence ao João (src/rotas_resultado.py) e devolve só `{complementos}`. Para não duplicar
nem sobrescrever o caminho, o endpoint combinado da A é `POST /revisao/sugestoes/completo` (PROPOSTA: unificar depois,
com o João removendo o handler dele e a A assumindo `/revisao/sugestoes`).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .complementos import sugerir_complementos
from .revisao import ErroRevisao, ItemRevisao, _parse_quantidade, normalizar_unidade, revisar_e_redigir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/revisao", tags=["revisao"])


class RevisaoRequest(BaseModel):
    itens: list[ItemRevisao] = Field(max_length=5000)
    redigir: bool = True   # False = só texto fixo (sem LLM)


class RevisaoResponse(BaseModel):
    revisao_id: str
    erros: list[ErroRevisao]


class ComplementoSugerido(BaseModel):
    """Complemento E2 (da C) pronto para a tela. Só vira linha em orcamento_itens depois do aceite."""
    id: str                       # estável: mesma regra + mesma descrição = mesmo id (recusa vale após edições)
    regra: str
    descricao: str
    quantidade: float
    unidade: str
    categoria: str
    motivo: str
    origem_linhas: list[int]      # mesmas linhas usadas pelos erros E1 (linhaOrigem, senão a posição 1-based)
    origem_item_ids: list[str]    # ids das linhas da lista que motivaram a sugestão (para a tela apontar)
    estimativa_consumo: bool      # estimativa de CONSUMO da C; nada a ver com estimativa de PREÇO da B


class SugestoesCompletasResponse(BaseModel):
    revisao_id: str
    erros: list[ErroRevisao]
    complementos: list[ComplementoSugerido]
    complementos_disponiveis: bool
    complementos_erro: str | None = None


@router.post("/erros", response_model=RevisaoResponse)
def revisar(req: RevisaoRequest) -> RevisaoResponse:
    """Propõe correções E1. Não altera nada: a tela só aplica o que o arquiteto aceitar."""
    # Endpoint síncrono: o FastAPI o executa em threadpool, então a chamada ao LLM não bloqueia o event loop.
    rid, erros = revisar_e_redigir(req.itens, redigir=req.redigir)
    return RevisaoResponse(revisao_id=rid, erros=erros)


def _id_complemento(regra: str, descricao: str) -> str:
    return hashlib.sha1(f"{regra}|{descricao}".encode()).hexdigest()[:12]


def _complementos(itens: list[ItemRevisao]) -> list[ComplementoSugerido]:
    """Chama `sugerir_complementos` da C direto (função pura), com a quantidade já convertida de texto para número."""
    dicts: list[dict[str, Any]] = []
    ids_por_linha: dict[int, list[str]] = {}
    for pos, it in enumerate(itens, start=1):
        linha = it.linha_origem or it.linha or pos
        if it.id:
            ids_por_linha.setdefault(linha, []).append(it.id)
        dicts.append({
            "linha": linha, "categoria": it.categoria or "", "descricao": it.descricao or "",
            "quantidade": _parse_quantidade(it.quantidade),
            "unidade": normalizar_unidade(it.unidade) or (it.unidade or ""),
        })
    saida = []
    for c in sugerir_complementos(dicts):
        saida.append(ComplementoSugerido(
            id=_id_complemento(c.regra, c.descricao), regra=c.regra, descricao=c.descricao, quantidade=c.quantidade,
            unidade=c.unidade, categoria=c.categoria, motivo=c.motivo, origem_linhas=c.origem_linhas,
            origem_item_ids=[i for n in c.origem_linhas for i in ids_por_linha.get(n, [])],
            estimativa_consumo=c.estimativa,
        ))
    return saida


@router.post("/sugestoes/completo", response_model=SugestoesCompletasResponse)
def sugestoes_completo(req: RevisaoRequest) -> SugestoesCompletasResponse:
    """Erros E1 (A) + complementos E2 (C). Se a C falhar, os erros E1 saem do mesmo jeito e a resposta diz que os
    complementos não puderam ser calculados. Nada é gravado nem aplicado: a decisão é do arquiteto, na tela."""
    rid, erros = revisar_e_redigir(req.itens, redigir=req.redigir)
    try:
        complementos, disponivel, motivo = _complementos(req.itens), True, None
    except Exception:  # noqa: BLE001 - a C é de outra fatia; a revisão E1 não pode depender dela
        logger.exception("sugerir_complementos falhou; devolvendo só os erros E1")
        complementos, disponivel, motivo = [], False, "Não foi possível calcular os complementos agora."
    return SugestoesCompletasResponse(
        revisao_id=rid, erros=erros, complementos=complementos,
        complementos_disponiveis=disponivel, complementos_erro=motivo,
    )
