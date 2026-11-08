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

from .cache import chave_cache
from .compra import conteudo_embalagem, normalizar_unidade
from .config import get_settings
from .precos import Oferta
from .regiao import regional_por_nome
from .validacao_serper import _buscar, converter_preco

logger = logging.getLogger(__name__)

MIN_MESMO = 0.75
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


def semelhanca(descricao: str, titulo: str) -> float:
    """Fração das palavras do item que aparecem no título; 0 se faltar alguma medida do item."""
    item = _tokens(descricao) - FRACAS
    anuncio = _tokens(titulo)
    if len(item) < 2 or not _medidas(item) <= anuncio:
        return 0.0
    return len(item & anuncio) / len(item)


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
