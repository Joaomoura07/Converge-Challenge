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


def lojas_confirmadas(ofertas: list[Oferta], generico: bool = False) -> int:
    """Lojas com preço confirmado na página. No item genérico, o "parecido" confirmado também conta (é a estimativa)."""
    aceitas = ("sim", "parecido") if generico else ("sim",)
    return len({o.loja.lower() for o in ofertas if o.link_verificado and o.preco and o.mesmo_produto in aceitas})


def sem_medidas(descricao: str) -> str:
    """'Azulejo português azul 60x60' -> 'Azulejo português azul' (palavras com número saem)."""
    import re
    return " ".join(w for w in descricao.split() if not re.search(r"\d", w))


def consulta_sem(descricao: str, excluir: set[str]) -> str:
    sites = sorted(d for d in excluir if d and "google." not in d)[:MAX_EXCLUSOES]
    return " ".join([descricao, "preço", *(f"-site:{d}" for d in sites)])


def oferta_da_pagina(descricao: str, unidade: str | None, url: str, dominio: str, loja: str, pagina,
                     generico: bool = False) -> Oferta | None:
    """Núcleo puro: a página aberta vira oferta confirmada, ou None.
    Item genérico: a página que casa com o pedido TIRANDO a medida vira "parecido" (estimativa com preço real).
    Medido em 08/11: "Azulejo português azul 60x60" não achava nada porque azulejo português é vendido em 15x15 e
    20x20; as lojas de azulejo (R$ 245, R$ 280, R$ 420) ficavam de fora pela medida."""
    from .conferir_links import conflito, e_listagem
    from .google_shopping import MIN_MESMO, MIN_PARECIDO, _embalagem, semelhanca
    if not pagina or pagina.http != 200 or not pagina.produto or not pagina.precos or pagina.esgotado:
        return None
    if e_listagem(url, pagina):
        return None
    igual = "sim"
    if semelhanca(descricao, pagina.nome) < MIN_MESMO:
        base = sem_medidas(descricao)
        if not (generico and base != descricao and len(base.split()) >= 2
                and semelhanca(base, pagina.nome) >= max(MIN_PARECIDO, 0.66)):
            return None
        igual = "parecido"
    emb = _embalagem(pagina.nome, unidade, descricao)
    if emb is None:
        return None
    preco = min(pagina.precos)   # JSON-LD pode trazer price e highPrice: o de venda é o menor
    o = Oferta(loja=loja, dominio=dominio, url=url, titulo=pagina.nome, preco=preco, embalagem=emb,
               mesmo_produto=igual, link_verificado=True)
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
                                  referencia: float | None = None, generico: bool = False) -> list[Oferta]:
    from .busca import dominio_de, eh_pagina_de_busca, fonte_nao_e_loja
    from .conferir_links import ATIVO, SIMULTANEAS, _abrir
    from .regiao import regional_por_dominio
    chaves = get_settings().serper_keys
    if not chaves or not ATIVO:
        return []
    consultas = [consulta_sem(descricao, excluir)]
    if sem_medidas(descricao) != descricao and len(sem_medidas(descricao).split()) >= 2:
        consultas.append(f"{sem_medidas(descricao)} preço comprar")   # 2ª rodada, só se a 1ª não confirmar nada
    saida: list[Oferta] = []
    vistos = set(excluir)
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            for consulta in consultas:
                if saida:
                    break
                saida = await _rodada(cli, consulta, descricao, unidade, vistos, referencia, generico, chaves)
        logger.info("Outras lojas para '%s': %d confirmadas", descricao, len(saida))
        return saida
    except Exception as exc:  # noqa: BLE001 — a busca extra nunca derruba a pesquisa
        logger.warning("Busca em outras lojas falhou para '%s' (%s)", descricao, type(exc).__name__)
        return []


async def _rodada(cli, consulta: str, descricao: str, unidade: str | None, vistos: set[str], referencia: float | None,
                  generico: bool, chaves: list[str]) -> list[Oferta]:
    """Uma consulta no Google: abre até MAX_PAGINAS resultados de sites ainda não vistos e devolve os confirmados."""
    from .busca import dominio_de, eh_pagina_de_busca, fonte_nao_e_loja
    from .conferir_links import SIMULTANEAS, _abrir
    from .regiao import regional_por_dominio
    j = await serper.post(cli, URL_BUSCA, {"q": consulta, "gl": "br", "hl": "pt-br", "num": 10}, chaves)
    candidatos = []
    for r in ((j or {}).get("organic") or []):
        link = str(r.get("link") or "") if isinstance(r, dict) else ""
        dom = dominio_de(link) or ""
        if not dom or dom in vistos or "google." in dom or eh_pagina_de_busca(link) or fonte_nao_e_loja(dom, link):
            continue
        vistos.add(dom)
        regional = regional_por_dominio(dom)
        candidatos.append((link, dom, regional.nome if regional else dom))
        if len(candidatos) >= MAX_PAGINAS:
            break
    porteiro = asyncio.Semaphore(SIMULTANEAS)
    paginas = await asyncio.gather(*(_abrir(cli, link, porteiro) for link, _, _ in candidatos))
    return [o for (link, dom, loja), pg in zip(candidatos, paginas)
            if (o := oferta_da_pagina(descricao, unidade, link, dom, loja, pg, generico)) and na_faixa(o, referencia)]
