"""E10 — Ganho na tela: tempo e custo à mão × com o agente. Função pura."""

from __future__ import annotations

from pydantic import BaseModel

MINUTOS_POR_ITEM_A_MAO = 18.0   # estimativa: achar loja, comparar, anotar, somar frete (≈6 h para 20 itens)
CAMBIO_BRL = 5.5                # US$ -> R$ (só para exibir o custo de IA)


class Ganho(BaseModel):
    minutos_a_mao: float
    segundos_reais: float
    custo_ia_brl: float
    reducao_pct: float          # 0–100, quanto do tempo foi poupado
    texto_a_mao: str
    texto_real: str
    texto_custo: str
    resumo: str                 # "À mão: ~6 h. Aqui: 28 s. Custo de IA: R$ 0,30"


def _duracao(segundos: float) -> str:
    s = round(segundos)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        m, r = divmod(s, 60)
        return f"{m} min" + (f" {r} s" if r else "")
    h, r = divmod(s, 3600)
    return f"{h} h" + (f" {r // 60} min" if r // 60 else "")


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _custo_texto(custo_brl_exato: float) -> str:
    """Frações de centavo não viram "R$ 0,00": a tela diria que foi de graça quando não foi."""
    if 0 < custo_brl_exato < 0.005:
        return "menos de R$ 0,01"
    return _brl(round(custo_brl_exato, 2))


def calcular_ganho(n_itens: int, segundos_reais: float, custo_usd: float = 0.0,
                   minutos_por_item: float = MINUTOS_POR_ITEM_A_MAO,
                   cambio: float = CAMBIO_BRL, reaproveitados: int = 0) -> Ganho:
    """``reaproveitados``: itens cujo preço veio de pesquisa anterior (cache de 7 dias da Fatia B).
    Sem esse aviso, "Aqui: 2 s" numa obra já pesquisada parece número inventado."""
    n = max(0, int(n_itens))
    real = max(0.0, float(segundos_reais))
    min_mao = round(n * minutos_por_item, 1)
    custo_exato = max(0.0, float(custo_usd)) * cambio
    custo = round(custo_exato, 2)
    a_mao_s = min_mao * 60
    reducao = round(max(0.0, 1 - real / a_mao_s) * 100, 1) if a_mao_s > 0 else 0.0
    ta = "~" + _duracao(a_mao_s)
    tr, tc = _duracao(real), _custo_texto(custo_exato)
    k = min(max(0, int(reaproveitados)), n)
    aqui = tr
    if k:
        palavra = "preço reaproveitado" if n == 1 else "preços reaproveitados"   # "1 de 3 preços"
        aqui = f"{tr}, com {k} de {n} {palavra} de pesquisa recente"
    return Ganho(minutos_a_mao=min_mao, segundos_reais=round(real, 1), custo_ia_brl=custo,
                 reducao_pct=reducao, texto_a_mao=ta, texto_real=tr, texto_custo=tc,
                 resumo=f"À mão: {ta}. Aqui: {aqui}. Custo de IA: {tc}")
