"""Pré-aquece o cache de preços para a demo (fatia B, etapa 9).

    python -m scripts.aquecer_cache docs/arquivos-teste/03-cozinha-gracas/orcamento_cozinha-gracas.json
    python -m scripts.aquecer_cache <arquivo> --manter 0.5      # padrão: metade fica no cache
    python -m scripts.aquecer_cache <arquivo> --manter 1        # tudo no cache (demo à prova de rede ruim)

1. pesquisa TODOS os itens do arquivo (com o agente), o que grava cada um no cache;
2. tira do cache os itens MAIS RÁPIDOS até sobrar a fração --manter. Os lentos (os que precisaram do agente)
   ficam no cache: na demo, metade aparece na hora e a outra metade chega ao vivo em poucos segundos,
   sem ninguém esperar 50 s por um item difícil.

Lê o JSON de orçamento (chave "itens") e o CSV de lista de materiais (; ou ,, UTF-8 ou Windows-1252).
Não substitui o importador da fatia A: é só para a demo.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from src import cache
from src.busca import local_do_cep, na_regiao
from src.modelos import ItemEntrada, ResultadoItem
from src.pesquisa import pesquisar_itens

COLUNAS_DESCRICAO = ("descricao", "produto", "material", "item", "nome")


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().strip().lower()


def _numero(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) and "," in v else float(v)
    except ValueError:
        return None


def ler_itens(caminho: Path) -> list[ItemEntrada]:
    if caminho.suffix.lower() == ".json":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        brutos = dados["itens"] if isinstance(dados, dict) else dados
    elif caminho.suffix.lower() in (".csv", ".txt"):
        cru = caminho.read_bytes()
        try:
            texto = cru.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = cru.decode("cp1252")
        dialeto = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=";,\t")
        linhas = list(csv.DictReader(io.StringIO(texto), dialect=dialeto))
        brutos = [{_sem_acento(k): v for k, v in linha.items() if k} for linha in linhas]
    else:
        raise SystemExit(f"Formato não suportado no pré-aquecimento: {caminho.suffix} (use .json ou .csv)")

    itens = []
    for n, b in enumerate(brutos, start=1):
        desc = next((b[c] for c in COLUNAS_DESCRICAO if b.get(c)), None)
        if not desc or not str(desc).strip():
            continue
        itens.append(ItemEntrada(id=str(n), descricao=str(desc).strip(), quantidade=_numero(b.get("quantidade")),
                                 unidade=(b.get("unidade") or None), categoria=b.get("categoria") or None))
    return itens


@dataclass
class Medida:
    item: ItemEntrada
    resultado: ResultadoItem
    segundos: float                 # resultado final (depois do agente, se houve)
    na_tela: float | None = None    # 1º aviso: quando o item apareceu na tela (provisório da fase 1)


def escolher_para_apagar(medidas: list[Medida], manter: float) -> list[Medida]:
    """Só itens que ficaram no cache (com preço) contam. Apaga os mais rápidos; os lentos ficam aquecidos."""
    em_cache = [m for m in medidas if m.resultado.preco_emb_med is not None]
    n_manter = round(len(em_cache) * manter)
    return sorted(em_cache, key=lambda m: m.segundos)[: len(em_cache) - n_manter]


def cep_do_arquivo(caminho: Path) -> str | None:
    """O JSON de orçamento traz a obra (`obra.cep`); CSV não traz: use --cep."""
    if caminho.suffix.lower() != ".json":
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return (dados.get("obra") or {}).get("cep") if isinstance(dados, dict) else None
    except (ValueError, OSError):
        return None


async def aquecer(itens: list[ItemEntrada], manter: float, usar_agente: bool = True,
                  cep: str | None = None) -> tuple[list[Medida], list[Medida], float]:
    # mesma região que a pesquisa do orçamento usará na demo (busca aberta com cidade/UF da obra)
    local = await local_do_cep(cep)
    print(f"Região da busca aberta: {f'{local.cidade}/{local.uf}' if local else 'sem cidade (passe --cep)'}")
    with na_regiao(local):
        return await _aquecer(itens, manter, usar_agente)


async def _aquecer(itens: list[ItemEntrada], manter: float, usar_agente: bool) -> tuple[list[Medida], list[Medida], float]:
    t0 = time.perf_counter()
    prontos: dict[str, float] = {}
    na_tela: dict[str, float] = {}

    async def ao_terminar(r: ResultadoItem):
        prontos[r.item_id] = time.perf_counter() - t0
        na_tela.setdefault(r.item_id, prontos[r.item_id])
        print(f"  [{prontos[r.item_id]:5.1f}s] item {r.item_id:>3}: {r.status}", flush=True)

    # usar_cache=False: pesquisa de verdade e regrava (preço e imagem do dia)
    resultados = await pesquisar_itens(itens, ao_terminar=ao_terminar, usar_agente=usar_agente, usar_cache=False)
    total = time.perf_counter() - t0
    medidas = [Medida(i, r, prontos.get(i.id, total), na_tela.get(i.id)) for i, r in zip(itens, resultados)]
    apagar = escolher_para_apagar(medidas, manter)
    for m in apagar:
        await cache.apagar(m.item.descricao)
    return medidas, apagar, total


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo", type=Path)
    ap.add_argument("--manter", type=float, default=0.5, help="fração dos itens que fica no cache (0 a 1)")
    ap.add_argument("--sem-agente", action="store_true", help="não deixa o agente refazer buscas (mais rápido)")
    ap.add_argument("--cep", help="CEP da obra (o JSON de orçamento já traz em obra.cep)")
    a = ap.parse_args()

    itens = ler_itens(a.arquivo)
    print(f"{len(itens)} itens em {a.arquivo.name}. Pesquisando todos...")
    medidas, apagados, total = asyncio.run(aquecer(itens, a.manter, usar_agente=not a.sem_agente,
                                                   cep=a.cep or cep_do_arquivo(a.arquivo)))
    fora = {m.item.id for m in apagados}

    tela = sorted(m.na_tela for m in medidas if m.na_tela is not None)
    print(f"\nPronto em {total:.1f} s.")
    if tela:
        print(f"Na tela: 1º item em {tela[0]:.1f} s · metade em {tela[len(tela) // 2]:.1f} s · "
              f"{len(tela)} de {len(medidas)} antes do agente terminar\n")
    print(f"{'item':>4}  {'tela':>6}  {'final':>6}  {'status':22} {'agente':>6}  {'na demo':10} descrição")
    for m in sorted(medidas, key=lambda m: (m.na_tela if m.na_tela is not None else m.segundos)):
        r = m.resultado
        demo = "ao vivo" if m.item.id in fora else ("cache" if r.preco_emb_med is not None else "ao vivo*")
        tela_s = f"{m.na_tela:5.1f}s" if m.na_tela is not None else "    — "
        print(f"{m.item.id:>4}  {tela_s}  {m.segundos:5.1f}s  {r.status:22} {r.iteracoes:>6}  {demo:10} {m.item.descricao[:60]}")
    por_status: dict[str, int] = {}
    for m in medidas:
        por_status[m.resultado.status] = por_status.get(m.resultado.status, 0) + 1
    print(f"\nPor status: {por_status}")
    print(f"No cache: {sum(1 for m in medidas if m.resultado.preco_emb_med is not None) - len(apagados)} · "
          f"ao vivo na demo: {len(medidas) - (sum(1 for m in medidas if m.resultado.preco_emb_med is not None) - len(apagados))}")
    print("* sem preço: será pesquisado de novo na demo (não fica no cache).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
