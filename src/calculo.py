"""Etapa ⑤ da pesquisa: transforma as ofertas conferidas em preço, confiança e lista de compra.

Python puro, sem IA (conta não se pede para LLM). Passos:
1. cada oferta vira preço por UNIDADE BASE (R$/m², R$/L, R$/kg, R$/un, R$/m) — assim "R$ 97,90/m²" e
   "R$ 122,22 a caixa de 1,8 m²" ficam comparáveis;
2. tira outliers (fora de 40%–250% da mediana) e calcula mín / mediana / máx;
3. escolhe a embalagem de referência e converte a faixa para "R$ por embalagem";
4. calcula a confiança e quantas embalagens comprar (src/compra.py).
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field

from .compra import Conteudo, conteudo_embalagem, necessidade_na_unidade, normalizar_unidade, qtd_embalagens
from .modelos import Fonte, ItemEntrada
from .precos import Oferta, ResultadoExtracao

OUTLIER_MIN, OUTLIER_MAX = 0.4, 2.5
MIN_EMBALAGEM_OBRA = {"l": 0.9, "kg": 0.9}   # genérico: descarta 60 ml / 250 ml (artesanato, amostra)


@dataclass
class Calculo:
    tem_preco: bool
    estimativa: bool = False
    embalagem: str | None = None
    conteudo: Conteudo | None = None
    qtd_embalagens: int | None = None
    perda: float = 0.0
    premissa: str | None = None
    preco_emb_min: float | None = None
    preco_emb_med: float | None = None
    preco_emb_max: float | None = None
    preco_un_min: float | None = None
    preco_un_med: float | None = None
    preco_un_max: float | None = None
    unidade_preco: str | None = None
    confianca: str | None = None
    fontes: list[Fonte] = field(default_factory=list)
    descartadas: dict[str, int] = field(default_factory=dict)   # motivo -> quantas
    motivo: str | None = None


@dataclass
class _Normalizada:
    oferta: Oferta
    conteudo: Conteudo
    unitario: float


def _confianca(lojas: int, dispersao: float) -> str:
    if lojas >= 3 and dispersao <= 0.25:
        return "alta"
    if lojas >= 2 and dispersao <= 0.50:
        return "media"
    return "baixa"


def _referencia(validas: list[_Normalizada], item: ItemEntrada) -> Conteudo:
    """Embalagem de referência: a citada no próprio item (ex.: '...18L'), senão a mais comum entre as
    ofertas — preferindo embalagem de verdade (caixa 1,8 m²) a preço avulso (1 m²)."""
    do_item = conteudo_embalagem(item.descricao)
    unidade = validas[0].conteudo.unidade
    if do_item and do_item.unidade == unidade:
        return do_item
    conteudos = [v.conteudo for v in validas]
    reais = [c for c in conteudos if c.quantidade != 1.0] or conteudos
    contagem = Counter(reais)
    # Com a quantidade do item: a embalagem com MENOR custo total para a necessidade, pelos preços vistos.
    # Avaliação real: tinta genérica para 12 m² (~1,6 L) saía como 1 latão de 18 L.
    custos = {}
    for c in contagem:
        n = qtd_embalagens(item.descricao, item.quantidade, item.unidade, c)[0]
        if n:
            custos[c] = n * statistics.median(v.oferta.preco for v in validas if v.conteudo == c)
    if custos:
        return min(custos, key=lambda c: (custos[c], -contagem[c]))
    return max(contagem, key=lambda c: (contagem[c], c.quantidade))


# Trava da embalagem (P1 da passagem): a embalagem vem do LLM e pode errar. Avaliação real (etapa 8): o preço
# POR m² da Ferreira Costa (R$ 88,90) veio rotulado "caixa 1,8 m²" → R$ 49,39/m², virou o mínimo da faixa.
SUSPEITO_ABAIXO = 0.65          # R$/unidade abaixo de 65% da mediana das OUTRAS lojas: desconfia da embalagem
RELEITURA_ACEITA = (0.85, 1.18)  # lido como preço avulso, precisa cair perto das outras lojas
MIN_OUTRAS_LOJAS = 2


def _corrigir_embalagens(mesma: list[_Normalizada]) -> tuple[list[_Normalizada], int]:
    """Oferta de embalagem (ex.: caixa 1,8 m²) com R$/unidade muito abaixo das outras lojas e que, lida como
    preço AVULSO (R$/m²), encaixa nas outras: o LLM rotulou o preço por m² como preço da caixa.

    Só nessa direção (a do erro observado). A contrária ("preço da caixa rotulado como m²") é numericamente
    indistinguível de ser a OUTRA loja a errada com 3 lojas (testado), então fica para o filtro de outlier.
    Decide com os valores originais de todas as lojas. Python puro, sem nova chamada ao LLM."""
    saida, corrigidas = [], 0
    for n in mesma:
        outras = [o for o in mesma if o.oferta.loja != n.oferta.loja]
        if n.conteudo.quantidade == 1.0 or len({o.oferta.loja for o in outras}) < MIN_OUTRAS_LOJAS:
            saida.append(n)
            continue
        ref = statistics.median(o.unitario for o in outras)
        avulso = n.oferta.preco / ref
        if n.unitario / ref < SUSPEITO_ABAIXO and RELEITURA_ACEITA[0] <= avulso <= RELEITURA_ACEITA[1]:
            c = Conteudo(1.0, n.conteudo.unidade)
            oferta = n.oferta.model_copy(update={"embalagem": c.unidade.replace("m2", "m²").replace("m3", "m³")})
            saida.append(_Normalizada(oferta, c, n.oferta.preco))
            corrigidas += 1
        else:
            saida.append(n)
    return saida, corrigidas


def calcular(item: ItemEntrada, extracao: ResultadoExtracao, generico: bool | None = None) -> Calculo:
    generico = item.classificacao == "pendente_especificacao" if generico is None else generico
    descartadas: Counter = Counter()

    # 1. candidatas: produto exato; para genérico (estimativa), aceita também "parecido"
    aceitas = ("sim", "parecido") if generico else ("sim",)
    candidatas = [o for o in extracao.ofertas if o.preco and o.mesmo_produto in aceitas]
    normalizadas: list[_Normalizada] = []
    for o in candidatas:
        c = conteudo_embalagem(o.embalagem)
        if c is None:
            descartadas["embalagem desconhecida"] += 1
            continue
        if generico and c.quantidade < MIN_EMBALAGEM_OBRA.get(c.unidade, 0):
            descartadas["embalagem pequena (não é de obra)"] += 1
            continue
        normalizadas.append(_Normalizada(o, c, o.preco / c.quantidade))
    if not normalizadas:
        return Calculo(tem_preco=False, estimativa=generico, descartadas=dict(descartadas),
                       motivo="nenhuma oferta com preço e embalagem comparável")

    # 2. mesma unidade base: a mais frequente; no empate, a que o quantitativo do item consegue usar
    #    (igual à do item > convertível por rendimento/consumo > outra). Depois, outliers pela mediana.
    contagem = Counter(n.conteudo.unidade for n in normalizadas)

    def utilidade(u: str) -> int:
        if normalizar_unidade(item.unidade) == u:
            return 2
        return 1 if necessidade_na_unidade(item.descricao, item.quantidade or 1, item.unidade, u) else 0

    unidade_base = max(contagem, key=lambda u: (contagem[u], utilidade(u)))
    for n in normalizadas:
        if n.conteudo.unidade != unidade_base:
            descartadas[f"unidade diferente ({n.conteudo.unidade})"] += 1
    mesma = [n for n in normalizadas if n.conteudo.unidade == unidade_base]
    mesma, corrigidas = _corrigir_embalagens(mesma)
    descartadas["embalagem corrigida (preço avulso × embalagem)"] += corrigidas
    mediana = statistics.median(n.unitario for n in mesma)
    validas = [n for n in mesma if OUTLIER_MIN * mediana <= n.unitario <= OUTLIER_MAX * mediana]
    descartadas["preço fora da faixa (outlier)"] += len(mesma) - len(validas)
    # uma oferta por loja (a mais barata entre as válidas): "3 lojas" significa 3 lojas de verdade,
    # e a fatia C (logística) recebe um preço por loja. Avaliação real: Leroy veio 2× na argamassa.
    por_loja: dict[str, _Normalizada] = {}
    for n in validas:
        if n.oferta.loja not in por_loja or n.unitario < por_loja[n.oferta.loja].unitario:
            por_loja[n.oferta.loja] = n
    descartadas["mesma loja (ficou a mais barata)"] += len(validas) - len(por_loja)
    validas = list(por_loja.values())
    descartadas = Counter({k: v for k, v in descartadas.items() if v})

    unitarios = sorted(n.unitario for n in validas)
    u_min, u_med, u_max = unitarios[0], statistics.median(unitarios), unitarios[-1]

    # 3. embalagem de referência e faixa em R$ por embalagem
    ref = _referencia(validas, item)
    rotulo = next((n.oferta.embalagem for n in validas if n.conteudo == ref and n.oferta.embalagem), None) \
        or f"{ref.quantidade:g} {ref.unidade}"

    def emb(v: float) -> float:
        return round(v * ref.quantidade, 2)

    fontes = [Fonte(loja=n.oferta.loja, dominio=n.oferta.dominio, url=n.oferta.url,
                    preco_embalagem=emb(n.unitario), embalagem=rotulo) for n in validas]

    # 4. R$ por unidade do quantitativo só quando a unidade da embalagem é a mesma do item (m² com m²)
    ui = normalizar_unidade(item.unidade)
    mesma_unidade = ui == unidade_base
    n_emb, perda, premissa = qtd_embalagens(item.descricao, item.quantidade, item.unidade, ref)

    lojas = len({n.oferta.loja for n in validas})
    confianca = _confianca(lojas, (u_max - u_min) / u_med if u_med else 1.0)
    if generico and confianca == "alta":
        confianca = "media"   # estimativa de item genérico nunca é "alta"

    return Calculo(
        tem_preco=True, estimativa=generico, embalagem=rotulo, conteudo=ref, qtd_embalagens=n_emb, perda=perda,
        premissa=premissa, preco_emb_min=emb(u_min), preco_emb_med=emb(u_med), preco_emb_max=emb(u_max),
        preco_un_min=round(u_min, 4) if mesma_unidade else None, preco_un_med=round(u_med, 4) if mesma_unidade else None,
        preco_un_max=round(u_max, 4) if mesma_unidade else None, unidade_preco=ui if mesma_unidade else None,
        confianca=confianca, fontes=fontes, descartadas=dict(descartadas))
