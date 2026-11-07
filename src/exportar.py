"""E11 — Exportar o plano de compra em Excel, agrupado por loja (para levar ao cliente e à loja)."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .ganho import Ganho
from .logistica import Fornecedor, Logistica, _precos_por_loja, _dominio
from .viabilidade import Viabilidade

BRL = '"R$" #,##0.00'
NEGRITO = Font(bold=True)
CABECALHO = PatternFill("solid", fgColor="DDDDDD")
LOJA = PatternFill("solid", fgColor="EFEFEF")


def _link_da_loja(item: dict[str, Any], f: Fornecedor) -> tuple[float | None, str]:
    """(menor preço de embalagem nessa loja, url dessa fonte)."""
    melhor: tuple[float, str] | None = None
    for fonte in item.get("fontes") or []:
        if _dominio(fonte.get("dominio") or fonte.get("url")) != _dominio(f.dominio):
            continue
        p = fonte.get("preco_embalagem")
        if isinstance(p, (int, float)) and p > 0 and (melhor is None or p < melhor[0]):
            melhor = (float(p), fonte.get("url") or "")
    return melhor if melhor else (None, "")


def _linha_cabecalho(ws, linha: int, titulos: list[str]) -> None:
    for c, t in enumerate(titulos, 1):
        cel = ws.cell(row=linha, column=c, value=t)
        cel.font, cel.fill = NEGRITO, CABECALHO


def gerar_xlsx(obra: dict[str, Any], itens: list[dict[str, Any]], fornecedores: list[Fornecedor],
               logistica: Logistica | None = None, viabilidade: Viabilidade | None = None,
               ganho: Ganho | None = None) -> bytes:
    """Devolve o .xlsx em bytes. Abas: Plano de compra (por loja), Pendentes, Resumo."""
    forn = {f.id: f for f in fornecedores}
    wb = Workbook()

    # --- Plano de compra, agrupado por loja ---
    ws = wb.active
    ws.title = "Plano de compra"
    ws["A1"] = f"Plano de compra — {obra.get('nome', 'Obra')}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"CEP da obra: {obra.get('cep', '—')}"
    r = 4
    atribuidos: set[int] = set()
    for loja in (logistica.lojas if logistica else []):
        f = forn.get(loja.id)
        ws.cell(row=r, column=1, value=f"{loja.nome} — {loja.distancia_km} km").font = NEGRITO
        for c in range(1, 8):
            ws.cell(row=r, column=c).fill = LOJA
        r += 1
        _linha_cabecalho(ws, r, ["Item", "Embalagem", "Qtd. embalagens", "Preço unit.", "Subtotal",
                                 "Confiança", "Fonte"])
        r += 1
        for i in loja.itens:
            it = itens[i]
            preco, url = _link_da_loja(it, f) if f else (None, "")
            q = it.get("qtd_embalagens") or 0
            ws.cell(row=r, column=1, value=it.get("descricao") or it.get("produto") or f"Item {i + 1}")
            ws.cell(row=r, column=2, value=it.get("embalagem"))
            ws.cell(row=r, column=3, value=q)
            ws.cell(row=r, column=4, value=preco).number_format = BRL
            ws.cell(row=r, column=5, value=round(preco * q, 2) if preco else None).number_format = BRL
            ws.cell(row=r, column=6, value=it.get("confianca"))
            if url:
                cel = ws.cell(row=r, column=7, value=url)
                cel.hyperlink = url
                cel.font = Font(color="0563C1", underline="single")
            atribuidos.add(i)
            r += 1
        ws.cell(row=r, column=4, value="Produtos").font = NEGRITO
        ws.cell(row=r, column=5, value=loja.subtotal).number_format = BRL
        r += 1
        ws.cell(row=r, column=4, value="Frete").font = NEGRITO
        ws.cell(row=r, column=5, value=loja.frete).number_format = BRL
        if loja.abaixo_do_minimo:
            ws.cell(row=r, column=6, value=f"Atenção: abaixo do pedido mínimo (R$ {loja.pedido_minimo:.2f})")
        r += 2
    if logistica:
        ws.cell(row=r, column=4, value="TOTAL").font = NEGRITO
        ws.cell(row=r, column=5, value=logistica.total).number_format = BRL
        ws.cell(row=r, column=5).font = NEGRITO
    for c, w in enumerate([46, 22, 16, 14, 14, 14, 50], 1):
        ws.column_dimensions[get_column_letter(c)].width = w

    # --- Pendentes e sem loja ---
    wp = wb.create_sheet("Pendentes")
    _linha_cabecalho(wp, 1, ["Item", "Status", "Observação"])
    rp = 2
    for i, it in enumerate(itens):
        if i in atribuidos:
            continue
        wp.cell(row=rp, column=1, value=it.get("descricao") or it.get("produto") or f"Item {i + 1}")
        wp.cell(row=rp, column=2, value=it.get("status") or "sem loja")
        wp.cell(row=rp, column=3, value=it.get("pergunta") or "Sem preço em loja cadastrada")
        rp += 1
    for c, w in enumerate([46, 24, 60], 1):
        wp.column_dimensions[get_column_letter(c)].width = w

    # --- Resumo ---
    wr = wb.create_sheet("Resumo")
    linhas: list[tuple[str, Any, str | None]] = []
    if viabilidade:
        linhas += [("Orçamento do cliente", viabilidade.orcamento_cliente, BRL),
                   ("Total mínimo", viabilidade.total_min, BRL), ("Total médio", viabilidade.total_med, BRL),
                   ("Total máximo", viabilidade.total_max, BRL), ("Situação", viabilidade.resumo, None)]
        for s in viabilidade.sugestoes:
            linhas.append(("Sugestão", s.texto, None))
    if logistica:
        linhas += [("Estratégia de compra", logistica.estrategia.replace("_", " "), None),
                   ("Frete total", logistica.frete_total, BRL),
                   ("Economia estimada", logistica.economia_estimada, BRL)]
    if ganho:
        linhas.append(("Ganho de tempo", ganho.resumo, None))
    for k, (rot, val, fmt) in enumerate(linhas, 1):
        wr.cell(row=k, column=1, value=rot).font = NEGRITO
        cel = wr.cell(row=k, column=2, value=val)
        cel.alignment = Alignment(wrap_text=True, vertical="top")
        if fmt:
            cel.number_format = fmt
    wr.column_dimensions["A"].width = 24
    wr.column_dimensions["B"].width = 90

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
