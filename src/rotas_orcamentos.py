"""Fatia A, etapa 08: POST /orcamentos ("Enviar para a IA").

Valida o corpo pelo contrato da importação, grava orçamento e itens de uma vez (função SQL `criar_orcamento`,
itens em `buscando`, classificação única `classificar_item`) e chama `pesquisar_orcamento(id)` da Fatia B na
MESMA requisição (a Vercel encerra o que roda depois da resposta). A tela já conhece o `orcamento_id` (UUID gerado
por ela) e acompanha pelo Realtime enquanto a requisição está aberta.

Reenvio e recuperação: o mesmo corpo com o mesmo UUID recupera o orçamento (não duplica itens); conteúdo
diferente com o mesmo UUID dá 409. Se a pesquisa falhar ou a resposta se perder, o orçamento continua gravado:
reenviar o mesmo corpo é seguro (quem decide se pesquisa de novo é a reserva da B, que não roda duas vezes ao mesmo tempo).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from langfuse import get_client, observe
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import get_settings
from .revisao import classificar_item

logger = logging.getLogger(__name__)
router = APIRouter(tags=["orcamentos"])

UNIDADES = ("m", "m2", "m3", "un", "kg", "l", "cm", "mm")
LIMITE_ITENS = 5000   # o contrato permite 100 mil; a requisição é única e o banco recebe tudo de uma vez


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)   # decisão D7: quantidade em texto é recusada (422)


class ObraIn(_Estrito):
    nome: str = Field(min_length=1, max_length=120)
    cep: str
    orcamento_cliente: float = Field(gt=0, lt=1_000_000_000_000)   # em reais, com centavos

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if not v:
            raise ValueError("Dê um nome à obra.")
        return v

    @field_validator("cep")
    @classmethod
    def _cep(cls, v: str) -> str:
        limpo = re.sub(r"[\s.\-]", "", v)
        if not re.fullmatch(r"\d{8}", limpo):
            raise ValueError("O CEP deve ter 8 dígitos.")
        return limpo   # texto: o zero à esquerda é preservado


class ItemIn(_Estrito):
    """Item já revisado pelo arquiteto. Mesmos campos de tests/importacao/contrato.py (Item) mais o `id` da tela."""

    id: str = Field(min_length=1, max_length=64)   # ID estável da linha na tela (vira id_linha)
    linha: int = Field(ge=1)
    categoria: str | None = None
    descricao: str = Field(min_length=1, max_length=2000)
    descricao_original: str | None = None
    quantidade: float = Field(gt=0, lt=1_000_000_000)
    unidade: Literal["m", "m2", "m3", "un", "kg", "l", "cm", "mm"]
    nivel: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
    origem_item: Literal["arquivo", "manual"] = "manual"
    sugestao_aceita_id: str | None = None
    # Complemento da C (E2). Só é gravado depois da decisão do arquiteto.
    sugerido: bool = False
    sugestao_regra: str | None = None
    sugestao_motivo: str | None = None
    origem_linhas: list[int] | None = None
    aceito: bool | None = None
    estimativa_consumo: bool = False   # consumo estimado pela C: NÃO é a estimativa de preço da B

    @field_validator("descricao")
    @classmethod
    def _descricao(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if not v:
            raise ValueError("Descreva o material.")
        return v

    @model_validator(mode="after")
    def _complemento(self) -> "ItemIn":
        if self.sugerido and (not self.sugestao_regra or not self.origem_linhas or self.aceito is None):
            raise ValueError("Complemento sugerido precisa de regra, linhas de origem e decisão (aceito).")
        return self


class OrcamentoIn(_Estrito):
    orcamento_id: UUID
    obra: ObraIn
    origem: dict[str, Any]   # {tipo, modo, ...}: obrigatória, como no contrato da importação (TC-095)
    itens: list[ItemIn] = Field(min_length=1, max_length=LIMITE_ITENS)

    @field_validator("orcamento_id", mode="before")
    @classmethod
    def _uuid(cls, v: Any) -> Any:   # strict não converte texto em UUID; a tela manda o texto do UUID
        return UUID(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def _ids_unicos(self) -> "OrcamentoIn":
        ids = [i.id for i in self.itens]
        if len(set(ids)) != len(ids):
            raise ValueError("Há itens com o mesmo id.")
        return self


# --------------------------------------------------------------------------- persistência


def calcular_hash(obra: dict[str, Any], itens: list[dict[str, Any]], *, demo: bool = False) -> str:
    """Resumo do CONTEÚDO enviado (obra e itens persistidos). Detecta conflito no reenvio com o mesmo UUID.
    A origem do arquivo é informativa; o modo demo entra no hash porque muda como o preço é obtido."""
    base = json.dumps({"obra": obra, "itens": itens, **({"demo": True} if demo else {})},
                      ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(base.encode()).hexdigest()


def _item_para_banco(i: ItemIn) -> dict[str, Any]:
    return {
        "id_linha": i.id, "linha": i.linha, "categoria": i.categoria,
        "descricao_original": i.descricao_original or i.descricao, "descricao": i.descricao,
        "quantidade": i.quantidade, "unidade": i.unidade, "nivel": i.nivel, "origem_item": i.origem_item,
        "extras": i.extras,
        # Classificação única da A: a B confirma na pesquisa e a C só lê.
        "classificacao": classificar_item(i.descricao),
        "sugestao_aceita_id": i.sugestao_aceita_id, "sugerido": i.sugerido, "sugestao_regra": i.sugestao_regra,
        "sugestao_motivo": i.sugestao_motivo, "origem_linhas": i.origem_linhas, "aceito": i.aceito,
        "estimativa_consumo": i.estimativa_consumo,
    }


def _supabase_ok() -> bool:
    return get_settings().supabase_configured


@observe(name="orcamentos.gravar", capture_input=False, capture_output=False)
def _criar_no_banco(orcamento_id: str, hash_conteudo: str, obra: dict, origem: dict, itens: list[dict]) -> dict:
    """Chama a função SQL `criar_orcamento` (uma transação: orçamento e itens, ou nada). Síncrono (supabase-py)."""
    from .database import get_supabase

    resp = get_supabase().rpc("criar_orcamento", {
        "p_id": orcamento_id, "p_hash": hash_conteudo, "p_obra": obra, "p_origem": origem, "p_itens": itens,
    }).execute()
    dados = resp.data
    if isinstance(dados, list):
        dados = dados[0] if dados else None
    if not isinstance(dados, dict) or "resultado" not in dados:
        raise RuntimeError("resposta inesperada de criar_orcamento")
    try:
        get_client().update_current_span(metadata={"itens": len(itens), "resultado": dados["resultado"]})
    except Exception:  # noqa: BLE001 - telemetria nunca derruba a gravação
        pass
    return dados


async def _pesquisar(orcamento_id: str) -> dict:
    from .orcamento import pesquisar_orcamento   # import tardio: as rotas não dependem da pesquisa para subir

    return await pesquisar_orcamento(orcamento_id)


# códigos SQLSTATE de dado inválido (check, not null, parâmetro inválido): culpa do corpo, não do servidor
_CODIGOS_DADO_INVALIDO = {"23514", "23502", "23505", "22023", "22P02", "22003"}


def _erro_do_banco(exc: Exception) -> HTTPException:
    codigo = str(getattr(exc, "code", "") or "")
    if codigo in _CODIGOS_DADO_INVALIDO:
        return HTTPException(status_code=422, detail={"mensagem": "O banco recusou os dados enviados.", "codigo": codigo})
    return HTTPException(status_code=502, detail={"mensagem": "Não consegui gravar o orçamento. Tente de novo."})


# --------------------------------------------------------------------------- rota


@router.post("/orcamentos")
async def criar_orcamento(req: OrcamentoIn) -> dict[str, Any]:
    """"Enviar para a IA": grava, pesquisa na mesma requisição e devolve o estado."""
    if not _supabase_ok():
        raise HTTPException(status_code=503, detail="Supabase não configurado")

    # Complemento recusado nunca vira linha: com status 'buscando' a B o pesquisaria à toa (PROPOSTA da A).
    ignorados = [i.id for i in req.itens if i.sugerido and i.aceito is False]
    mantidos = [i for i in req.itens if not (i.sugerido and i.aceito is False)]
    if not mantidos:
        raise HTTPException(status_code=422, detail="Nenhum item para enviar: todos os complementos foram recusados.")

    orcamento_id = str(req.orcamento_id)
    itens_db = [_item_para_banco(i) for i in mantidos]
    obra = req.obra.model_dump()
    hash_conteudo = calcular_hash(obra, itens_db, demo=req.origem.get("demo") is True)

    try:
        gravado = await asyncio.to_thread(_criar_no_banco, orcamento_id, hash_conteudo, obra, req.origem, itens_db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao gravar o orçamento %s", orcamento_id)
        raise _erro_do_banco(exc) from exc

    resultado = gravado["resultado"]
    if resultado == "conflito":
        raise HTTPException(status_code=409, detail={
            "mensagem": "Já existe um orçamento com este código e conteúdo diferente. Gere um novo envio.",
            "orcamento_id": orcamento_id,
        })

    # 'criado' ou 'existente' (reenvio equivalente, por exemplo depois de perder a resposta): chama a pesquisa
    # nos dois casos. A reserva da B garante que ela não roda duas vezes ao mesmo tempo nem repete orçamento concluído.
    try:
        pesquisa = await _pesquisar(orcamento_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("A pesquisa do orçamento %s falhou", orcamento_id)
        raise HTTPException(status_code=502, detail={
            "mensagem": "O orçamento foi salvo, mas a pesquisa falhou. Reenvie o mesmo pedido para tentar de novo.",
            "orcamento_id": orcamento_id,
            "recuperavel": True,
        }) from exc

    return {
        "orcamento_id": orcamento_id,
        "resultado": resultado,                      # criado | existente
        "itens": len(itens_db),
        "complementos_recusados_ignorados": ignorados,
        "pesquisa": pesquisa,                        # o que a B devolveu (status, itens, por_status...)
    }
