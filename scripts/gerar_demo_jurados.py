"""Gera exemplos pequenos e sintéticos. Sem cotações; não consulta serviços.

Depois: node scripts/gerar_demo_skp.mjs e ATUALIZAR_FIXTURE_DEMO=1 npm test no frontend.
"""
import csv
import json
import uuid
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "frontend/public/exemplos/demo"
DADOS = json.loads((RAIZ / "docs/arquivos-teste/demo-jurados.json").read_text(encoding="utf-8"))
CABECALHO = ["Descrição", "Quantidade", "Unidade", "Categoria"]


def tabelas(nome, itens, titulo):
    with (DESTINO / f"{nome}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(CABECALHO); w.writerows(itens)
    with (DESTINO / f"{nome}.txt").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t"); w.writerow(CABECALHO); w.writerows(itens)
    wb = Workbook(); ws = wb.active; ws.title = "Materiais"
    ws.append(CABECALHO)
    for linha in itens: ws.append(linha)
    for row in ws:
        for cell in row:
            cell.font = Font(name="Arial", size=11, color="FFFFFF" if cell.row == 1 else "172C43", bold=cell.row == 1)
            cell.alignment = Alignment(vertical="center")
            if cell.row == 1: cell.fill = PatternFill("solid", fgColor="194F90")
    for col, largura in zip("ABCD", [66, 14, 12, 22]): ws.column_dimensions[col].width = largura
    for row in range(1, len(itens) + 2): ws.row_dimensions[row].height = 27
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    ws["A1"].comment = Comment("Obra fictícia. Edite descrição, quantidade e unidade. Nenhum preço foi pré-preenchido.", "Orça")
    for row in range(2, len(itens) + 2):
        ws.cell(row, 2).comment = Comment("Quantidade sintética para demonstração, não levantamento de obra real.", "Orça")
    wb.save(DESTINO / f"{nome}.xlsx")
    c = canvas.Canvas(str(DESTINO / f"{nome}.pdf"), pagesize=landscape(A4), invariant=1)
    c.setTitle(titulo); c.setAuthor("Orça — exemplos sintéticos")
    c.setFillColorRGB(.10, .23, .38); c.setFont("Helvetica-Bold", 21); c.drawString(42, 545, titulo)
    c.setFont("Helvetica", 10); c.drawString(42, 521, "Obra fictícia | Quantitativo para demonstração | Preços pesquisados somente após o envio")
    # O roteiro vem antes da tabela para não virar uma linha de material no leitor PDF.
    c.drawString(42, 499, "Teste 2: confira a unidade da tomada e complete a tinta." if nome == "teste_2" else "Confira os materiais e observe as fontes, embalagens e especificações no resultado.")
    xs = [42, 540, 635, 700]
    c.setFillColorRGB(.10, .31, .56); c.rect(36, 456, 772, 29, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 10)
    for x, t in zip(xs, CABECALHO): c.drawString(x, 466, t)
    for n, linha in enumerate(itens):
        y = 431 - n * 43
        c.setFillColorRGB(.95, .97, .99) if n % 2 == 0 else c.setFillColorRGB(1, 1, 1)
        c.rect(36, y - 14, 772, 39, fill=1, stroke=0)
        c.setFillColorRGB(.10, .17, .26); c.setFont("Helvetica", 10)
        for x, v in zip(xs, linha): c.drawString(x, y, str(v).replace("²", "2"))
    c.save()


def guid(n):
    # GUID IFC de 22 caracteres, determinístico para manter diffs legíveis.
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"orca-demo:{n}").int
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
    out = ""
    for _ in range(22): out = alphabet[value & 63] + out; value >>= 6
    return out


