import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { lerArquivo } from "./arquivo";
import { decodificarStep } from "./ifc";
import { ehErro, type Importacao } from "./tipos";

const DIR = "../tests/importacao/fixtures/modelos/ifc";
const ler = async (arquivo: string, bytes?: Uint8Array) =>
  lerArquivo({ nome: arquivo, bytes: bytes ?? new Uint8Array(readFileSync(`${DIR}/${arquivo}`)) });
const ok = (r: Awaited<ReturnType<typeof ler>>): Importacao => {
  if (ehErro(r)) throw new Error(r.erro.mensagem);
  return r;
};

describe("leitor de IFC", () => {
  it("ifc-01: confere o resultado esperado escrito à mão (ifc-esperado.json)", async () => {
    const esperado = JSON.parse(readFileSync(`${DIR}/ifc-esperado.json`, "utf8"))["ifc-01-apto-minimo.ifc"];
    const r = ok(await ler("ifc-01-apto-minimo.ifc"));
    expect(r.origem.formato).toBe("ifc");
    expect(r.itens.map((i) => ({ descricao: i.descricao, quantidade: i.quantidade, unidade: i.unidade }))).toEqual(
      esperado.itens_esperados_no_futuro.map((i: { descricao: string; quantidade: number; unidade: string }) => ({
        descricao: i.descricao,
        quantidade: i.quantidade,
        unidade: i.unidade,
      })),
    );
    expect(r.itens).toHaveLength(esperado.total_linhas);
    expect(r.itens.every((i) => i.nivel === "Terreo")).toBe(true);
    expect(r.avisos).toEqual([]);
    const portas = r.itens.find((i) => i.descricao === "Porta 80")!;
    expect(portas.extras.origem_ifc).toMatchObject({ classe: "IFCDOOR", elementos: 2, esquema: "IFC4" });
  });

  it("ifc-02: milímetros, material, acentos codificados, pavimento por agregação e área ausente", async () => {
    const r = ok(await ler("ifc-02-casa-mm-material.ifc"));
    const por = Object.fromEntries(r.itens.map((i) => [i.descricao, i]));
    expect(por["Piso Cozinha (área)"]).toMatchObject({ quantidade: 12.5, unidade: "m2", nivel: "Térreo" });
    // dois revestimentos com o mesmo material: só um declara área -> soma 8 e avisa
    expect(por["Revestimento cerâmico (área) — Porcelanato 60x60"]).toMatchObject({
      quantidade: 8,
      unidade: "m2",
      nivel: "Térreo",
      categoria: "Revestimentos",
    });
    // laje sem quantidade: entra sem medida, com aviso
    expect(por["Contrapiso (área)"].quantidade).toBeNull();
    // 4200 mm -> 4,2 m
    expect(por["Guarda-corpo vidro (comprimento)"]).toMatchObject({ quantidade: 4.2, unidade: "m", nivel: "Superior" });
    // a mesma janela em pavimentos diferentes vira duas linhas
    expect(r.itens.filter((i) => i.descricao === "Janela 120x100").map((i) => i.nivel).sort()).toEqual(["Superior", "Térreo"]);
    expect(por["Spot LED d'Embutir"]).toMatchObject({ quantidade: 1, unidade: "un", categoria: "Elétrica" });
    // parede sem nome usa o nome da classe
    expect(por["Parede (área)"].quantidade).toBeNull();
    expect(r.avisos.filter((a) => a.codigo === "QUANTIDADE_AUSENTE")).toHaveLength(3);
  });

  it("ifc-03: área só nas propriedades (padrão ArchiCAD), em texto com vírgula ou número, preferindo a líquida", async () => {
    const r = ok(await ler("ifc-03-areas-em-propriedades.ifc"));
    const por = Object.fromEntries(r.itens.map((i) => [i.descricao, i]));
    // '63,8' em IFCLABEL (texto com vírgula decimal)
    expect(por["Piso 119 (área)"]).toMatchObject({ quantidade: 63.8, unidade: "m2", nivel: "1. korrus" });
    expect((por["Piso 119 (área)"].extras.origem_ifc as { area_da_propriedade?: string }).area_da_propriedade).toBe("120_Pindala");
    // líquida (5,8) vence a bruta (7,1)
    expect(por["Piso 53-3 (área)"].quantidade).toBe(5.8);
    // quantidade declarada vence a propriedade
    expect(por["Piso 200 (área)"].quantidade).toBe(1230);
    // parede: propriedade de área vazia e "Projected Component/Skin Area" (de camada) não contam
    expect(por["ARVUND-01 (área)"].quantidade).toBeNull();
    expect(r.avisos.filter((a) => a.codigo === "QUANTIDADE_AUSENTE")).toHaveLength(1);
  });

  it("recusa vazio, não-IFC, truncado e IFCZIP, com orientação", async () => {
    const vazio = await ler("a.ifc", new Uint8Array());
    expect(ehErro(vazio) && vazio.erro.codigo).toBe("ARQUIVO_VAZIO");
    const naoIfc = await ler("a.ifc", new TextEncoder().encode("isto não é um modelo"));
    expect(ehErro(naoIfc) && naoIfc.erro.codigo).toBe("FORMATO_INVALIDO");
    const inteiro = readFileSync(`${DIR}/ifc-01-apto-minimo.ifc`, "utf8");
    const truncado = await ler("a.ifc", new TextEncoder().encode(inteiro.slice(0, inteiro.length / 2)));
    expect(ehErro(truncado) && truncado.erro.codigo).toBe("ARQUIVO_CORROMPIDO");
    const zip = await ler("a.ifc", new Uint8Array([0x50, 0x4b, 3, 4, 0, 0]));
    expect(ehErro(zip) && zip.erro.mensagem).toMatch(/compactado/);
    const ifczip = await ler("a.ifczip", new Uint8Array([0x50, 0x4b, 3, 4]));
    expect(ehErro(ifczip)).toBe(true);
  });

  it("decodifica escapes do STEP", () => {
    expect(decodificarStep("Cer\\X2\\00E2\\X0\\mica")).toBe("Cerâmica");
    expect(decodificarStep("Sal\\X\\E3o")).toBe("Salão");
  });
});
