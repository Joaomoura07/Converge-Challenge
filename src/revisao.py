"""Fatia A, etapa 05: classificação única do item e revisor E1.

`classificar_item()` é a função única de classificação inicial (a B confirma na pesquisa, a C só lê).
`revisar_itens()` aplica regras Python sobre a lista de revisão e devolve erros E1 com fatos calculados.
O revisor apenas PROPÕE: nada é aplicado sem o clique do arquiteto, e a lista original nunca é alterada.
O LLM (`redigir_sugestoes`) só reescreve o texto a partir dos fatos; nunca escolhe nem inventa a correção.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

from langfuse import get_client, observe
from pydantic import BaseModel, ConfigDict, Field

from .config import PROMPTS_DIR, get_settings

logger = logging.getLogger(__name__)

Classificacao = Literal["definido", "pendente"]
Regra = Literal["unidade", "quantidade", "duplicado", "colunas_trocadas"]

# --------------------------------------------------------------------------- normalização


def _norm(texto: Any) -> str:
    """Minúsculas, sem acento, `m²`→`m2`, milhar `9.000`→`9000`, só letras/dígitos separados por espaço."""
    t = unicodedata.normalize("NFD", str(texto or "")).lower().replace("²", "2").replace("³", "3")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


UNIDADES_OFICIAIS = ("m", "m2", "m3", "un", "kg", "l", "cm", "mm")

# Mesmos apelidos de frontend/src/lib/importar/csv.ts (ALIAS_UNIDADE).
_ALIAS_UNIDADE = {
    "m": "m", "metro": "m", "metros": "m", "ml": "m", "m lin": "m", "mt": "m", "mts": "m",
    "m2": "m2", "m 2": "m2", "m^2": "m2", "metro2": "m2",
    "m3": "m3", "m 3": "m3", "m^3": "m3",
    "un": "un", "und": "un", "unid": "un", "unidade": "un", "unidades": "un", "pc": "un", "pcs": "un",
    "pç": "un", "pçs": "un", "peca": "un", "pecas": "un", "peça": "un", "peças": "un", "cj": "un",
    "jogo": "un", "par": "un", "pt": "un",
    "kg": "kg", "quilo": "kg", "quilos": "kg", "kgs": "kg",
    "l": "l", "lt": "l", "lts": "l", "litro": "l", "litros": "l",
    "cm": "cm", "mm": "mm",
}
# Unidades de venda fora da lista oficial. PROPOSTA: viram `un` (a B converte a embalagem na pesquisa).
_UNIDADES_VENDA = {
    "sc": "saco", "saco": "saco", "br": "barra", "barra": "barra", "cx": "caixa", "caixa": "caixa",
    "lata": "lata", "gl": "galão", "rl": "rolo", "rolo": "rolo", "pct": "pacote",
}


def normalizar_unidade(bruto: Any) -> str | None:
    """Unidade oficial equivalente ao texto (`mts`→`m`, `m²`→`m2`) ou None se não reconhecida."""
    t = str(bruto or "").strip().lower().replace("²", "2").replace("³", "3").rstrip(".")
    if not t:
        return None
    return _ALIAS_UNIDADE.get(t) or _ALIAS_UNIDADE.get(re.sub(r"\s+", "", t))


def _parse_quantidade(valor: Any) -> float | None:
    """Número BR ou EN → float; None se vazio ou não numérico. `3.000` é milhar (a tela já recusa `1.234`)."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _formatar_quantidade(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(round(n, 4)).replace(".", ",")


def _parece_numero(s: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:[.,]\d+)?", s.strip()))


# --------------------------------------------------------------------------- classificação

