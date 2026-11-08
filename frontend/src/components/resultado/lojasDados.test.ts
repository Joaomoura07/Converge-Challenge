import { describe, expect, it } from "vitest";
import { trajeto } from "./lojasDados";

describe("trajeto até a loja", () => {
  it("km com vírgula e tempo aproximado de carro", () => {
    expect(trajeto({ km: 1.4, minutos_aprox: 3 })).toBe("a 1,4 km · cerca de 3 min de carro");
  });
  it("sem tempo mostra só a distância; sem distância não mostra nada", () => {
    expect(trajeto({ km: 6.1, minutos_aprox: null })).toBe("a 6,1 km");
    expect(trajeto({ km: null, minutos_aprox: null })).toBeNull();
    expect(trajeto({ km: 0, minutos_aprox: 0 })).toBeNull();
  });
});
