// Amostras REAIS do acervo (docs/arquivos-teste): as tabelas do Revit em .txt passam pelo leitor.
// Cada uma deve ler sem erro, sem texto quebrado e sem sobrar linha de grupo ou total como item.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { importarTxt } from "./txt";

const ACERVO = join(__dirname, "../../../../docs/arquivos-teste");

const arquivos: { obra: string; nome: string; caminho: string }[] = [];
for (const obra of readdirSync(ACERVO, { withFileTypes: true }).filter((d) => d.isDirectory())) {
  for (const nome of readdirSync(join(ACERVO, obra.name))) {
    if (nome.toLowerCase().endsWith(".txt")) arquivos.push({ obra: obra.name, nome, caminho: join(ACERVO, obra.name, nome) });
  }
}
// Tabelas do Revit: o nome tem "revit" (obras 02 a 12) ou começa com "Tabela de" (obra 01).
const revit = arquivos.filter((a) => /revit/i.test(a.nome) || /^Tabela de /i.test(a.nome));
const outros = arquivos.filter((a) => !revit.includes(a));

describe("tabelas do Revit do acervo", () => {
  it("há amostras para testar", () => {
    expect(revit.length).toBeGreaterThanOrEqual(10);
  });

  for (const a of revit) {
    it(`${a.obra} / ${a.nome}`, () => {
      const r = importarTxt({ nome: a.nome, bytes: new Uint8Array(readFileSync(a.caminho)) });
      if ("erro" in r) throw new Error(`erro ${r.erro.codigo}: ${r.erro.mensagem}`);
      expect(r.origem).toMatchObject({ formato: "txt", delimitador: "\t" });
      expect(r.itens.length).toBeGreaterThan(0);
      const tudo = JSON.stringify(r.itens);
      expect(tudo).not.toMatch(/Ã|�/); // acentos intactos
      // nenhum item é título de grupo ou total
      for (const i of r.itens) {
        expect(i.descricao ?? "").not.toMatch(/^(sub)?total|^(n[ií]vel|ambiente|pavimento)\s*:/i);
      }
      const semQuantidade = r.itens.filter((i) => i.quantidade === null).length;
      const comAviso = r.avisos.map((x) => x.codigo);
      console.log(
        `${a.obra}/${a.nome}: ${r.itens.length} itens, ${semQuantidade} sem quantidade, software ${r.origem.software}, avisos [${[...new Set(comAviso)]}]`,
      );
    });
  }
});

describe("outros .txt do acervo (WhatsApp, briefing)", () => {
  it("não são tabelas do Revit: viram erro com orientação ou são lidos sem lixo", () => {
    expect(outros.length).toBeGreaterThan(0);
    for (const a of outros) {
      const r = importarTxt({ nome: a.nome, bytes: new Uint8Array(readFileSync(a.caminho)) });
      // Nunca lança; ou recusa com orientação, ou lê (e então os itens têm descrição).
      if ("erro" in r) expect(r.erro.mensagem.length).toBeGreaterThan(10);
      else expect(r.itens.every((i) => (i.descricao ?? "").length > 0 || i.quantidade !== null)).toBe(true);
    }
  });
});
