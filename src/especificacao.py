"""Especificações e conferências conservadoras, sem chamadas ao LLM."""
from __future__ import annotations

import re
import unicodedata

from .revisao import marcas_encontradas


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower().replace("²", "2").replace("³", "3"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    return re.sub(r"\s+", " ", t).strip()


GRUPOS = [
    ("cor", ("branco branca", "preto preta", "cinza", "bege", "azul", "verde", "vermelho vermelha", "cromado cromada", "dourado dourada")),
    ("acabamento", ("fosco fosca", "acetinado acetinada", "polido polida", "semibrilho semi-brilho", "natural", "retificado retificada")),
]
MEDIDA = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mm2|cm2|m2|mm|cm|ml|kg|kw|mpa|litros?|l|g|v|w|a|k|m)\b")
DIMENSAO = re.compile(r"\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?(?:\s*[x×]\s*\d+(?:\.\d+)?)?")


def atributos(texto: str) -> dict[str, set[str]]:
    t = normalizar(texto)
    saida: dict[str, set[str]] = {}
    for nome, grupos in GRUPOS:
        saida[nome] = {g.split()[0] for g in grupos if any(re.search(rf"\b{re.escape(a)}\b", t) for a in g.split())}
    saida["marca/linha"] = set(marcas_encontradas(t))
    saida["tonalidade"] = set(re.findall(r"\b(?:branco neve|branco gelo|cinza urbano|cinza tecnologico|vermelho cardinal)\b", t))
    # Unidades normalizadas: nunca comparar somente o número (20 A != 20 W).
    conversoes = {"cm": (10, "mm"), "m": (1000, "mm"), "ml": (0.001, "l"), "g": (0.001, "kg"), "kw": (1000, "w"), "litro": (1, "l"), "litros": (1, "l")}
    saida["medida"] = set()
    for numero, unidade in MEDIDA.findall(t):
        fator, unidade = conversoes.get(unidade, (1, unidade))
        saida["medida"].add(f"{float(numero) * fator:g}{unidade}")
    saida["dimensão"] = {re.sub(r"\s+", "", x).replace("×", "x") for x in DIMENSAO.findall(t)}
    saida["referência"] = set(re.findall(r"\b(?:ref(?:erencia)?|codigo|sku|ean|modelo)\s*[:#-]?\s*([a-z0-9][a-z0-9./-]*\d[a-z0-9./-]*)", t))
    return saida


def nao_confirmados(pedido: str, evidencia: str) -> list[str]:
    a, b = atributos(pedido), atributos(evidencia)
    return [f"{campo}: {valor}" for campo, valores in a.items() for valor in sorted(valores - b[campo])]


def orientacao(descricao: str) -> str:
    t = normalizar(descricao)
    familias = [
        (r"tinta|esmalte|verniz|selador|textura", "marca, linha, código da cor, acabamento, uso interno/externo e volume da embalagem"),
        (r"porcelanato|piso|revestimento|azulejo|ceramic|pastilha", "marca, coleção/referência, cor, dimensão das peças, espessura, acabamento, borda e local de aplicação"),
        (r"cabo|fio|disjuntor|tomada|interruptor|luminaria|lampada|spot|led|chuveiro", "marca, modelo/referência, tensão, potência ou corrente, seção/medidas, cor e instalação; para iluminação, temperatura de cor"),
        (r"tubo|conexao|torneira|misturador|registro|valvula|ducha", "marca, modelo/código, material, diâmetro/bitola, acabamento e tipo de instalação"),
        (r"cuba|pia|vaso|bacia|louca|lavatorio|tanque", "marca, modelo/código, material, cor, medidas e instalação"),
        (r"argamassa|rejunte|cimento|impermeabil", "marca, linha, classe (ex.: AC-III), aplicação, cor e peso da embalagem"),
        (r"mdf|mdp|chapa|granito|marmore|porta|janela", "marca, linha, material, cor/padrão, largura, altura, espessura e acabamento"),
    ]
    campos = next((c for p, c in familias if re.search(p, t)), "marca e modelo ou código do fabricante, material, medidas, cor, acabamento e embalagem")
    return f"Informe o que souber: {campos}. Preserve os detalhes já informados. Sem confirmação, o preço continua sendo uma estimativa."
