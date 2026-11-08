import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { errosPorId, contarErros, reduzir, estadoInicial } from "../lista";
import { importarCsv } from "./csv";
import { EXEMPLOS } from "./exemplos";
import { importacaoParaLinhas, quantidadeParaTexto } from "./paraLinhas";
import { ehErro } from "./tipos";

const PUBLICO = join(__dirname, "../../../public");
let contador = 0;
const novoId = () => `id-${++contador}`;

function lerExemplo(arquivo: string) {
  const bytes = new Uint8Array(readFileSync(join(PUBLICO, arquivo)));
  return importarCsv({ nome: arquivo.split("/").pop()!, bytes });
}

describe("três exemplos passam pelo mesmo leitor dos uploads", () => {
  const esperado: Record<string, { codificacao: string; delimitador: string; itens: number }> = {
    "apto-boa-viagem": { codificacao: "utf-8", delimitador: ";", itens: 5 },
    "casa-terrea-aldeia": { codificacao: "utf-8", delimitador: ";", itens: 5 },
    "escritorio-ilha-do-leite": { codificacao: "utf-8", delimitador: ";", itens: 5 },
  };

  for (const ex of EXEMPLOS) {
    it(`${ex.rotulo}: lê sem erro, com a codificação e o separador certos`, () => {
      const r = lerExemplo(ex.arquivo);
      expect(ehErro(r)).toBe(false);
      if (ehErro(r)) return;
      expect(r.origem.codificacao).toBe(esperado[ex.id].codificacao);
      expect(r.origem.delimitador).toBe(esperado[ex.id].delimitador);
      expect(r.itens).toHaveLength(esperado[ex.id].itens);
      // acentos intactos (nenhum "Ã" nem "�")
      const tudo = JSON.stringify(r.itens);
      expect(tudo).not.toMatch(/Ã|�/);
    });

    it(`${ex.rotulo}: vira linhas da lista com a linha de origem`, () => {
      const r = lerExemplo(ex.arquivo);
      if (ehErro(r)) throw new Error("não deveria falhar");
      const linhas = importacaoParaLinhas(r, novoId);
      expect(linhas).toHaveLength(r.itens.length);
      expect(linhas[0].linhaOrigem).toBe(r.itens[0].linha);
      expect(new Set(linhas.map((l) => l.id)).size).toBe(linhas.length);
      const estado = reduzir(estadoInicial, { tipo: "importar", linhas, como: "substituir" });
      // o relatório fica no registro de testes: quantos erros restam para o arquiteto
      console.log(`${ex.rotulo}: ${linhas.length} linhas, ${contarErros(errosPorId(estado.linhas))} campos com erro, ${r.avisos.length} avisos`);
    });
  }
});

describe("conversão para a lista", () => {
  it("quantidade vira texto com vírgula e null vira vazio", () => {
    expect(quantidadeParaTexto(12.5)).toBe("12,5");
    expect(quantidadeParaTexto(1234)).toBe("1234");
    expect(quantidadeParaTexto(null)).toBe("");
  });

  it("acrescentar mantém as linhas editadas; substituir troca tudo", () => {
    const r = lerExemplo(EXEMPLOS[2].arquivo);
    if (ehErro(r)) throw new Error("não deveria falhar");
    const novas = importacaoParaLinhas(r, novoId);
    const base = reduzir(estadoInicial, { tipo: "importar", linhas: novas.slice(0, 2), como: "substituir" });
    const editado = reduzir(base, { tipo: "editar", id: base.linhas[0].id, campo: "descricao", valor: "EDITADO" });
    const somado = reduzir(editado, { tipo: "importar", linhas: novas.slice(2, 4), como: "acrescentar" });
    expect(somado.linhas).toHaveLength(4);
    expect(somado.linhas[0].descricao).toBe("EDITADO");
    const trocado = reduzir(somado, { tipo: "importar", linhas: novas.slice(0, 1), como: "substituir" });
    expect(trocado.linhas).toHaveLength(1);
  });
});
