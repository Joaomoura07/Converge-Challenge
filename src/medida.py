"""Aviso de medida: a IA confere se a medida do pedido combina com a embalagem achada nas lojas.

Medido em 08/11 (Caixa d'água Fortlev 1000, 1 un): a pesquisa leu "1000 L" e seguiu em silêncio, sem dizer ao arquiteto
que ele escreveu "1000" sem unidade. Aqui os SINAIS saem de regras (sem IA); com sinal, o modelo rápido redige a frase
(ou diz que está tudo certo) e, sem modelo, a frase pronta de cada sinal vale. O aviso aparece no item como `motivo`.
"""

from __future__ import annotations

import json
import logging
import re

from langfuse import observe

from . import chaves_llm
from . import custo as _custo
from .compra import Conteudo, normalizar_unidade
from .config import get_settings, load_prompt
from .modelos import ItemEntrada

logger = logging.getLogger(__name__)

_NUMERO_SOLTO = re.compile(r"(?<![\w.,/-])(\d{2,6}(?:[.,]\d+)?)(?![\w.,/²³-]|\s*(?:mm|cm|ml|kg|g|m|l|lt|v|w|a|x|%|un)\b)", re.I)
_UNIDADE_DE_AREA_OU_LINHA = {"m2", "m", "m3"}


def _num(texto: str) -> float | None:
    try:
        return float(texto.replace(".", "").replace(",", ".")) if re.search(r",\d{1,2}$", texto) or texto.count(".") > 1 \
            else float(texto.replace(",", "."))
    except ValueError:
        return None


def sinais_de_medida(item: ItemEntrada, embalagem: str | None, conteudo: Conteudo | None,
                     medida_assumida: bool = False) -> list[str]:
    """Pontos que o arquiteto deve conferir. Lista vazia = nada estranho."""
    if conteudo is None:
        return []
    saida: list[str] = []
    rotulo = embalagem or f"{conteudo.quantidade:g} {conteudo.unidade}"
    if conteudo.unidade != "un":
        for achado in _NUMERO_SOLTO.findall(item.descricao or ""):
            n = _num(achado)
            if n is not None and abs(n - conteudo.quantidade) < 1e-6 and n >= 2:
                saida.append(f"O pedido diz «{achado}» sem unidade e a pesquisa entendeu {rotulo}.")
                break
    ui = normalizar_unidade(item.unidade)
    if ui in _UNIDADE_DE_AREA_OU_LINHA and conteudo.unidade == "un":
        saida.append(f"O pedido está em {item.unidade}, mas o produto é vendido em unidades ({rotulo}).")
    if medida_assumida and not saida:
        saida.append(f"Contei cada unidade como uma embalagem de {rotulo}; confira se é essa a medida.")
    return saida


def _frase_pronta(sinais: list[str]) -> str:
    return " ".join(sinais) + " Se a medida estiver errada, corrija a descrição ou a unidade e use Pesquisar de novo."


async def _perguntar(item: ItemEntrada, embalagem: str | None, sinais: list[str], cliente=None) -> tuple[bool, str | None]:
    """(respondeu, aviso). respondeu=False quando o modelo não pôde responder (vale a frase pronta)."""
    from .precos import _cliente   # import tardio: precos importa este pacote de configuração
    s = get_settings()
    texto = (f"Pedido: {item.descricao} | quantidade {item.quantidade} {item.unidade}\n"
             f"Embalagem achada: {embalagem}\nPontos estranhados:\n- " + "\n- ".join(sinais))
    sufixo = " /no_think" if "qwen3" in s.pesquisa_modelo_extracao.lower() else ""
    mensagens = [{"role": "system", "content": load_prompt("analise_medida")}, {"role": "user", "content": texto + sufixo}]
    try:
        async with chaves_llm.pool_extracao().vaga() as chave:
            cli = cliente or _cliente(chave)
            try:
                r = await cli.chat.completions.create(model=s.pesquisa_modelo_extracao, messages=mensagens,
                                                     temperature=0, top_p=s.llm_top_p, max_tokens=300)
            finally:
                if cliente is None:
                    await cli.close()
        _custo.registrar(getattr(getattr(r, "usage", None), "cost", 0))
        bruto = re.sub(r"<think>.*?</think>", "", r.choices[0].message.content or "", flags=re.S)
        achou = re.search(r"\{.*\}", bruto, flags=re.S)
        aviso = json.loads(achou.group(0)).get("aviso") if achou else None
        return True, (str(aviso).strip()[:300] or None) if aviso else None
    except Exception as exc:  # noqa: BLE001 — sem modelo, vale a frase pronta
        logger.warning("Conferência de medida sem o modelo (%s): usando a frase pronta", type(exc).__name__)
        return False, None


@observe(name="medida.conferir")
async def aviso_de_medida(item: ItemEntrada, embalagem: str | None, conteudo: Conteudo | None,
                          medida_assumida: bool = False, cliente=None) -> str | None:
    """Frase para o arquiteto conferir a medida, ou None quando nada está estranho. Nunca levanta."""
    sinais = sinais_de_medida(item, embalagem, conteudo, medida_assumida)
    if not sinais:
        return None
    respondeu, aviso = await _perguntar(item, embalagem, sinais, cliente)
    if respondeu and aviso is None and not medida_assumida:
        return None           # o modelo olhou o conjunto e a medida está certa
    return aviso or _frase_pronta(sinais)
