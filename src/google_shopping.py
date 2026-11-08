"""Google Shopping (serper.dev) como FONTE de preço, não só como conferência.

Medido em 07/11 nos 3 exemplos do site: comparado com a mediana do Google, só 38 de 113 itens batiam (≤ 25%) e 33
passavam de 50% de diferença; nos piores casos o nosso preço vinha de UMA loja só (Spot Stella 7W: R$ 367 contra R$ 66).
O Shopping devolve dezenas de anúncios estruturados (título, preço, loja, link) por produto, inclusive de lojas menores.
Entrar com eles no cálculo (mediana sem outliers, 1 oferta por loja) deixa o preço muito mais perto do mercado.

Regras para não comparar banana com laranja (anúncio só entra se):
- o título tem TODAS as medidas do item ("18L", "60x60", "3/4", "25 mm") e a marca/linha (palavras próprias);
- o título tem a maioria das palavras do item (≥ 75% = mesmo produto; ≥ 55% e o item é genérico = parecido);
- a embalagem sai do próprio título ("18L", "20kg", "kit 2 latas") ou é unidade, quando o item é contado em unidades.
O preço é o do anúncio (texto estruturado do Google, não lido por LLM): não há o que alucinar.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from langfuse import observe

from . import serper
from .cache import chave_cache
from .compra import conteudo_embalagem, normalizar_unidade
from .config import get_settings
from .precos import Oferta
from .regiao import regional_por_nome
from .validacao_serper import _buscar, converter_preco

logger = logging.getLogger(__name__)

MIN_MESMO = 0.66            # 2 de 3 palavras: a cor ("Cinza Urbano" x "Cinza Tecnológico") quase não muda o preço da linha
MIN_PARECIDO = 0.55
MAX_OFERTAS = 12
DOMINIO_SHOPPING = "google.com"   # o link do anúncio abre no Google Shopping
# palavras que não identificam o produto (a chave do cache já tira as vazias)
FRACAS = {"preco", "comprar", "branco", "branca", "cinza", "preto", "preta", "cor", "para", "com", "kit", "un",
          "unidade", "unidades", "cozinha", "banheiro", "parede", "piso"}


# Mesmo código escrito de jeitos diferentes nos anúncios (medido em 08/11: "ACIII", "AC-III", "Ac-3", "AC III")
_ROMANOS = {"1": "i", "2": "ii", "3": "iii"}


def _normalizar_codigos(texto: str) -> str:
    t = texto.lower()
    t = re.sub(r"\bac\s*-?\s*(iii|ii|i|[123])\b", lambda m: "ac" + _ROMANOS.get(m.group(1), m.group(1)), t)
    return re.sub(r"(?<=[a-z])-(?=[a-z])", "", t)   # "toque-de-seda" fica como está; "ac-iii" já virou "aciii"


def _tokens(texto: str) -> set[str]:
    return set(chave_cache(_normalizar_codigos(texto)).split())


def _medidas(tokens: set[str]) -> set[str]:
    """Palavras com número: medidas e códigos ('18l', '60x60', '3/4', '2.5', 'ac-iii' não tem número)."""
    return {t for t in tokens if re.search(r"\d", t)}


def _numeros(tokens: set[str]) -> set[float]:
    return {float(n) for t in tokens for n in re.findall(r"\d+(?:\.\d+)?", t)}


def semelhanca(descricao: str, titulo: str) -> float:
    """Fração das palavras do item que aparecem no título; 0 se faltar alguma medida do item.
    Medida compara pelo NÚMERO: "2,5" do item casa com "2,5mm" ou "2.50mm" do anúncio (medido em 08/11: o cabo SIL
    2,5 ficava sem preço porque "2.5" ≠ "2.5mm")."""
    item = _tokens(descricao) - FRACAS
    anuncio = _tokens(titulo)
    if len(item) < 2 or not _numeros(_medidas(item)) <= _numeros(anuncio):
        return 0.0
    palavras = item - _medidas(item)
    comuns = len(palavras & anuncio) + len(_medidas(item))
    return comuns / len(item) if len(palavras & anuncio) >= min(2, len(palavras)) else 0.0


def _embalagem(titulo: str, unidade_item: str | None) -> str | None:
    if conteudo_embalagem(titulo):
        return titulo
    if normalizar_unidade(unidade_item) in ("un", None):
        return "unidade"
    return None


def ler_anuncios(descricao: str, unidade_item: str | None, anuncios: list[dict], generico: bool) -> list[Oferta]:
    """Núcleo puro: anúncios do Shopping -> ofertas (1 por loja, as mais parecidas primeiro)."""
    candidatos = []
    for a in anuncios:
        titulo, loja = str(a.get("title") or ""), str(a.get("source") or "").strip()
        preco = converter_preco(a.get("price"))
        if not titulo or not loja or preco is None:
            continue
        s = semelhanca(descricao, titulo)
        igual = "sim" if s >= MIN_MESMO else "parecido" if (generico and s >= MIN_PARECIDO) else None
        emb = _embalagem(titulo, unidade_item)
        if igual is None or emb is None:
            continue
        link = str(a.get("link") or "") or f"https://www.google.com/search?tbm=shop&q={quote_plus(titulo)}"
        if not link.startswith("http"):
            continue
        regional = regional_por_nome(loja)
        candidatos.append((s, Oferta(loja=regional.nome if regional else loja,
                                     dominio=regional.dominio if regional and regional.dominio else DOMINIO_SHOPPING,
                                     url=link, titulo=titulo, preco=preco, embalagem=emb, mesmo_produto=igual)))
    candidatos.sort(key=lambda c: -c[0])
    saida, lojas = [], set()
    for _, o in candidatos:
        if o.loja.lower() in lojas:
            continue
        lojas.add(o.loja.lower())
        saida.append(o)
        if len(saida) >= MAX_OFERTAS:
            break
    return saida


# ------------------------------------------------------------------ lojas da região: busca do Google nos sites delas
URL_BUSCA = "https://google.serper.dev/search"
SITES_POR_CONSULTA = 4          # medido em 08/11: com 12 "site:" o Serper responde 400
MAX_LOJAS_REGIONAIS = 8         # as mais perto da obra (2 consultas)
_PRECO_NO_TRECHO = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")


def ler_resultados_regionais(descricao: str, unidade_item: str | None, organicos: list[dict]) -> list[Oferta]:
    """Núcleo puro: resultados da busca do Google nos sites das lojas da região -> ofertas.
    O preço é o 1º "R$ 00,00" escrito no trecho (sem LLM); o produto precisa casar com o item como no Shopping."""
    from .busca import dominio_de, eh_pagina_de_busca
    from .regiao import regional_por_dominio
    saida, lojas = [], set()
    for o in organicos:
        titulo, trecho, link = str(o.get("title") or ""), str(o.get("snippet") or ""), str(o.get("link") or "")
        loja = regional_por_dominio(dominio_de(link))
        achou = _PRECO_NO_TRECHO.search(trecho)
        if loja is None or loja.nome in lojas or not achou or eh_pagina_de_busca(link):
            continue
        texto = f"{titulo} {trecho[:achou.start()]}"   # o nome do produto vem antes do preço no trecho
        if semelhanca(descricao, texto) < MIN_MESMO:
            continue
        emb = _embalagem(texto, unidade_item)
        preco = converter_preco(achou.group(1))
        if emb is None or preco is None:
            continue
        lojas.add(loja.nome)
        saida.append(Oferta(loja=loja.nome, dominio=loja.dominio, url=link, titulo=texto[:200], preco=preco,
                            embalagem=emb, mesmo_produto="sim"))
    return saida


@observe(name="busca.lojas_da_regiao")
async def ofertas_regionais(descricao: str, unidade_item: str | None) -> list[Oferta]:
    """Preço nas lojas PERTO DA OBRA (Google Maps pelo CEP -> busca do Google dentro dos sites delas).
    Sem região, sem chave ou com falha: lista vazia."""
    import asyncio

    import httpx

    from .regiao import LOJAS_DA_REGIAO
    chaves = get_settings().serper_keys
    dominios = [l.dominio for l in LOJAS_DA_REGIAO.get() if l.dominio][:MAX_LOJAS_REGIONAIS]
    if not chaves or not dominios:
        return []
    grupos = [dominios[i:i + SITES_POR_CONSULTA] for i in range(0, len(dominios), SITES_POR_CONSULTA)]

    async def uma(cli: httpx.AsyncClient, grupo: list[str]) -> list[dict]:
        q = f"{descricao} " + " OR ".join(f"site:{d}" for d in grupo)
        j = await serper.post(cli, URL_BUSCA, {"q": q, "gl": "br", "hl": "pt-br", "num": 10}, chaves)
        return [o for o in ((j or {}).get("organic") or []) if isinstance(o, dict)]

    try:
        async with httpx.AsyncClient(timeout=6.0) as cli:
            respostas = await asyncio.gather(*(uma(cli, g) for g in grupos))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Busca nas lojas da região falhou para '%s' (%s)", descricao, type(exc).__name__)
        return []
    return ler_resultados_regionais(descricao, unidade_item, [o for r in respostas for o in r])


@observe(name="busca.google_shopping")
async def ofertas_google(descricao: str, unidade_item: str | None, generico: bool = False) -> list[Oferta]:
    """Ofertas do Google Shopping para o item. Sem chave ou com falha: lista vazia (a pesquisa segue sem elas)."""
    if not get_settings().serper_keys:
        return []
    try:
        anuncios = await _buscar(descricao)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Shopping falhou para '%s' (%s)", descricao, type(exc).__name__)
        return []
    return ler_anuncios(descricao, unidade_item, anuncios, generico)
