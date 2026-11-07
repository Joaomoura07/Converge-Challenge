// Roda o leitor de TXT do Revit contra os casos .txt de tests/importacao (TC-003, 013, 057 a 066).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { comparar, FIX, manifest } from "./comparar-fixtures";
import { importarTxt } from "./txt";

const casos = manifest.casos.filter(
  (c) => c.tipo === "parse" && c.variantes.every((v) => v.entrada.endsWith(".txt") && !v.entrada.startsWith("grandes/")),
);

describe("fixtures TXT de tests/importacao", () => {
  it("encontrou os casos de TXT do acervo", () => {
    expect(casos.map((c) => c.id)).toEqual(expect.arrayContaining(["TC-003", "TC-057", "TC-066"]));
  });

  for (const caso of casos) {
    for (const v of caso.variantes) {
      it(`${caso.id} [${caso.prioridade}] ${caso.titulo}${caso.variantes.length > 1 ? ` (${v.entrada})` : ""}`, () => {
        const caminho = join(FIX, v.entrada);
        expect(existsSync(caminho)).toBe(true);
        const bytes = new Uint8Array(readFileSync(caminho));
        const t0 = performance.now();
        const obt = importarTxt({ nome: v.entrada.split("/").pop()!, bytes });
        const ms = performance.now() - t0;
        const esp = JSON.parse(readFileSync(join(FIX, v.esperado!), "utf8"));
        if (esp.resumo) {
          // TC-066: 5.000 linhas, conferidas por resumo (total, soma, primeiro e último) e em menos de 3 s
          expect("erro" in obt).toBe(false);
          if ("erro" in obt) return;
          const r = esp.resumo;
          expect(obt.itens).toHaveLength(r.total_itens);
          expect(obt.itens.reduce((s, i) => s + (i.quantidade ?? 0), 0)).toBeCloseTo(r.soma_quantidade, 2);
          expect(obt.itens[0]).toMatchObject({ linha: r.primeiro.linha, descricao: r.primeiro.descricao, quantidade: r.primeiro.quantidade, unidade: r.primeiro.unidade, nivel: r.primeiro.nivel });
          expect(obt.itens.at(-1)).toMatchObject({ linha: r.ultimo.linha, descricao: r.ultimo.descricao, quantidade: r.ultimo.quantidade, nivel: r.ultimo.nivel });
          expect(obt.origem.formato).toBe(r.formato);
          expect(obt.origem.software).toBe(r.software);
          expect(ms).toBeLessThan(3000);
          return;
        }
        expect(comparar(esp, obt)).toEqual([]);
      });
    }
  }
});

describe("casos próprios do TXT do Revit", () => {
  const enc = (t: string) => new TextEncoder().encode(t);

  it("12,50 m² vira 12.5 m2 e os acentos ficam intactos (leitura de quantidade da revisão)", () => {
    const r = importarTxt({ nome: "paredes.txt", bytes: enc("Tabela de paredes\nFamília e tipo\tÁrea\tNível\n\nParede básica: Alvenaria 14cm\t12,50 m²\tTérreo\n") });
    if ("erro" in r) throw new Error("não deveria falhar");
    expect(r.itens[0]).toMatchObject({ descricao: "Parede básica: Alvenaria 14cm", quantidade: 12.5, unidade: "m2", nivel: "Térreo" });
    expect(r.origem).toMatchObject({ formato: "txt", software: "revit", delimitador: "\t" });
  });

  it("um .txt que não é tabela (lista do WhatsApp) é recusado com orientação", () => {
    const r = importarTxt({ nome: "lista.txt", bytes: enc("Oi, preciso de:\n- 3 sacos de cimento\n- 2 latas de tinta\n") });
    expect("erro" in r && r.erro.codigo).toBe("CABECALHO_NAO_ENCONTRADO");
    expect("erro" in r && r.erro.mensagem).toMatch(/Revit|\.csv/);
  });

  it("o nível de grupo não sobrescreve o nível que a própria linha traz", () => {
    const r = importarTxt({ nome: "a.txt", bytes: enc("Tabela\nFamília e tipo\tContagem\tNível\n\nNível: Térreo\nPorta A\t2\t\nPorta B\t1\tSuperior\n") });
    if ("erro" in r) throw new Error("não deveria falhar");
    expect(r.itens.map((i) => i.nivel)).toEqual(["Térreo", "Superior"]);
  });

  it("total que bate com a soma não gera aviso; que diverge gera na linha do total", () => {
    const base = "T\nFamília e tipo\tContagem\n\nA\t6\nB\t4\n";
    const ok = importarTxt({ nome: "ok.txt", bytes: enc(base + "Total geral: 10\n") });
    const ruim = importarTxt({ nome: "ruim.txt", bytes: enc(base + "Total geral\t12\n") });
    if ("erro" in ok || "erro" in ruim) throw new Error("não deveria falhar");
    expect(ok.avisos).toEqual([]);
    expect(ruim.avisos.map((a) => `${a.codigo}@${a.linha}`)).toEqual(["TOTAL_DIVERGENTE@6"]);
  });

  it("medida em pés e polegadas não é convertida e avisa", () => {
    const r = importarTxt({ nome: "w.txt", bytes: enc("Wall Schedule\nFamily and Type\tLength\tLevel\n\nBasic Wall\t\"12' 6\"\"\"\tLevel 1\n") });
    if ("erro" in r) throw new Error("não deveria falhar");
    expect(r.itens[0]).toMatchObject({ quantidade: null, unidade: "ft-in" });
    expect(r.avisos.map((a) => a.codigo)).toContain("UNIDADE_IMPERIAL");
  });
});
