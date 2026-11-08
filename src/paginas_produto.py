"""Leitura limitada das páginas encontradas; texto externo é evidência, nunca instrução."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from dataclasses import replace
from urllib.parse import urlparse

from langfuse import observe

from . import custo
from .busca import ResultadoWeb, _rodizio_global, link_direto_produto
from .config import get_settings
from .especificacao import normalizar

logger = logging.getLogger(__name__)


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
        paginas = {r["url"]: recortar(r.get("raw_content") or "", produto)
                   for r in dados.get("results", []) if r.get("url") in permitidas}
        paginas = {u: t for u, t in paginas.items() if t.strip()}
        custo.registrar_paginas(len(paginas))
        # Página prevalece sobre snippet antigo; URLs com falha preservam o trecho da busca.
        return [replace(r, trecho=paginas[r.url], pagina_lida=True) if r.url in paginas else r for r in resultados]
    except Exception as exc:
        logger.info("Leitura de página indisponível (%s); mantendo resultados da busca", type(exc).__name__)
        return resultados