# Marcas e linhas/modelos reconhecíveis (normalizados). Definido = ao menos uma presente.
# PROPOSTA: lista inicial montada a partir do acervo sintético; cresce com o uso.
_MARCAS = frozenset(
    _norm(m)
    for m in (
        "suvinil|coral|metalatex|decor colors|rende muito|decora|toque de seda|sparlack|tarkett|durafloor|eliane|"
        "portobello|portinari|ceusa|biancogres|atlas|quartzolit|votomassa|votoran|qualical|gerdau|belgo|sikatop|"
        "sika|supermix|brasilit|placo|placomix|knauf|isover|armstrong|deca|docol|celite|roca|lorenzetti|tigre|"
        "amanco|fortlev|steck|schneider|easy9|pial|legrand|liz|orion|philips|ledvance|taschibra|stella|avant|"
        "samsung|lg|pormade|sincol|pado|papaiz|yale|sasazaki|blum|hafele|rehau|guararapes|tramontina|rinnai|"
        "sodramar|viapol|3m|norton|cortag|astra|windfree|azalea|vogue|acqua duo|hydra|debba|morgana|silestone|"
        "tandembox|clip top|bidim|santa luzia|sao gabriel|"
        # 08/11 (Fatia B): marcas usadas nos exemplos do site, que passaram a ser específicos
        "sil|prysmian|afumex|intelbras|duratex|cebrace|blindex|ciser|tigreflex"
    ).split("|")
)
_COR_COM_CORAL = re.compile(r"\b(?:cor|tom|rosa|salmao|laranja|vermelho) coral\b")


def marcas_encontradas(descricao: Any) -> list[str]:
    """Marcas/modelos reconhecidos na descrição (para auditoria e para a B confirmar)."""
    pad = f" {_COR_COM_CORAL.sub(' ', _norm(descricao))} "
    return sorted(m for m in _MARCAS if f" {m} " in pad)


def classificar_item(descricao: str | None) -> Classificacao:
    """Função única de classificação da A. `definido` tem marca e/ou modelo reconhecível; o resto é `pendente`."""
    return "definido" if marcas_encontradas(descricao) else "pendente"


# --------------------------------------------------------------------------- famílias de produto


@dataclass(frozen=True)
class Familia:
    chave: str
    nome: str
    padrao: re.Pattern[str]
    unidades: frozenset[str]
    unidade_padrao: str
    faixas: dict[str, tuple[float, float]] = field(default_factory=dict)  # unidade -> (mín, máx) plausíveis


def _f(chave: str, nome: str, regex: str, unidades: str, faixas: dict[str, tuple[float, float]] | None = None) -> Familia:
    lista = unidades.split()
    return Familia(chave, nome, re.compile(regex), frozenset(lista), lista[0], faixas or {})


