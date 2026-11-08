"""Google Shopping (serper.dev) como FONTE de preço, não só como conferência.

Medido em 07/11 nos 3 exemplos do site: comparado com a mediana do Google, só 38 de 113 itens batiam (≤ 25%) e 33
passavam de 50% de diferença; nos piores casos o nosso preço vinha de UMA loja só (Spot Stella 7W: R$ 367 contra R$ 66).
O Shopping devolve dezenas de anúncios estruturados (título, preço, loja, link) por produto, inclusive de lojas menores.
Entrar com eles no cálculo (mediana sem outliers, 1 oferta por loja) deixa o preço muito mais perto do mercado.

Anúncios com título abreviado podem servir para estimar, inclusive para itens especificados.
A embalagem sai do título ("18L", "20kg", "kit 2 latas") ou é unidade para itens contados em unidades.
Preço e URL precisam vir da mesma oferta. Links do Shopping e de listagens não são fontes de compra.
"""

from __future__ import annotations

import logging
import re

from langfuse import observe

from . import serper
from .cache import chave_cache
from .compra import conteudo_embalagem, normalizar_unidade
from .config import get_settings
from .precos import Oferta
from .regiao import regional_por_nome
from .especificacao import conflitos_explicitos, nao_confirmados, texto_para_similaridade
from .busca import dominio_de, link_direto_produto, nome_da_loja
from .validacao_serper import _buscar, converter_preco

logger = logging.getLogger(__name__)

MIN_MESMO = 0.66            # aplicado somente após confirmar os atributos solicitados
MIN_PARECIDO = 0.55
MAX_OFERTAS = 12
DOMINIO_SHOPPING = "google.com"  # compatibilidade com ofertas antigas
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
    """Ordena por relevância; um título abreviado pode servir como estimativa."""
    if conflitos_explicitos(descricao, titulo):
        return 0.0
    item = _tokens(texto_para_similaridade(descricao)) - FRACAS
    anuncio = _tokens(texto_para_similaridade(titulo)) - FRACAS
    medidas = _medidas(item)
    palavras = item - medidas
    comuns = len(palavras & anuncio)
    if not comuns or comuns < min(2, len(palavras)):
        return 0.0
    numeros = _numeros(anuncio)
    medidas_comuns = sum(_numeros({v}) <= numeros for v in medidas)
    score = min(1.0, (comuns + medidas_comuns) / min(len(item), len(anuncio)))
    if len(item) == 1 or medidas_comuns < len(medidas) or nao_confirmados(descricao, titulo):
        return min(score, MIN_MESMO - 0.01)
    return score


_ROTULO_UNIDADE = {"l": "L", "kg": "kg", "m2": "m²", "m3": "m³", "m": "m"}

# Material vendido em CHAPA ou PEÇA de pedra, cujo anúncio traz as medidas ("275cmx183cm", "1850 x 2750 mm") e não a
# área. Medido em 08/11 (Cozinha Graças): "Mdf Branco 18mm 2l Tx 275cmx183cm" saiu como "2 L" (o "2l" é "2 lados") e
# "Granito Branco Itaúnas 0,50x0,15m" como "0,15 m" (a 2ª medida da peça lida como comprimento).
_CHAPA = re.compile(r"\b(mdf|mdp|compensado|osb|chapa|chapas|granito|marmore|quartzo|ardosia|tampo|bancada|pedra)\b")
_LADOS = re.compile(r"\b\d\s*(?:l|f|lados?|faces?)\b", re.I)    # "2l", "2f", "2 faces": lados da chapa, não litros
_NUM = r"(\d+(?:[.,]\d+)?)"
_DIMENSOES = re.compile(rf"{_NUM}\s*(mm|cm|m)?\s*[x×]\s*{_NUM}\s*(mm|cm|m)?(?:\s*[x×]\s*{_NUM}\s*(mm|cm|m)?)?", re.I)
AREA_MINIMA_M2 = 0.3        # peça menor que isso (pedrinha, batente) não é o material do quantitativo em m²
AREA_MAXIMA_M2 = 20.0


