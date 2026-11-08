"""Abre a página de cada oferta e confere se o LINK é do produto pedido e se o PREÇO é o da loja.

Medido em 08/11 nos 4 casos da demo (95 links): página de categoria no lugar do produto ("/tinta-acrilica",
"/eletrica/tomadas-e-interruptores"), outro produto da mesma linha ("Toque Fosco" no lugar de "Toque de Seda";
"Conjunto 1 Interruptor e 2 Tomadas" no lugar da tomada), outro acabamento ou cor (porcelanato "Natural" para
"polido"; argamassa "Branca" para "cinza"), kit de 10 com preço de 1 e preço diferente do da página.

Como confere (sem crédito de API: GET direto na loja):
1. lê os dados de produto que a própria loja publica para o Google (JSON-LD `Product`: nome, preço, estoque);
   sem eles, o título da página; se a loja bloqueia robô (403), o endereço do link (slug);
2. ERRADO (a oferta sai da conta e o link some): Google, página de busca/categoria, 404/410, esgotado, outro tipo,
   linha, acabamento, cor ou kit, ou preço da página a mais de 15% do anunciado;
3. CONFIRMADO (`link_verificado=True`): o nome da página bate e o preço da página é o anunciado (até 15%, que
   cobre o preço no Pix). Sem preço legível no HTML, a IA de extração lê o texto da página, com a mesma trava de
   sempre: o preço só vale se estiver escrito no texto;
4. sem como saber (bloqueio, tempo esgotado): a oferta fica, sem confirmar; a tela não mostra o link.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

import httpx
from langfuse import observe

from .precos import Oferta

logger = logging.getLogger(__name__)

TIMEOUT_S = 6.0
SIMULTANEAS = 12
TOLERANCIA_PRECO = 0.15
MAX_LEITURAS_IA = 4          # páginas sem preço no HTML lidas pela IA, por item
CACHE_S = 1800.0
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}

TIPOS = frozenset("tomada interruptor joelho luva curva tinta massa selador argamassa rejunte porcelanato spot "
                  "luminaria plafon fita cabo disjuntor registro torneira misturador cuba assento bacia chuveiro "
                  "ducha sifao lampada refletor".split())
ACABAMENTOS = {"polido": "polido", "polida": "polido", "acetinado": "acetinado", "acetinada": "acetinado",
               "natural": "natural", "fosco": "fosco", "fosca": "fosco", "brilhante": "brilhante",
               "semibrilho": "semibrilho", "lustroso": "lustroso", "lustrosa": "lustroso", "esmaltado": "esmaltado"}
CORES = {"branco": "branco", "branca": "branco", "cinza": "cinza", "preto": "preto", "preta": "preto",
         "bege": "bege", "marrom": "marrom", "azul": "azul", "verde": "verde", "vermelho": "vermelho",
         "vermelha": "vermelho", "amarelo": "amarelo", "amarela": "amarelo", "grafite": "grafite"}
VAZIAS = {"de", "da", "do", "das", "dos", "e", "com", "para", "a", "o"}
_KIT = re.compile(r"\b(?:kit|jogo|pack|pacote)\s*(?:com\s*|c\s*)?(\d{1,3})\b(?!\s*(?:mm|cm|m|l|kg|w|v|a|x)\b)"
                  r"|\b(\d{1,3})\s*(?:unidades|unids?|pecas|pcs)\b")
_LISTA = re.compile(r"/(?:categoria|category|c|k|busca|search|pesquisa|colecao|collections?|departamento)(?:/|$)", re.I)

_cache: dict[str, tuple[float, "Pagina"]] = {}
ATIVO = True   # os testes de unidade desligam (tests/conftest.py): eles usam links de mentira


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def _palavras(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _norm(s))


def _singular(p: str) -> str:
    return p[:-1] if p.endswith("s") and len(p) > 4 else p


@dataclass
class Pagina:
    http: int | None                     # None = não abriu (rede, tempo)
    final: str = ""
    nome: str = ""                       # nome do produto na página (JSON-LD, og:title ou <title>)
    produto: bool = False                # a página declara um Product
    precos: list[float] = field(default_factory=list)
    esgotado: bool = False
    texto: str = ""                      # texto visível (para a IA ler o preço quando o HTML não traz)


# ------------------------------------------------------------------ leitura da página (puro)
def ler_html(http: int, final: str, corpo: str) -> Pagina:
    p = Pagina(http=http, final=final)
    for bloco in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", corpo, re.S | re.I):
        try:
            j = json.loads(bloco.strip())
        except Exception:  # noqa: BLE001 — JSON-LD quebrado é comum; segue com o resto
            continue
        pilha = j if isinstance(j, list) else [j]
        while pilha:
            x = pilha.pop()
            if not isinstance(x, dict):
                continue
            if isinstance(x.get("@graph"), list):
                pilha.extend(x["@graph"])
            tipos = x.get("@type") if isinstance(x.get("@type"), list) else [x.get("@type")]
            if "Product" not in tipos:
                continue
            p.produto = True
            p.nome = p.nome or html.unescape(str(x.get("name") or "")).strip()
            ofertas = x.get("offers") if isinstance(x.get("offers"), list) else [x.get("offers")]
            for o in ofertas:
                if not isinstance(o, dict):
                    continue
                for k in ("price", "lowPrice", "highPrice"):
                    try:
                        v = float(str(o.get(k)).replace(",", "."))
                        if v > 0:
                            p.precos.append(v)
                    except (TypeError, ValueError):
                        pass
                if re.search(r"OutOfStock|SoldOut|Discontinued", str(o.get("availability") or ""), re.I):
                    p.esgotado = True
    if not p.nome:
        og = re.search(r"<meta[^>]+property=[\"']og:title[\"'][^>]*content=[\"']([^\"']+)", corpo, re.I)
        ti = re.search(r"<title[^>]*>(.*?)</title>", corpo, re.S | re.I)
        p.nome = html.unescape((og.group(1) if og else (ti.group(1) if ti else "")).strip())
    texto = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", corpo, flags=re.S | re.I)
    p.texto = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", texto)).split())[:200000]
    return p


def slug(url: str) -> str:
    """Palavras do endereço: 'kit-c--10-tomada-dupla-20a' -> 'kit c 10 tomada dupla 20a'."""
    caminho = unquote(urlparse(url or "").path)
    return " ".join(re.findall(r"[A-Za-z0-9]+", caminho.replace("-", " ").replace("_", " ")))


def _palavras_do_caminho(url: str) -> list[str]:
    """Palavras do caminho inteiro, sem códigos ('/Conj-4X2-interruptor/dp/B0F2X' -> conj, interruptor, dp)."""
    return [w for w in re.findall(r"[a-z]+", _norm(unquote(urlparse(url or "").path))) if len(w) > 1]


def e_listagem(url: str, pagina: Pagina | None) -> bool:
    """Página de busca/categoria: caminho de lista, ou página sem produto declarado e endereço curto
    ('/tinta-acrilica', '/eletrica/tomadas-e-interruptores', '/liz-branco')."""
    from .busca import eh_pagina_de_busca, eh_pagina_de_listagem
    host = (urlparse(url or "").hostname or "").lower()
    if eh_pagina_de_busca(url) or eh_pagina_de_listagem(host, url) or _LISTA.search(urlparse(url or "").path):
        return True
    if "%20" in (url or "") or re.search(r"[?&](?:q|query|busca|ft|termo)=", url or ""):
        return True
    n = len([w for w in _palavras_do_caminho(url) if w not in VAZIAS])
    if pagina and pagina.http == 200:
        return not pagina.produto and n <= 3
    # loja bloqueou robô (401/403/429): endereço de 2 palavras ('/liz-branco') é vitrine, não produto
    return bool(pagina and pagina.http in (401, 403, 429) and n <= 2)


def pecas(texto: str) -> int | None:
    for a, b in _KIT.findall(_norm(texto)):
        n = int(a or b)
        if 2 <= n <= 500:
            return n
    return None


def conflito(pedido: str, nome: str, oferta: Oferta) -> str | None:
    """Por que o produto da página NÃO é o pedido (ou None). `nome` = nome da página ou, sem ela, o slug."""
    from .revisao import marcas_encontradas
    ped = [_singular(w) for w in _palavras(pedido)]
    pag = {_singular(w) for w in _palavras(nome)}
    if not pag:
        return None
    tipo = next((w for w in ped if w in TIPOS), None)
    # o produto da página é o PRIMEIRO tipo do nome: "Conjunto 1 Interruptor e 2 Tomadas" é interruptor;
    # "Argamassa ACIII Porcelanato" é argamassa (para porcelanato)
    primeiro = next((w for w in (_singular(x) for x in _palavras(nome)) if w in TIPOS), None)
    if tipo and primeiro and primeiro != tipo:
        return f"outro produto ({primeiro})"
    for marca in marcas_encontradas(pedido):              # linha de várias palavras: "toque de seda", "rende muito"
        partes = {_singular(w) for w in _palavras(marca)} - VAZIAS
        if len(partes) >= 2 and len(partes & pag) >= 1 and not partes <= pag:
            return f"outra linha (não é {marca})"
    pa = {ACABAMENTOS[w] for w in ped if w in ACABAMENTOS}
    na = {ACABAMENTOS[w] for w in pag if w in ACABAMENTOS}
    if pa and na and not pa & na:
        return f"outro acabamento ({', '.join(sorted(na))})"
    pc = {CORES[w] for w in ped if w in CORES}
    nc = {CORES[w] for w in pag if w in CORES}
    if pc and nc and not pc & nc:
        return f"outra cor ({', '.join(sorted(nc))})"
    n = pecas(nome)
    do_anuncio = pecas(oferta.titulo) or pecas(oferta.embalagem or "")
    if n and not do_anuncio and not pecas(pedido):
        return f"kit de {n} com preço de 1"
    if n and do_anuncio and n != do_anuncio:
        # medido em 08/11: anúncio "kit 2" (R$ 61,28 a peça) cujo link era um kit de 5 (R$ 24,51 a peça)
        return f"o link é um kit de {n}, o anúncio diz {do_anuncio}"
    return None


def preco_confere(oferta: Oferta, pagina: Pagina) -> bool | None:
    """True/False comparando com os preços que a página declara; None se a página não declara preço."""
    if not pagina.precos or not oferta.preco:
        return None
    perto = min(pagina.precos, key=lambda v: abs(v - oferta.preco))
    return abs(perto - oferta.preco) / oferta.preco <= TOLERANCIA_PRECO


@dataclass
class Veredito:
    errado: str | None = None            # motivo para tirar a oferta
    confirmado: bool = False
    ler_com_ia: bool = False
    parecido: bool = False               # outro acabamento/cor/linha: não é o pedido, mas serve para a ESTIMATIVA


def julgar(pedido: str, oferta: Oferta, pagina: Pagina | None) -> Veredito:
    """Núcleo puro da conferência de um link."""
    host = (urlparse(oferta.url or "").hostname or "").lower()
    if re.search(r"(^|\.)(google|bing|duckduckgo|yahoo)\.", host):
        return Veredito(errado="link do buscador, não da loja")
    if e_listagem(oferta.url, pagina):
        return Veredito(errado="página de busca ou categoria, não do produto")
    if pagina and pagina.http in (404, 410):
        return Veredito(errado="página não existe mais")
    if pagina and pagina.esgotado:
        return Veredito(errado="produto esgotado na loja")
    legivel = bool(pagina and pagina.http == 200 and pagina.nome and "mercado libre" not in _norm(pagina.nome))
    nome = pagina.nome if legivel else slug(oferta.url)
    if motivo := conflito(pedido, nome, oferta):
        return Veredito(errado=motivo, parecido=motivo.startswith(("outro acabamento", "outra cor", "outra linha")))
    if not legivel:
        return Veredito()                                   # bloqueou robô: sem como confirmar
    confere = preco_confere(oferta, pagina)
    if confere is False:
        return Veredito(errado=f"preço da página diferente (R$ {min(pagina.precos, key=lambda v: abs(v - oferta.preco)):.2f})")
    if confere is True:
        return Veredito(confirmado=True)
    return Veredito(ler_com_ia=bool(pagina.texto and oferta.preco))


# ------------------------------------------------------------------ rede
async def _abrir(cli: httpx.AsyncClient, url: str, porteiro: asyncio.Semaphore) -> Pagina:
    agora = time.monotonic()
    if (g := _cache.get(url)) and agora - g[0] < CACHE_S:
        return g[1]
    try:
        async with porteiro:
            r = await cli.get(url, headers=UA, follow_redirects=True, timeout=TIMEOUT_S)
        pagina = ler_html(r.status_code, str(r.url), r.text[:800000]) if r.status_code == 200 else Pagina(r.status_code, str(r.url))
    except Exception as exc:  # noqa: BLE001 — loja fora do ar ou lenta: sem como saber
        logger.info("Não abriu %s (%s)", url[:80], type(exc).__name__)
        pagina = Pagina(None, url)
    _cache[url] = (agora, pagina)
    return pagina


def _trecho_do_produto(p: Pagina) -> str:
    """Pedaço do texto em volta do nome do produto (onde fica o preço principal)."""
    i = _norm(p.texto).find(_norm(p.nome)[:40]) if p.nome else -1
    ini = max(i, 0)
    return p.texto[ini:ini + 3500]


async def _ler_com_ia(pedido: str, oferta: Oferta, pagina: Pagina) -> bool | None:
    """A IA de extração lê o texto da página; o preço só vale se estiver escrito nele (trava de sempre)."""
    from .busca import ResultadoWeb
    from .precos import extrair_e_conferir
    rw = ResultadoWeb(titulo=pagina.nome, url=oferta.url, dominio=oferta.dominio, loja=oferta.loja,
                      trecho=_trecho_do_produto(pagina))
    try:
        r = await asyncio.wait_for(extrair_e_conferir(pedido, [rw]), timeout=25)
    except Exception as exc:  # noqa: BLE001
        logger.info("IA não leu a página %s (%s)", oferta.url[:80], type(exc).__name__)
        return None
    lida = next((o for o in r.ofertas if o.preco), None)
    if lida is None or not oferta.preco:
        return None
    return lida.mesmo_produto != "nao" and abs(lida.preco - oferta.preco) / oferta.preco <= TOLERANCIA_PRECO


@observe(name="pesquisa.conferir_links", capture_input=False, capture_output=False)
async def conferir(pedido: str, ofertas: list[Oferta], cliente: httpx.AsyncClient | None = None) -> list[Oferta]:
    """Ofertas com link errado saem; as confirmadas ganham `link_verificado=True`. Nunca levanta exceção."""
    if not ofertas or not ATIVO:
        return ofertas
    try:
        porteiro = asyncio.Semaphore(SIMULTANEAS)
        urls = list(dict.fromkeys(o.url for o in ofertas if o.url))
        if cliente is not None:
            paginas = dict(zip(urls, await asyncio.gather(*(_abrir(cliente, u, porteiro) for u in urls))))
        else:
            async with httpx.AsyncClient() as cli:
                paginas = dict(zip(urls, await asyncio.gather(*(_abrir(cli, u, porteiro) for u in urls))))
        saida, para_ia = [], []
        for o in ofertas:
            v = julgar(pedido, o, paginas.get(o.url))
            if v.errado and v.parecido:
                # medido em 08/11: tirar de vez deixava o porcelanato "polido" sem nada (as lojas tinham natural e
                # acetinado); como "parecido" ele vira estimativa com pergunta e nunca passa por exato. Se a página
                # mostra o preço anunciado, o link é de um produto real com preço real: vale para a estimativa.
                pg = paginas.get(o.url)
                real = bool(pg and pg.http == 200 and preco_confere(o, pg))
                saida.append(o.model_copy(update={"mesmo_produto": "parecido", "link_verificado": real}))
                continue
            if v.errado:
                logger.info("Link removido (%s): %s %s", v.errado, o.loja, o.url[:90])
                continue
            o = o.model_copy(update={"link_verificado": v.confirmado})
            if v.ler_com_ia and len(para_ia) < MAX_LEITURAS_IA:
                para_ia.append(len(saida))
            saida.append(o)
        if para_ia:
            try:
                lidas = await asyncio.gather(*(_ler_com_ia(pedido, saida[i], paginas[saida[i].url]) for i in para_ia))
            except Exception as exc:  # noqa: BLE001 — sem a IA, ficam sem confirmar (os errados já saíram)
                logger.warning("Leitura das páginas pela IA falhou (%s)", type(exc).__name__, exc_info=True)
                return saida
            fora = set()
            for i, ok in zip(para_ia, lidas):
                if ok is True:
                    saida[i] = saida[i].model_copy(update={"link_verificado": True})
                elif ok is False:
                    fora.add(i)
            saida = [o for i, o in enumerate(saida) if i not in fora]
        return saida
    except Exception as exc:  # noqa: BLE001 — a conferência nunca derruba a pesquisa
        logger.warning("Conferência de links falhou (%s): ofertas seguem sem confirmar", type(exc).__name__, exc_info=True)
        return [o.model_copy(update={"link_verificado": False}) for o in ofertas]