# Ordem importa: o primeiro padrão que casa vence (específicos antes de genéricos).
# Faixas e unidades esperadas são REFERÊNCIAS PROPOSTAS (dados sintéticos), não norma técnica.
FAMILIAS: tuple[Familia, ...] = (
    _f("rejunte", "rejunte", r"\brejunte", "m2 kg un"),
    _f("nivelador", "nivelador/espaçador", r"\b(nivelador|espacador)\b", "un kg"),
    _f("argamassa", "argamassa", r"argamassa|votomassa|quartzolit ac|\bac (i|ii|iii)\b", "m2 kg un"),
    _f("massa_drywall", "massa de drywall", r"placomix|massa (para )?juntas|massa .*drywall", "m2 kg un"),
    _f("fita_drywall", "fita de drywall", r"fita de papel", "m un"),
    _f("massa_pintura", "massa/selador", r"massa (corrida|acrilica)|selador|fundo preparador|textura", "m2 l kg un"),
    _f("tinta", "tinta", r"\btintas?\b|esmalte|metalatex|suvinil|decor colors|rende muito|\bdecora\b|toque de seda|"
       r"\bt seda\b|coral", "m2 l un"),
    _f("la_de_vidro", "lã de vidro", r"la de vidro|isover", "m2 un"),
    _f("placa_drywall", "placa de drywall", r"\bplaca (st|ru|rv)\b|\bplaco\b", "m2 un"),
    _f("perfil_drywall", "perfil de drywall", r"\bmontante\b|\bguia 48\b", "m un", {"m": (1, 20000)}),
    _f("forro", "forro", r"\bforro", "m2 un"),
    _f("parafuso", "parafuso", r"parafuso", "un kg", {"un": (1, 200000)}),
    _f("painel_led", "painel de LED", r"painel (avant|led)|luminaria painel|\bavant\b", "un", {"un": (1, 2000)}),
    _f("iluminacao", "iluminação", r"\bspot\b|stella|arandela|lampada|philips", "un", {"un": (1, 2000)}),
    _f("fita_led", "fita de LED", r"fita led|ledvance", "m un", {"m": (1, 2000)}),
    _f("fonte", "fonte", r"\bfonte\b", "un"),
    _f("disjuntor", "disjuntor", r"disjuntor|easy9|\bdr steck", "un", {"un": (1, 200)}),
    _f("quadro_eletrico", "quadro elétrico", r"quadro steck|quadro de (distribuicao|luz)", "un", {"un": (1, 30)}),
    _f("tomada", "tomada/interruptor", r"tomada|interruptor|\bliz\b|\bpial\b|\borion\b|\busb\b", "un", {"un": (1, 3000)}),
    _f("cabo", "cabo elétrico", r"\bcabo\b|afumex|\bsil\b|\bfio\b", "m un", {"m": (1, 50000)}),
    _f("eletroduto", "eletroduto", r"tigreflex|eletroduto", "m un", {"m": (1, 20000)}),
    _f("caixinha", "caixa de embutir", r"caixinha", "un", {"un": (1, 3000)}),
    _f("porta", "porta", r"\bporta\b|pormade|sincol", "un", {"un": (1, 300)}),
    _f("fechadura", "fechadura", r"fechadura|\byale\b", "un", {"un": (1, 300)}),
    _f("janela", "janela", r"janela|maxim ar|sasazaki", "un", {"un": (1, 300)}),
    _f("vidro", "vidro/espelho/box", r"\bvidro\b|\bespelho\b|\bbox\b", "m2 un"),
    _f("vaso", "vaso sanitário", r"\bvaso\b|celite azalea|deca vogue|roca debba|\bassento\b", "un", {"un": (1, 200)}),
    _f("louca_metal", "louças e metais", r"\bcuba\b|lavatorio|barra pne|\bpne\b|\bralo\b|caixa sifonada|registro|"
       r"torneira|ducha|monocomando|chuveiro|acqua duo|hydra|docol", "un", {"un": (1, 500)}),
    _f("tubo", "tubo/conexão", r"\btubo\b|\bjoelho\b", "m un", {"m": (1, 20000)}),
    _f("ferro", "ferro/arame/tela", r"\bferro\b|vergalhao|\barame\b|tela q", "kg un m"),
    _f("cimento", "cimento/cal", r"cimento|\bcal\b|qualical|votoran", "un kg"),
    _f("agregado", "areia/brita", r"\bareia\b|\bbrita\b|pedrisco", "m3 kg", {"m3": (0.1, 2000)}),
    _f("concreto", "concreto", r"concreto|supermix", "m3", {"m3": (0.1, 2000)}),
    _f("tijolo", "tijolo/bloco", r"tijolo|bloco ceramico", "un", {"un": (1, 500000)}),
    _f("telha", "telha", r"\btelha", "m2 un"),
    _f("rodape", "rodapé/soleira", r"rodape|soleira", "m un"),
    _f("revestimento", "piso/revestimento", r"porcelanato|portobello|portinari|eliane|ceusa|biancogres|azulejo|"
       r"pastilha|revestimento|calacata|sao tome|cotto|\batlas\b|silestone|granito|travertino|marmore|\bpiso\b|"
       r"tarkett|durafloor|\bdeck\b|\bpedra\b", "m2 un", {"m2": (0.1, 20000)}),
    _f("split", "ar-condicionado", r"\bsplit\b|ar condicionado|windfree|btus", "un", {"un": (1, 200)}),
    _f("mdf", "MDF", r"\bmdf\b", "m2 un"),
    _f("fita_borda", "fita de borda", r"fita de borda", "m un"),
    _f("ferragem_movel", "ferragem de móvel", r"dobradica|corredica|puxador|blum|hafele", "un"),
    _f("mobiliario", "mobiliário", r"\bcama\b|\bsofa\b|\bmesa\b|\bbanqueta\b", "un"),
    _f("abrasivo", "fita/lixa", r"\bfita 3m\b|fita crepe|\blixa\b|norton", "un m"),
)


def familia_de(descricao: Any) -> Familia | None:
    pad = f" {_COR_COM_CORAL.sub(' ', _norm(descricao))} "
    for fam in FAMILIAS:
        if fam.padrao.search(pad.strip()):
            return fam
    return None


# --------------------------------------------------------------------------- contrato


