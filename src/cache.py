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
    """Lê os dois formatos da tabela: o do SQL único da fatia A (`resultado` jsonb com tudo dentro)
    e o antigo da fatia B (colunas soltas: descricao, ofertas, modelo, provedor)."""
    try:
        atualizado = datetime.fromisoformat(str(linha["atualizado_em"]).replace("Z", "+00:00"))
        dados = linha["resultado"] if isinstance(linha.get("resultado"), dict) else linha
        ofertas = [Oferta(**o) for o in (dados.get("ofertas") or [])]
        iteracoes = max(0, int(dados.get("iteracoes") or 0))
    except Exception:  # noqa: BLE001 — linha corrompida não pode quebrar a pesquisa
        logger.warning("Linha do cache ilegível (%s): ignorada", linha.get("chave"))
        return None
    return EntradaCache(chave=linha["chave"], descricao=dados.get("descricao") or "",
                        extracao=ResultadoExtracao(ofertas=ofertas, modelo=dados.get("modelo") or "cache"),
                        imagem_url=linha.get("imagem_url"), provedor=dados.get("provedor"),
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


# Formatos da tabela, do oficial para os de reserva. Medido em 07/11 à tarde: a tabela passou por um formato
# temporário (`resultado` jsonb) e voltou ao de colunas com `iteracoes` (sql/002_orcamentos.sql da fatia A).
def _colunas(linha: dict) -> dict:                       # oficial: sql/002_orcamentos.sql
    return linha


def _colunas_sem_iteracoes(linha: dict) -> dict:         # banco ainda no sql/002_cache_precos.sql da fatia B
    return {k: v for k, v in linha.items() if k != "iteracoes"}


def _resultado_jsonb(linha: dict) -> dict:               # formato temporário visto em 07/11 ~14h30
    dentro = {k: linha[k] for k in ("descricao", "ofertas", "modelo", "provedor", "iteracoes")}
    return {"chave": linha["chave"], "resultado": dentro, "imagem_url": linha["imagem_url"],
            "atualizado_em": linha["atualizado_em"]}


_FORMATOS = [_colunas, _colunas_sem_iteracoes, _resultado_jsonb]
_formato = 0   # índice do formato que o banco aceitou (fica guardado: não tenta de novo o que já falhou)


def _gravar_sync(linha: dict, cliente) -> None:
    """Grava no formato oficial; se o banco recusar alguma coluna (PGRST204), passa para o próximo formato.
    (Com várias colunas faltando o PostgREST cita só uma, então não dá para escolher pelo nome.)"""
    global _formato
    while True:
        try:
            cliente.table(TABELA).upsert(_FORMATOS[_formato](linha), on_conflict="chave").execute()
            return
        except Exception as exc:  # noqa: BLE001
            if "PGRST204" not in str(exc) or _formato == len(_FORMATOS) - 1:
                raise
            _formato += 1
            logger.warning("cache_precos recusou uma coluna (%s): gravando no formato %s", str(exc)[:90],
                           _FORMATOS[_formato].__name__)


@observe(name="cache.gravar")
async def gravar(descricao: str, extracao: ResultadoExtracao, imagem_url: str | None, provedor: str | None = None,
                 anterior: EntradaCache | None = None, cliente=None, iteracoes: int = 0) -> bool:
    """Grava/atualiza o cache. Só grava pesquisa útil (alguma oferta com preço).
    Uma nova imagem verificada substitui a antiga; sem foto nova, preserva a anterior."""
    chave = chave_cache(descricao)
    if not chave or not any(o.preco for o in extracao.ofertas):
        return False
    linha = {
        "chave": chave, "descricao": descricao,
        "ofertas": [o.model_dump() for o in extracao.ofertas],
        "imagem_url": imagem_url or (anterior.imagem_url if anterior else None),
        "modelo": extracao.modelo or None, "provedor": provedor, "iteracoes": iteracoes,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await asyncio.to_thread(_gravar_sync, linha, cliente or _cliente())
        return True
    except Exception as exc:  # noqa: BLE001
        if not _tabela_ausente(exc):
            logger.warning("Falha ao gravar o cache (%s): resultado segue sem cache", type(exc).__name__)
        return False
