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
    ("material", ("cobre", "aluminio", "pvc", "cpvc", "ppr", "inox inoxidavel", "latao")),
    ("conexão", ("soldavel soldaveis", "roscavel roscaveis rosqueavel rosqueaveis", "solda",)),
    ("aplicação", ("externo externa externos externas exterior exteriores", "interno interna internos internas interior interiores")),
]
MEDIDA = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mm2|cm2|m2|mm|cm|ml|kg|kw|mpa|litros?|l|g|v|w|a|k|m)\b")
_EIXO = r"\d+(?:\.\d+)?\s*(?:mm|cm|m)?"
DIMENSAO = re.compile(rf"(?<![\w.]){_EIXO}\s*[x×]\s*{_EIXO}(?:\s*[x×]\s*{_EIXO})?(?![\w.])")
REFERENCIA = re.compile(r"\b(?:ref(?:erencia)?|codigo|sku|ean|modelo)\b\.?\s*[:#=-]?\s*([a-z0-9][a-z0-9./-]*)")
CONVERSOES = {"cm": (10, "mm"), "m": (1000, "mm"), "ml": (0.001, "l"), "g": (0.001, "kg"),
              "kw": (1000, "w"), "litro": (1, "l"), "litros": (1, "l"), "cm2": (100, "mm2"), "m2": (1000000, "mm2")}


def _medida(numero: str, unidade: str) -> str:
    fator, unidade = CONVERSOES.get(unidade, (1, unidade))
    valor = f"{float(numero) * fator:.12f}".rstrip("0").rstrip(".")
    return f"{valor}{unidade}"


def texto_para_similaridade(texto: str) -> str:
    """Usar após conferir atributos: unidades equivalentes não reduzem a similaridade textual."""
    t = DIMENSAO.sub(" dimensao ", normalizar(texto))
    return MEDIDA.sub(lambda m: _medida(*m.groups()), t)


def acessorio_incompativel(pedido: str, titulo: str) -> bool:
    acessorio = re.match(r"\s*(?:kit\s+)?(assento|tampa|suporte|refil)\b.*\bpara\b", normalizar(titulo))
    return bool(acessorio and not re.search(rf"\b{acessorio[1]}\b", normalizar(pedido)))


def _dimensoes(texto: str) -> list[tuple[str, str]]:
    """Canônica em mm + números originais. Sem unidade explícita, não inferir escala."""
    saida = []
    for d in DIMENSAO.findall(texto):
        pares = re.findall(r"(\d+(?:\.\d+)?)\s*(mm|cm|m)?", d)
        comum = next((u for _, u in pares if u), "")
        bruta = "x".join(f"{float(n):g}" for n, _ in pares)
        canonica = bruta
        if comum:
            fatores = {"mm": 1, "cm": 10, "m": 1000}
            canonica = "x".join(f"{float(n) * fatores[u or comum]:g}" for n, u in pares) + "mm"
        saida.append((canonica, bruta))
    return saida


def _presente(valor: str, texto: str) -> bool:
    return bool(re.search(rf"(?<![\w/-]){re.escape(valor)}(?!\w|[./-]\w)", texto))


def atributos(texto: str) -> dict[str, set[str]]:
    t = normalizar(texto)
    saida: dict[str, set[str]] = {}
    for nome, grupos in GRUPOS:
        saida[nome] = {g.split()[0] for g in grupos if any(re.search(rf"\b{re.escape(a)}\b", t) for a in g.split())}
    saida["marca/linha"] = set(marcas_encontradas(t))
    saida["tonalidade"] = set(re.findall(r"\b(?:branco neve|branco gelo|cinza urbano|cinza tecnologico|vermelho cardinal)\b", t))
    # Unidades normalizadas: nunca comparar somente o número (20 A != 20 W).
    saida["medida"] = set()
    # Não interpretar o último eixo de 60x120cm como uma medida independente.
    for numero, unidade in MEDIDA.findall(DIMENSAO.sub(" ", t)):
        saida["medida"].add(_medida(numero, unidade))
    saida["dimensão"] = {d for d, _ in _dimensoes(t)}
    saida["referência"] = {v.rstrip("./-") for v in REFERENCIA.findall(t)}
    saida["classe"] = {"ac" + {"1": "i", "2": "ii", "3": "iii"}.get(v, v)
                        for v in re.findall(r"\bac\s*-?\s*(iii|ii|i|[123])\b", t)}
    saida["marca explícita"] = {m[0] or m[1] for m in re.findall(r'\bmarca\s*[:=]?\s*(?:"([^"]+)"|([a-z0-9][a-z0-9-]*))', t)}
    return saida


def nao_confirmados(pedido: str, evidencia: str, *, titulo: str | None = None) -> list[str]:
    a, b = atributos(pedido), atributos(evidencia)
    t = normalizar(evidencia)
    # O anúncio não precisa repetir o rótulo "referência"/"marca"; precisa conter o valor inteiro.
    for campo in ("referência", "marca explícita"):
        b[campo] |= {v for v in a[campo] if _presente(v, t)}
    b["dimensão"] |= {bruta for _, bruta in _dimensoes(t) if bruta in a["dimensão"]}
    faltam = {f"{campo}: {valor}" for campo, valores in a.items() for valor in valores - b[campo]}
    faltam.update(conflitos_explicitos(pedido, titulo or evidencia))
    return sorted(faltam)


def conflitos_explicitos(pedido: str, titulo: str) -> list[str]:
    """Só contradições do título. Uma característica ausente não exclui a oferta."""
    a, b = atributos(pedido), atributos(titulo)
    conflitos = []
    if acessorio_incompativel(pedido, titulo):
        conflitos.append("tipo: acessório para o produto pedido")
    b["dimensão"] |= {d for _, d in _dimensoes(normalizar(titulo)) if d in a["dimensão"]}
    for campo in ("tonalidade", "material", "conexão", "aplicação", "dimensão", "marca/linha", "marca explícita"):
        if a[campo] and b[campo] and a[campo].isdisjoint(b[campo]):
            conflitos.append(f"{campo}: título incompatível com o pedido")
    for campo in ("cor", "classe", "referência"):
        if a[campo] and b[campo] - a[campo]:
            conflitos.append(f"{campo}: título informa outra variante")
    # Grandezas diferentes não conflitam: 220 V e 7500 W podem coexistir.
    for medida in a["medida"] - b["medida"]:
        unidade = re.sub(r"^[\d.]+", "", medida)
        if any(re.sub(r"^[\d.]+", "", v) == unidade for v in b["medida"]):
            conflitos.append(f"medida: título incompatível ({medida})")
    exclusivos = {"fosco", "acetinado", "polido", "semibrilho"}
    if a["acabamento"] & exclusivos and (b["acabamento"] & exclusivos) - a["acabamento"]:
        conflitos.append("acabamento: título incompatível com o pedido")
    return conflitos


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
