"""Verifica links de compra em lote. As referências ainda servem para estimar."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from urllib.parse import urlparse

from langfuse import observe

from .busca import _rodizio_global, eh_pagina_de_busca, eh_pagina_de_listagem, fonte_nao_e_loja
from .config import get_settings
from .google_shopping import MIN_MESMO, semelhanca
from .precos import Oferta

logger = logging.getLogger(__name__)
LIMITE_LINKS = 20
_PRECO = r"R\$\s*(\d+(?:\.\d{3})*,\d{2})(?!\d)"
_CONDICAO = re.compile(r"\b(?:pix|boleto|parcel\w*|cupom|frete|cashback|a partir de|preco anterior|economize|desconto|assinatura|clube)\b|\b\d+\s*x\b")
_ROTULO_PAGAMENTO = re.compile(r"^\W*(?:a vista\s+)?(?:no pix|via pix|com pix|no boleto|com cupom)\b")
_RELACIONADOS = re.compile(r"^\W*(?:produtos relacionados|quem viu|quem comprou|veja tambem|outros produtos|compre junto)\b")
_LISTAGEM = re.compile(r"^\W*(?:resultados (?:da busca|para)|filtrar por|ordenar por|todos os produtos|mostrar mais produtos|\d+ (?:itens|produtos|resultados))\b")
_AUSENTE = re.compile(r"(?:pagina|produto) nao encontrad[ao]|(?:page|product) not found|\b(?:http|status|erro|error)\s*:?\s*(?:404|410)\b|^(?:404|410)(?:$|\s*[:–-])")
_SEM_ESTOQUE = re.compile(r"\b(?:produto (?:indisponivel|esgotado|sem estoque)|fora de estoque|temporariamente indisponivel|indisponivel para compra|anuncio (?:esta |foi )?(?:pausado|finalizado|encerrado|indisponivel)|anuncio nao esta disponivel|nao e possivel comprar|avise[- ]me quando (?:chegar|disponivel))\b")
_COMPRAR = re.compile(r"\b(?:comprar|adicionar ao carrinho|adicionar a sacola|em estoque)\b")
_LINHA_PRECO = re.compile(rf"^(?:\W*|(?:por|preco(?: de venda)?)\s*:?\s*){_PRECO}", re.I)


def _normalizar(texto: str) -> str:
    from unicodedata import normalize
    return " ".join(normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode().split())


def _identidade(titulo: str) -> list[str]:
    return [p for p in re.findall(r"[a-z0-9]+", _normalizar(titulo))
            if p not in {"a", "o", "de", "da", "do", "das", "dos", "e", "para"}]


def _candidata(oferta: Oferta) -> bool:
    if not oferta.preco or oferta.mesmo_produto == "nao":
        return False
    try:
        u = urlparse(oferta.url)
        host = u.hostname or ""
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443) or not u.path.strip("/"):
            return False
        if "." not in host or host.endswith((".local", ".internal", ".localhost")):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        return not (re.search(r"(^|\.)(google|googleadservices|bing|duckduckgo|yahoo)\.", host)
                    or eh_pagina_de_busca(oferta.url) or eh_pagina_de_listagem(host, oferta.url)
                    or fonte_nao_e_loja(host, oferta.url))
    except ValueError:
        return False


def _leitura(texto: str) -> tuple[bool, str, set[float]]:
    """Identifica indisponibilidade ou um preço de venda ligado ao título principal."""
    linhas = []
    for linha in texto[:16000].splitlines():
        if _RELACIONADOS.match(_normalizar(linha)):
            break
        if limpa := re.sub(r"~~.*?~~|[*_]", "", linha).strip():
            linhas.append(limpa)
    if any(_AUSENTE.search(_normalizar(linha.lstrip("# "))) for linha in linhas[:6]) or any(
        _SEM_ESTOQUE.search(_normalizar(linha)) for linha in linhas
    ):
        return True, "", set()
    titulos = [(i, linha[2:].strip()) for i, linha in enumerate(linhas) if linha.startswith("# ")]
    if len(titulos) != 1 or any(_LISTAGEM.match(_normalizar(linha)) for linha in linhas):
        return False, "", set()
    i_titulo, titulo = titulos[0]
    detalhes = linhas[i_titulo + 1:i_titulo + 31]
    if not _COMPRAR.search(_normalizar(" ".join(detalhes))):
        return False, "", set()
    precos = set()
    rotulo_condicional = False
    for i, linha in enumerate(detalhes):
        t = _normalizar(linha)
        anterior = rotulo_condicional
        condicional = bool(_CONDICAO.search(t))
        rotulo_condicional = condicional and not re.search(_PRECO, linha, re.I)
        if condicional or (anterior and not t.startswith(("por ", "preco de venda"))):
            continue
        if i + 1 < len(detalhes) and _ROTULO_PAGAMENTO.match(_normalizar(detalhes[i + 1])):
            continue
        linha = re.sub(rf"\bde\s*:?\s+{_PRECO}\s+por\s*:?\s*", "", linha, flags=re.I)
        if re.match(r"\W*(?:de\s*:?\s+|era\s+)r\$", linha, re.I):
            continue
        if _LINHA_PRECO.match(linha):
            precos.update(float(v.replace(".", "").replace(",", ".")) for v in re.findall(_PRECO, linha, re.I))
    return False, titulo, precos


@observe(name="pesquisa.links_compra", capture_input=False, capture_output=False)
async def verificar_ofertas(descricao: str, ofertas: list[Oferta]) -> list[Oferta]:
    s = get_settings()
    # 1º a conferência direta na loja (src/conferir_links.py): tira os links errados e confirma os certos.
    from .conferir_links import conferir
    # confirmação antiga (do cache) não vale: a página é conferida de novo agora
    ofertas = [o.model_copy(update={"link_verificado": False}) if o.link_verificado else o for o in ofertas]
    ofertas = await conferir(descricao, ofertas)
    # 2º o Tavily Extract, só para o que ficou sem confirmar (loja que bloqueia robô)
    urls = list(dict.fromkeys(o.url for o in ofertas if _candidata(o) and not o.link_verificado))[:LIMITE_LINKS]
    if not urls or not s.pesquisa_paginas_por_rodada or not s.tavily_keys:
        return ofertas
    try:
        from tavily import AsyncTavilyClient
        rodizio = _rodizio_global()
        dados = None
        for _ in range(len(s.tavily_keys)):   # chave sem crédito: tenta a próxima (antes desistia e nada era confirmado)
            chave = rodizio.atual
            if not chave:
                return ofertas
            try:
                dados = await asyncio.wait_for(AsyncTavilyClient(api_key=chave).extract(
                    urls=urls, extract_depth="basic", format="markdown", timeout=s.pesquisa_pagina_timeout_s,
                ), timeout=s.pesquisa_pagina_timeout_s + 1)
                break
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ in ("ForbiddenError", "InvalidAPIKeyError", "UsageLimitExceededError"):
                    rodizio.descartar_atual(type(exc).__name__)
                    continue
                raise
        if dados is None:
            return ofertas
        leituras = {r["url"]: _leitura(r.get("raw_content") or "") for r in dados.get("results", []) if r.get("url") in urls}
        indisponiveis = {url for url, (ausente, _, _) in leituras.items() if ausente}
        indisponiveis.update(r["url"] for r in dados.get("failed_results", []) if r.get("url") in urls
                             and _AUSENTE.search(_normalizar(str(r.get("error") or ""))))
    except Exception as exc:
        logger.info("Verificação de links indisponível (%s)", type(exc).__name__)
        return ofertas
    saida = []
    for o in ofertas:
        if o.url in indisponiveis:
            continue
        _, titulo, precos = leituras.get(o.url, (False, "", set()))
        # Na estimativa, a semelhança é suficiente. No link, cor e kit fazem parte da identidade.
        identidade = _identidade(titulo)
        verificado = (precos == {o.preco} and semelhanca(descricao, titulo) >= MIN_MESMO
                      and identidade == _identidade(o.titulo) and set(_identidade(descricao)) <= set(identidade))
        saida.append(o.model_copy(update={"link_verificado": True}) if verificado and not o.link_verificado else o)
    return saida
