"""E8 — Viabilidade: o orçamento do cliente cobre a lista de compra?

Função pura. Entrada por item (da Fatia B): ``preco_emb_min/med/max``, ``qtd_embalagens``,
``status``, ``estimativa`` (faixa estimada de item genérico) e, opcionalmente, ``similar``
(T2: ``{descricao, preco_emb_med}``). O frete vem da E7 (``calcular_logistica``).

Todas as economias sugeridas saem de números que o sistema já tem (faixa mín–máx, frete,
similar); nada é chutado. São SUGESTÕES: o arquiteto decide.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

SEM_PRECO = ("pendente_especificacao", "nao_encontrado", "erro", "buscando")


class Sugestao(BaseModel):
    tipo: str                          # similar | preco_minimo | frete | pendencias
    texto: str
    economia: float | None = None      # R$; None quando não dá para estimar sem inventar
    itens: list[int] = []


class Viabilidade(BaseModel):
    orcamento_cliente: float
    total_min: float
    total_med: float
    total_max: float
    frete: float
    cabe: bool                         # cabe no total médio
    cabe_no_minimo: bool               # cabe se tudo sair pelo menor preço encontrado
    diferenca: float                   # med - orçamento (positivo = falta; negativo = sobra)
    resumo: str
    inclui_estimativas: bool
    completo: bool                     # False se há itens sem preço: o total é só um piso
    itens_sem_preco: list[int]
    sugestoes: list[Sugestao]


def _brl(v: float) -> str:
    return "R$ " + f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _custos(it: dict[str, Any]) -> tuple[float, float, float] | None:
    q = it.get("qtd_embalagens") or 0
    mn, md, mx = (it.get(k) for k in ("preco_emb_min", "preco_emb_med", "preco_emb_max"))
    if not q or md is None or md <= 0:
        return None
    return (q * (mn or md), q * md, q * (mx or md))


def calcular_viabilidade(itens: list[dict[str, Any]], orcamento_cliente: float,
                         frete_total: float = 0.0) -> Viabilidade:
    mn = md = mx = 0.0
    sem_preco: list[int] = []
    estim = False
    linhas: list[tuple[int, float, float]] = []      # (idx, med, med-min)
    for i, it in enumerate(itens):
        c = None if it.get("status") in ("nao_encontrado", "erro", "buscando") else _custos(it)
        if c is None:
            sem_preco.append(i)
            continue
        mn, md, mx = mn + c[0], md + c[1], mx + c[2]
        estim = estim or bool(it.get("estimativa")) or it.get("status") == "pendente_especificacao"
        linhas.append((i, c[1], c[1] - c[0]))
    frete = round(float(frete_total or 0), 2)
    mn, md, mx = round(mn + frete, 2), round(md + frete, 2), round(mx + frete, 2)

    dif = round(md - orcamento_cliente, 2)
    cabe, cabe_min = md <= orcamento_cliente, mn <= orcamento_cliente
    n_sem = len(sem_preco)
    completo = n_sem == 0
    if cabe:
        resumo = f"Cabe: total estimado {_brl(md)} para orçamento de {_brl(orcamento_cliente)} (sobram {_brl(-dif)})."
    elif cabe_min:
        resumo = (f"Cabe só no menor preço: média {_brl(md)} passa {_brl(dif)} do orçamento, "
                  f"mas o total mínimo {_brl(mn)} cabe.")
    else:
        resumo = f"Não cabe: faltam {_brl(dif)} (média {_brl(md)} para orçamento de {_brl(orcamento_cliente)})."
    if not completo:
        # itens sem preço ficam fora da soma: o total real é MAIOR que o mostrado
        plural = "item ainda sem preço ficou" if n_sem == 1 else "itens ainda sem preço ficaram"
        if cabe or cabe_min:
            resumo = (f"Ainda não dá para afirmar: {n_sem} {plural} fora do total. "
                      + resumo.replace("Cabe:", "Até agora cabe:", 1).replace("Cabe só", "Até agora cabe só", 1))
        else:
            resumo += f" E {n_sem} {plural} fora desse total, então a diferença tende a ser maior."

    sug: list[Sugestao] = []
    for i, it in enumerate(itens):                     # T2: similar técnico mais barato
        s, q = it.get("similar"), it.get("qtd_embalagens") or 0
        if s and s.get("preco_emb_med") and it.get("preco_emb_med") and q:
            eco = round((it["preco_emb_med"] - s["preco_emb_med"]) * q, 2)
            if eco > 0:
                sug.append(Sugestao(tipo="similar", economia=eco, itens=[i],
                                    texto=f"Trocar por {s.get('descricao', 'similar técnico')} "
                                          f"economiza {_brl(eco)} (confirme se atende à especificação)."))
    maiores = sorted(linhas, key=lambda x: x[2], reverse=True)[:3]
    eco_min = round(sum(x[2] for x in maiores), 2)
    if eco_min > 0:
        sug.append(Sugestao(tipo="preco_minimo", economia=eco_min, itens=[x[0] for x in maiores],
                            texto=f"Fechar os {len(maiores)} itens de maior variação de preço na loja mais barata "
                                  f"economiza até {_brl(eco_min)}."))
    if frete > 0 and md > 0 and frete / md > 0.08:
        sug.append(Sugestao(tipo="frete", economia=frete,
                            texto=f"O frete ({_brl(frete)}) pesa {frete / md:.0%} do total: "
                                  f"retirar na loja ou agrupar entregas pode eliminá-lo."))
    pend = [i for i, it in enumerate(itens) if it.get("status") == "pendente_especificacao"]
    if pend:
        sug.append(Sugestao(tipo="pendencias", itens=pend,
                            texto=f"{len(pend)} item(ns) ainda sem especificação entram com valor estimado: "
                                  f"defini-los pode mudar o total."))
    sug.sort(key=lambda s: (s.economia is None, -(s.economia or 0)))
    sug = sug[:3] if not cabe else sug[:1]             # se cabe, só a dica mais útil

    return Viabilidade(orcamento_cliente=orcamento_cliente, total_min=mn, total_med=md, total_max=mx,
                       frete=frete, cabe=cabe, cabe_no_minimo=cabe_min, diferenca=dif, resumo=resumo,
                       inclui_estimativas=estim, completo=completo, itens_sem_preco=sem_preco, sugestoes=sug)