def _sem_acento(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def _unidade_comum(pares: list[tuple[str, str | None]]) -> str:
    """"185 x 275cm": a unidade escrita vale para todas as medidas; sem nenhuma escrita, pela maior ("90x90x2" = cm,
    "1850x2750" = mm, "1,2x0,6" = m). Decidir medida por medida lia a espessura "2" de "90x90x2" como 2 metros."""
    escrita = next((u.lower() for _, u in pares if u), "")
    if escrita:
        return escrita
    maior = max(float(v.replace(",", ".")) for v, _ in pares)
    return "mm" if maior >= 1000 else "cm" if maior >= 10 else "m"


def _em_metros(valor: str, unidade: str | None, comum: str) -> float:
    return float(valor.replace(",", ".")) / {"mm": 1000, "cm": 100, "m": 1}[(unidade or comum).lower()]


def area_pelas_dimensoes(titulo: str) -> float | None:
    """Área (m²) de uma chapa/peça pelas duas MAIORES medidas do título (a menor é a espessura): "18 x 1850 x 2750 mm"
    = 5,09 m²; "0,50x0,15m" = 0,075 m². Sem medidas, fora de 0,3 a 20 m² ou ambíguo: None."""
    achou = _DIMENSOES.search(titulo or "")
    if not achou:
        return None
    g = achou.groups()
    pares = [(g[0], g[1]), (g[2], g[3])] + ([(g[4], g[5])] if g[4] else [])
    comum = _unidade_comum(pares)
    medidas = sorted((_em_metros(v, u, comum) for v, u in pares), reverse=True)
    area = medidas[0] * medidas[1]
    return round(area, 2) if AREA_MINIMA_M2 <= area <= AREA_MAXIMA_M2 else None


def _embalagem(titulo: str, unidade_item: str | None, descricao: str = "") -> str | None:
    """Rótulo curto da embalagem lida no título ("20 kg", "18 L", "kit 5 unidades"), que a tela mostra e o cálculo
    relê. Antes ia o título inteiro e a tela mostrava "Compre Produtos QUARTZOLIT em Promoção..." como embalagem."""
    if normalizar_unidade(unidade_item) == "m2" and _CHAPA.search(_sem_acento(f"{descricao} {titulo}")):
        area = area_pelas_dimensoes(titulo)
        if area is None:
            return None             # peça pequena ou sem medidas: não dá para comparar em R$/m²
        return f"{area:g} m²".replace(".", ",")
    titulo = _DIMENSOES.sub(" ", _LADOS.sub(" ", titulo)) if _CHAPA.search(_sem_acento(titulo)) else titulo
    c = conteudo_embalagem(titulo)
    if c:
        q = f"{c.quantidade:g}".replace(".", ",")
        if c.unidade == "un":
            return "unidade" if c.quantidade == 1 else f"kit {q} unidades"
        return f"{q} {_ROTULO_UNIDADE.get(c.unidade, c.unidade)}"
    if normalizar_unidade(unidade_item) in ("un", None):
        return "unidade"
    return None


def _imagem(anuncio: dict) -> str | None:
    """`imageUrl` do anúncio do Shopping (miniatura do Google, abre em qualquer navegador). Só http(s)."""
    url = str(anuncio.get("imageUrl") or "").strip()
    return url if url.startswith("http") else None


def ler_anuncios(descricao: str, unidade_item: str | None, anuncios: list[dict], generico: bool) -> list[Oferta]:
    """Núcleo puro: anúncios do Shopping -> ofertas (1 por loja, as mais parecidas primeiro)."""
    candidatos = []
    for a in anuncios:
        titulo, loja = str(a.get("title") or ""), str(a.get("source") or "").strip()
        preco = converter_preco(a.get("price"))
        if not titulo or not loja or preco is None:
            continue
        s = semelhanca(descricao, titulo)
        igual = "sim" if s >= MIN_MESMO else "parecido" if s >= MIN_PARECIDO else None
        emb = _embalagem(titulo, unidade_item, descricao)
        if igual is None or emb is None:
            continue
        link = str(a.get("link") or "")
        if not link_direto_produto(link):
            continue
        regional = regional_por_nome(loja)
        candidatos.append((s, Oferta(loja=regional.nome if regional else loja,
                                     dominio=dominio_de(link),
                                     url=link, titulo=titulo, preco=preco, embalagem=emb, mesmo_produto=igual,
                                     imagem=_imagem(a))))
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
MAX_LOJAS_REGIONAIS = 12        # as mais perto da obra (3 consultas de 4 sites; medido em 08/11: com 8 só 4 de 24 itens tinham loja da região)
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
        score = semelhanca(descricao, texto)
        if score < MIN_PARECIDO:
            continue
        emb = _embalagem(texto, unidade_item, descricao)
        preco = converter_preco(achou.group(1))
        if emb is None or preco is None:
            continue
        lojas.add(loja.nome)
        saida.append(Oferta(loja=loja.nome, dominio=loja.dominio, url=link, titulo=texto[:200], preco=preco,
                            embalagem=emb, mesmo_produto="sim" if score >= MIN_MESMO else "parecido"))
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
    diretas = ler_anuncios(descricao, unidade_item, anuncios, generico)
    # Uma busca adicional em lote, sem LLM: preço e URL vêm da mesma evidência.
    # Não transplanta preço do Shopping para uma URL de outra variante/loja.
    if sum(generico or o.mesmo_produto == "sim" for o in diretas) >= get_settings().pesquisa_min_lojas:
        return diretas
    import httpx
    try:
        async with httpx.AsyncClient(timeout=6.0) as cli:
            j = await serper.post(cli, URL_BUSCA, {"q": f"{descricao} comprar preço", "gl": "br", "hl": "pt-br", "num": 8})
        organicos = []
        for o in (j or {}).get("organic", []):
            url = str(o.get("link") or "")
            titulo = str(o.get("title") or "")
            trecho = str(o.get("snippet") or "")
            preco = _PRECO_NO_TRECHO.search(trecho)
            if link_direto_produto(url) and preco:
                organicos.append({"title": titulo, "link": url, "price": preco.group(1),
                                  "source": nome_da_loja(dominio_de(url), titulo)})
        novas = ler_anuncios(descricao, unidade_item, organicos, generico)
        por_url = {o.url: o for o in diretas}
        for o in novas:
            if o.url not in por_url or (por_url[o.url].mesmo_produto == "parecido" and o.mesmo_produto == "sim"):
                por_url[o.url] = o
        return list(por_url.values())
    except Exception as exc:
        logger.info("Busca de links diretos falhou (%s)", type(exc).__name__)
        return diretas


# ------------------------------------------------------------------ link da LOJA no lugar do link do Google
# Medido em 08/11: 76 de 120 anúncios do Shopping traziam `google.com/search?ibp=oshop...` (a página do produto no Google,
# com várias lojas), que o usuário abria achando que era a loja. Aqui cada loja de domínio conhecido é procurada pelo
# Google (busca com site:) e, achando a página do produto nela, o link passa a ser o da loja. Sem achar, continua o
# link do Google e a tela avisa que é do Google.
LOJAS_CONHECIDAS = {   # nome como o Shopping escreve (sem acento, minúsculo) -> domínio da loja
    "mercado livre": "mercadolivre.com.br", "mercadolivre": "mercadolivre.com.br", "amazon": "amazon.com.br",
    "magazine luiza": "magazineluiza.com.br", "magalu": "magazineluiza.com.br", "casas bahia": "casasbahia.com.br",
    "americanas": "americanas.com.br", "madeiramadeira": "madeiramadeira.com.br", "madeira madeira": "madeiramadeira.com.br",
    "leroy merlin": "leroymerlin.com.br", "telhanorte": "telhanorte.com.br", "c&c": "cec.com.br", "obramax": "obramax.com.br",
    "sodimac": "sodimac.com.br", "ferreira costa": "ferreiracosta.com", "tumelero": "tumelero.com.br", "sertao": "sertao.com.br",
    "padovani": "padovani.com.br", "dicico": "dicico.com.br", "leo madeiras": "leomadeiras.com.br",
    "casa do construtor": "casadoconstrutor.com.br", "mmartan": "mmartan.com.br", "kabum": "kabum.com.br",
}
MAX_DOMINIOS_RESOLVER = 12


def dominio_da_loja(loja: str) -> str | None:
    """'Leroy Merlin' / 'Amazon.com.br - Retail' / 'mercadolivre.com.br' -> domínio da loja, ou None se não conhecida."""
    nome = _sem_acento(loja).strip()
    if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", nome):
        return nome[4:] if nome.startswith("www.") else nome
    for chave in sorted(LOJAS_CONHECIDAS, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(chave)}(?![a-z0-9])", nome):
            return LOJAS_CONHECIDAS[chave]
    regional = regional_por_nome(loja)
    return regional.dominio if regional and regional.dominio else None


MIN_TITULO_IGUAL = 0.75     # a página da loja precisa ter o título parecido com o do ANÚNCIO do Shopping, não só com o item


def _mesmo_titulo(a: str, b: str) -> float:
    ta, tb = _tokens(a) - FRACAS, _tokens(b) - FRACAS
    return len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0


def trocar_links_do_google(descricao: str, ofertas: list[Oferta], organicos: list[dict]) -> list[Oferta]:
    """Núcleo puro: para cada oferta com link do Google, usa o resultado orgânico da MESMA loja que seja a página do
    MESMO produto do anúncio. Medido em 08/11: só comparar com o nome do item ligava "Deca Vogue Plus" (bacia) à página
    do assento "Vogue Plus" e "Hydra Max" a uma máscara de cabelo. Por isso o título da página também precisa
    combinar com o título do anúncio do Shopping. Na dúvida, o link continua o do Google (a tela avisa)."""
    from .busca import dominio_de, eh_pagina_de_busca
    paginas: list[tuple[str, str, str]] = []   # (domínio, link, título+trecho)
    for o in organicos:
        link, titulo = str(o.get("link") or ""), str(o.get("title") or "")
        dom = dominio_de(link)
        if dom and not eh_pagina_de_busca(link) and semelhanca(descricao, f"{titulo} {o.get('snippet') or ''}"[:300]) >= MIN_MESMO:
            paginas.append((dom, link, f"{titulo} {o.get('snippet') or ''}"[:300]))
    saida = []
    for o in ofertas:
        dom = dominio_da_loja(o.loja) if o.dominio == DOMINIO_SHOPPING else None
        melhor, nota = None, 0.0
        for d, link, texto in paginas:
            if dom and (d == dom or d.endswith("." + dom) or dom.endswith("." + d)):
                n = _mesmo_titulo(o.titulo, texto)
                if n > nota:
                    melhor, nota = link, n
        saida.append(o.model_copy(update={"url": melhor, "dominio": dom}) if melhor and nota >= MIN_TITULO_IGUAL and dom else o)
    return saida


@observe(name="busca.links_das_lojas")
async def resolver_links_das_lojas(descricao: str, ofertas: list[Oferta]) -> list[Oferta]:
    """Troca o link do Google pelo da loja nas ofertas do Shopping. Falha, sem chave ou sem achar: devolve como veio."""
    import asyncio

    import httpx
    chaves = get_settings().serper_keys
    pendentes = [o for o in ofertas if o.dominio == DOMINIO_SHOPPING]
    dominios = list(dict.fromkeys(d for d in (dominio_da_loja(o.loja) for o in pendentes) if d))[:MAX_DOMINIOS_RESOLVER]
    if not chaves or not dominios:
        return ofertas
    grupos = [dominios[i:i + SITES_POR_CONSULTA] for i in range(0, len(dominios), SITES_POR_CONSULTA)]

    async def uma(cli: httpx.AsyncClient, grupo: list[str]) -> list[dict]:
        q = f"{descricao} " + " OR ".join(f"site:{d}" for d in grupo)
        j = await serper.post(cli, URL_BUSCA, {"q": q, "gl": "br", "hl": "pt-br", "num": 10}, chaves)
        return [o for o in ((j or {}).get("organic") or []) if isinstance(o, dict)]

    try:
        async with httpx.AsyncClient(timeout=6.0) as cli:
            respostas = await asyncio.gather(*(uma(cli, g) for g in grupos))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Não deu para achar o link das lojas de '%s' (%s)", descricao, type(exc).__name__)
        return ofertas
    return trocar_links_do_google(descricao, ofertas, [o for r in respostas for o in r])
