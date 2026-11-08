"""Plano de compra em PDF (irmão do Excel de src/exportar.py): para o arquiteto levar ao cliente ou à loja.

Mesmo conteúdo que a tela de resultado mostra, sem recalcular nada: total, "cabe ou não" e ganho vêm da viabilidade e
do ganho que a Fatia C já gravou; a conta de cada item é a mesma da viabilidade (qtd. de embalagens × preço médio).
Seções: resumo → itens com preço (com as lojas e o link de cada fonte) → onde comprar (por loja) → o que depende
de você (pendentes e sem preço) → aviso de que o preço é estimativa de pesquisa.

Segurança: descrição, pergunta e motivo vêm de arquivos enviados pelo usuário, e o Paragraph do reportlab lê um
mini-HTML. Todo texto de usuário passa por `_t()` (escapa `<`, `&` e troca o que a fonte não desenha) e só link
http(s) vira hiperlink.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .ganho import Ganho
from .logistica import Logistica
from .viabilidade import Viabilidade

# Cores: tinta, cinza de apoio, linha fina e um azul só (a cor de ação do site).
TINTA = colors.HexColor("#1b1b1f")
APOIO = colors.HexColor("#5b5b66")
LINHA = colors.HexColor("#c9c9d1")
FUNDO = colors.HexColor("#f1f1f4")
ACAO = colors.HexColor("#1f4fbf")
AVISO = colors.HexColor("#8a5a00")

LARGURA = A4[0] - 30 * mm                       # margens de 15 mm
MAX_DESCRICAO = 240                             # descrição enorme não pode estourar a página
MAX_LOJAS_POR_ITEM = 5
_BASE = {"fontName": "Helvetica", "textColor": TINTA, "leading": 11, "fontSize": 8.5}


def _estilo(nome: str, **kw: Any) -> ParagraphStyle:
    return ParagraphStyle(nome, **{**_BASE, **kw})


CORPO = _estilo("corpo")
PEQUENO = _estilo("pequeno", fontSize=7.5, leading=9.5, textColor=APOIO)
DIREITA = _estilo("direita", alignment=TA_RIGHT)
DIREITA_PEQ = _estilo("direita_peq", alignment=TA_RIGHT, fontSize=7.5, leading=9.5, textColor=APOIO)
CABECALHO = _estilo("cabecalho", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white)
CABECALHO_DIR = _estilo("cabecalho_dir", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white,
                        alignment=TA_RIGHT)
TITULO = _estilo("titulo", fontName="Helvetica-Bold", fontSize=20, leading=24)
SECAO = _estilo("secao", fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=14, spaceAfter=6,
                textColor=ACAO)
LOJA = _estilo("loja", fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceAfter=3, keepWithNext=1)

# ---------------------------------------------------------------- texto seguro
_TROCAS = {"≈": "~", "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "⌀": "diam. ", " ": " ", "​": "",
           "−": "-", "‑": "-"}
_CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _limpar(s: Any) -> str:
    """Só o que a Helvetica (WinAnsi) desenha: acento, ², R$, travessão... O resto vira o equivalente ou '?'."""
    texto = _CONTROLE.sub(" ", str(s if s is not None else ""))
    saida: list[str] = []
    for ch in texto:
        ch = _TROCAS.get(ch, ch)
        try:
            ch.encode("cp1252")
            saida.append(ch)
        except UnicodeEncodeError:
            alt = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
            saida.append(alt or "?")
    return " ".join("".join(saida).split())


def _t(s: Any, limite: int | None = None) -> str:
    """Texto de usuário pronto para dentro de um Paragraph."""
    texto = _limpar(s)
    if limite and len(texto) > limite:
        texto = texto[: limite - 1].rstrip() + "…"
    return escape(texto)


def _link(url: Any, rotulo: str) -> str:
    """Hiperlink só para http(s); qualquer outro esquema (file:, javascript:) vira texto simples."""
    u = str(url or "").strip()
    if re.match(r"^https?://", u, re.I) and not _CONTROLE.search(u):
        return f'<link href="{escape(u, {chr(34): "&quot;"})}" color="#1f4fbf">{rotulo}</link>'
    return rotulo


# ---------------------------------------------------------------- formatos pt-BR
def _num(v: float, casas: int = 2) -> str:
    texto = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto.rstrip("0").rstrip(",") if casas > 2 else texto


def _brl(v: float | None) -> str:
    return "—" if v is None else "R$ " + _num(abs(v)) if v >= 0 else "-R$ " + _num(abs(v))


def _qtd(q: Any, u: Any) -> str:
    if not isinstance(q, (int, float)):
        return "—"
    un = {"m2": "m²", "m3": "m³", "l": "L"}.get(str(u or "").lower(), str(u or ""))
    return f"{_num(float(q), 3)} {_limpar(un)}".strip()


def _dominio(d: Any) -> str:
    d = re.sub(r"^https?://", "", str(d or "").lower().strip())
    return re.sub(r"^www\.", "", d).split("/")[0]


# ---------------------------------------------------------------- dados do item
SEM_PRECO = ("nao_encontrado", "erro", "buscando")
SITUACAO = {
    "pendente_especificacao": "Pendente de especificação",
    "nao_encontrado": "Sem preço encontrado",
    "erro": "Erro na pesquisa",
    "buscando": "Ainda pesquisando",
}


def _nome(it: dict[str, Any], posicao: int) -> str:
    return it.get("produto_normalizado") or it.get("descricao") or it.get("produto") or f"Item {posicao + 1}"


def _total_item(it: dict[str, Any]) -> float | None:
    """Mesma conta da viabilidade: qtd. de embalagens × preço médio da embalagem. None = fora do total."""
    if it.get("status") in SEM_PRECO:
        return None
    q, med = it.get("qtd_embalagens") or 0, it.get("preco_emb_med")
    if not q or not isinstance(med, (int, float)) or med <= 0:
        return None
    return round(float(q) * float(med), 2)


def _compra(it: dict[str, Any]) -> str:
    q, emb = it.get("qtd_embalagens"), it.get("embalagem")
    if not q or not emb:
        return "—"
    return f"{q} × {_t(emb, 40)}"


def _lojas_do_item(it: dict[str, Any]) -> str:
    """Uma linha por loja (menor preço de cada), com o link da fonte: é a prova de onde o preço veio."""
    por_loja: dict[str, dict[str, Any]] = {}
    for f in it.get("fontes") or []:
        preco = f.get("preco_embalagem")
        if not isinstance(preco, (int, float)) or preco <= 0:
            continue
        chave = _dominio(f.get("dominio") or f.get("url")) or str(f.get("loja"))
        if chave not in por_loja or preco < por_loja[chave]["preco_embalagem"]:
            por_loja[chave] = f
    linhas = []
    for f in sorted(por_loja.values(), key=lambda x: x["preco_embalagem"])[:MAX_LOJAS_POR_ITEM]:
        rotulo = f"{_t(f.get('loja') or f.get('dominio'), 30)} {_brl(float(f['preco_embalagem']))}"
        linhas.append(_link(f.get("url"), rotulo))
    return "<br/>".join(linhas) if linhas else "—"


# ---------------------------------------------------------------- blocos
def _tabela(linhas: list[list[Any]], larguras: list[float], extra: list[tuple] | None = None) -> Table:
    t = Table(linhas, colWidths=larguras, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACAO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINHA),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        *(extra or []),
    ]))
    return t


def _resumo(itens: list[dict[str, Any]], viab: Viabilidade | None,
            logi: Logistica | None, ganho: Ganho | None) -> list[Any]:
    com_preco = sum(1 for it in itens if _total_item(it) is not None)
    soma = round(sum(_total_item(it) or 0 for it in itens), 2)
    linhas: list[list[Any]] = []

    def linha(rotulo: str, valor: str, destaque: bool = False) -> None:
        estilo = _estilo("v", fontName="Helvetica-Bold", fontSize=11, leading=14) if destaque else CORPO
        linhas.append([Paragraph(rotulo, PEQUENO), Paragraph(valor, estilo)])

    if viab:
        linha("Total estimado (média das lojas)", _brl(viab.total_med), True)
        linha("Faixa de preço", f"{_brl(viab.total_min)} a {_brl(viab.total_max)}")
        linha("Orçamento do cliente", _brl(viab.orcamento_cliente))
        linha("Situação", _t(viab.resumo))
        for s in viab.sugestoes[:3]:
            linha("Dica", _t(s.texto))
    else:
        linha("Total estimado (média das lojas)", _brl(soma), True)
    linha("Itens", f"{len(itens)} na lista, {com_preco} com preço"
                   + (f", {len(itens) - com_preco} ainda sem preço" if len(itens) > com_preco else ""))
    if logi and logi.frete_total:
        linha("Frete estimado", _brl(logi.frete_total))
    if ganho:
        linha("Tempo poupado", _t(ganho.resumo))

    t = Table(linhas, colWidths=[42 * mm, LARGURA - 42 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FUNDO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBEFORE", (0, 0), (0, -1), 2, ACAO),
    ]))
    return [Paragraph("Resumo", SECAO), t]


def _tabela_itens(itens: list[dict[str, Any]]) -> list[Any]:
    cab = [Paragraph("Item", CABECALHO), Paragraph("Quantidade", CABECALHO), Paragraph("Compra", CABECALHO),
           Paragraph("Preço da embalagem", CABECALHO_DIR), Paragraph("Total", CABECALHO_DIR),
           Paragraph("Onde achei (preço por embalagem)", CABECALHO)]
    linhas: list[list[Any]] = [cab]
    for i, it in enumerate(itens):
        total = _total_item(it)
        if total is None and it.get("preco_emb_med") is None:
            continue                       # sem preço nenhum: vai só para "o que depende de você"
        nome = f"<b>{_t(_nome(it, i), MAX_DESCRICAO)}</b>"
        if it.get("estimativa") or it.get("status") == "pendente_especificacao":
            nome += '<br/><font size="7.5" color="#8a5a00">Estimativa: falta especificar o produto</font>'
        premissa = it.get("premissa")
        if premissa:
            nome += f'<br/><font size="7.5" color="#5b5b66">Conta: {_t(premissa, 140)}</font>'
        med, mn, mx = it.get("preco_emb_med"), it.get("preco_emb_min"), it.get("preco_emb_max")
        faixa = ""
        if isinstance(mn, (int, float)) and isinstance(mx, (int, float)) and mn != mx:
            faixa = f"<br/>{_brl(float(mn))} a {_brl(float(mx))}"
        linhas.append([
            Paragraph(nome, CORPO),
            Paragraph(_qtd(it.get("quantidade"), it.get("unidade")), CORPO),
            Paragraph(_compra(it), CORPO),
            Paragraph(f"<b>{_brl(float(med))}</b>{faixa}" if isinstance(med, (int, float)) else "—", DIREITA),
            Paragraph(f"<b>{_brl(total)}</b>" if total is not None else "—", DIREITA),
            Paragraph(_lojas_do_item(it), PEQUENO),
        ])
    if len(linhas) == 1:
        return [Paragraph("Itens com preço", SECAO),
                Paragraph("Nenhum item tem preço pesquisado ainda.", CORPO)]
    larguras = [50 * mm, 21 * mm, 24 * mm, 27 * mm, 22 * mm, LARGURA - 144 * mm]
    return [Paragraph("Itens com preço", SECAO), _tabela(linhas, larguras)]


def _plano_por_loja(itens: list[dict[str, Any]], logi: Logistica | None) -> list[Any]:
    if not logi or not logi.lojas:
        return []
    blocos: list[Any] = [Paragraph("Onde comprar", SECAO),
                         Paragraph("Cada item na loja onde saiu mais barato, como na tela de resultado.", PEQUENO),
                         Spacer(1, 4)]
    for loja in logi.lojas:
        dist = getattr(loja, "distancia_km", None)
        tempo = getattr(loja, "tempo_min", None)
        sub = f"{len(loja.itens)} {'item' if len(loja.itens) == 1 else 'itens'}"
        if dist is not None:
            sub += f" · {_num(float(dist), 1)} km" + (f" ({tempo} min)" if tempo is not None else "")
        cab = Paragraph(f"{_t(loja.nome, 60)} <font size='8' color='#5b5b66'>{sub}</font>", LOJA)
        linhas: list[list[Any]] = [[Paragraph("Item", CABECALHO), Paragraph("Compra", CABECALHO),
                                    Paragraph("Preço", CABECALHO_DIR), Paragraph("Subtotal", CABECALHO_DIR)]]
        alvo = _dominio(loja.id)
        for i in loja.itens:
            if not 0 <= i < len(itens):
                continue
            it = itens[i]
            preco = None
            for f in it.get("fontes") or []:
                p = f.get("preco_embalagem")
                if _dominio(f.get("dominio") or f.get("url")) == alvo and isinstance(p, (int, float)) and p > 0:
                    preco = float(p) if preco is None else min(preco, float(p))
            q = it.get("qtd_embalagens") or 0
            linhas.append([Paragraph(_t(_nome(it, i), MAX_DESCRICAO), CORPO), Paragraph(_compra(it), CORPO),
                           Paragraph(_brl(preco), DIREITA),
                           Paragraph(_brl(round(preco * q, 2)) if preco and q else "—", DIREITA)])
        linhas.append([Paragraph("", CORPO), Paragraph("", CORPO), Paragraph("<b>Produtos</b>", DIREITA),
                       Paragraph(f"<b>{_brl(loja.subtotal)}</b>", DIREITA)])
        if loja.frete:
            linhas.append([Paragraph("", CORPO), Paragraph("", CORPO), Paragraph("Frete", DIREITA),
                           Paragraph(_brl(loja.frete), DIREITA)])
        extra: list[tuple] = [("LINEBELOW", (0, -1), (-1, -1), 0.8, LINHA)]
        if loja.abaixo_do_minimo:
            linhas.append([Paragraph(f'<font color="#8a5a00">Atenção: abaixo do pedido mínimo da loja '
                                     f"({_brl(loja.pedido_minimo)}).</font>", PEQUENO), "", "", ""])
            extra = [("SPAN", (0, -1), (-1, -1)), ("LINEBELOW", (0, -1), (-1, -1), 0.8, LINHA)]
        bloco = [cab, _tabela(linhas, [LARGURA - 90 * mm, 30 * mm, 30 * mm, 30 * mm], extra)]
        blocos += [KeepTogether(bloco)] if len(linhas) <= 12 else bloco   # loja pequena não racha entre páginas
        blocos.append(Spacer(1, 8))
    return blocos


def _pendentes(itens: list[dict[str, Any]]) -> list[Any]:
    linhas: list[list[Any]] = [[Paragraph("Item", CABECALHO), Paragraph("Situação", CABECALHO),
                                Paragraph("O que falta", CABECALHO)]]
    for i, it in enumerate(itens):
        status = it.get("status")
        if status not in SITUACAO and _total_item(it) is not None:
            continue
        if status not in SITUACAO:
            status = "nao_encontrado"
        detalhe = it.get("pergunta") or it.get("motivo") or "Sem preço em loja pesquisada."
        linhas.append([Paragraph(f"<b>{_t(_nome(it, i), MAX_DESCRICAO)}</b>", CORPO),
                       Paragraph(SITUACAO[status], CORPO), Paragraph(_t(detalhe, 400), CORPO)])
    if len(linhas) == 1:
        return []
    return [Paragraph("O que depende de você", SECAO),
            Paragraph("Estes itens estão fora do total ou entram só como estimativa. "
                      "Especifique o produto no site para fechar o valor.", PEQUENO),
            Spacer(1, 4), _tabela(linhas, [55 * mm, 36 * mm, LARGURA - 91 * mm])]


class _Paginas(_canvas.Canvas):
    """Rodapé com 'página X de Y': o total só se sabe no fim, então guarda as páginas e carimba ao salvar."""

    def __init__(self, *a: Any, titulo: str = "", **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._titulo = titulo
        self._salvas: list[dict[str, Any]] = []

    def showPage(self) -> None:  # noqa: N802 — nome do reportlab
        self._salvas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._salvas)
        for estado in self._salvas:
            self.__dict__.update(estado)
            self._rodape(total)
            super().showPage()
        super().save()

    def _rodape(self, total: int) -> None:
        self.setFont("Helvetica", 7.5)
        self.setFillColor(APOIO)
        self.setStrokeColor(LINHA)
        self.setLineWidth(0.4)
        self.line(15 * mm, 13 * mm, A4[0] - 15 * mm, 13 * mm)
        self.drawString(15 * mm, 9 * mm, self._titulo)
        self.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Página {self._pageNumber} de {total}")


def gerar_pdf(obra: dict[str, Any], itens: list[dict[str, Any]], logistica: Logistica | None = None,
              viabilidade: Viabilidade | None = None, ganho: Ganho | None = None,
              agora: datetime | None = None) -> bytes:
    """Devolve o PDF em bytes. `itens` na mesma ordem que `logistica.lojas[].itens` usa como índice."""
    agora = agora or datetime.now()
    nome = _t(obra.get("nome") or "Obra", 120)
    titulo_rodape = _limpar(f"Plano de compra — {obra.get('nome') or 'Obra'}")[:90]

    historia: list[Any] = [
        Paragraph("Plano de compra", TITULO),
        Spacer(1, 2),
        Paragraph(f"<b>{nome}</b> · CEP {_t(obra.get('cep') or '—', 20)} · gerado em {agora:%d/%m/%Y}", CORPO),
        *_resumo(itens, viabilidade, logistica, ganho),
        *_tabela_itens(itens),
        *_plano_por_loja(itens, logistica),
        *_pendentes(itens),
        Spacer(1, 12),
        Paragraph("Os preços são médias de anúncios de lojas online na data da pesquisa e podem mudar. "
                  "Confirme preço, estoque e prazo com a loja antes de fechar a compra. "
                  "Os links de cada preço estão na coluna “Onde achei”.", PEQUENO),
    ]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=18 * mm, title=_limpar(f"Plano de compra — {obra.get('nome') or 'Obra'}"),
                            author="Orça", subject="Plano de compra")
    # o título do rodapé vai por parâmetro (nada de estado de classe: duas exportações simultâneas não se misturam)
    doc.build(historia, canvasmaker=lambda *a, **kw: _Paginas(*a, titulo=titulo_rodape, **kw))
    return buf.getvalue()
