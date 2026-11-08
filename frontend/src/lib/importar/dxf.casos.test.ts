import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { lerArquivo } from "./arquivo";
import { ehErro } from "./tipos";

const DIR = "../tests/importacao/fixtures/modelos/casos";
const esperado = JSON.parse(readFileSync(`${DIR}/dxf-esperado.json`, "utf8")) as Record<string, any>;

describe("DXF: casos com resultado esperado calculado à mão", () => {
  for (const [arquivo, esp] of Object.entries(esperado).filter(([k]) => k.endsWith(".dxf"))) {
    it(arquivo, async () => {
      const r = await lerArquivo({ nome: arquivo, bytes: new Uint8Array(readFileSync(`${DIR}/${arquivo}`)) });
      if (esp.erro) {
        expect(ehErro(r) && r.erro.codigo).toBe(esp.erro);
        return;
      }
      if (ehErro(r)) throw new Error(r.erro.mensagem);
      expect(r.itens.map((i) => ({ linha: i.linha, descricao: i.descricao, categoria: i.categoria, quantidade: i.quantidade, unidade: i.unidade })))
        .toEqual(esp.itens.map((i: any) => ({ linha: i.linha, descricao: i.descricao, categoria: i.categoria, quantidade: i.quantidade, unidade: i.unidade })));
      expect(r.avisos.map((a) => ({ linha: a.linha, codigo: a.codigo }))).toEqual(esp.avisos);
    });
  }
});
