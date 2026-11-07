"""Etapa ① da pesquisa: cache de preços no Supabase (tabela cache_precos, sql/002_cache_precos.sql).

- Chave = descrição normalizada: "Tinta Suvinil Toque de Seda, Branco Neve 18 L" e
  "tinta suvinil branco neve toque seda 18L" caem na mesma linha.
- Guarda as ofertas conferidas + a imagem escolhida (não guarda a conta: ela depende da quantidade
  de cada orçamento e é refeita por src/calculo.py, que é instantâneo).
- Válido por N dias (PESQUISA_CACHE_DIAS). Vencido continua disponível como reserva para quando
  a busca falhar ("preço de dd/mm").
- Nunca derruba a pesquisa: tabela ausente, rede fora ou dado estranho = "não está no cache".
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from langfuse import observe

from .config import get_settings
from .precos import Oferta, ResultadoExtracao

logger = logging.getLogger(__name__)

TABELA = "cache_precos"
PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "para", "pra", "com", "em", "e", "a", "o", "cor", "na", "no", "p"}
_avisou_tabela = False


def chave_cache(descricao: str) -> str:
    """Minúsculas, sem acento, unidades coladas ao número (18 L -> 18l), sem palavras vazias,
    sem repetição e em ordem alfabética (a ordem das palavras não muda o produto)."""
    t = unicodedata.normalize("NFKD", descricao or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)                                   # 2,5 -> 2.5
    t = re.sub(r"(\d)\s+(mm2|cm2|m2|m3|ml|lt|l|kg|g|mm|cm|m)\b", r"\1\2", t)   # 18 l -> 18l
    t = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", t)                             # 60 x 60 -> 60x60
    tokens = {w.strip(".") for w in re.findall(r"[a-z0-9.]+", t)} - PALAVRAS_VAZIAS - {""}
    return " ".join(sorted(tokens))


@dataclass
class EntradaCache:
    chave: str
    descricao: str
    extracao: ResultadoExtracao
    imagem_url: str | None
    provedor: str | None
    atualizado_em: datetime
    vencido: bool
    iteracoes: int = 0   # buscas extras do agente quando o produto foi pesquisado (sql/003)

    @property
    def data_preco(self) -> str:
        """Para a tela: 'preço de 07/11'."""
        return self.atualizado_em.astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m")


def _cliente():
    from .database import get_supabase   # import tardio: os testes trocam o cliente
    return get_supabase()


def _tabela_ausente(exc: Exception) -> bool:
    global _avisou_tabela
    if "PGRST205" in str(exc) or (TABELA in str(exc) and "schema cache" in str(exc)):
        if not _avisou_tabela:
            logger.warning("Tabela %s não existe no Supabase: rode sql/002_cache_precos.sql. Seguindo sem cache.", TABELA)
            _avisou_tabela = True
        return True
    return False


def _para_entrada(linha: dict, dias: int, agora: datetime) -> EntradaCache | None:
    try:
        atualizado = datetime.fromisoformat(str(linha["atualizado_em"]).replace("Z", "+00:00"))
        ofertas = [Oferta(**o) for o in (linha.get("ofertas") or [])]
        iteracoes = max(0, int(linha.get("iteracoes") or 0))
    except Exception:  # noqa: BLE001 — linha corrompida não pode quebrar a pesquisa
        logger.warning("Linha do cache ilegível (%s): ignorada", linha.get("chave"))
        return None
    return EntradaCache(chave=linha["chave"], descricao=linha.get("descricao") or "",
                        extracao=ResultadoExtracao(ofertas=ofertas, modelo=linha.get("modelo") or "cache"),
                        imagem_url=linha.get("imagem_url"), provedor=linha.get("provedor"),
                        atualizado_em=atualizado, vencido=agora - atualizado > timedelta(days=dias), iteracoes=iteracoes)


def _ler_sync(chave: str, cliente) -> dict | None:
    r = cliente.table(TABELA).select("*").eq("chave", chave).limit(1).execute()
    return r.data[0] if r.data else None


@observe(name="cache.ler")
async def ler(descricao: str, aceitar_vencido: bool = False, cliente=None) -> EntradaCache | None:
    """Devolve a entrada válida (ou vencida, se aceitar_vencido) ou None."""
    chave = chave_cache(descricao)
    if not chave:
        return None
    try:
        linha = await asyncio.to_thread(_ler_sync, chave, cliente or _cliente())
    except Exception as exc:  # noqa: BLE001
        if not _tabela_ausente(exc):
            logger.warning("Falha ao ler o cache (%s): seguindo sem cache", type(exc).__name__)
        return None
    if not linha:
        return None
    entrada = _para_entrada(linha, get_settings().pesquisa_cache_dias, datetime.now(timezone.utc))
    if entrada is None or (entrada.vencido and not aceitar_vencido):
        return None
    return entrada


async def apagar(descricao: str, cliente=None) -> bool:
    """Tira um produto do cache (usado pelo pré-aquecimento da demo para deixar parte dos itens 'ao vivo')."""
    chave = chave_cache(descricao)
    try:
        cli = cliente or _cliente()
        await asyncio.to_thread(lambda: cli.table(TABELA).delete().eq("chave", chave).execute())
        return True
    except Exception as exc:  # noqa: BLE001
        if not _tabela_ausente(exc):
            logger.warning("Falha ao apagar do cache (%s)", type(exc).__name__)
        return False


_sem_coluna_iteracoes = False


def _falta_coluna_iteracoes(exc: Exception) -> bool:
    """PostgREST: PGRST204 = coluna não existe (sql/003 ainda não rodado)."""
    return "iteracoes" in str(exc) and ("PGRST204" in str(exc) or "column" in str(exc).lower())


def _gravar_sync(linha: dict, cliente) -> None:
    global _sem_coluna_iteracoes
    if _sem_coluna_iteracoes:
        linha = {k: v for k, v in linha.items() if k != "iteracoes"}
    try:
        cliente.table(TABELA).upsert(linha, on_conflict="chave").execute()
    except Exception as exc:  # noqa: BLE001
        if "iteracoes" not in linha or not _falta_coluna_iteracoes(exc):
            raise
        logger.warning("Coluna cache_precos.iteracoes não existe (rode sql/003_cache_precos_iteracoes.sql): gravando sem ela")
        _sem_coluna_iteracoes = True
        cliente.table(TABELA).upsert({k: v for k, v in linha.items() if k != "iteracoes"}, on_conflict="chave").execute()


@observe(name="cache.gravar")
async def gravar(descricao: str, extracao: ResultadoExtracao, imagem_url: str | None, provedor: str | None = None,
                 anterior: EntradaCache | None = None, cliente=None, iteracoes: int = 0) -> bool:
    """Grava/atualiza o cache. Só grava pesquisa útil (alguma oferta com preço).
    Imagem estável: se já havia uma imagem para este produto, ela é mantida."""
    chave = chave_cache(descricao)
    if not chave or not any(o.preco for o in extracao.ofertas):
        return False
    linha = {
        "chave": chave, "descricao": descricao,
        "ofertas": [o.model_dump() for o in extracao.ofertas],
        "imagem_url": (anterior.imagem_url if anterior and anterior.imagem_url else None) or imagem_url,
        "modelo": extracao.modelo or None, "provedor": provedor,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "iteracoes": iteracoes,
    }
    try:
        await asyncio.to_thread(_gravar_sync, linha, cliente or _cliente())
        return True
    except Exception as exc:  # noqa: BLE001
        if not _tabela_ausente(exc):
            logger.warning("Falha ao gravar o cache (%s): resultado segue sem cache", type(exc).__name__)
        return False
