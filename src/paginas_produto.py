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

_PAGINA_AUSENTE = re.compile(
    r"(?:p[aá]gina|produto)\s+n[aã]o\s+encontrad[ao]|(?:page|product)\s+not\s+found", re.I,
)
_HTTP_AUSENTE = re.compile(r"^(?:404|410)\b|\b(?:http(?:\s+error)?|status(?:\s+code)?|error|erro)\s*[:=]?\s*(?:404|410)\b", re.I)


def _conteudo_indisponivel(texto: str) -> bool:
    """Algumas lojas retornam HTTP 200 com um título de página de erro."""
    inicio = [linha.strip(" #*\t") for linha in texto[:2000].splitlines() if linha.strip()][:6]
    return any(_PAGINA_AUSENTE.fullmatch(re.sub(r"^(?:404|410)\s*[-–:]\s*", "", linha).rstrip(".!"))
               or _HTTP_AUSENTE.fullmatch(linha)
               or re.fullmatch(r"(?:erro\s+)?404(?:\s*[-–:]\s*)?(?:not found)?", linha, re.I) for linha in inicio)


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
async def aprofundar(produto: str, resultados: list[ResultadoWeb], cliente=None, *, limite: int | None = None) -> list[ResultadoWeb]:
    s = get_settings()
    acc = custo.atual()
    indisponiveis = acc.urls_indisponiveis if acc else set()
    resultados = [r for r in resultados if r.url not in indisponiveis]
    if not s.pesquisa_paginas_por_rodada or (cliente is None and not s.tavily_keys):
        return resultados
    vistos = acc.urls if acc else set()
    candidatos = []
    for r in resultados:
        if r.url in vistos or not url_publica(r.url) or not link_direto_produto(r.url):
            continue
        candidatos.append(r)
        vistos.add(r.url)
        if len(candidatos) >= (limite or s.pesquisa_paginas_por_rodada):
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
            conteudo = r.get("raw_content") or ""
            if _conteudo_indisponivel(conteudo):
                indisponiveis.add(r["url"])
            else:
                paginas[r["url"]] = recortar(conteudo, produto)
        for r in dados.get("failed_results", []):
            erro = str(r.get("error") or "").strip()
            ausente = (_HTTP_AUSENTE.search(erro) or _PAGINA_AUSENTE.search(erro)
                       or erro.lower() in {"not found", "gone"})
            if r.get("url") in permitidas and ausente:
                indisponiveis.add(r["url"])
        paginas = {u: t for u, t in paginas.items() if t.strip()}
        custo.registrar_paginas(len(paginas))
        return [replace(r, trecho=paginas[r.url], pagina_lida=True) if r.url in paginas else r
                for r in resultados if r.url not in indisponiveis]
    except Exception as exc:
        logger.info("Leitura de página indisponível (%s); mantendo resultados da busca", type(exc).__name__)
        return [r for r in resultados if r.url not in indisponiveis]
