"""GET /orcamentos/{id}/exportar.pdf — plano de compra em PDF, irmão do Excel da Fatia C (exportar.xlsx).

Arquivo separado para não mexer em `rotas_resultado.py` (da C). Lê o orçamento e os itens pelas mesmas funções da C.
Frete, viabilidade e ganho vêm do que a C já gravou em `orcamentos` (é o que a tela mostra); só se faltar algum,
calcula na hora pelo mesmo caminho do Excel.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from .config import get_settings
from .exportar_pdf import gerar_pdf
from .ganho import Ganho
from .logistica import Logistica
from .viabilidade import Viabilidade

logger = logging.getLogger(__name__)
router = APIRouter(tags=["exportar"])

PDF = "application/pdf"
NAO_ENCONTRADO = "Orçamento não encontrado."


def _ler(modelo: Any, dado: Any) -> Any:
    """Coluna jsonb da C → modelo. Dado ausente ou fora do formato = None (cai no cálculo na hora)."""
    if not dado:
        return None
    try:
        return modelo.model_validate(dado)
    except Exception:  # noqa: BLE001
        logger.warning("Coluna de %s fora do formato esperado; recalculando", modelo.__name__)
        return None


@router.get("/orcamentos/{orcamento_id}/exportar.pdf")
def exportar_pdf(orcamento_id: str) -> Response:
    """Plano de compra em PDF: resumo, itens com preço e fontes, onde comprar e o que depende do arquiteto."""
    try:
        uuid.UUID(orcamento_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
    if not get_settings().supabase_configured:
        raise HTTPException(status_code=503, detail="Supabase não configurado")
    from . import rotas_resultado as rr   # import tardio: as funções da C que leem o banco

    orc = rr._ou_404(orcamento_id)
    itens = rr._carregar_itens(orcamento_id)
    logi = _ler(Logistica, orc.get("logistica"))
    viab = _ler(Viabilidade, orc.get("viabilidade"))
    ganho = _ler(Ganho, orc.get("ganho"))
    if itens and (logi is None or viab is None):
        forn = rr._carregar_fornecedores() if rr._frete_ativo() else rr._lojas_pelas_fontes(itens)
        r = rr.calcular_resultado(orc, itens, forn)
        logi = logi or _ler(Logistica, r.get("logistica"))
        viab = viab or _ler(Viabilidade, r.get("viabilidade"))
        ganho = ganho or _ler(Ganho, r.get("ganho"))
    try:
        arquivo = gerar_pdf({"nome": orc.get("nome") or "Obra", "cep": orc.get("cep") or "—"},
                            itens, logi, viab, ganho)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao gerar o PDF do orçamento %s", orcamento_id)
        raise HTTPException(status_code=500, detail="Não consegui gerar o PDF. Tente de novo em instantes.")
    return Response(content=arquivo, media_type=PDF,
                    headers={"Content-Disposition": 'attachment; filename="plano-de-compra.pdf"',
                             "Cache-Control": "no-store"})
