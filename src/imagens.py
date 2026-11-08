"""Recuperação de fotos sem LLM. A reserva só é usada se as imagens da busca falharem."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from urllib.parse import urlparse

import httpx
from langfuse import observe

from . import serper
from .config import get_settings

logger = logging.getLogger(__name__)
PRAZO_RESERVA_S = 8.0


def normalizar_url_imagem(valor: object) -> str | None:
    """Corrige templates de CDN conhecidos; rejeita URLs locais e protocolos não web."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    url = valor.strip()
    if url.startswith("//"):
        url = "https:" + url
    try:
        u = urlparse(url)
        host = (u.hostname or "").lower().rstrip(".")
        if (u.scheme not in ("http", "https") or u.username or u.password
                or u.port not in (None, 80, 443) or "." not in host
                or host.endswith((".local", ".internal", ".localhost"))):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        if host == "mlcdn.com.br" or host.endswith(".mlcdn.com.br"):
            url = re.sub(r"(?:\{w\}|%7bw%7d)x(?:\{h\}|%7bh%7d)", "600x600", url, flags=re.I)
        # A página é HTTPS: evita mixed content também para URLs antigas do cache.
        return re.sub(r"^http:", "https:", url, flags=re.I)
    except ValueError:
        return None


def ler_imagens_serper(dados: dict) -> list:
    from .busca import ImagemWeb, _FORA, _LIXO

    saida = []
    for i in (dados.get("images") or [])[:10]:
        if not isinstance(i, dict):
            continue
        original = normalizar_url_imagem(i.get("imageUrl"))
        titulo = i.get("title")
        if not original or not isinstance(titulo, str) or not titulo.strip():
            continue
        if _FORA.search(str(i.get("link") or "") + original) or _LIXO.search(original):
            continue
        saida.append(ImagemWeb(original, titulo))
        miniatura = normalizar_url_imagem(i.get("thumbnailUrl"))
        if miniatura and miniatura != original:
            # Guarda o título e URL de origem como evidência para não aceitar uma variante
            # incompatível só porque a miniatura tem URL opaca no Google.
            saida.append(ImagemWeb(miniatura, titulo, origem_url=original))
    return saida


@observe(name="busca.imagens_reserva", capture_output=False)
async def buscar_imagens_reserva(consulta: str) -> list:
    if not get_settings().serper_keys:
        return []
    try:
        async with httpx.AsyncClient(timeout=4.0) as cliente:
            dados = await asyncio.wait_for(serper.post(
                cliente, "https://google.serper.dev/images",
                {"q": consulta, "gl": "br", "hl": "pt-br", "num": 10}), timeout=4.5)
        return ler_imagens_serper(dados) if isinstance(dados, dict) else []
    except Exception as exc:
        logger.info("Reserva de imagens indisponível (%s)", type(exc).__name__)
        return []


async def completar_imagem(resposta, consulta: str) -> None:
    """No máximo 8 s extras; indisponibilidade de foto nunca derruba os preços."""
    from .busca import escolher_imagem_verificada

    async def recuperar():
        novas = await buscar_imagens_reserva(consulta)
        resposta.imagens.extend(novas)
        resposta.imagem = await escolher_imagem_verificada(novas, consulta, max_checar=6)

    try:
        await asyncio.wait_for(recuperar(), timeout=PRAZO_RESERVA_S)
    except Exception as exc:
        logger.info("Recuperação de imagem encerrada (%s)", type(exc).__name__)


async def imagem_do_cache(entrada, descricao: str) -> str | None:
    """Completa a foto do resultado, sem renovar os preços do cache.

    Não atualiza cache_precos: seu trigger renova atualizado_em em QUALQUER update,
    inclusive se apenas imagem_url mudar. A foto segue com o item do orçamento.
    """
    from .busca import RespostaBusca

    existente = normalizar_url_imagem(entrada.imagem_url)
    if existente:
        return existente
    r = RespostaBusca(descricao, "cache")
    await completar_imagem(r, descricao)
    return r.imagem
