"""E2 — Itens esquecidos: sugere complementos que costumam faltar na lista de materiais.

Regras determinísticas (sem LLM): porcelanato -> argamassa + rejunte + nivelador,
pintura -> selador + massa + fita + lixa, vaso -> assento + engate + anel, drywall -> perfis...
Tudo é SUGESTÃO (o arquiteto clica "Aceitar"); quantidades são estimativas e vêm marcadas
com ``estimativa=True``. Função pura: não acessa rede nem banco.

Uso:
    sugerir_complementos([{"linha": 1, "categoria": "Revestimentos", "descricao": "Porcelanato 90x90",
                           "quantidade": 48, "unidade": "m2"}, ...])
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from .compra import com_apelidos


class Complemento(BaseModel):
    """Um item sugerido. Já no formato aceito por ``Item`` do contrato (descricao/quantidade/unidade)."""

    regra: str                      # id da regra que disparou (ex.: "porcelanato")
    descricao: str
    quantidade: float
    unidade: str                    # unidades do contrato: un, m, m2, kg, l...
    categoria: str
    motivo: str                     # frase para mostrar ao arquiteto
    origem_linhas: list[int]        # linhas do arquivo que motivaram a sugestão
    estimativa: bool = True


def _norm(texto: str | None) -> str:
    """minúsculas, sem acento, espaços colapsados."""
    if not texto:
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s).strip()


def _unidade(u: str | None) -> str:
    u = _norm(u).replace("²", "2").replace("³", "3").replace(".", "")
    return {"m2": "m2", "m 2": "m2", "metro quadrado": "m2", "l": "l", "lt": "l", "litro": "l",
            "litros": "l", "und": "un", "unid": "un", "un": "un", "pc": "un", "pç": "un"}.get(u, u)


def _qtd(item: dict[str, Any]) -> float:
    try:
        q = float(item.get("quantidade") or 0)
    except (TypeError, ValueError):
        return 0.0
    return q if q > 0 else 0.0


def _texto(item: dict[str, Any]) -> str:
    """categoria + descrição: serve só para ACIONAR uma regra (a categoria ajuda: 'Pintura')."""
    return _norm(f"{item.get('categoria') or ''} {item.get('descricao') or ''}")


def _desc(item: dict[str, Any]) -> str:
    """só a descrição: usada para exclusões e para saber o que JÁ está na lista.
    A categoria não pode entrar aqui ('Revestimentos e argamassas' não significa que há argamassa).
    Com os apelidos de src/compra.py: medido no site em 07/11, "Votomassa AC-II" (162 m²) não era reconhecida como
    argamassa, entrava na área de piso e a regra sugeria 98 sacos de argamassa para uma lista que já tinha."""
    return com_apelidos(_norm(item.get("descricao")))


def _ceil(x: float) -> int:
    return max(1, math.ceil(x - 1e-9))


# --- Regras --------------------------------------------------------------------------------------
# gatilho: palavras (já sem acento) que, no texto categoria+descricao, ativam a regra
# medida: "area" (soma m2) ou "un" (soma unidades)
# ja_tem: palavras que, se já existirem na lista, evitam sugerir aquele complemento
# gera: (descricao, categoria, unidade, funcao(medida)->qtd, 'ja_tem' keywords)


@dataclass(frozen=True)
class _Comp:
    descricao: str
    unidade: str
    qtd: Callable[[float], float]
    ja_tem: tuple[str, ...]
    categoria: str


@dataclass(frozen=True)
class _Regra:
    id: str
    gatilhos: tuple[str, ...]
    exclui: tuple[str, ...]          # se o texto contém isso, NÃO é gatilho (ex.: "rejunte" em revestimento)
    medida: str                       # "area" | "un"
    motivo: str                       # {m} é substituído pela medida somada
    complementos: tuple[_Comp, ...]


REGRAS: tuple[_Regra, ...] = (
    _Regra(
        id="porcelanato",
        gatilhos=("porcelanato", "ceramica", "revestimento", "piso", "azulejo", "pastilha"),
        exclui=("argamassa", "rejunte", "nivelador", "espacador", "tinta", "rodape", "soleira",
                "manta", "impermeabil", "cola"),
        medida="area",
        motivo="Para {m} de piso/revestimento costumam faltar argamassa, rejunte e niveladores.",
        complementos=(
            _Comp("Argamassa colante AC-III 20 kg (saco)", "un", lambda a: _ceil(a * 6 / 20),
                  ("argamassa", "ac-iii", "aciii"), "Revestimentos e argamassas"),
            _Comp("Rejunte 5 kg (saco)", "un", lambda a: _ceil(a * 0.5 / 5),
                  ("rejunte",), "Revestimentos e argamassas"),
            _Comp("Espaçador/nivelador de piso (pacote 100 un)", "un", lambda a: _ceil(a * 5 / 100),
                  ("nivelador", "espacador"), "Revestimentos e argamassas"),
        ),
    ),
    _Regra(
        id="pintura",
        gatilhos=("tinta", "pintura", "acrilica", "esmalte", "latex"),
        exclui=("selador", "massa", "fita", "lixa", "rolo", "pincel", "trincha", "primer"),
        medida="area",
        motivo="Para {m} de pintura costumam faltar selador, massa corrida, fita crepe e lixa.",
        complementos=(
            _Comp("Selador acrílico 18 L (lata)", "un", lambda a: _ceil(a / 100),
                  ("selador", "primer"), "Pintura"),
            _Comp("Massa corrida 25 kg (lata)", "un", lambda a: _ceil(a / 50),
                  ("massa corrida", "massa acrilica", "massa para parede"), "Pintura"),
            _Comp("Fita crepe 48 mm x 50 m (rolo)", "un", lambda a: _ceil(a / 15),
                  ("fita crepe", "fita 3m", "fita azul"), "Pintura"),
            _Comp("Lixa para massa grão 150 (folha)", "un", lambda a: _ceil(a / 2),
                  ("lixa",), "Pintura"),
        ),
    ),
    _Regra(
        id="vaso",
        gatilhos=("vaso sanitario", "bacia sanitaria", "bacia", "vaso"),
        # "vaso com caixa acoplada" é o próprio vaso; só a caixa vendida À PARTE ("caixa acoplada
        # para vaso...") é acessório e não conta.
        exclui=("assento", "tampa", "caixa acoplada para", "caixa acoplada p/", "caixa de descarga",
                "valvula", "engate", "anel", "parafuso", "sifao", "flexivel"),
        medida="un",
        motivo="Para {m} vaso(s) sanitário(s) costumam faltar assento, engate flexível e anel de vedação.",
        complementos=(
            _Comp("Assento sanitário", "un", lambda n: _ceil(n), ("assento", "tampa"), "Louças e metais"),
            _Comp("Engate flexível 40 cm", "un", lambda n: _ceil(n), ("engate", "flexivel"),
                  "Louças e metais"),
            _Comp("Anel de vedação para vaso", "un", lambda n: _ceil(n), ("anel",), "Louças e metais"),
        ),
    ),
    _Regra(
        id="drywall",
        gatilhos=("drywall", "gesso acartonado", "placa de gesso", "dry wall"),
        exclui=("perfil", "montante", "guia", "massa", "fita", "parafuso", "lixa"),
        medida="area",
        motivo="Para {m} de drywall costumam faltar perfis, massa, fita telada e parafusos.",
        complementos=(
            _Comp("Perfil montante/guia 3 m (barra)", "un", lambda a: _ceil(a * 0.8),
                  ("perfil", "montante", "guia"), "Drywall"),
            _Comp("Massa para drywall 5 kg", "un", lambda a: _ceil(a * 0.4 / 5),
                  ("massa para drywall", "massa para junta", "massa drywall"), "Drywall"),
            _Comp("Fita telada para junta (rolo 90 m)", "un", lambda a: _ceil(a * 1.2 / 90),
                  ("fita telada", "fita para junta", "fita drywall"), "Drywall"),
            _Comp("Parafuso GN25 (caixa 1000 un)", "un", lambda a: _ceil(a * 15 / 1000),
                  ("parafuso",), "Drywall"),
        ),
    ),
    _Regra(
        id="cuba",
        gatilhos=("cuba", "lavatorio", "pia ", "tanque"),
        exclui=("sifao", "valvula", "flexivel", "engate", "torneira", "misturador", "monocomando"),
        medida="un",
        motivo="Para {m} cuba(s)/lavatório(s) costumam faltar sifão, válvula e engate flexível.",
        complementos=(
            _Comp("Sifão flexível universal", "un", lambda n: _ceil(n), ("sifao",), "Louças e metais"),
            _Comp("Válvula de escoamento 1\"", "un", lambda n: _ceil(n), ("valvula",), "Louças e metais"),
            _Comp("Engate flexível 40 cm", "un", lambda n: _ceil(n * 2), ("engate", "flexivel"),
                  "Louças e metais"),
        ),
    ),
)


def _area_m2(item: dict[str, Any]) -> float:
    """Área em m² de um item de pintura/revestimento. Tinta em litros vira área (≈5 m²/L, 2 demãos)."""
    q, u = _qtd(item), _unidade(item.get("unidade"))
    if u == "m2":
        return q
    if u == "l":
        return q * 5
    return 0.0


def sugerir_complementos(itens: list[dict[str, Any]]) -> list[Complemento]:
    """Devolve complementos que provavelmente faltam em ``itens``.

    ``itens``: dicts com linha, categoria, descricao, quantidade, unidade (contrato ``Item``).
    Não repete o que já está na lista e soma a medida de todos os itens que acionam a mesma regra.
    """
    textos = [_texto(it) for it in itens]
    descricoes = [_desc(it) for it in itens]
    todo_o_texto = " ".join(descricoes)
    saida: list[Complemento] = []

    for regra in REGRAS:
        total, linhas = 0.0, []
        for idx, (it, txt, desc) in enumerate(zip(itens, textos, descricoes)):
            if not any(g in txt for g in regra.gatilhos):
                continue
            if any(e in desc for e in regra.exclui):
                continue
            medida = _area_m2(it) if regra.medida == "area" else (
                _qtd(it) if _unidade(it.get("unidade")) in ("un", "") else 0.0)
            if medida <= 0:
                continue
            total += medida
            linhas.append(int(it.get("linha") or idx + 1))
        if total <= 0:
            continue

        rotulo = f"{total:g} m²" if regra.medida == "area" else f"{total:g}"
        for c in regra.complementos:
            if any(k in todo_o_texto for k in c.ja_tem):
                continue
            saida.append(Complemento(
                regra=regra.id, descricao=c.descricao, quantidade=float(c.qtd(total)),
                unidade=c.unidade, categoria=c.categoria,
                motivo=regra.motivo.format(m=rotulo), origem_linhas=linhas,
            ))
    return saida
