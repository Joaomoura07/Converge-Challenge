"""Lista de compra: entende embalagens ("lata 18 L", "caixa 2,16 m²", "kit 2 latas 18 L"),
aplica perda por tipo de material e converte o quantitativo em número de embalagens.

PREMISSAS (aproximações de obra; a tela mostra "≈" quando usadas):
- Rendimento de tinta/esmalte/verniz/selador em m² por litro, já considerando 2 demãos.
- Consumo de argamassa, rejunte, massa, impermeabilizante e textura em kg por m².
Python puro, sem IA: o mesmo item dá sempre a mesma conta.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

UNIDADES = {"m²": "m2", "m2": "m2", "m³": "m3", "m3": "m3", "m": "m", "metro": "m", "metros": "m",
            "l": "l", "lt": "l", "litro": "l", "litros": "l", "ml": "l",
            "kg": "kg", "g": "kg", "un": "un", "und": "un", "unid": "un", "unidade": "un", "unidades": "un",
            "pc": "un", "pç": "un", "peça": "un", "peças": "un", "peca": "un", "pecas": "un", "par": "un",
            "cm": "cm", "mm": "mm"}
_FATOR = {"ml": 0.001, "g": 0.001}

_CONTEUDO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(m²|m2|m³|m3|ml|litros?|lt|l|kg|g|metros?|m|un|und|unid\w*|p[cç]s?|pe[cç]as?)(?![a-z0-9²³])",
                       re.I)
# "kit 2 latas", "pacote 100 un", "caixa com 12 unidades". A palavra da unidade é OBRIGATÓRIA e o número não
# pode ter decimal — senão "caixa 2,16 m²" virava "2 caixas de 16 m²" (bug pego na própria revisão do código).
_MULTIPLO = re.compile(r"\b(?:kit|pack|pacote|caixa|cx|jogo|conjunto)\s*(?:com\s*)?(\d+)(?![.,]\d)\s*(?:x\s*)?"
                       r"(latas?|unid\w*|un|und|p[cç]s?|pe[cç]as?|sacos?|rolos?|gal[oõ]es|gal[aã]o|barras?|baldes?)\b", re.I)

# (padrão no nome do produto, valor) — a PRIMEIRA que casar vale (ordem importa: "tinta para piso" é tinta)
RENDIMENTO_M2_POR_L = [("esmalte", 9.0), ("verniz", 10.0), ("selador", 11.0), ("fundo", 10.0), ("tinta", 8.0)]
CONSUMO_KG_POR_M2 = [("argamassa", 5.0), ("rejunte", 0.3), ("massa", 0.6), ("impermeabiliz", 3.0), ("textura", 2.0)]
PERDAS = [(r"tinta|massa|selador|esmalte|verniz|textura|fundo prepar", 0.05),
          (r"porcelanato|piso|revestimento|azulejo|pastilha|ceramic|laminado|vinilico|rodape", 0.10),
          (r"argamassa|rejunte", 0.05),
          (r"cabo|fio |eletroduto|tubo|cano|conduite", 0.10)]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def normalizar_unidade(u: str | None) -> str | None:
    if not u:
        return None
    return UNIDADES.get(u.strip().lower().rstrip("."), UNIDADES.get(_norm(u).strip().rstrip("."), None))


@dataclass(frozen=True)
class Conteudo:
    quantidade: float   # na unidade base
    unidade: str        # m2 | m3 | m | l | kg | un


def conteudo_embalagem(embalagem: str | None) -> Conteudo | None:
    """'lata 18 L' -> 18 l · 'caixa 2,16 m²' -> 2.16 m2 · 'kit 2 latas 18 L' -> 36 l · '60 ml' -> 0.06 l ·
    'm²' -> 1 m2 · 'unidade' -> 1 un. Devolve None se não der para entender."""
    if not embalagem:
        return None
    texto = embalagem.strip()
    mult = 1.0
    m = _MULTIPLO.search(texto)
    resto = texto
    if m:
        mult = float(m.group(1))
        resto = texto[m.end():]
    c = _CONTEUDO.search(resto) or (None if m else _CONTEUDO.search(texto))
    if c:
        valor = float(c.group(1).replace(",", "."))
        bruto = c.group(2).lower()
        chave = "ml" if bruto == "ml" else "g" if bruto == "g" else bruto
        unidade = normalizar_unidade(chave) or normalizar_unidade(bruto.rstrip("s"))
        if unidade in ("cm", "mm") or unidade is None:
            return None
        return Conteudo(round(mult * valor * _FATOR.get(chave, 1.0), 6), unidade)
    if m:                                   # "pacote 100" / "kit 6 peças" sem conteúdo por unidade
        return Conteudo(mult, "un")
    sozinho = normalizar_unidade(_norm(texto).replace("²", "2"))
    if sozinho in ("m2", "m", "l", "kg", "un", "m3"):
        return Conteudo(1.0, sozinho)
    if re.search(r"\b(unidade|peca|par)\b", _norm(texto)):
        return Conteudo(1.0, "un")
    return None


# Lista real do arquiteto quase nunca diz "tinta" ou "argamassa": diz a marca/linha ("Suvinil T. Seda branco neve",
# "Coral Decora", "Quartzolit AC-III", "Votomassa AC-II"). Medido no site em 07/11: 12 de 33 itens do escritório
# ficavam sem nº de embalagens ("não sei converter m2 em l") e fora do subtotal. O apelido acrescenta a palavra do
# material; as tabelas acima continuam decidindo pela ordem (ex.: "Selador Coral" segue sendo selador).
APELIDOS = [
    (r"\bac[- ]?(i{1,3}|[123])\b|argamassa", "argamassa"),
    (r"suvinil|\bcoral\b|sherwin|lukscolor|eucatex|renner|iquine|hidracor|toque de seda|t\. ?seda|decora|"
     r"fosco completo|acrilic|latex", "tinta"),
    (r"portinari|portobello|eliane|ceusa|biancogres|incepa|ceramica|ceramico", "porcelanato revestimento"),
]


def _com_apelidos(produto: str) -> str:
    p = _norm(produto)
    extras = [palavra for padrao, palavra in APELIDOS if re.search(padrao, p)]
    return " ".join([p, *extras])


def perda_para(produto: str) -> float:
    p = _com_apelidos(produto)
    return next((v for padrao, v in PERDAS if re.search(padrao, p)), 0.0)


def _tabela(tabela, produto):
    p = _com_apelidos(produto)
    return next(((nome, v) for nome, v in tabela if nome in p), None)


@dataclass(frozen=True)
class Necessidade:
    quantidade_base: float      # quanto é preciso na unidade da embalagem (ex.: 22.5 l)
    premissa: str | None        # texto da premissa usada, se houve conversão (mostrado com "≈")


def necessidade_na_unidade(produto: str, quantidade: float, unidade_item: str | None, unidade_base: str) -> Necessidade | None:
    """Converte o quantitativo (ex.: 180 m² de parede) para a unidade da embalagem (ex.: litros de tinta)."""
    ui = normalizar_unidade(unidade_item)
    if ui is None or quantidade is None:
        return None
    if ui == unidade_base:
        return Necessidade(quantidade, None)
    if ui == "m2" and unidade_base == "l" and (r := _tabela(RENDIMENTO_M2_POR_L, produto)):
        return Necessidade(quantidade / r[1], f"rendimento ≈ {r[1]:g} m²/L ({r[0]}, 2 demãos)")
    if ui == "m2" and unidade_base == "kg" and (c := _tabela(CONSUMO_KG_POR_M2, produto)):
        return Necessidade(quantidade * c[1], f"consumo ≈ {c[1]:g} kg/m² ({c[0]})")
    return None


def qtd_embalagens(produto: str, quantidade: float | None, unidade_item: str | None, conteudo: Conteudo | None):
    """Número de embalagens a comprar (arredonda para cima) com a perda do material.
    Devolve (n, perda, premissa) ou (None, perda, motivo) quando a conversão não é possível."""
    perda = perda_para(produto)
    if quantidade is None or conteudo is None or conteudo.quantidade <= 0:
        return None, perda, "sem quantidade ou embalagem conhecida"
    nec = necessidade_na_unidade(produto, quantidade, unidade_item, conteudo.unidade)
    if nec is None:
        return None, perda, f"não sei converter {unidade_item} em {conteudo.unidade}"
    n = math.ceil(nec.quantidade_base * (1 + perda) / conteudo.quantidade - 1e-9)
    return max(n, 1), perda, nec.premissa