def ifc(nome, itens):
    linhas = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('Quantitativo sintetico para demonstracao'),'2;1');",
              f"FILE_NAME('{nome}.ifc','2026-11-08T12:00:00',('Orca'),('Orca'),'Orca','Orca','');",
              "FILE_SCHEMA(('IFC4'));", "ENDSEC;", "DATA;",
              "#1=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);", "#2=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);",
              "#3=IFCUNITASSIGNMENT((#1,#2));",
              f"#4=IFCPROJECT('{guid(4)}',$,'Demo sintetica',$,$,$,$,$,#3);",
              f"#5=IFCBUILDINGSTOREY('{guid(5)}',$,'Terreo',$,$,$,$,$,.ELEMENT.,0.);"]
    alvos = []; num = 10
    for desc, qtd, un, _ in itens:
        # Arquivos IFC usam quantidades geométricas ou contagem, nunca o erro de unidade da planilha.
        if desc.startswith("Tomada"): un = "un"
        # STEP: caracteres fora de ASCII escritos como escape Unicode.
        desc = "".join(ch if ord(ch) < 128 else f"\\X2\\{ord(ch):04X}\\X0\\" for ch in desc).replace("'", "''")
        for _ in range(int(qtd) if un == "un" else 1):
            alvos.append(f"#{num}")
            if un == "m2":
                tipo = "CLADDING" if desc.startswith("Tinta") else "FLOORING"
                linhas += [f"#{num}=IFCCOVERING('{guid(num)}',$,'{desc}',$,$,$,$,$,.{tipo}.);",
                           f"#{num+1}=IFCQUANTITYAREA('NetArea',$,$,{float(qtd)},$);",
                           f"#{num+2}=IFCELEMENTQUANTITY('{guid(num+2)}',$,'BaseQuantities',$,$,(#{num+1}));",
                           f"#{num+3}=IFCRELDEFINESBYPROPERTIES('{guid(num+3)}',$,$,$,(#{num}),#{num+2});"]
            else:
                linhas.append(f"#{num}=IFCBUILDINGELEMENTPROXY('{guid(num)}',$,'{desc}',$,$,$,$,$,.ELEMENT.);")
            num += 4
    linhas += [f"#{num}=IFCRELCONTAINEDINSPATIALSTRUCTURE('{guid(num)}',$,$,$,({','.join(alvos)}),#5);", "ENDSEC;", "END-ISO-10303-21;"]
    (DESTINO / f"{nome}.ifc").write_text("\n".join(linhas) + "\n", encoding="ascii")


def dxf(nome, geometria=False):
    p = [0,"SECTION",2,"HEADER",9,"$ACADVER",1,"AC1021",9,"$INSUNITS",70,6,0,"ENDSEC"]
    blocos = [("Spot Stella 7W 3000K",4), ("Joelho Tigre soldavel 25mm",8), ("Lata de tinta Suvinil Toque de Seda Branco Neve 18L",1)]
    if geometria: blocos = [("PORTA",2), ("TOMADA",4)]
    p += [0,"SECTION",2,"BLOCKS"]
    for desc, _ in blocos:
        p += [0,"BLOCK",8,"0",2,desc,70,0,10,0,20,0,30,0,3,desc,0,"LINE",8,"0",10,0,20,0,11,.2,21,.2,0,"ENDBLK",8,"0"]
    p += [0,"ENDSEC",0,"SECTION",2,"ENTITIES"]
    if geometria:
        p += [0,"LWPOLYLINE",8,"PISO",90,4,70,1,10,0,20,0,10,6,20,0,10,6,20,3,10,0,20,3]
        p += [0,"LINE",8,"RODAPE",10,0,20,0,11,18,21,0]
    for y, (desc, qtd) in enumerate(blocos):
        for x in range(qtd): p += [0,"INSERT",8,"0",2,desc,10,x,20,y,30,0]
    p += [0,"ENDSEC",0,"EOF"]
    (DESTINO / f"{nome}.dxf").write_text("\n".join(map(str,p)) + "\n", encoding="utf-8")


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, chave, titulo in [("teste_1","pesquisa","Materiais especificados — Boa Viagem"),
                                ("teste_2","revisao","Revisão de uma reforma — Casa Forte"),
                                ("MODELO","modelo","Modelo de lista — Orça")]:
        tabelas(nome, DADOS[chave], titulo)
    with (DESTINO / "componentes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.writer(f, delimiter=";"); w.writerow(CABECALHO); w.writerows(DADOS["componentes"])
    ifc("teste_1", DADOS["componentes"]); ifc("teste_2", DADOS["revisao"]); ifc("MODELO", DADOS["modelo"])
    dxf("teste_1"); dxf("teste_2", True); dxf("MODELO", True)
    print("Exemplos CSV, TXT, Excel, PDF, IFC e DXF gerados; falta gerar SKP.")


if __name__ == "__main__": main()
