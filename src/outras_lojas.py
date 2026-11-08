"""Busca extra quando sobram poucas lojas com link CONFIRMADO (pedido de 08/11).

Uma busca no Google (Serper, que tem crédito próprio) com o nome do item e `-site:` para cada site que já foi tentado.
Cada resultado é ABERTO: entra só a página que declara o produto (JSON-LD), com nome que casa com o pedido, sem
conflito de tipo/linha/acabamento/cor/kit e com preço legível. O preço é o da própria página, então o link já sai
confirmado. Nunca levanta exceção: falha = nenhuma oferta nova.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from langfuse import observe

from . import serper
from .config import get_settings
from .precos import Oferta

logger = logging.getLogger(__name__)

MIN_LOJAS_CONFIRMADAS = 2
# Medido em 08/11: para "Spot Stella 7W 3000K" (R$ 55 o de embutir) a busca extra achou o "Spot para Trilho Trace"
# da mesma marca e potência a R$ 239, confirmado na página, e ele substituiu os certos. A página nova só entra se o
# preço por unidade cair perto do que a busca já tinha visto (confirmado ou não).
FAIXA_DA_REFERENCIA = (0.5, 2.0)
MAX_EXCLUSOES = 8          # "-site:" demais e o Google ignora a consulta
MAX_PAGINAS = 8
URL_BUSCA = "https://google.serper.dev/search"


def lojas_confirmadas(ofertas: list[Oferta]) -> int:
    return len({o.loja.lower() for o in ofertas if o.link_verificado and o.preco and o.mesmo_produto == "sim"})


def consulta_sem(descricao: str, excluir: set[str]) -> str:
    sites = sorted(d for d in excluir if d and "google." not in d)[:MAX_EXCLUSOES]
    return " ".join([descricao, "preço", *(f"-site:{d}" for d in sites)])


def oferta_da_pagina(descricao: str, unidade: str | None, url: str, dominio: str, loja: str, pagina) -> Oferta | None:
    """Núcleo puro: a página aberta vira oferta confirmada, ou None."""
    from .conferir_links import conflito, e_listagem
    from .google_shopping import MIN_MESMO, _embalagem, semelhanca
    if not pagina or pagina.http != 200 or not pagina.produto or not pagina.precos or pagina.esgotado:
        return None
    if e_listagem(url, pagina) or semelhanca(descricao, pagina.nome) < MIN_MESMO:
        return None
    emb = _embalagem(pagina.nome, unidade, descricao)
    if emb is None:
        return None
    preco = min(pagina.precos)   # JSON-LD pode trazer price e highPrice: o de venda é o menor
    o = Oferta(loja=loja, dominio=dominio, url=url, titulo=pagina.nome, preco=preco, embalagem=emb,
               mesmo_produto="sim", link_verificado=True)
    return None if conflito(descricao, pagina.nome, o) else o


@observe(name="busca.outras_lojas", capture_input=False, capture_output=False)
def na_faixa(oferta: Oferta, referencia: float | None) -> bool:
    """Preço por unidade base (R$/L, R$/un...) dentro da faixa da referência; sem referência, aceita."""
    from .compra import conteudo_embalagem
    c = conteudo_embalagem(oferta.embalagem)
    if referencia is None or not c or not c.quantidade or not oferta.preco:
        return True
    lo, hi = FAIXA_DA_REFERENCIA
    return lo <= (oferta.preco / c.quantidade) / referencia <= hi


def referencia_de(ofertas: list[Oferta]) -> float | None:
    """Mediana do preço por unidade base das ofertas do MESMO produto já vistas (confirmadas ou não)."""
    import statistics

    from .compra import conteudo_embalagem
    vals = []
    for o in ofertas:
        c = conteudo_embalagem(o.embalagem)
        if o.preco and o.mesmo_produto == "sim" and c and c.quantidade:
            vals.append(o.preco / c.quantidade)
    return statistics.median(vals) if vals else None


async def ofertas_em_outras_lojas(descricao: str, unidade: str | None, excluir: set[str],
                                  referencia: float | None = None) -> list[Oferta]:
    from .busca import dominio_de, eh_pagina_de_busca, fonte_nao_e_loja
    from .conferir_links import ATIVO, SIMULTANEAS, _abrir
    from .regiao import regional_por_dominio
    chaves = get_settings().serper_keys
    if not chaves or not ATIVO:
        return []
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            j = await serper.post(cli, URL_BUSCA, {"q": consulta_sem(descricao, excluir), "gl": "br", "hl": "pt-br",
                                                   "num": 10}, chaves)
            candidatos, vistos = [], set(excluir)
            for r in ((j or {}).get("organic") or []):
                link = str(r.get("link") or "") if isinstance(r, dict) else ""
                dom = dominio_de(link) or ""
                if (not dom or dom in vistos or "google." in dom or eh_pagina_de_busca(link)
                        or fonte_nao_e_loja(dom, link)):
                    continue
                vistos.add(dom)
                regional = regional_por_dominio(dom)
                candidatos.append((link, dom, regional.nome if regional else dom))
                if len(candidatos) >= MAX_PAGINAS:
                    break
            porteiro = asyncio.Semaphore(SIMULTANEAS)
            paginas = await asyncio.gather(*(_abrir(cli, link, porteiro) for link, _, _ in candidatos))
        saida = [o for (link, dom, loja), pg in zip(candidatos, paginas)
                 if (o := oferta_da_pagina(descricao, unidade, link, dom, loja, pg)) and na_faixa(o, referencia)]
        logger.info("Outras lojas para '%s': %d páginas abertas, %d confirmadas", descricao, len(candidatos), len(saida))
        return saida
    except Exception as exc:  # noqa: BLE001 — a busca extra nunca derruba a pesquisa
        logger.warning("Busca em outras lojas falhou para '%s' (%s)", descricao, type(exc).__name__)
        return []
