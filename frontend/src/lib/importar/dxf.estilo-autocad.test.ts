import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { lerArquivo } from "./arquivo";
import { ehErro } from "./tipos";

it("DXF estilo AutoCAD R2000 (CRLF, Windows-1252, POLYLINE antigo, INSERT em matriz)", async () => {
  const bytes = new Uint8Array(readFileSync("../tests/importacao/fixtures/modelos/autocad-r2000-1252.dxf"));
  const r = await lerArquivo({ nome: "x.dxf", bytes });
  if (ehErro(r)) throw new Error(r.erro.mensagem);
  const por = Object.fromEntries(r.itens.map((i) => [i.descricao, i.quantidade]));
  expect(por["Porta"]).toBe(6); // matriz 2x3
  expect(por["Piso (área)"]).toBe(12); // 3 x 4 m
  expect(por["Parede (comprimento)"]).toBe(24.5); // 5+6+5+6 da polilinha aberta + 2,5 da linha
});
