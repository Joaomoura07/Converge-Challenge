import { describe, expect, it } from "vitest";

import { normalizarApiUrl } from "./apiUrl";
import { urlExportar } from "@/components/resultado/resultado";

describe("normalizarApiUrl", () => {
  it.each([
    ["orca-api-x7k2.vercel.app", "https://orca-api-x7k2.vercel.app"],          // o caso real de 07/11
    ["https://orca-api-x7k2.vercel.app/", "https://orca-api-x7k2.vercel.app"],
    [' "https://orca-api-x7k2.vercel.app" ', "https://orca-api-x7k2.vercel.app"],
    ["http://localhost:8000", "http://localhost:8000"],
    ["localhost:8000", "http://localhost:8000"],
    ["127.0.0.1:8010/", "http://127.0.0.1:8010"],
    ["HTTPS://API.EXEMPLO.COM", "HTTPS://API.EXEMPLO.COM"],
    ["", ""],
    [undefined, ""],
  ])("%s → %s", (bruto, esperado) => {
    expect(normalizarApiUrl(bruto)).toBe(esperado);
  });

  it("o link do Excel usa a mesma regra", () => {
    expect(urlExportar("abc", "orca-api-x7k2.vercel.app")).toBe("https://orca-api-x7k2.vercel.app/orcamentos/abc/exportar.xlsx");
    expect(urlExportar("abc", "")).toBeNull();
  });
});
