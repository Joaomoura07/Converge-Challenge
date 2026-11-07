// Roda o leitor de CSV contra os casos TC-xxx de tests/importacao (entradas .csv e seus .esperado.json).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { comparar, FIX, manifest, ordenar } from "./comparar-fixtures";
import { importarCsv } from "./csv";

const casosCsv = manifest.casos.filter(
  (c) => c.tipo === "parse" && c.variantes.every((v) => v.entrada.endsWith(".csv") && !v.entrada.startsWith("grandes/")),
);

describe("fixtures CSV de tests/importacao", () => {
  for (const caso of casosCsv) {
    for (const v of caso.variantes) {
      const rotulo = `${caso.id} [${caso.prioridade}] ${caso.titulo}${caso.variantes.length > 1 ? ` (${v.entrada})` : ""}`;
      it(rotulo, () => {
        const caminho = join(FIX, v.entrada);
        expect(existsSync(caminho)).toBe(true);
        const bytes = new Uint8Array(readFileSync(caminho));
        const obt = importarCsv({ nome: v.entrada.split("/").pop()!, bytes });
        const esp = JSON.parse(readFileSync(join(FIX, v.esperado!), "utf8"));
        expect(comparar(esp, obt)).toEqual([]);
      });
    }
  }

  it("TC-100 determinismo: o mesmo arquivo três vezes dá o mesmo JSON", () => {
    const bytes = new Uint8Array(readFileSync(join(FIX, "TC-001.csv")));
    const saidas = [0, 1, 2].map(() => JSON.stringify(ordenar(importarCsv({ nome: "TC-001.csv", bytes: bytes.slice() }))));
    expect(new Set(saidas).size).toBe(1);
    const esp = JSON.parse(readFileSync(join(FIX, "TC-001.esperado.json"), "utf8"));
    expect(comparar(esp, JSON.parse(saidas[0]))).toEqual([]);
  });

  it("recusa arquivo acima de 20 MB antes de ler (TC-085)", () => {
    const r = importarCsv({ nome: "grande.csv", bytes: new Uint8Array(25 * 1024 * 1024) });
    expect("erro" in r && r.erro.codigo).toBe("ARQUIVO_GRANDE_DEMAIS");
  });
});
