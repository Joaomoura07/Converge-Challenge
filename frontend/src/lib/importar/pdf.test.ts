// PDF com texto: as amostras REAIS do acervo (docs/arquivos-teste), mais os casos de falha.
// Usa a build "legacy" do PDF.js (Node, sem worker); a tela usa a build do navegador com worker da MESMA versão.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import * as pdfjsLegacy from "pdfjs-dist/legacy/build/pdf.mjs";
import { importarPdf, LIMITE_PAGINAS, type PdfjsMinimo } from "./pdf";

const pdfjs = pdfjsLegacy as unknown as PdfjsMinimo;
const ACERVO = join(__dirname, "../../../../docs/arquivos-teste");

const todos: { obra: string; nome: string; caminho: string }[] = [];
for (const obra of readdirSync(ACERVO, { withFileTypes: true }).filter((d) => d.isDirectory())) {
  for (const nome of readdirSync(join(ACERVO, obra.name))) {
    if (nome.toLowerCase().endsWith(".pdf")) todos.push({ obra: obra.name, nome, caminho: join(ACERVO, obra.name, nome) });
  }
}
const pedidos = todos.filter((a) => /^Pedido de cotação/i.test(a.nome));
const quadros = todos.filter((a) => /^PR-08/i.test(a.nome));
const escaneados = todos.filter((a) => /^Digitaliza/i.test(a.nome));
const ler = (c: string) => new Uint8Array(readFileSync(c));

describe("pedidos de cotação (tabela com cabeçalho)", () => {
  it("há amostras", () => expect(pedidos.length).toBeGreaterThanOrEqual(10));

  for (const a of pedidos) {
    it(`${a.obra} / ${a.nome}`, async () => {
      const r = await importarPdf({ nome: a.nome, bytes: ler(a.caminho), pdfjs });
      if ("erro" in r) throw new Error(`${r.erro.codigo}: ${r.erro.mensagem}`);
      expect(r.origem.formato).toBe("pdf");
      expect(r.itens.length).toBeGreaterThan(10);
      // o número do item no PDF vai de 1 até o último: nenhuma linha se perdeu nem foi duplicada
      const numeros = r.itens.map((i) => Number(i.extras.Item));
      expect(numeros).toEqual(Array.from({ length: numeros.length }, (_, k) => k + 1));
      for (const i of r.itens) {
        expect(i.descricao && i.descricao.length).toBeGreaterThan(3);
        expect(i.quantidade).not.toBeNull();
        expect(i.quantidade!).toBeGreaterThan(0);
        expect(i.unidade).toBe("un"); // quantidade de embalagens lida como un
        expect(i.descricao).toMatch(/\(.+\)$/); // embalagem na descrição
      }
      expect(JSON.stringify(r.itens)).not.toMatch(/Ã|�/);
      expect(r.avisos.map((x) => x.codigo)).toEqual(expect.arrayContaining(["EMBALAGEM_COMO_UNIDADE", "EXTRACAO_AMBIGUA"]));
    });
  }

  it("a amostra 01 lê as linhas conhecidas do pedido (inclui a página 2)", async () => {
    const a = pedidos.find((p) => p.obra.startsWith("01"))!;
    const r = await importarPdf({ nome: a.nome, bytes: ler(a.caminho), pdfjs });
    if ("erro" in r) throw new Error(r.erro.mensagem);
    expect(r.itens[0]).toMatchObject({ descricao: "Selador acrílico (lata 18 L)", quantidade: 1, unidade: "un" });
    expect(r.itens[1]).toMatchObject({ descricao: "Massa corrida PVA Suvinil (barrica 25 kg)", quantidade: 5 });
    expect(r.itens[6]).toMatchObject({ descricao: "Lixa para massa Norton A275 grão 150 (folha)", quantidade: 40 });
    expect(r.itens.length).toBeGreaterThanOrEqual(38); // a página 2 começa no item 38
  });
});

