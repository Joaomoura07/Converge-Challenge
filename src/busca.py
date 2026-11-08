"""Etapa ①② da pesquisa: monta a consulta e busca na web (Tavily → DuckDuckGo).

Duas buscas em paralelo por item:
1. FIXA: uma lista de lojas brasileiras conhecidas (sem blog, fórum ou preço em dólar; imagem confiável);
2. ABERTA: qualquer loja do Brasil, com a cidade e a UF da obra (do CEP), só anúncios com preço escrito.
   Medido em 07/11: só com a lista fixa a média era 1,4 loja por item.
Não extrai preço: isso é da etapa ③ (src/precos.py).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata
from contextlib import contextmanager
from contextvars import ContextVar
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

# Redes com LOJA FÍSICA no estado da obra (só as confirmadas; o resto do país entra pela busca aberta, que já usa a
# cidade do CEP). Quando a obra é no estado, essas lojas vêm antes na busca e a fonte é marcada "perto da obra".
REDES_REGIONAIS: dict[str, set[str]] = {
    "PE": {"ferreiracosta.com", "armazemcoral.com.br"},
    "AL": {"ferreiracosta.com"},
    "BA": {"ferreiracosta.com"},
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
    """Lojas da lista fixa. Anúncio com preço escrito vem antes do sem preço: a Leroy Merlin carrega o preço por
    JavaScript e o anúncio dela, sem 'R$', tomava a vaga de uma loja que rende preço (achado de 07/11)."""
    vistos, por_loja, saida = set(), {}, []
    for titulo, url, trecho in brutos:
        dom = dominio_de(url)
        loja = loja_de(dom)
        if not loja or url in vistos or por_loja.get(loja, 0) >= MAX_POR_LOJA or eh_pagina_de_busca(url):
            continue
        vistos.add(url)
        por_loja[loja] = por_loja.get(loja, 0) + 1
        saida.append(ResultadoWeb(titulo=titulo or "", url=url, dominio=dom, loja=loja, trecho=(trecho or "")[:1200]))
    local = LOCAL_DA_OBRA.get()
    # com preço antes; entre eles, lojas com unidade no estado da obra antes (sort estável: mantém a ordem da busca)
    saida.sort(key=lambda r: (not tem_preco(r.titulo, r.trecho), not perto_da_obra(r.dominio, local)))
    return saida[:limite]


def perto_da_obra(dominio: str, local: "Local | None") -> bool:
    """A loja tem unidade física no estado da obra (tabela REDES_REGIONAIS)."""
    if not local or not dominio:
        return False
    return any(dominio == d or dominio.endswith("." + d) for d in REDES_REGIONAIS.get(local.uf.upper(), ()))


# ------------------------------------------------------------------ busca aberta (lojas da região da obra)
@dataclass(frozen=True)
class Local:
    cidade: str
    uf: str


# O local da obra vale para a pesquisa inteira do orçamento (inclusive dentro do agente) sem mudar a assinatura de
# nenhuma função nem o contrato com A/C: quem pesquisa um orçamento define com `na_regiao(...)`.
LOCAL_DA_OBRA: ContextVar[Local | None] = ContextVar("local_da_obra", default=None)


@contextmanager
def na_regiao(local: Local | None):
    token = LOCAL_DA_OBRA.set(local)
    try:
        yield
    finally:
        LOCAL_DA_OBRA.reset(token)


_locais: dict[str, Local | None] = {}


async def local_do_cep(cep: str | None) -> Local | None:
    """CEP da obra → cidade e UF (ViaCEP, grátis, sem chave). Falha = None (a busca segue sem local)."""
    digitos = re.sub(r"\D", "", cep or "")
    if len(digitos) != 8:
        return None
    if digitos in _locais:
        return _locais[digitos]
    import httpx
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            j = (await c.get(f"https://viacep.com.br/ws/{digitos}/json/")).json()
        local = Local(j["localidade"], j["uf"]) if j.get("localidade") and j.get("uf") else None
    except Exception as exc:  # noqa: BLE001 — sem rede/ViaCEP fora: pesquisa continua sem local
        logger.warning("ViaCEP falhou para o CEP da obra (%s): busca sem cidade", type(exc).__name__)
        return None   # não guarda a falha: tenta de novo no próximo orçamento
    _locais[digitos] = local
    return local


# Sites que não são loja (ou cujo preço não é de uma loja: comparadores, importados)
BLOQUEADOS = ["youtube.com", "facebook.com", "instagram.com", "pinterest.com", "pinterest.com.br", "tiktok.com",
              "x.com", "twitter.com", "linkedin.com", "reddit.com", "wikipedia.org", "reclameaqui.com.br",
              "buscape.com.br", "zoom.com.br", "google.com", "aliexpress.com", "shein.com", "temu.com",
              "shopee.com.br", "olx.com.br", "gov.br", "jusbrasil.com.br",
              # órgãos públicos, ensino e militares: editais, licitações e leilões não são loja. Medido no site em
              # 07/11: interruptor a R$ 5,50 com fonte num edital de leilão da Justiça Federal (jfpe.jus.br, PDF)
              "jus.br", "leg.br", "mp.br", "edu.br", "mil.br", "def.br",
              # bases de preço de licitação/obra pública: preço de referência, não oferta de loja (medido em 07/11)
              "bancodeprecos.com.br", "buscadorsinapi.com.br"]
_DOCUMENTO = re.compile(r"\.(pdf|docx?|xlsx?|odt|ods|pptx?)(?:$|[?#])", re.I)
_TEM_PRECO = re.compile(r"R\$\s?\d")
_PARTES_DO_DOMINIO = re.compile(r"^(www|loja|lojas|shop|m)\.", re.I)


def tem_preco(titulo: str, trecho: str) -> bool:
    """Anúncio sem 'R$ 123' escrito não rende preço: a trava anti-alucinação descartaria o que o LLM dissesse."""
    return bool(_TEM_PRECO.search(f"{titulo} {trecho}"))


def nome_da_loja(dominio: str, titulo: str) -> str:
    """'Tinta Coral 18L | Casa do Construtor' (casadoconstrutor.com.br) -> 'Casa do Construtor'.
    O fim do título só vale se combinar com o domínio: medido em 07/11, ele às vezes é categoria ou estado
    ('material elétrico', 'SP'). Senão, o domínio: 'acmateriais.com.br' -> 'Acmateriais'."""
    base = _PARTES_DO_DOMINIO.sub("", dominio).split(".")[0]
    rotulo = re.sub(r"[^a-z0-9]", "", _sem_acento(base))
    for sep in (" | ", " - ", " – "):
        if sep in (titulo or ""):
            fim = titulo.rsplit(sep, 1)[1].strip()
            compacto = re.sub(r"[^a-z0-9]", "", _sem_acento(fim))
            if 2 <= len(fim) <= 30 and len(compacto) >= 3 and (compacto in rotulo or rotulo in compacto):
                return fim
    return base.replace("-", " ").title() or dominio


def _bloqueado(dominio: str) -> bool:
    return any(dominio == b or dominio.endswith("." + b) for b in BLOQUEADOS)


# Página de LISTAGEM de uma loja (filtro por marca/medida), não a do produto: o preço lido é de algum item da lista.
# Medido no cache em 07/11: 43 de 60 ofertas da Leroy Merlin eram listagem ("/pedra-britada/peso-do-produto-na-
# embalagem/1400_Kg..." virou brita a R$ 1.450/m³). Produto da Leroy termina em "_<código>".
_PRODUTO_POR_LOJA = {"leroymerlin.com.br": re.compile(r"_\d{5,}/?$")}


def eh_pagina_de_listagem(dominio: str, url: str) -> bool:
    """Decide pelo endereço do LINK (é ele que diz se a página é produto ou lista); `dominio` fica na assinatura
    para quem chama com os dois campos da oferta."""
    partes = urlparse(url or "")
    host = (partes.hostname or "").lower()
    padrao = next((p for d, p in _PRODUTO_POR_LOJA.items() if host == d or host.endswith("." + d)), None)
    return padrao is not None and not padrao.search(partes.path)


def fonte_nao_e_loja(dominio: str, url: str) -> bool:
    """Site bloqueado ou arquivo (PDF, planilha): nunca vira fonte de preço. Usado na busca aberta e, no cálculo,
    também nas ofertas que já estavam no cache antes deste filtro."""
    return _bloqueado(dominio or "") or bool(_DOCUMENTO.search(url or ""))


def _da_regiao(texto: str, local: Local | None) -> bool:
    if not local:
        return False
    t = _sem_acento(texto)
    return _sem_acento(local.cidade) in t or bool(re.search(rf"\b{local.uf.lower()}\b", t))


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def _filtra_aberto(brutos: list[tuple[str, str, str]], limite: int, local: Local | None) -> list[ResultadoWeb]:
    """Lojas fora da lista fixa: só com preço escrito, sem página de busca, 1 por domínio; as da região primeiro."""
    vistos, saida = set(), []
    for titulo, url, trecho in brutos:
        dom = dominio_de(url)
        if (not dom or dom in vistos or loja_de(dom) or fonte_nao_e_loja(dom, url) or eh_pagina_de_busca(url)
                or not tem_preco(titulo or "", trecho or "")):
            continue
        vistos.add(dom)
        saida.append(ResultadoWeb(titulo=titulo or "", url=url, dominio=dom, loja=nome_da_loja(dom, titulo or ""),
                                  trecho=(trecho or "")[:1200]))
    saida.sort(key=lambda r: not _da_regiao(f"{r.titulo} {r.trecho}", local))   # sort estável: mantém a ordem
    return saida[:limite]


MAX_DOMINIOS_REGIONAIS = 15   # o Tavily aceita uma lista curta de domínios por busca
MAX_REGIONAIS = 4             # anúncios de lojas da região por item (1 por loja)
MIN_COM_PRECO_SEM_ABERTA = 2   # a lista fixa já basta (mesmo número que faz o agente refazer: pesquisa_min_lojas)


def consulta_regional(consulta: str, local: Local | None) -> str:
    return f"{consulta} {local.cidade} {local.uf}" if local else consulta


MOTIVOS_TAVILY = {"UsageLimitExceededError": "limite de requisições por minuto (429)",
                  "ForbiddenError": "plano esgotado ou sem permissão (403/432/433)",
                  "InvalidAPIKeyError": "chave inválida (401)"}
ESFRIAR_S = 20.0   # 429 do Tavily é limite por minuto: passa sozinho, a chave volta depois de alguns segundos


class _RodizioChaves:
    """Usa uma chave Tavily por vez. Chave inválida ou de plano esgotado sai DE VEZ; chave que só bateu no limite por
    minuto (429) descansa `ESFRIAR_S` segundos e volta. Antes, qualquer erro tirava a chave para sempre: uma rajada de
    buscas (16 simultâneas por orçamento) bastava para o processo da Vercel ficar "sem chave válida" até reiniciar."""

    def __init__(self, chaves: list[str]):
        self.chaves = list(chaves)
        self.i = 0
        self._ate: dict[int, float] = {}      # índice -> instante (monotonic) em que a chave volta; inf = definitivo
        self._motivo: dict[int, str] = {}

    @property
    def atual(self) -> str | None:
        agora = time.monotonic()
        for passo in range(len(self.chaves)):
            idx = (self.i + passo) % len(self.chaves)
            if self._ate.get(idx, 0.0) <= agora:
                self.i = idx
                return self.chaves[idx]
        return None

    def descartar_atual(self, motivo: str) -> None:
        logger.warning("Tavily: chave %d/%d descartada (%s)", self.i + 1, len(self.chaves), motivo)
        self._ate[self.i] = float("inf")
        self._motivo[self.i] = MOTIVOS_TAVILY.get(motivo, motivo)
        self.i = (self.i + 1) % max(len(self.chaves), 1)

    def esfriar_atual(self, motivo: str, segundos: float = ESFRIAR_S) -> None:
        logger.warning("Tavily: chave %d/%d em pausa por %.0f s (%s)", self.i + 1, len(self.chaves), segundos, motivo)
        self._ate[self.i] = time.monotonic() + segundos
        self._motivo[self.i] = MOTIVOS_TAVILY.get(motivo, motivo)
        self.i = (self.i + 1) % max(len(self.chaves), 1)

    def espera_s(self) -> float | None:
        """Quanto falta para a primeira chave que está só em pausa voltar (None = nenhuma volta sozinha)."""
        agora = time.monotonic()
        pausas = [t - agora for t in self._ate.values() if t != float("inf")]
        return max(0.0, min(pausas)) if pausas else None

    def resumo(self) -> str:
        """Por que não há chave: aparece no motivo do item, para o diagnóstico não depender dos logs da Vercel."""
        if not self.chaves:
            return "nenhuma chave configurada: TAVILY_API_KEYS vazia neste servidor"
        return "; ".join(f"chave {i + 1}: {self._motivo.get(i, 'ok')}" for i in range(len(self.chaves)))

    async def sem_chave(self, consulta: str) -> "RespostaBusca":
        return RespostaBusca(consulta, "nenhum", erro=f"sem chave Tavily válida ({self.resumo()})")


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


# O ddgs raspa buscadores sem chave e eles bloqueiam IP de nuvem de vez em quando. Tenta o Brave (rápido, ~1 s) e,
# se falhar ou vier vazio, o modo "auto" (que sorteia outros motores). A soma dos prazos é DDG_TIMEOUT_S.
DDG_BACKENDS = (("brave", 3.0), ("auto", DDG_TIMEOUT_S - 3.0))


async def _ddg_texto(consulta: str) -> list[dict]:
    """Resultados de texto do ddgs, tentando um motor por vez. Levanta o último erro se nenhum render nada."""
    from ddgs import DDGS

    ultimo: Exception = RuntimeError("ddgs sem resultados")
    for backend, prazo in DDG_BACKENDS:
        def _sync(backend=backend):
            with DDGS() as d:
                return d.text(consulta, region="br-pt", max_results=25, backend=backend) or []
        try:
            texto = await asyncio.wait_for(asyncio.to_thread(_sync), timeout=prazo)
            if texto:
                return texto
        except Exception as exc:  # noqa: BLE001 — timeout, bloqueio, sem resultados
            ultimo = exc
            logger.info("DuckDuckGo (%s) falhou: %s", backend, type(exc).__name__)
    raise ultimo


async def _serper_texto(consulta: str) -> list[tuple[str, str, str]]:
    """Busca orgânica do Google (serper.dev) como reserva do Tavily. Sem chave ou com falha: lista vazia.
    Gasta crédito do Serper, por isso só entra depois que o Tavily falhou ou veio vazio."""
    import httpx

    from . import serper

    chaves = get_settings().serper_keys
    if not chaves:
        return []
    try:
        async with httpx.AsyncClient(timeout=6.0) as cli:
            j = await serper.post(cli, "https://google.serper.dev/search",
                                  {"q": consulta, "gl": "br", "hl": "pt-br", "num": 10}, chaves)
    except Exception as exc:  # noqa: BLE001
        logger.info("Serper (reserva da busca) falhou: %s", type(exc).__name__)
        return []
    return [(o.get("title"), o.get("link"), o.get("snippet")) for o in ((j or {}).get("organic") or [])
            if isinstance(o, dict) and o.get("link")]


async def _serper_busca(consulta: str, limite: int) -> RespostaBusca:
    return RespostaBusca(consulta, "serper", _filtra(await _serper_texto(consulta), limite))


async def _duckduckgo(consulta: str, limite: int) -> RespostaBusca:
    """Reserva: só texto (a busca de imagem dobrava o tempo) e com limite de tempo."""
    texto = await _ddg_texto(consulta)
    brutos = [(x.get("title"), x.get("href"), x.get("body")) for x in texto]
    return RespostaBusca(consulta, "duckduckgo", _filtra(brutos, limite))


async def _tavily_aberto(consulta: str, limite: int, rodizio: _RodizioChaves, local: Local | None) -> RespostaBusca:
    """Qualquer loja do Brasil (menos as da lista fixa, que a outra busca já cobre), com a cidade/UF da obra."""
    from tavily import AsyncTavilyClient
    from tavily.errors import ForbiddenError, InvalidAPIKeyError, UsageLimitExceededError

    q = consulta_regional(consulta, local)
    while rodizio.atual:
        try:
            r = await AsyncTavilyClient(api_key=rodizio.atual).search(
                q, search_depth="basic", max_results=10, include_images=True, country="brazil",
                exclude_domains=list(LOJAS) + BLOQUEADOS, timeout=20)
            brutos = [(x.get("title"), x.get("url"), x.get("content")) for x in r.get("results", [])]
            imagens = [ImagemWeb(i.get("url", ""), i.get("description") or "") if isinstance(i, dict) else ImagemWeb(i)
                       for i in r.get("images", [])]
            return RespostaBusca(q, "tavily", _filtra_aberto(brutos, limite, local), [i for i in imagens if i.url])
        except (UsageLimitExceededError, InvalidAPIKeyError, ForbiddenError) as exc:
            rodizio.descartar_atual(type(exc).__name__)
    return RespostaBusca(q, "nenhum", erro="sem chave Tavily válida")


async def _duckduckgo_aberto(consulta: str, limite: int, local: Local | None) -> RespostaBusca:
    q = consulta_regional(consulta, local)
    texto = await _ddg_texto(q)
    return RespostaBusca(q, "duckduckgo", _filtra_aberto([(x.get("title"), x.get("href"), x.get("body")) for x in texto],
                                                        limite, local))


async def _serper_aberto(consulta: str, limite: int, local: Local | None) -> RespostaBusca:
    q = consulta_regional(consulta, local)
    return RespostaBusca(q, "serper", _filtra_aberto(await _serper_texto(q), limite, local))


async def _buscar_aberta(consulta: str, limite: int, rodizio: _RodizioChaves, local: Local | None) -> RespostaBusca:
    """Nunca levanta exceção: busca aberta que falha só deixa o item com as lojas da lista fixa."""
    try:
        r = await _tavily_aberto(consulta, limite, rodizio, local)
        if r.resultados:
            return r
    except Exception as exc:  # noqa: BLE001
        logger.info("Busca aberta no Tavily falhou (%s); tentando Serper e DuckDuckGo", type(exc).__name__)
    try:
        r = await _serper_aberto(consulta, limite, local)
        if r.resultados:
            return r
    except Exception as exc:  # noqa: BLE001
        logger.info("Busca aberta no Serper falhou (%s); tentando DuckDuckGo", type(exc).__name__)
    try:
        return await _duckduckgo_aberto(consulta, limite, local)
    except Exception as exc:  # noqa: BLE001
        return RespostaBusca(consulta, "nenhum", erro=f"busca aberta: {type(exc).__name__}")


async def _com_prazo(fazer_busca, prazo_s: float, consulta: str) -> RespostaBusca:
    """A busca aberta às vezes leva 10 s (medido em 07/11) e o item esperava por ela: 1º item na tela foi de ~6 s
    para 20 s. Passou do prazo, o item segue só com a lista fixa."""
    try:
        return await asyncio.wait_for(fazer_busca(), timeout=prazo_s)   # criada aqui: cancelada antes de começar não vira aviso
    except asyncio.TimeoutError:
        logger.info("Busca aberta passou de %.0f s: item segue com a lista fixa", prazo_s)
        return RespostaBusca(consulta, "nenhum", erro="busca aberta: tempo esgotado")


@observe(as_type="retriever", name="busca.web")
async def buscar(consulta: str, limite: int | None = None, rodizio: _RodizioChaves | None = None) -> RespostaBusca:
    """Busca FIXA (lista de lojas) e ABERTA (região da obra) em paralelo; junta as duas.
    A aberta pode ser desligada em `pesquisa_busca_aberta` (ex.: cota do Tavily acabando)."""
    s = get_settings()
    limite = limite or s.pesquisa_max_lojas
    rodizio = rodizio or _rodizio_global()
    t0 = time.perf_counter()
    if not s.pesquisa_busca_aberta:
        resp = await _buscar_fixa(consulta, limite, rodizio)
    else:
        # As duas começam juntas. Se a lista fixa já trouxe 2+ anúncios com preço, o item não espera a aberta
        # (medido em 07/11: esperar a aberta levava o 1º item na tela de ~6 s para 12–20 s).
        local = LOCAL_DA_OBRA.get()
        tarefa_aberta = asyncio.ensure_future(
            _com_prazo(lambda: _buscar_aberta(consulta, s.pesquisa_max_abertas, rodizio, local),
                       s.pesquisa_prazo_aberta_s, consulta))
        # Lojas da REGIÃO da obra (Google Maps pelo CEP): busca DENTRO dos sites delas. É o diferencial (comprar perto
        # de quem compra), então o item sempre espera essa busca, com prazo.
        tarefa_regional = asyncio.ensure_future(
            _com_prazo(lambda: _buscar_regional(consulta, rodizio), s.pesquisa_prazo_aberta_s, consulta))
        resp = await _buscar_fixa(consulta, limite, rodizio)
        if sum(tem_preco(r.titulo, r.trecho) for r in resp.resultados) >= MIN_COM_PRECO_SEM_ABERTA:
            tarefa_aberta.cancel()
            aberta = RespostaBusca(consulta, "nenhum")
        else:
            aberta = await tarefa_aberta
        regional = await tarefa_regional
        urls = {r.url for r in regional.resultados}
        juntos = regional.resultados + [r for r in resp.resultados + aberta.resultados if r.url not in urls]
        resp.resultados = juntos[: s.pesquisa_max_anuncios]
        if resp.resultados:
            resp.erro = None
        if not resp.imagens:
            resp.imagens = aberta.imagens
        if resp.provedor == "nenhum":
            resp.provedor = aberta.provedor
    resp.imagem = await escolher_imagem_verificada(resp.imagens, consulta)
    resp.ms = int((time.perf_counter() - t0) * 1000)
    return resp


async def _buscar_regional(consulta: str, rodizio: _RodizioChaves) -> RespostaBusca:
    """Produto procurado DENTRO dos sites das lojas da região da obra (src/regiao.py). Só anúncio com preço escrito.
    Sem lojas da região (sem CEP, sem chave do Serper): resposta vazia, sem gastar busca."""
    from tavily import AsyncTavilyClient

    from .regiao import dominios_regionais, regional_por_dominio
    dominios = dominios_regionais()[:MAX_DOMINIOS_REGIONAIS]
    if not dominios or not rodizio.atual:
        return RespostaBusca(consulta, "nenhum")
    try:
        r = await AsyncTavilyClient(api_key=rodizio.atual).search(
            consulta, search_depth="basic", max_results=10, include_domains=dominios, timeout=20)
    except Exception as exc:  # noqa: BLE001 — a busca regional nunca derruba a busca do item
        logger.info("Busca nas lojas da região falhou (%s)", type(exc).__name__)
        return RespostaBusca(consulta, "nenhum")
    saida, vistos = [], set()
    for x in r.get("results", []):
        titulo, url, trecho = x.get("title") or "", x.get("url") or "", x.get("content") or ""
        dom = dominio_de(url)
        loja = regional_por_dominio(dom)
        if (loja is None or dom in vistos or eh_pagina_de_busca(url) or fonte_nao_e_loja(dom, url)
                or not tem_preco(titulo, trecho)):
            continue
        vistos.add(dom)
        saida.append(ResultadoWeb(titulo=titulo, url=url, dominio=dom, loja=loja.nome, trecho=trecho[:1200]))
    return RespostaBusca(consulta, "tavily", saida[:MAX_REGIONAIS])


async def _buscar_fixa(consulta: str, limite: int, rodizio: _RodizioChaves) -> RespostaBusca:
    """Tavily primeiro; se der erro OU vier sem nenhuma loja da lista, tenta o DuckDuckGo."""
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
            serper_r = await _serper_busca(consulta, limite)
            if serper_r.resultados:
                if resp and resp.imagens:
                    serper_r.imagens = resp.imagens
                return serper_r
        except Exception as exc:  # noqa: BLE001
            erros.append(f"serper: {type(exc).__name__}")
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
    return resp
