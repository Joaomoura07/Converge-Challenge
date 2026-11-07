"""Etapa ①② da pesquisa: monta a consulta e busca na web (Tavily → DuckDuckGo).

Só traz resultados de uma LISTA FIXA de lojas brasileiras (decisão do plano: evita blog,
fórum e preço em dólar). Não extrai preço: isso é da etapa ③ (src/precos.py).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlparse

from langfuse import observe

from .config import get_settings
from .modelos import ItemEntrada

logger = logging.getLogger(__name__)

# Domínio -> nome da loja. A Fatia C casa `dominio` com a tabela `fornecedores`.
LOJAS: dict[str, str] = {
    "leroymerlin.com.br": "Leroy Merlin",
    "cec.com.br": "C&C",
    "telhanorte.com.br": "Telhanorte",
    "obramax.com.br": "Obramax",
    "ferreiracosta.com": "Ferreira Costa",
    "madeiramadeira.com.br": "MadeiraMadeira",
    "amazon.com.br": "Amazon",
    "mercadolivre.com.br": "Mercado Livre",
    "magazineluiza.com.br": "Magazine Luiza",
    "casasbahia.com.br": "Casas Bahia",
    "americanas.com.br": "Americanas",
    "dicico.com.br": "Dicico",
    "loja.suvinil.com.br": "Loja Suvinil",
    # Lojas oficiais das marcas e redes regionais vistas nas buscas reais (avaliação da etapa 2)
    "lojadexco.com.br": "Loja Dexco (Deca)",
    "tramontina.com.br": "Loja Tramontina",
    "sertao.com.br": "Sertão",
    "padovani.com.br": "Padovani",
    "tumelero.com.br": "Tumelero",
}
MAX_POR_LOJA = 2   # evita 5 resultados da mesma loja (a média precisa de lojas diferentes)

PALAVRAS_RUIDO = re.compile(r"\b(\d+[.,]?\d*\s*(m2|m²|m3|m³|un|und|unid|pç|pc)\b)", re.I)


@dataclass
class ResultadoWeb:
    titulo: str
    url: str
    dominio: str
    loja: str
    trecho: str


@dataclass
class ImagemWeb:
    url: str
    descricao: str = ""


@dataclass
class RespostaBusca:
    consulta: str
    provedor: str                     # "tavily" | "duckduckgo" | "nenhum"
    resultados: list[ResultadoWeb] = field(default_factory=list)
    imagens: list[ImagemWeb] = field(default_factory=list)   # candidatas
    erro: str | None = None
    ms: int = 0
    imagem: str | None = None         # a ESCOLHIDA (uma só por produto); None → tela mostra a hachura


# ------------------------------------------------------------------ escolha da imagem
_FORA = re.compile(r"ytimg|youtube|pinterest|instagram|facebook|fbcdn|blogspot|wikipedia|tiktok", re.I)
_LIXO = re.compile(r"logo|banner|icon|sprite|placeholder|selo|\.svg(\?|$)|\.gif(\?|$)", re.I)
_AMBIENTE = re.compile(r"\b(room|living|kitchen|bathroom|bedroom|interior|space|decor|ambiente|sala|cozinha|banheiro)\b", re.I)
_PRODUTO = re.compile(r"\b(displayed|product|white background|isolated|packaging|box|close-up|closeup)\b", re.I)
_MINIATURA = re.compile(r"[-_/](\d{2,3})[-x](\d{2,3})(?:[/?._-]|$)")
# Cor em PT (item) -> palavras equivalentes em PT/EN (descrição da imagem vem em inglês)
CORES = {
    "branco": {"branco", "branca", "white"}, "preto": {"preto", "preta", "black"},
    "cinza": {"cinza", "gray", "grey", "graphite", "grafite"}, "cromado": {"cromado", "cromada", "chrome", "silver"},
    "dourado": {"dourado", "dourada", "gold", "golden"}, "rose": {"rose", "rosé", "rose gold"},
    "cobre": {"cobre", "copper"}, "inox": {"inox", "stainless"}, "bege": {"bege", "beige"},
    "vermelho": {"vermelho", "vermelha", "red"}, "azul": {"azul", "blue"}, "verde": {"verde", "green"},
}
_STOP = {"de", "da", "do", "com", "para", "e", "em", "a", "o", "preco", "preço", "cm", "mm", "m", "x"}
NOTA_MINIMA = 2.0


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def _cores_em(texto: str) -> set[str]:
    t = f" {_norm(texto)} "
    return {cor for cor, palavras in CORES.items() if any(f" {_norm(p)} " in t or f"-{_norm(p)}-" in t for p in palavras)}


_MEDIDA = re.compile(r"(?<!\d)(\d{2,4})\s?[x×]\s?(\d{2,4})(?!\d)", re.I)


def _medidas_em(texto: str) -> set[tuple[int, int]]:
    """'56x34', '60X60', '1200 x 2400' -> {(34, 56), ...} (ordem não importa: 56x34 == 34x56).
    Ignora tamanhos de miniatura de CDN (ex.: '-290-290', '420x420')."""
    out = set()
    for a, b in _MEDIDA.findall(texto):
        par = tuple(sorted((int(a), int(b))))
        if par[0] == par[1] and par[0] in (100, 120, 150, 200, 250, 290, 300, 400, 420, 500, 600, 800, 1000):
            continue  # provável tamanho de imagem, não medida de produto (exceto se o item pedir, e aí casa igual)
        out.add(par)
    return out


def nota_imagem(img: ImagemWeb, produto: str) -> float:
    """Nota de quão bem a imagem representa ESTE produto (regra fixa e explicável)."""
    url_desc = f"{img.url} {img.descricao}"
    if _FORA.search(img.url) or _LIXO.search(img.url):
        return -100.0
    nota = 0.0
    if loja_de(dominio_de(img.url)) or any(t in img.url.lower() for t in
                                           ("vtexassets", "mlstatic", "mlcdn", "media-amazon", "cdn.leroymerlin")):
        nota += 2  # imagem servida por loja
    # ATENÇÃO: a descrição do Tavily é escrita a partir da CONSULTA e "concorda" com ela mesmo quando
    # a foto é de outro produto (caso real: URL "cuba_inox_69x49", descrição "showcasing its 56x34 cm").
    # Por isso a URL (escrita pela loja) manda; a descrição vale pouco e só é usada quando a URL é muda.
    termos = {t for t in re.findall(r"[a-z0-9]+", _norm(produto)) if len(t) > 1 and t not in _STOP}
    na_url = f" {re.sub(r'[^a-z0-9]+', ' ', _norm(img.url))} "
    na_desc = f" {re.sub(r'[^a-z0-9]+', ' ', _norm(img.descricao))} "
    for t in termos:                                                      # marca, modelo, medida
        if f" {t} " in na_url:
            nota += 1.0
        elif f" {t} " in na_desc:
            nota += 0.3
    cores_item = _cores_em(produto)
    cores_img = _cores_em(img.url) or _cores_em(img.descricao)
    if cores_item and cores_img:
        nota += 2 if cores_item & cores_img else -4                       # cor errada pesa muito
    medidas_item = _medidas_em(produto)
    medidas_img = _medidas_em(img.url) or _medidas_em(img.descricao)
    if medidas_item and medidas_img:
        nota += 2 if medidas_item & medidas_img else -10                  # medida errada (69x49 ≠ 56x34) = OUTRO produto
    if _PRODUTO.search(img.descricao):
        nota += 1
    if _AMBIENTE.search(img.descricao):
        nota -= 1.5
    m = _MINIATURA.search(img.url)
    if m and max(int(m.group(1)), int(m.group(2))) < 300:
        nota -= 1
    return nota


def _candidatas(imagens: list[ImagemWeb], produto: str) -> list[ImagemWeb]:
    """Acima da nota mínima, da melhor para a pior. Empate decidido pela URL (sempre o mesmo resultado)."""
    boas = [i for i in imagens if nota_imagem(i, produto) >= NOTA_MINIMA]
    return sorted(boas, key=lambda i: (nota_imagem(i, produto), -len(i.url), i.url), reverse=True)


def escolher_imagem(imagens: list[ImagemWeb], produto: str) -> str | None:
    """Uma imagem só: a de maior nota (sem checar se carrega)."""
    c = _candidatas(imagens, produto)
    return c[0].url if c else None


_ASSINATURAS = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


async def imagem_carrega(url: str) -> bool:
    """A URL entrega uma imagem de verdade? (Algumas lojas devolvem uma página HTML para quem vem de fora.)"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=4, follow_redirects=True, headers={"User-Agent": _UA}) as c:
            async with c.stream("GET", url) as r:
                if r.status_code != 200:
                    return False
                inicio = b""
                async for pedaco in r.aiter_bytes():
                    inicio += pedaco
                    if len(inicio) >= 16:
                        break
        return inicio.startswith(_ASSINATURAS) or (inicio[:4] == b"RIFF" and inicio[8:12] == b"WEBP") \
            or inicio[4:12] in (b"ftypavif", b"ftypheic")
    except Exception:  # noqa: BLE001 — timeout, DNS, TLS: trata como "não carrega"
        return False