class ItemRevisao(BaseModel):
    """Linha da lista de revisão (a mesma forma de `Linha` em frontend/src/lib/lista.ts)."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str | None = None
    descricao: str | None = ""
    quantidade: str | float | int | None = ""
    unidade: str | None = ""
    categoria: str | None = ""
    nivel: str | None = None
    linha_origem: int | None = Field(default=None, alias="linhaOrigem")
    linha: int | None = None


class Alteracao(BaseModel):
    item_id: str | None
    linha: int
    campo: Literal["quantidade", "unidade"]
    de: str
    para: str


class ItemRef(BaseModel):
    item_id: str | None
    linha: int


class Correcao(BaseModel):
    acao: Literal["alterar", "remover", "mesclar"]
    alteracoes: list[Alteracao] = Field(default_factory=list)
    remover: list[ItemRef] = Field(default_factory=list)


class ErroRevisao(BaseModel):
    id: str                      # determinístico: o mesmo problema mantém o ID ao revalidar
    regra: Regra
    linhas: list[int]            # linhas da lista (linha do arquivo quando existe, senão a posição 1-based)
    item_ids: list[str | None]
    campo: str
    valor_atual: Any
    correcao: Correcao | None    # None = erro sem proposta segura; o arquiteto decide
    motivo: str                  # texto fixo, montado só dos fatos
    fatos: dict[str, Any]
    texto: str                   # redação mostrada ao arquiteto (LLM ou texto fixo)
    redacao: Literal["fixa", "llm"] = "fixa"


# --------------------------------------------------------------------------- revisor


@dataclass
class _L:
    pos: int
    id: str | None
    linha: int
    desc: str
    norm: str
    qtd_txt: str
    qtd: float | None
    un_txt: str
    un: str | None
    cat: str
    nivel: str
    fam: Familia | None
    definido: bool


def _preparar(itens: list[ItemRevisao | dict]) -> list[_L]:
    out: list[_L] = []
    for i, bruto in enumerate(itens, start=1):
        it = bruto if isinstance(bruto, ItemRevisao) else ItemRevisao.model_validate(bruto)
        desc = (it.descricao or "").strip()
        qtd_txt = "" if it.quantidade is None else str(it.quantidade).strip()
        un_txt = (it.unidade or "").strip()
        out.append(_L(
            pos=i, id=it.id, linha=it.linha_origem or it.linha or i, desc=desc, norm=_norm(desc),
            qtd_txt=qtd_txt, qtd=_parse_quantidade(it.quantidade), un_txt=un_txt,
            un=normalizar_unidade(un_txt), cat=_norm(it.categoria), nivel=_norm(it.nivel),
            fam=familia_de(desc), definido=classificar_item(desc) == "definido",
        ))
    return out


def _id_erro(regra: str, campo: str, chaves: list[Any], extra: Any) -> str:
    base = json.dumps([regra, campo, sorted(map(str, chaves)), extra], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def _chave(l: _L) -> str:
    return l.id or f"linha:{l.linha}"


def _ref(l: _L) -> ItemRef:
    return ItemRef(item_id=l.id, linha=l.linha)


def _erro(regra: Regra, campo: str, ls: list[_L], valor_atual: Any, correcao: Correcao | None,
          motivo: str, fatos: dict[str, Any]) -> ErroRevisao:
    ident = [_chave(l) for l in ls]
    para = correcao.model_dump(mode="json") if correcao else None
    return ErroRevisao(
        id=_id_erro(regra, campo, ident, [valor_atual, para]),
        regra=regra, linhas=[l.linha for l in ls], item_ids=[l.id for l in ls], campo=campo,
        valor_atual=valor_atual, correcao=correcao, motivo=motivo, fatos=fatos,
        texto=_texto_fixo(motivo, correcao),
    )


def _alt(l: _L, campo: Literal["quantidade", "unidade"], de: str, para: str) -> Alteracao:
    return Alteracao(item_id=l.id, linha=l.linha, campo=campo, de=de, para=para)


def _alterar(*alts: Alteracao) -> Correcao:
    return Correcao(acao="alterar", alteracoes=list(alts))


# ---- colunas trocadas


def _regra_colunas_trocadas(ls: list[_L]) -> tuple[list[ErroRevisao], set[int]]:
    """Quantidade escrita na coluna Unidade (e a unidade na coluna Quantidade). Um erro agrupa todas as linhas."""
    afetadas: list[_L] = []
    alts: list[Alteracao] = []
    for l in ls:
        if not _parece_numero(l.un_txt) or _parece_numero(l.qtd_txt):
            continue
        if l.qtd_txt:
            nova_un = normalizar_unidade(l.qtd_txt) or ("un" if l.qtd_txt.lower() in _UNIDADES_VENDA else "")
        else:
            nova_un = l.fam.unidade_padrao if l.fam else ""
        # Se a "unidade" da coluna Quantidade não for reconhecida e não houver como inferir, limpa o campo.
        afetadas.append(l)
        alts.append(_alt(l, "quantidade", l.qtd_txt, l.un_txt))
        alts.append(_alt(l, "unidade", l.un_txt, nova_un))
    if not afetadas:
        return [], set()
    fatos = {
        "linhas": len(afetadas),
        "exemplo": {"linha": afetadas[0].linha, "quantidade": afetadas[0].qtd_txt, "unidade": afetadas[0].un_txt},
        "unidade_inferida_da_familia": [l.linha for l in afetadas if not l.qtd_txt and l.fam],
    }
    motivo = (f"Em {len(afetadas)} linha(s) a coluna Quantidade traz texto ou está vazia e a coluna Unidade traz um "
              "número; as duas colunas parecem trocadas.")
    valor = [{"linha": l.linha, "quantidade": l.qtd_txt, "unidade": l.un_txt} for l in afetadas]
    e = _erro("colunas_trocadas", "colunas", afetadas, valor, _alterar(*alts), motivo, fatos)
    return [e], {l.pos for l in afetadas}


# ---- unidade


def _regra_unidade(ls: list[_L], ignorar: set[int]) -> list[ErroRevisao]:
    erros: list[ErroRevisao] = []
    for l in ls:
        if l.pos in ignorar:
            continue
        fam = l.fam
        fatos: dict[str, Any] = {"unidade": l.un_txt, "familia": fam.nome if fam else None}
        novo: str | None = None
        motivo = ""
        if not l.un_txt:
            if not fam:
                continue  # sem unidade e sem pista do produto: a validação da tela já cobra
            novo = fam.unidade_padrao
            fatos.update(subtipo="ausente", inferida_da_familia=True)
            motivo = f"A unidade está em branco; para {fam.nome} costuma-se usar {novo}."
        elif l.un is None:
            venda = _UNIDADES_VENDA.get(l.un_txt.lower().rstrip("."))
            if venda:
                novo = "un"
                fatos.update(subtipo="fora_da_lista", significado=venda)
                motivo = (f"A unidade \"{l.un_txt}\" ({venda}) não está na lista oficial ({', '.join(UNIDADES_OFICIAIS)}). "
                          f"Proposta: contar {venda}s como un; a pesquisa converte a embalagem.")
            else:
                fatos.update(subtipo="desconhecida")
                motivo = f"A unidade \"{l.un_txt}\" não é reconhecida. Use: {', '.join(UNIDADES_OFICIAIS)}."
        else:
            canon = l.un
            aceita_na_tela = l.un_txt in (canon, "m²", "m³")
            if fam and fam.unidades and canon not in fam.unidades:
                novo = fam.unidade_padrao
                fatos.update(subtipo="incompativel", esperadas=sorted(fam.unidades), unidade_oficial=canon)
                motivo = (f"A unidade {l.un_txt} é incomum para {fam.nome} (esperado: "
                          f"{', '.join(sorted(fam.unidades))}). Proposta: {novo}.")
            elif not aceita_na_tela:
                novo = canon
                fatos.update(subtipo="grafia", unidade_oficial=canon)
                motivo = f"A unidade \"{l.un_txt}\" deve ser escrita como {canon}."
        if not motivo:
            continue
        corr = _alterar(_alt(l, "unidade", l.un_txt, novo)) if novo is not None and novo != l.un_txt else None
        erros.append(_erro("unidade", "unidade", [l], l.un_txt, corr, motivo, fatos))
    return erros


# ---- quantidade desproporcional


def _regra_quantidade(ls: list[_L], ignorar: set[int]) -> list[ErroRevisao]:
    erros: list[ErroRevisao] = []
    for l in ls:
        if l.pos in ignorar or l.qtd is None or l.qtd <= 0 or not l.fam or not l.un:
            continue
        faixa = l.fam.faixas.get(l.un)
        if not faixa:
            continue
        minimo, maximo = faixa
        if minimo <= l.qtd <= maximo:
            continue
        lado = "acima" if l.qtd > maximo else "abaixo"
        fatos = {"quantidade": l.qtd, "unidade": l.un, "familia": l.fam.nome, "faixa": [minimo, maximo], "lado": lado}
        corr = None
        # Única correção proposta: erro de milhar (valor múltiplo de 1000 que cai na faixa ao dividir por 1000).
        if lado == "acima" and l.qtd % 1000 == 0 and minimo <= l.qtd / 1000 <= maximo:
            novo = _formatar_quantidade(l.qtd / 1000)
            corr = _alterar(_alt(l, "quantidade", l.qtd_txt, novo))
            fatos["fator"] = 1000
        motivo = (f"{_formatar_quantidade(l.qtd)} {l.un} de {l.fam.nome} está {lado} do plausível "
                  f"({_formatar_quantidade(minimo)} a {_formatar_quantidade(maximo)} {l.un}).")
        erros.append(_erro("quantidade", "quantidade", [l], l.qtd_txt, corr, motivo, fatos))

    # Referência cruzada: argamassa e rejunte (m2) não devem passar muito da área de revestimento da lista.
    base = sum(l.qtd for l in ls if l.fam and l.fam.chave == "revestimento" and l.un == "m2" and l.qtd and l.qtd > 0)
    if base > 0:
        for l in ls:
            if (l.pos in ignorar or not l.fam or l.fam.chave not in ("rejunte", "argamassa")
                    or l.un != "m2" or not l.qtd or l.qtd <= base * 1.5):
                continue
            fatos = {"quantidade": l.qtd, "unidade": "m2", "area_revestimentos_m2": base, "limite_razao": 1.5}
            motivo = (f"{_formatar_quantidade(l.qtd)} m2 de {l.fam.nome} supera em mais de 50% a área de "
                      f"revestimentos da lista ({_formatar_quantidade(base)} m2).")
            erros.append(_erro("quantidade", "quantidade", [l], l.qtd_txt, None, motivo, fatos))
    return erros


# ---- duplicados


_CORES = frozenset("branc pret azul verd vermelh cinz grafit amarel palh beg marrom laranj ros dourad prat cromad inox".split())
_ACABAMENTOS = {"fosc": "fosco", "mat": "fosco", "acetinad": "acetinado", "seda": "acetinado",
                "brilhant": "brilhante", "gloss": "brilhante", "polid": "polido"}


def _radical(tok: str) -> str:
    return tok.rstrip("aoes")


def _especificacao(l: _L) -> tuple[set[str], set[str], set[str]]:
    toks = l.norm.split()
    cores = {_radical(t) for t in toks if _radical(t) in _CORES}
    acab = {_ACABAMENTOS[k] for t in toks for k in (t, _radical(t)) if k in _ACABAMENTOS}
    nums = set(re.findall(r"\d+", l.norm))
    return cores, acab, nums


def _conflito(a: _L, b: _L) -> str | None:
    """Diferença de especificação que impede tratar as linhas como o mesmo produto."""
    ca, aa, na = _especificacao(a)
    cb, ab, nb = _especificacao(b)
    if ca and cb and not (ca & cb):
        return "cor"
    if aa and ab and not (aa & ab):
        return "acabamento"
    if na and nb and not (na <= nb or nb <= na):
        return "medida"
    return None


def _regra_duplicados(ls: list[_L]) -> list[ErroRevisao]:
    erros: list[ErroRevisao] = []
    usados: set[int] = set()

    # (1) mesmo nome normalizado, mesma unidade, categoria e nível: mescla somando as quantidades.
    grupos: dict[tuple[str, str | None, str, str], list[_L]] = {}
    for l in ls:
        if l.norm:
            grupos.setdefault((l.norm, l.un or l.un_txt.lower(), l.cat, l.nivel), []).append(l)
    for membros in grupos.values():
        if len(membros) < 2:
            continue
        manter, resto = membros[0], membros[1:]
        usados.update(m.pos for m in membros)
        qs = [m.qtd for m in membros]
        soma = sum(qs) if all(q is not None for q in qs) else None  # type: ignore[arg-type]
        alts = []
        if soma is not None:
            alts.append(_alt(manter, "quantidade", manter.qtd_txt, _formatar_quantidade(soma)))
        corr = Correcao(acao="mesclar", alteracoes=alts, remover=[_ref(m) for m in resto])
        fatos = {"descricao": manter.desc, "unidade": manter.un or manter.un_txt, "quantidades": qs, "soma": soma}
        motivo = (f"\"{manter.desc}\" aparece {len(membros)} vezes com a mesma unidade. Proposta: manter a linha "
                  f"{manter.linha}" + (f" com a soma {_formatar_quantidade(soma)}" if soma is not None else "") + ".")
        erros.append(_erro("duplicado", "descricao", membros, [_dados_linha(m) for m in membros], corr, motivo, fatos))

    # (2) nomes distintos, mesma família, unidade e quantidade, sem conflito de especificação e com ao menos
    # uma linha genérica (pendente). Duas marcas diferentes, ambas definidas, não são tratadas como duplicata.
    cand: dict[int, dict[int, _L]] = {}  # pos da linha a remover -> {pos da mantida: linha}
    for i, a in enumerate(ls):
        for b in ls[i + 1:]:
            if a.pos in usados or b.pos in usados or not a.fam or a.fam is not b.fam:
                continue
            if a.norm == b.norm or a.qtd is None or b.qtd is None or a.qtd != b.qtd or a.qtd <= 0:
                continue
            if not a.un or a.un != b.un or (a.cat and b.cat and a.cat != b.cat) or (a.nivel != b.nivel):
                continue
            if a.definido and b.definido:
                continue
            if _conflito(a, b):
                continue
            remover, manter = (b, a) if not b.definido else (a, b)
            cand.setdefault(remover.pos, {})[manter.pos] = manter
    for pos, mantidas in sorted(cand.items()):
        l = next(x for x in ls if x.pos == pos)
        ordem = sorted(mantidas.values(), key=lambda x: x.pos)
        fatos = {"familia": l.fam.nome if l.fam else None, "unidade": l.un, "quantidade": l.qtd,
                 "genericos": [l.linha], "candidatos_a_manter": [m.linha for m in ordem]}
        if len(ordem) == 1:
            m = ordem[0]
            corr: Correcao | None = Correcao(acao="remover", remover=[_ref(l)])
            motivo = (f"\"{l.desc}\" (linha {l.linha}) parece o mesmo item de \"{m.desc}\" (linha {m.linha}): "
                      f"mesma família ({l.fam.nome if l.fam else ''}), unidade e quantidade. "
                      f"Proposta: manter a linha {m.linha} e remover a {l.linha}.")
        else:
            corr = None
            motivo = (f"\"{l.desc}\" (linha {l.linha}) pode repetir mais de uma linha "
                      f"({', '.join(str(m.linha) for m in ordem)}); escolha qual manter.")
        erros.append(_erro("duplicado", "descricao", [*ordem, l], [_dados_linha(x) for x in [*ordem, l]], corr, motivo, fatos))
    return erros


def _dados_linha(l: _L) -> dict[str, Any]:
    return {"linha": l.linha, "descricao": l.desc, "quantidade": l.qtd_txt, "unidade": l.un_txt}


def _texto_fixo(motivo: str, correcao: Correcao | None) -> str:
    if correcao is None:
        return f"{motivo} Sem proposta automática: confira e corrija manualmente."
    return motivo


def revisar_itens(itens: list[ItemRevisao | dict]) -> list[ErroRevisao]:
    """Erros E1 da lista. Função pura e determinística: não altera `itens`, não chama LLM nem rede."""
    ls = _preparar(itens)
    trocadas, pos_trocadas = _regra_colunas_trocadas(ls)
    erros = [*trocadas, *_regra_unidade(ls, pos_trocadas), *_regra_quantidade(ls, pos_trocadas), *_regra_duplicados(ls)]
    erros.sort(key=lambda e: (e.linhas[0] if e.linhas else 0, e.regra, e.id))
    return erros


# --------------------------------------------------------------------------- redação por LLM

# Teto de erros enviados ao LLM por chamada: uma lista grande de erros estouraria max_tokens (JSON cortado,
# chamada paga perdida) e o custo cresceria sem limite. O que passar do teto mantém o texto fixo.
MAX_ERROS_LLM = 30

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _numeros(texto: str) -> set[str]:
    return {format(float(n.replace(",", ".")), "g") for n in _NUM.findall(texto)}


def _extrair_json(conteudo: str) -> dict[str, Any]:
    ini, fim = conteudo.find("{"), conteudo.rfind("}")
    if ini < 0 or fim <= ini:
        raise ValueError("resposta sem JSON")
    obj = json.loads(conteudo[ini:fim + 1])
    if not isinstance(obj, dict):
        raise ValueError("JSON não é objeto")
    return obj


def _carregar_prompt() -> str:
    return (PROMPTS_DIR / "revisao_redacao.md").read_text(encoding="utf-8")


@observe(as_type="generation", name="llm.featherless", capture_input=False, capture_output=False)
def _chamar_llm(client: Any, model: str, mensagens: list[dict]) -> str:
    lf = get_client()
    resp = client.chat.completions.create(model=model, messages=mensagens, temperature=0.2, max_tokens=2500, timeout=25)
    usage = resp.usage
    custo = getattr(usage, "cost", None) if usage else None
    conteudo = (resp.choices[0].message.content or "") if resp.choices else ""
    try:
        lf.update_current_generation(
            model=model, model_parameters={"temperature": 0.2},
            usage_details={"input": usage.prompt_tokens, "output": usage.completion_tokens} if usage else None,
            cost_details={"total": float(custo)} if custo is not None else None,
        )
    except Exception:  # noqa: BLE001 - telemetria nunca derruba a revisão
        logger.warning("Falha ao registrar a generation no Langfuse")
    return conteudo


def redigir_sugestoes(erros: list[ErroRevisao], client: Any = None, model: str | None = None) -> list[ErroRevisao]:
    """Troca `texto` pela redação do LLM quando ela passa nas checagens; senão mantém o texto fixo.

    O LLM recebe só os fatos calculados e a correção JÁ decidida pelas regras. Recusamos texto que traga número
    ausente dos fatos, e qualquer falha (rede, JSON, modelo) cai no texto fixo. IDs, linhas e correção não mudam.
    """
    if not erros:
        return erros
    s = get_settings()
    if client is None:
        if not s.llm_configured:
            return erros
        from .agent import build_llm_client
        client = build_llm_client()
    modelo = model or s.featherless_model_fast or s.featherless_model
    enviados = erros[:MAX_ERROS_LLM]
    payload = {e.id: {"regra": e.regra, "campo": e.campo, "linhas": e.linhas, "fatos": e.fatos,
                      "motivo": e.motivo, "correcao": e.correcao.model_dump(mode="json") if e.correcao else None}
               for e in enviados}
    base = json.dumps(payload, ensure_ascii=False)
    try:
        resposta = _extrair_json(_chamar_llm(client, modelo, [
            {"role": "system", "content": _carregar_prompt()},
            {"role": "user", "content": base},
        ]))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redação do revisor falhou (%s); usando texto fixo", type(exc).__name__)
        _marcar_falha(type(exc).__name__)
        return erros
    permitidos = _numeros(base)
    saida: list[ErroRevisao] = []
    for e in erros:
        t = resposta.get(e.id) if e.id in payload else None
        ok = isinstance(t, str) and 0 < len(t.strip()) <= 320 and _numeros(t) <= permitidos
        saida.append(e.model_copy(update={"texto": t.strip(), "redacao": "llm"}) if ok else e)
    return saida


def _marcar_falha(motivo: str) -> None:
    try:
        get_client().update_current_span(level="WARNING", status_message=f"redação do revisor: {motivo}")
    except Exception:  # noqa: BLE001
        pass


def revisao_id(itens: list[ItemRevisao | dict]) -> str:
    """Identifica o conteúdo revisado: a mesma lista dá o mesmo ID (PROPOSTA, a fechar na etapa 06)."""
    base = json.dumps([i.model_dump(mode="json") if isinstance(i, ItemRevisao) else i for i in itens],
                      ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(base.encode()).hexdigest()[:16]


@observe(as_type="chain", name="revisao.e1", capture_input=False, capture_output=False)
def revisar_e_redigir(itens: list[ItemRevisao | dict], redigir: bool = True) -> tuple[str, list[ErroRevisao]]:
    """Revisão E1 completa: regras Python e, se pedido, redação pelo LLM. Registra só contagens no Langfuse."""
    rid = revisao_id(itens)
    erros = revisar_itens(itens)
    if redigir:
        erros = redigir_sugestoes(erros)
    try:
        get_client().update_current_span(
            metadata={"revisao_id": rid, "itens": len(itens), "erros": len(erros),
                      "por_regra": {r: sum(e.regra == r for e in erros) for r in ("unidade", "quantidade", "duplicado", "colunas_trocadas")},
                      "redigidos_por_llm": sum(e.redacao == "llm" for e in erros)})
    except Exception:  # noqa: BLE001
        pass
    return rid, erros
