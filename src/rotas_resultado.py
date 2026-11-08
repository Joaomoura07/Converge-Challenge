"""Rotas da Fatia C (João): sugestões de itens esquecidos, resultado da compra e exportação.

Arquivo SEPARADO para não dar conflito no ``main.py``. Para ligar, basta:

    from .rotas_resultado import router as resultado_router
    app.include_router(resultado_router)

Rotas:
  POST /revisao/sugestoes              -> {complementos: [...]}                      (E2)
  POST /orcamentos/{id}/resultado      -> roda E7 + E8 + E10 e grava logistica/viabilidade/ganho em `orcamentos` (o gancho da Fatia B chama no fim da pesquisa)
  GET  /orcamentos/{id}/exportar.xlsx  -> plano de compra em Excel                   (E11)

Colunas esperadas no Supabase (combinadas em PARA-SAMUEL.md): ``orcamentos`` (cep, orcamento_cliente,
logistica, viabilidade, ganho, custo_usd; e as colunas da Fatia B pesquisa_iniciada_em/pesquisa_concluida_em), ``orcamento_itens`` e ``fornecedores``.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from langfuse import observe
from pydantic import BaseModel, Field

from .complementos import sugerir_complementos
from .database import get_supabase
from .exportar import gerar_xlsx
from .ganho import Ganho, calcular_ganho
from .logistica import Fornecedor, Logistica, calcular_logistica, distancias_km, enriquecer_rotas_lojas
from .viabilidade import Viabilidade, calcular_viabilidade

logger = logging.getLogger(__name__)
router = APIRouter(tags=["resultado"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# FRETE EM PAUSA (decisão do João, 07/11): enquanto FRETE_ATIVO não for "true", o frete é sempre R$ 0, não se
# consulta CEP/API e não se usa a tabela `fornecedores`. O plano de compra agrupa por loja pelo menor preço de
# cada item, usando as próprias `fontes`. Para voltar ao frete: FRETE_ATIVO=true (e cadastrar fornecedores).
def _frete_ativo() -> bool:
    return os.getenv("FRETE_ATIVO", "false").strip().lower() in ("1", "true", "sim")


def _lojas_pelas_fontes(itens: list[dict[str, Any]]) -> list[Fornecedor]:
    """Lojas a partir de `fontes[]` (sem frete): id = dominio, frete 0, sem distância, sem pedido mínimo."""
    vistas: dict[str, Fornecedor] = {}
    for it in itens:
        for f in it.get("fontes") or []:
            dom = str(f.get("dominio") or "").strip().lower()
            if dom and dom not in vistas:
                vistas[dom] = Fornecedor(id=dom, nome=f.get("loja") or dom, dominio=dom)
    return list(vistas.values())


# --- Acesso ao banco (isolado aqui para os testes trocarem por dados falsos) ---------------------------


def _carregar_orcamento(orcamento_id: str) -> dict[str, Any] | None:
    r = get_supabase().table("orcamentos").select("*").eq("id", orcamento_id).limit(1).execute()
    return r.data[0] if r.data else None


def _carregar_itens(orcamento_id: str) -> list[dict[str, Any]]:
    r = get_supabase().table("orcamento_itens").select("*").eq("orcamento_id", orcamento_id).execute()
    # Complemento sugerido (E2) só entra na conta depois que o arquiteto aceita (`aceito` = true).
    linhas = [i for i in (r.data or []) if not (i.get("sugerido") and i.get("aceito") is not True)]
    # ordem estável: os índices de logistica.lojas[].itens apontam para ESTA lista
    return sorted(linhas, key=lambda i: (i.get("linha") is None, i.get("linha") or 0, str(i.get("id"))))


def _carregar_fornecedores() -> list[Fornecedor]:
    r = get_supabase().table("fornecedores").select("*").eq("ativo", True).execute()
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


def _reaproveitados(itens: list[dict[str, Any]], inicio: Any) -> int:
    """Itens cujo preço é anterior ao início desta pesquisa: vieram do cache (a B grava em `preco_data`
    a data do preço, que no cache é a da pesquisa original). Folga de 1 s para relógios diferentes."""
    if not inicio:
        return 0
    n = 0
    for i in itens:
        if not i.get("preco_data"):
            continue
        antes = _segundos(i["preco_data"], inicio)
        if antes is not None and antes > 1.0:
            n += 1
    return n


@observe(name="fatia_c.resultado", as_type="chain", capture_input=False, capture_output=False)
def calcular_resultado(orc: dict[str, Any], itens: list[dict[str, Any]],
                       fornecedores: list[Fornecedor]) -> dict[str, Any]:
    """Roda logística (E7), viabilidade (E8) e ganho (E10). Cada parte vem ``None`` se faltar dado."""
    lg: Logistica | None = None
    if itens and _frete_ativo() and fornecedores:
        km = distancias_km(orc.get("cep") or "", fornecedores)
        lg = calcular_logistica(itens, fornecedores, km)
    elif itens:
        lg = calcular_logistica(itens, _lojas_pelas_fontes(itens), {})   # frete 0: só agrupa pelo menor preço
        if lg and lg.lojas:
            enriquecer_rotas_lojas(lg.lojas, str(orc.get("cep") or ""))
    vi: Viabilidade | None = None
    if orc.get("orcamento_cliente") is not None:
        vi = calcular_viabilidade(itens, float(orc["orcamento_cliente"]), lg.frete_total if lg else 0.0)

    agora = datetime.now(timezone.utc)
    # colunas da Fatia B (pesquisa_*); `iniciado_em`/`concluido_em` ficam como alternativa
    inicio = orc.get("pesquisa_iniciada_em") or orc.get("iniciado_em")
    fim = orc.get("pesquisa_concluida_em") or orc.get("concluido_em") or agora
    seg = _segundos(inicio, fim)
    ganho = (calcular_ganho(len(itens), seg, float(orc.get("custo_usd") or 0),
                            reaproveitados=_reaproveitados(itens, inicio))
             if seg is not None else None)

    dados = {
        "logistica": lg.model_dump(mode="json") if lg else None,
        "viabilidade": vi.model_dump(mode="json") if vi else None,
        "ganho": ganho.model_dump(mode="json") if ganho else None,
    }
    if vi:   # colunas do SQL único (orcamentos.total_*) que ninguém gravava; mesmos números da viabilidade
        dados |= {"total_min": vi.total_min, "total_med": vi.total_med, "total_max": vi.total_max}
    return dados


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
    dados = calcular_resultado(orc, _carregar_itens(orcamento_id),
                               _carregar_fornecedores() if _frete_ativo() else [])
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
    itens = _carregar_itens(orcamento_id)
    forn = _carregar_fornecedores() if _frete_ativo() else _lojas_pelas_fontes(itens)
    r = calcular_resultado(orc, itens, forn)
    lg = Logistica.model_validate(r["logistica"]) if r["logistica"] else None
    vi = Viabilidade.model_validate(r["viabilidade"]) if r["viabilidade"] else None
    ganho = Ganho.model_validate(r["ganho"]) if r["ganho"] else None
    arquivo = gerar_xlsx({"nome": orc.get("nome") or "Obra", "cep": orc.get("cep") or "—"},
                         itens, forn, lg, vi, ganho)
    return Response(content=arquivo, media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="plano-de-compra.xlsx"'})
