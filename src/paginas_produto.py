"""Leitura limitada das páginas encontradas; texto externo é evidência, nunca instrução."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from urllib.parse import urlparse

from langfuse import observe

from . import custo
from .busca import ResultadoWeb, _rodizio_global, link_direto_produto
from .config import get_settings
from .especificacao import nao_confirmados, normalizar

logger = logging.getLogger(__name__)
EXIGIR_PRECO_DA_PAGINA = ContextVar("exigir_preco_da_pagina", default=False)


@contextmanager
def modo_preco_da_pagina(ativo: bool):
    token = EXIGIR_PRECO_DA_PAGINA.set(ativo)
    try:
        yield
    finally:
        EXIGIR_PRECO_DA_PAGINA.reset(token)


_VALOR = r"R\$\s*((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?)(?!\d|[.,]\d)"
_CONDICAO = re.compile(r"\b(pix|boleto|parcel\w*|cupom|frete|cashback|a partir de|a partir|preco anterior|preco original|preco sugerido|economize)\b|\b\d+\s*x\s*(?:de\s*)?r\$", re.I)
_RELACIONADOS = re.compile(r"^\W*(?:produtos relacionados|quem viu|quem comprou|voce tambem pode gostar|veja tambem|compre junto)\b")


def preco_claro_da_pagina(texto: str) -> tuple[str, float | None]:
    """Um único valor de venda em BRL no bloco do produto; recusa ambiguidade."""
    linhas = []
    for linha in texto.splitlines():
        if _RELACIONADOS.search(normalizar(linha)):
            break
        linhas.append(linha)
    principal = "\n".join(linhas)
    if len(principal) > 100_000 or re.search(r"\b(produto indisponivel|fora de estoque|avise-me quando|esgotado)\b", normalizar(principal)):
        return principal, None
    valores = set()
    rotulo_condicional = False
    for linha in linhas:
        limpa = re.sub(r"~~.*?~~|[*_]", "", linha)
        if not limpa.strip():
            continue
        anterior_condicional = rotulo_condicional
        condicional = bool(_CONDICAO.search(normalizar(limpa)))
        rotulo_condicional = condicional and not re.search(_VALOR, limpa, re.I)
        if condicional or (anterior_condicional and not re.match(r"\s*(?:por\b|preco de venda\b)", normalizar(limpa))):
            continue
        limpa = re.sub(rf"\bde\s*:?\s+{_VALOR}\s+por\s*:?\s*", "", limpa, flags=re.I)
        if re.match(r"\W*(?:de\s*:?\s+|era\s+)r\$", limpa, re.I):
            continue
        valores.update(float(v.replace(".", "").replace(",", ".")) for v in re.findall(_VALOR, limpa, re.I))
    preco = next(iter(valores)) if len(valores) == 1 else None
    return principal, preco if preco and 0 < preco < 100_000_000 else None


def url_publica(url: str) -> bool:
    try:
        u = urlparse(url)
        host = u.hostname or ""
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            return False
        if "." not in host or host.endswith((".local", ".internal", ".localhost")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


def recortar(texto: str, produto: str, limite=1400) -> str:
    """Cabeçalho + linhas técnicas/preço relevantes. Nunca mandar HTML/página inteira ao LLM."""
    linhas = [re.sub(r"\s+", " ", x).strip() for x in texto[:100000].splitlines() if x.strip()]
    termos = set(normalizar(produto).split()) - {"de", "com", "para", "e"}
    escolhidas = linhas[:3]
    for linha in linhas[3:]:
        t = normalizar(linha)
        if re.search(r"r\$|referencia|modelo|dimens|acabamento|voltagem|potencia|cor:|marca:", t) or len(termos & set(t.split())) >= 2:
            escolhidas.append(linha)
    return "\n".join(dict.fromkeys(escolhidas))[:limite]


@observe(name="pesquisa.paginas", capture_output=False)
async def aprofundar(produto: str, resultados: list[ResultadoWeb], cliente=None) -> list[ResultadoWeb]:
    s = get_settings()
    if not s.pesquisa_paginas_por_rodada or (cliente is None and not s.tavily_keys):
        return resultados
    acc = custo.atual()
    vistos = acc.urls if acc else set()
    candidatos = []
    for r in resultados:
        if r.url in vistos or not url_publica(r.url) or not link_direto_produto(r.url):
            continue
        candidatos.append(r)
        vistos.add(r.url)
        if len(candidatos) >= s.pesquisa_paginas_por_rodada:
            break
    if not candidatos:
        return resultados
    if cliente is None:
        from tavily import AsyncTavilyClient
        chave = _rodizio_global().atual
        if not chave:
            return resultados
        cliente = AsyncTavilyClient(api_key=chave)
    try:
        dados = await asyncio.wait_for(cliente.extract(
            urls=[r.url for r in candidatos], extract_depth="basic", timeout=s.pesquisa_pagina_timeout_s),
            timeout=s.pesquisa_pagina_timeout_s + 1)
        permitidas = {r.url for r in candidatos}
        paginas = {}
        for r in dados.get("results", []):
            if r.get("url") not in permitidas:
                continue
            raw = r.get("raw_content") or ""
            principal, preco = preco_claro_da_pagina(raw) if EXIGIR_PRECO_DA_PAGINA.get() else (raw, None)
            if preco is not None and nao_confirmados(produto, principal):
                preco = None
            if trecho := recortar(principal, produto):
                paginas[r["url"]] = (trecho, preco)
        custo.registrar_paginas(len(paginas))
        # Página prevalece sobre snippet antigo; URLs com falha preservam o trecho da busca.
        return [replace(r, trecho=paginas[r.url][0], pagina_lida=True, preco_pagina=paginas[r.url][1])
                if r.url in paginas else r for r in resultados]
    except Exception as exc:
        logger.info("Leitura de página indisponível (%s); mantendo resultados da busca", type(exc).__name__)
        return resultados
