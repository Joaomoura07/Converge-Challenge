import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { lerArquivo } from "./arquivo";
import { ehErro } from "./tipos";

const ler = (n: string) => new Uint8Array(readFileSync(`../tests/importacao/fixtures/modelos/${n}`));

describe("leitor DXF", () => {
  it("conta blocos, soma área e comprimento em metros", async () => {
    const r = await lerArquivo({ nome: "planta-cm.dxf", bytes: ler("planta-cm.dxf") });
    if (ehErro(r)) throw new Error(r.erro.mensagem);
    const por = Object.fromEntries(r.itens.map((i) => [i.descricao, i]));
    expect(por["Porta"].quantidade).toBe(2);
    expect(por["Porta"].unidade).toBe("un");
    expect(por["Piso (área)"].quantidade).toBe(20);
    expect(por["Piso (área)"].unidade).toBe("m2");
    expect(por["Parede (comprimento)"].quantidade).toBe(9);
    expect(por["Porta"].extras).toHaveProperty("origem_dxf");
    expect(r.origem.formato).toBe("dxf");
  });
  it("sem unidade do desenho, medidas entram sem quantidade e com aviso", async () => {
    const r = await lerArquivo({ nome: "planta-sem-unidade.dxf", bytes: ler("planta-sem-unidade.dxf") });
    if (ehErro(r)) throw new Error(r.erro.mensagem);
    expect(r.itens.find((i) => i.descricao === "Piso (área)")?.quantidade).toBeNull();
    expect(r.itens.find((i) => i.descricao === "Porta")?.quantidade).toBe(2);
    expect(r.avisos.some((a) => a.codigo === "QUANTIDADE_AUSENTE")).toBe(true);
  });
  it("recusa vazio, corrompido e DWG com orientação", async () => {
    expect(ehErro(await lerArquivo({ nome: "a.dxf", bytes: new Uint8Array() }))).toBe(true);
    const lixo = await lerArquivo({ nome: "a.dxf", bytes: new TextEncoder().encode("isso nao e dxf") });
    expect(ehErro(lixo)).toBe(true);
    const dwg = await lerArquivo({ nome: "a.dwg", bytes: new Uint8Array([65, 67, 49, 48]) });
    expect(ehErro(dwg) && dwg.erro.mensagem).toContain("DXF");
  });
});
