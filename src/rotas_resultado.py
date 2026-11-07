"""Rotas da Fatia C (João): sugestões de itens esquecidos, resultado da compra e exportação.

Arquivo SEPARADO para não dar conflito no ``main.py``. Para ligar, basta:

    from .rotas_resultado import router as resultado_router
    app.include_router(resultado_router)

Rotas:
  POST /revisao/sugestoes              -> {complementos: [...]}                      (E2)
  POST /orcamentos/{id}/resultado      -> roda E7 + E8 + E10 e grava em `orcamentos` (o Enzo chama no fim da pesquisa)
  GET  /orcamentos/{id}/exportar.xlsx  -> plano de compra em Excel                   (E11)

Colunas esperadas no Supabase (combinadas em PARA-SAMUEL.md): ``orcamentos`` (cep, orcamento_cliente,
logistica, viabilidade, ganho, iniciado_em, concluido_em, custo_usd), ``orcamento_itens`` e ``fornecedores``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .complementos import sugerir_complementos
from .database import get_supabase
from .exportar import gerar_xlsx
from .ganho import Ganho, calcular_ganho
from .logistica import Fornecedor, Logistica, calcular_logistica, distancias_km
from .viabilidade import Viabilidade, calcular_viabilidade

logger = logging.getLogger(__name__)
router = APIRouter(tags=["resultado"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --- Acesso ao banco (isolado aqui para os testes trocarem por dados falsos) ---------------------------


def _carregar_orcamento(orcamento_id: str) -> dict[str, Any] | None:
    r = get_supabase().table("orcamentos").select("*").eq("id", orcamento_id).limit(1).execute()
    return r.data[0] if r.data else None


def _carregar_itens(orcamento_id: str) -> list[dict[str, Any]]:
    r = get_supabase().table("orcamento_itens").select("*").eq("orcamento_id", orcamento_id).execute()
    # ordem estável: os índices de logistica.lojas[].itens apontam para ESTA lista
    return sorted(r.data or [], key=lambda i: (i.get("linha") is None, i.get("linha") or 0, str(i.get("id"))))


def _carregar_fornecedores() -> list[Fornecedor]:
    r = get_supabase().table("fornecedores").select("*").execute()
    return [Fornecedor.model_validate(row) for row in (r.data or [])]


def _gravar_resultado(orcamento_id: str, dados: dict[str, Any]) -> None:
    get_supabase().table("orcamentos").update(dados).eq("id", orcamento_id).execute()


# --- Núcleo (sem rede além do banco/CEP): calcula tudo que a tela de resultado precisa --------------------


def _segundos(inicio: Any, fim: Any) -> float | None:
    try:
        a = datetime.fromisoformat(str(inicio).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(fim).replace("Z", "+00:00"))
        return max(0.0, (b - a).total_seconds())
    except (TypeError, ValueError):
        return None


def calcular_resultado(orc: dict[str, Any], itens: list[dict[str, Any]],
                       fornecedores: list[Fornecedor]) -> dict[str, Any]:
    """Roda logística (E7), viabilidade (E8) e ganho (E10). Cada parte vem ``None`` se faltar dado."""
    lg: Logistica | None = None
    if itens and fornecedores:
        km = distancias_km(orc.get("cep") or "", fornecedores)
        lg = calcular_logistica(itens, fornecedores, km)

    vi: Viabilidade | None = None
    if orc.get("orcamento_cliente") is not None:
        vi = calcular_viabilidade(itens, float(orc["orcamento_cliente"]), lg.frete_total if lg else 0.0)

    agora = datetime.now(timezone.utc)
    seg = _segundos(orc.get("iniciado_em"), orc.get("concluido_em") or agora)
    ganho = calcular_ganho(len(itens), seg, float(orc.get("custo_usd") or 0)) if seg is not None else None

    return {
        "logistica": lg.model_dump(mode="json") if lg else None,
        "viabilidade": vi.model_dump(mode="json") if vi else None,
        "ganho": ganho.model_dump(mode="json") if ganho else None,
        "concluido_em": (orc.get("concluido_em") or agora.isoformat()),
    }


# --- Rotas ---------------------------------------------------------------------------------------------


class SugestoesIn(BaseModel):
    itens: list[dict[str, Any]] = Field(max_length=5000)


@router.post("/revisao/sugestoes")
def sugestoes(corpo: SugestoesIn) -> dict[str, Any]:
    """E2: complementos que costumam faltar. A Fatia A junta isto com os `erros` do revisor (E1)."""
    return {"complementos": [c.model_dump(mode="json") for c in sugerir_complementos(corpo.itens)]}


def _ou_404(orcamento_id: str) -> dict[str, Any]:
    orc = _carregar_orcamento(orcamento_id)
    if orc is None:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    return orc


@router.post("/orcamentos/{orcamento_id}/resultado")
def resultado(orcamento_id: str) -> dict[str, Any]:
    """Calcula frete, viabilidade e ganho e grava em `orcamentos` (a tela atualiza via Realtime)."""
    orc = _ou_404(orcamento_id)
    dados = calcular_resultado(orc, _carregar_itens(orcamento_id), _carregar_fornecedores())
    try:
        _gravar_resultado(orcamento_id, dados)
    except Exception:  # noqa: BLE001
        logger.exception("Não foi possível gravar o resultado do orçamento %s", orcamento_id)
        raise HTTPException(status_code=502, detail="Calculei o resultado, mas não consegui salvar no banco.")
    return dados


@router.get("/orcamentos/{orcamento_id}/exportar.xlsx")
def exportar(orcamento_id: str) -> Response:
    """E11: plano de compra em Excel, agrupado por loja."""
    orc = _ou_404(orcamento_id)
    itens, forn = _carregar_itens(orcamento_id), _carregar_fornecedores()
    r = calcular_resultado(orc, itens, forn)
    lg = Logistica.model_validate(r["logistica"]) if r["logistica"] else None
    vi = Viabilidade.model_validate(r["viabilidade"]) if r["viabilidade"] else None
    ganho = Ganho.model_validate(r["ganho"]) if r["ganho"] else None
    arquivo = gerar_xlsx({"nome": orc.get("nome") or "Obra", "cep": orc.get("cep") or "—"},
                         itens, forn, lg, vi, ganho)
    return Response(content=arquivo, media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="plano-de-compra.xlsx"'})
