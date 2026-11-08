"""Métricas da pesquisa de preço para o pitch (fatia B, com a fatia D).

    python -m scripts.metricas_pitch docs/arquivos-teste/03-cozinha-gracas/orcamento_cozinha-gracas.json
    python -m scripts.metricas_pitch <arquivo> --sem-cache        # pesquisa tudo de novo (mais lento, custo real)
    python -m scripts.metricas_pitch --orcamento <uuid>           # lê um orçamento já pesquisado no Supabase

Mede o que o pitch precisa dizer com número de verdade:
- quantos itens a IA resolveu sozinha (preço com fonte), quantos o agente refez, quantos pedem o arquiteto;
- tempo até o 1º item na tela e até o fim;
- custo de IA (Featherless, `usage.cost`) por orçamento e por item.
Imprime uma tabela em Markdown para colar no roteiro. Só dados sintéticos.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.modelos import ResultadoItem

DOLAR_EM_REAIS = 5.4   # aproximação para o pitch; o custo medido é em US$


@dataclass
class Metricas:
    itens: int
    com_preco: int          # definido ou estimativa, sempre com fonte
    definidos: int
    pendentes: int          # pedem a especificação do arquiteto
    nao_encontrados: int    # inclui erro
    agente_refez: int       # itens em que o agente reformulou a busca
    lojas_media: float
    primeiro_s: float | None
    total_s: float | None
    custo_usd: float | None

    def pct(self, n: int) -> str:
        return f"{(100 * n / self.itens):.0f}%" if self.itens else "—"


def resumir(resultados: list[ResultadoItem], primeiro_s: float | None, total_s: float | None,
            custo_usd: float | None) -> Metricas:
    com_preco = [r for r in resultados if r.preco_emb_med is not None]
    return Metricas(
        itens=len(resultados), com_preco=len(com_preco),
        definidos=sum(r.status == "definido" for r in resultados),
        pendentes=sum(r.status == "pendente_especificacao" for r in resultados),
        nao_encontrados=sum(r.status in ("nao_encontrado", "erro") for r in resultados),
        agente_refez=sum(r.iteracoes > 0 for r in resultados),
        lojas_media=round(sum(len(r.fontes) for r in com_preco) / len(com_preco), 1) if com_preco else 0.0,
        primeiro_s=primeiro_s, total_s=total_s, custo_usd=custo_usd)


def tabela(m: Metricas, titulo: str) -> str:
    def s(v): return "—" if v is None else f"{v:.1f} s"
    custo = "—" if m.custo_usd is None else (f"US$ {m.custo_usd:.4f} (≈ R$ {m.custo_usd * DOLAR_EM_REAIS:.2f}); "
                                             f"US$ {m.custo_usd / max(m.itens, 1):.5f} por item")
    linhas = [
        f"### {titulo}", "", "| Métrica | Valor |", "|---|---|",
        f"| Itens pesquisados | {m.itens} |",
        f"| Com preço e fonte (resolvidos sozinhos) | {m.com_preco} ({m.pct(m.com_preco)}) |",
        f"| Definidos | {m.definidos} ({m.pct(m.definidos)}) |",
        f"| Pedem a especificação do arquiteto | {m.pendentes} ({m.pct(m.pendentes)}) |",
        f"| Não encontrados | {m.nao_encontrados} ({m.pct(m.nao_encontrados)}) |",
        f"| A IA refez a busca sozinha | {m.agente_refez} ({m.pct(m.agente_refez)}) |",
        f"| Lojas por item com preço (média) | {m.lojas_media} |",
        f"| 1º item na tela | {s(m.primeiro_s)} |",
        f"| Orçamento completo | {s(m.total_s)} |",
        f"| Custo de IA | {custo} |",
    ]
    return "\n".join(linhas)


# ------------------------------------------------------------------ fontes dos dados
async def medir_arquivo(caminho: Path, usar_cache: bool) -> Metricas:
    from scripts.aquecer_cache import cep_do_arquivo, ler_itens
    from src.regiao import na_obra, preparar_obra
    from src.custo import acumular
    from src.pesquisa import pesquisar_itens

    itens = ler_itens(caminho)
    local, lojas = await preparar_obra(cep_do_arquivo(caminho))   # mesma região que o orçamento real usaria
    t0 = time.perf_counter()
    primeiro: list[float] = []

    async def ao_terminar(_r):
        if not primeiro:
            primeiro.append(time.perf_counter() - t0)

    with acumular() as custo, na_obra(local, lojas):
        resultados = await pesquisar_itens(itens, ao_terminar=ao_terminar, usar_cache=usar_cache)
    return resumir(resultados, primeiro[0] if primeiro else None, time.perf_counter() - t0, custo.usd)


def _data(v) -> datetime | None:
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None


def ler_orcamento(orcamento_id: str) -> Metricas:
    from src.database import get_supabase
    from src.orcamento import COLUNAS_GRAVADAS

    sb = get_supabase()
    cab = sb.table("orcamentos").select("*").eq("id", orcamento_id).limit(1).execute().data
    if not cab:
        raise SystemExit(f"Orçamento {orcamento_id} não encontrado no Supabase.")
    linhas = sb.table("orcamento_itens").select("*").eq("orcamento_id", orcamento_id).execute().data
    campos = set(COLUNAS_GRAVADAS) - {"atualizado_em"}
    resultados = [ResultadoItem(item_id=str(x["id"]), **{k: v for k, v in x.items() if k in campos and v is not None})
                  for x in linhas if x.get("status") != "buscando"]
    ini, fim = _data(cab[0].get("pesquisa_iniciada_em")), _data(cab[0].get("pesquisa_concluida_em"))
    total = (fim - ini).total_seconds() if ini and fim else None
    custo = cab[0].get("custo_usd")
    return resumir(resultados, None, total, float(custo) if custo is not None else None)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo", type=Path, nargs="?")
    ap.add_argument("--orcamento", help="UUID de um orçamento já pesquisado")
    ap.add_argument("--sem-cache", action="store_true", help="pesquisa tudo de novo (custo e tempo sem cache)")
    a = ap.parse_args()
    if a.orcamento:
        print(tabela(ler_orcamento(a.orcamento), f"Orçamento {a.orcamento}"))
    elif a.arquivo:
        m = asyncio.run(medir_arquivo(a.arquivo, usar_cache=not a.sem_cache))
        print(tabela(m, f"{a.arquivo.stem} ({'sem cache' if a.sem_cache else 'com o cache da demo'})"))
    else:
        ap.error("informe um arquivo ou --orcamento")
    return 0


if __name__ == "__main__":
    sys.exit(main())