describe("quadros de acabamentos (matriz com a quantidade na célula)", () => {
  it("há amostras", () => expect(quadros.length).toBeGreaterThanOrEqual(10));

  for (const a of quadros) {
    it(`${a.obra} / ${a.nome}`, async () => {
      const r = await importarPdf({ nome: a.nome, bytes: ler(a.caminho), pdfjs });
      if ("erro" in r) throw new Error(`${r.erro.codigo}: ${r.erro.mensagem}`);
      expect(r.itens.length).toBeGreaterThan(2);
      for (const i of r.itens) {
        expect(i.descricao && i.descricao.length).toBeGreaterThan(3);
        expect(i.descricao).not.toMatch(/\(\s*\d[\d.,]*\s*m/); // a quantidade saiu da descrição
        expect(i.quantidade).not.toBeNull();
        expect(["m2", "m", "un"]).toContain(i.unidade);
        expect(i.categoria).toBeTruthy();
      }
    });
  }

  it("a amostra 01 separa ambiente, categoria, descrição, quantidade e unidade", async () => {
    const a = quadros.find((p) => p.obra.startsWith("01"))!;
    const r = await importarPdf({ nome: a.nome, bytes: ler(a.caminho), pdfjs });
    if ("erro" in r) throw new Error(r.erro.mensagem);
    const piso = r.itens.find((i) => i.categoria === "Piso" && i.nivel === "Sala/Jantar");
    expect(piso).toMatchObject({ descricao: "Portobello cimento 90x90", quantidade: 24, unidade: "m2" });
    const rodape = r.itens.find((i) => i.descricao?.startsWith("Rodapé Santa Luzia") && i.nivel === "Sala/Jantar");
    expect(rodape).toMatchObject({ quantidade: 22, unidade: "m" });
    // as duas tintas da parede da sala (duas linhas na mesma célula) entram as duas
    expect(r.itens.filter((i) => i.nivel === "Sala/Jantar" && i.categoria === "Parede")).toHaveLength(2);
  });
});

describe("PDF que não dá para ler (orientação para CSV, Excel ou cadastro manual)", () => {
  it("escaneado, sem texto, é reconhecido", async () => {
    expect(escaneados.length).toBeGreaterThan(0);
    for (const a of escaneados) {
      const r = await importarPdf({ nome: a.nome, bytes: ler(a.caminho), pdfjs });
      expect("erro" in r && r.erro.codigo).toBe("PDF_SEM_TEXTO");
      expect("erro" in r && r.erro.mensagem).toMatch(/CSV|Excel|digite/i);
    }
  });

  it("arquivo que não é PDF (PNG renomeado) é recusado", async () => {
    const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]);
    const r = await importarPdf({ nome: "foto.pdf", bytes: png, pdfjs });
    expect("erro" in r && r.erro.codigo).toBe("FORMATO_INVALIDO");
  });

  it("PDF truncado é 'corrompido', sem lançar", async () => {
    const bytes = ler(pedidos[0].caminho);
    const r = await importarPdf({ nome: "x.pdf", bytes: bytes.slice(0, Math.floor(bytes.length / 3)), pdfjs });
    expect("erro" in r && r.erro.codigo).toBe("ARQUIVO_CORROMPIDO");
    expect("erro" in r && r.erro.mensagem).toMatch(/CSV|Excel|digite/i);
  });

  it("arquivo vazio", async () => {
    const r = await importarPdf({ nome: "x.pdf", bytes: new Uint8Array(0), pdfjs });
    expect("erro" in r && r.erro.codigo).toBe("ARQUIVO_VAZIO");
  });

  it("PDF protegido por senha (SIMULADO: não há PDF protegido no acervo; a exceção real do PDF.js é PasswordException)", async () => {
    const simulado = {
      getDocument: () => ({
        promise: Promise.reject(Object.assign(new Error("No password given"), { name: "PasswordException" })),
      }),
    } as unknown as PdfjsMinimo;
    const bytes = new TextEncoder().encode("%PDF-1.7\n...");
    const r = await importarPdf({ nome: "x.pdf", bytes, pdfjs: simulado });
    expect("erro" in r && r.erro.codigo).toBe("ARQUIVO_PROTEGIDO");
    expect("erro" in r && r.erro.mensagem).toMatch(/senha/i);
  });

  it(`PDF com mais de ${LIMITE_PAGINAS} páginas é recusado (SIMULADO)`, async () => {
    const simulado = {
      getDocument: () => ({ promise: Promise.resolve({ numPages: LIMITE_PAGINAS + 1, getPage: async () => ({}), destroy: async () => {} }) }),
    } as unknown as PdfjsMinimo;
    const r = await importarPdf({ nome: "x.pdf", bytes: new TextEncoder().encode("%PDF-1.7\n"), pdfjs: simulado });
    expect("erro" in r && r.erro.codigo).toBe("ARQUIVO_GRANDE_DEMAIS");
  });

  it("PDF com texto mas sem tabela de materiais recebe orientação", async () => {
    const texto = (str: string, y: number) => ({ str, transform: [1, 0, 0, 1, 40, y] });
    const simulado = {
      getDocument: () => ({
        promise: Promise.resolve({
          numPages: 1,
          getPage: async () => ({
            getTextContent: async () => ({
              items: [texto("Memorial descritivo da obra: pintura de paredes internas e externas.", 700), texto("Fim do documento", 680)],
            }),
          }),
          destroy: async () => {},
        }),
      }),
    } as unknown as PdfjsMinimo;
    const r = await importarPdf({ nome: "memorial.pdf", bytes: new TextEncoder().encode("%PDF-1.7\n"), pdfjs: simulado });
    expect("erro" in r && r.erro.codigo).toBe("CABECALHO_NAO_ENCONTRADO");
  });
});
