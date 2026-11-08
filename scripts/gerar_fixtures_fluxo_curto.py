"""Amostras sintéticas de regressão: no máximo 3 itens por arquivo, sem serviços externos."""
from pathlib import Path

from reportlab.pdfgen import canvas

DESTINO = Path(__file__).resolve().parents[1] / 'tests/importacao/fixtures/fluxo-curto'


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(DESTINO / 'quadro-fragmentado.pdf'))
    for x, texto in [(40, 'Ambiente'), (160, 'Piso'), (400, 'Parede')]:
        pdf.drawString(x, 740, texto)
    pdf.drawString(40, 710, 'Sala')
    # Uma célula PDF pode ser composta por vários operadores de texto.
    pdf.drawString(160, 710, 'Porcelanato')
    pdf.drawString(235, 710, '(12,50 m2)')
    pdf.drawString(400, 710, 'Tinta (20 m2)')
    pdf.save()

    pdf = canvas.Canvas(str(DESTINO / 'tabela-quantidade-ausente.pdf'))
    for x, texto in [(40, 'Descrição'), (300, 'Quantidade'), (420, 'Unidade')]:
        pdf.drawString(x, 740, texto)
    for y, desc, qtd, un in [(710, 'Cimento CP II', '2', 'un'), (680, 'Areia lavada', '', 'm3'), (650, 'Rejunte branco', '3', 'kg')]:
        for x, texto in [(40, desc), (300, qtd), (420, un)]:
            pdf.drawString(x, y, texto)
    pdf.save()

    dxf = '\n'.join(map(str, [0,'SECTION',2,'HEADER',9,'$INSUNITS',70,6,0,'ENDSEC',0,'SECTION',2,'ENTITIES',
        0,'LWPOLYLINE',8,'RODAPE',90,2,70,0,10,0,20,0,42,1,10,2,20,0,
        0,'LWPOLYLINE',8,'PISO',90,3,70,1,10,0,20,0,42,1,10,2,20,0,10,0,20,0,
        0,'ENDSEC',0,'EOF'])) + '\n'
    (DESTINO / 'curvas.dxf').write_text(dxf, encoding='utf-8')
    ifc = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Teste sintetico'),'2;1');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);
#2=IFCSIUNIT(*,.AREAUNIT.,.MILLI.,.SQUARE_METRE.);
#3=IFCUNITASSIGNMENT((#1));
#10=IFCSLAB('slab',$,'Laje de concreto',$,$,$,$,$,.FLOOR.);
#11=IFCQUANTITYAREA('NetArea',$,#2,12500000.,$);
#12=IFCELEMENTQUANTITY('qto',$,'Qto_SlabBaseQuantities',$,$,(#11));
#13=IFCRELDEFINESBYPROPERTIES('rel',$,$,$,(#10),#12);
ENDSEC;
END-ISO-10303-21;
"""
    (DESTINO / 'unidade-local.ifc').write_text(ifc, encoding='utf-8')
    print(f'4 arquivos sintéticos em {DESTINO}')


if __name__ == '__main__':
    main()
