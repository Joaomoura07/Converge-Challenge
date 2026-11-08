"""Alternativa de produto no "Pesquisar de novo" (fatia B).

O arquiteto escolhe um objetivo — maior qualidade, menor preço ou semelhante de outra marca — e:

    ① o LLM propõe UM produto concreto (só o nome; nunca preço)  →  ② a pesquisa normal (src/pesquisa.py) confere
    nas lojas, com fontes  →  ③ o código decide se a troca vale (achado à venda; no "menor preço", mais barato mesmo)

Se a alternativa não se sustenta, o item volta ao que era, com o motivo. O LLM nunca decide preço nem status:
ele só sugere o que pesquisar (regra nº 1 do agente: nenhum preço sem fonte).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from langfuse import get_client, observe

from . import custo as _custo
from .config import get_settings, load_prompt
from .modelos import ResultadoItem

logger = logging.getLogger(__name__)

Objetivo = Literal["qualidade", "preco", "semelhante"]
ROTULO: dict[str, str] = {
    "qualidade": "de maior qualidade",
    "preco": "de menor preço",
    "semelhante": "semelhante, de outra marca",
}
MAX_PRODUTO, MAX_POR_QUE = 160, 200


class AlternativaIndisponivel(Exception):
    """O LLM não respondeu, respondeu fora do formato ou não achou alternativa razoável."""


@dataclass(frozen=True)
class Alternativa:
    produto: str
    por_que: str


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _extrair_json(conteudo: str) -> dict[str, Any]:
    ini, fim = conteudo.find("{"), conteudo.rfind("}")
    if ini < 0 or fim <= ini:
        raise ValueError("resposta sem JSON")
    obj = json.loads(conteudo[ini:fim + 1])
    if not isinstance(obj, dict):
        raise ValueError("JSON não é objeto")
    return obj


@observe(as_type="generation", name="llm.featherless")
def _chamar_llm(client: Any, model: str, mensagens: list[dict]) -> str:
    # GLM-5.2 pensa antes de responder: max_tokens baixo devolve resposta vazia (skills/02).
    limite = get_settings().pesquisa_max_tokens_saida
    reserva = _custo.reservar(mensagens, limite)
    resp = client.chat.completions.create(model=model, messages=mensagens, temperature=0.3, max_tokens=limite, timeout=40)
    usage = resp.usage
    custo = getattr(usage, "cost", None) if usage else None
    _custo.registrar_resposta(reserva, usage)
    try:
        get_client().update_current_generation(
            model=model, model_parameters={"temperature": 0.3},
            usage_details={"input": usage.prompt_tokens, "output": usage.completion_tokens} if usage else None,
            cost_details={"total": float(custo)} if custo is not None else None)
    except Exception:  # noqa: BLE001 — telemetria nunca derruba a pesquisa
        logger.warning("Falha ao registrar a generation no Langfuse")
    return (resp.choices[0].message.content or "") if resp.choices else ""


def _validar(obj: dict, atual: str) -> Alternativa:
    produto = obj.get("produto")
    if not isinstance(produto, str) or not produto.strip():
        raise AlternativaIndisponivel("o modelo não achou alternativa razoável")
    produto = " ".join(produto.split())
    if not 5 <= len(produto) <= MAX_PRODUTO:
        raise AlternativaIndisponivel("produto sugerido fora do tamanho")
    if "r$" in produto.lower() or _norm(produto) == _norm(atual):
        raise AlternativaIndisponivel("o modelo repetiu o produto atual ou escreveu preço")
    por_que = obj.get("por_que")
    por_que = " ".join(por_que.split()) if isinstance(por_que, str) else ""
    # A frase não pode trazer número (preço, % de economia): números da tela vêm só da pesquisa.
    if not por_que or len(por_que) > MAX_POR_QUE or re.search(r"\d|r\$|%", por_que, re.I):
        por_que = ""
    return Alternativa(produto, por_que)


@observe(as_type="chain", name="pesquisa.alternativa")
def sugerir_alternativa(atual: str, objetivo: Objetivo, *, categoria: str | None = None,
                        client: Any = None, model: str | None = None) -> Alternativa:
    """Pede ao LLM UM produto para pesquisar no lugar de `atual`. Levanta AlternativaIndisponivel em qualquer falha."""
    if objetivo not in ROTULO:
        raise ValueError(f"objetivo desconhecido: {objetivo}")
    s = get_settings()
    if client is None:
        if not s.llm_configured:
            raise AlternativaIndisponivel("LLM não configurado")
        from .agent import build_llm_client
        client = build_llm_client().with_options(max_retries=0)
    pedido = {"produto_atual": atual, "objetivo": objetivo, "categoria": categoria}
    mensagens = [{"role": "system", "content": load_prompt("alternativa_produto")},
                 {"role": "user", "content": json.dumps(pedido, ensure_ascii=False)}]
    # Modelo frio (400/503) ou resposta vazia: tenta o reserva uma vez (skills/02, seção 4).
    modelos = [model] if model else list(dict.fromkeys(
        m for m in (s.pesquisa_modelo_alternativa, s.featherless_model_fallback or "Qwen/Qwen3-32B") if m))
    ultimo: Exception | None = None
    for modelo in modelos:
        try:
            return _validar(_extrair_json(_chamar_llm(client, modelo, mensagens)), atual)
        except AlternativaIndisponivel:
            raise   # o modelo respondeu, mas sem alternativa razoável: outro modelo não muda isso
        except Exception as exc:  # noqa: BLE001 — rede, modelo frio, JSON quebrado
            logger.warning("Sugestão de alternativa falhou com %s (%s)", modelo, type(exc).__name__)
            ultimo = exc
    raise AlternativaIndisponivel(type(ultimo).__name__) from ultimo


def _reais(v: float) -> str:
    inteiro, dec = f"{v:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{dec}"


def _unidade(u: str | None) -> str:
    return {"m2": "m²", "m3": "m³"}.get(u or "", u or "")


def _mais_barata(nova: ResultadoItem, anterior: ResultadoItem | None) -> bool | None:
    """True/False quando dá para comparar (mesma unidade de preço); None quando não dá."""
    if anterior is None or anterior.preco_emb_med is None or nova.preco_emb_med is None:
        return None
    if nova.preco_un_med is not None and anterior.preco_un_med is not None and nova.unidade_preco == anterior.unidade_preco:
        return nova.preco_un_med < anterior.preco_un_med
    if nova.embalagem and nova.embalagem == anterior.embalagem:
        return nova.preco_emb_med < anterior.preco_emb_med
    return None


def decidir(nova: ResultadoItem, anterior: ResultadoItem | None, alt: Alternativa, objetivo: Objetivo,
            original: str) -> tuple[ResultadoItem, bool]:
    """Escolhe o que gravar: a alternativa (com o motivo explicando a troca) ou o resultado anterior de volta.
    Devolve (resultado, trocou)."""
    rotulo = ROTULO[objetivo]
    if nova.status != "definido":
        # Não achou à venda com preço e fonte: mantém o anterior (se havia um) e conta por quê.
        aviso = f"A alternativa {rotulo} sugerida ({alt.produto}) não foi encontrada à venda com preço; mantive o produto anterior."
        if anterior is not None:
            return anterior.model_copy(update={"motivo": aviso}), False
        return nova, True
    if objetivo == "preco":
        barata = _mais_barata(nova, anterior)
        if barata is False:
            aviso = f"A alternativa sugerida ({alt.produto}) não saiu mais barata nas lojas; mantive o produto anterior."
            return anterior.model_copy(update={"motivo": aviso}), False
    partes = [f'Alternativa {rotulo} ao pedido "{original}".']
    if alt.por_que:
        partes.append(alt.por_que if alt.por_que.endswith(".") else alt.por_que + ".")
    if (anterior is not None and anterior.preco_un_med is not None and nova.preco_un_med is not None
            and anterior.unidade_preco == nova.unidade_preco and nova.unidade_preco):
        u = _unidade(nova.unidade_preco)
        partes.append(f"{_reais(nova.preco_un_med)}/{u} contra {_reais(anterior.preco_un_med)}/{u} do anterior.")
    return nova.model_copy(update={"motivo": " ".join(partes)}), True
