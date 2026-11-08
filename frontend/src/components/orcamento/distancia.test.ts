import { describe, expect, it } from "vitest";
import { distanciaDaLoja } from "./formato";

describe("distanciaDaLoja", () => {
  it("escreve em km com vírgula e avisa que é aproximada", () => {
    expect(distanciaDaLoja(4.2)).toBe("a 4,2 km de carro (aprox.)");
    expect(distanciaDaLoja(12)).toBe("a 12,0 km de carro (aprox.)");
  });
  it("sem distância válida não mostra nada", () => {
    for (const v of [null, undefined, 0, -3, Number.NaN]) expect(distanciaDaLoja(v as number | null | undefined)).toBeNull();
  });
});