async def escolher_imagem_verificada(imagens: list[ImagemWeb], produto: str, checar=imagem_carrega,
                                     max_checar: int = 3) -> str | None:
    """A melhor imagem QUE CARREGA. Checa as 3 melhores em paralelo e fica com a de maior nota que passou."""
    top = _candidatas(imagens, produto)[:max_checar]
    if not top:
        return None
    ok = await asyncio.gather(*(checar(i.url) for i in top))
    return next((i.url for i, passou in zip(top, ok) if passou), None)


def dominio_de(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def loja_de(dominio: str) -> str | None:
    """Casa subdomínios também (ex.: produto.mercadolivre.com.br)."""
    for d, nome in LOJAS.items():
        if dominio == d or dominio.endswith("." + d):
            return nome
    return None


def _limpa(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto)
    return re.sub(r"\s+", " ", PALAVRAS_RUIDO.sub(" ", texto)).strip()


def montar_consulta(item: ItemEntrada, complemento: str = "") -> str:
    """'Porcelanato Portobello Cimento Queimado 90x90' -> 'Porcelanato Portobello Cimento Queimado 90x90 preço'.
    Quantidades do quantitativo (48 m²) saem: atrapalham a busca. `complemento` é usado pelo agente ao refazer."""
    base = _limpa(item.descricao)
    partes = [base, complemento.strip(), "preço"]
    return " ".join(p for p in partes if p)


# Página de busca/listagem da loja, não o produto (achado da passagem: "magazineluiza.com.br/busca/...").
# Ela mostra vários produtos e preços: a fonte não aponta para o item e o preço pode ser de outro produto.
_PAGINA_DE_BUSCA = re.compile(
    r"/(busca|search|pesquisa|buscar)(/|\?|$)|/s\?|[?&](q|k|term|termo|text|query|busca|ft)=|//lista\.mercadolivre\.",
    re.I)


def eh_pagina_de_busca(url: str) -> bool:
    return bool(_PAGINA_DE_BUSCA.search(url or ""))


def _filtra(brutos: list[tuple[str, str, str]], limite: int) -> list[ResultadoWeb]:
    vistos, por_loja, saida = set(), {}, []
    for titulo, url, trecho in brutos:
        dom = dominio_de(url)
        loja = loja_de(dom)
        if not loja or url in vistos or por_loja.get(loja, 0) >= MAX_POR_LOJA or eh_pagina_de_busca(url):
            continue
        vistos.add(url)
        por_loja[loja] = por_loja.get(loja, 0) + 1
        saida.append(ResultadoWeb(titulo=titulo or "", url=url, dominio=dom, loja=loja, trecho=(trecho or "")[:1200]))
        if len(saida) >= limite:
            break
    return saida


class _RodizioChaves:
    """Usa uma chave Tavily por vez; pula para a próxima se esgotar créditos ou for inválida."""

    def __init__(self, chaves: list[str]):
        self.chaves = list(chaves)
        self.i = 0

    @property
    def atual(self) -> str | None:
        return self.chaves[self.i] if self.i < len(self.chaves) else None

    def descartar_atual(self, motivo: str) -> None:
        logger.warning("Tavily: chave %d/%d descartada (%s)", self.i + 1, len(self.chaves), motivo)
        self.i += 1


_rodizio: _RodizioChaves | None = None


def _rodizio_global() -> _RodizioChaves:
    global _rodizio
    if _rodizio is None:
        _rodizio = _RodizioChaves(get_settings().tavily_keys)
    return _rodizio


async def _tavily(consulta: str, limite: int, rodizio: _RodizioChaves) -> RespostaBusca:
    from tavily import AsyncTavilyClient
    from tavily.errors import ForbiddenError, InvalidAPIKeyError, UsageLimitExceededError

    while rodizio.atual:
        try:
            r = await AsyncTavilyClient(api_key=rodizio.atual).search(
                consulta, search_depth="basic", max_results=limite + 3, include_images=True,
                include_image_descriptions=True,  # sem custo extra; usado para escolher 1 imagem
                # NÃO usar country="brazil": combinado com include_domains, o Tavily volta com 0 resultados
                # na maioria das buscas (medido na avaliação da etapa 2). A lista de lojas já garante o Brasil.
                include_domains=list(LOJAS), timeout=20)
            brutos = [(x.get("title"), x.get("url"), x.get("content")) for x in r.get("results", [])]
            imagens = [ImagemWeb(i.get("url", ""), i.get("description") or "") if isinstance(i, dict) else ImagemWeb(i)
                       for i in r.get("images", [])]
            return RespostaBusca(consulta, "tavily", _filtra(brutos, limite), [i for i in imagens if i.url])
        except (UsageLimitExceededError, InvalidAPIKeyError, ForbiddenError) as exc:
            rodizio.descartar_atual(type(exc).__name__)
    return RespostaBusca(consulta, "nenhum", erro="sem chave Tavily válida")


DDG_TIMEOUT_S = 8


async def _duckduckgo(consulta: str, limite: int) -> RespostaBusca:
    """Reserva: só texto (a busca de imagem dobrava o tempo) e com limite de tempo."""
    from ddgs import DDGS

    def _sync():
        with DDGS() as d:
            return d.text(consulta, region="br-pt", max_results=25) or []

    texto = await asyncio.wait_for(asyncio.to_thread(_sync), timeout=DDG_TIMEOUT_S)
    brutos = [(x.get("title"), x.get("href"), x.get("body")) for x in texto]
    return RespostaBusca(consulta, "duckduckgo", _filtra(brutos, limite))


@observe(as_type="retriever", name="busca.web")
async def buscar(consulta: str, limite: int | None = None, rodizio: _RodizioChaves | None = None) -> RespostaBusca:
    """Tavily primeiro; se der erro OU vier sem nenhuma loja da lista, tenta o DuckDuckGo."""
    limite = limite or get_settings().pesquisa_max_lojas
    rodizio = rodizio or _rodizio_global()
    t0 = time.perf_counter()
    resp, erros = None, []
    for tentativa in range(2):  # o Tavily às vezes volta vazio sob carga: 1 nova tentativa antes da reserva
        try:
            resp = await _tavily(consulta, limite, rodizio)
            if resp.erro:
                erros.append(f"tavily: {resp.erro}")
                break  # sem chave válida: não adianta tentar de novo
            if resp.resultados:
                break
        except Exception as exc:  # noqa: BLE001 — timeout, rede, 5xx
            erros.append(f"tavily: {type(exc).__name__}")
        if tentativa == 0:
            await asyncio.sleep(0.5)
    if not resp or not resp.resultados:
        try:
            reserva = await _duckduckgo(consulta, limite)
            if not reserva.imagens and resp and resp.imagens:
                reserva.imagens = resp.imagens  # o Tavily devolve imagens mesmo sem resultados
            if reserva.resultados or not resp:
                resp = reserva
        except Exception as exc:  # noqa: BLE001
            erros.append(f"duckduckgo: {type(exc).__name__}")
    if not resp:
        resp = RespostaBusca(consulta, "nenhum")
    if not resp.resultados:
        resp.erro = "; ".join(erros) or "nenhuma loja da lista retornou resultado"
    resp.imagem = await escolher_imagem_verificada(resp.imagens, consulta)
    resp.ms = int((time.perf_counter() - t0) * 1000)
    return resp
