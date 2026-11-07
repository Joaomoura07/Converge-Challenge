// Exemplos reais. A ENTRADA sai do leitor de CSV de verdade; a RESPOSTA foi capturada do backend real
// (POST /revisao/sugestoes/completo, sem LLM) em 07/11/2026 e está em fixtures/. Se o leitor mudar a entrada,
// o primeiro teste de cada exemplo falha e a fixture precisa ser capturada de novo.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { importarCsv } from "../importar/csv";
import { importacaoParaLinhas } from "../importar/paraLinhas";
import { ehErro } from "../importar/tipos";
import { contarErros, errosPorId, estadoInicial, reduzir, type Acao, type EstadoLista, type Linha } from "../lista";
import { complementoParaLinha, paraItensRevisao } from "./aplicar";
import type { DadosRevisao, ItemParaRevisao } from "./tipos";

type Captura = { entrada: ItemParaRevisao[]; resposta: DadosRevisao };
const fixture = (nome: string): Captura => JSON.parse(readFileSync(join(__dirname, "fixtures", `${nome}.json`), "utf-8"));

function listaCasaTerrea(): Linha[] {
  const bytes = new Uint8Array(readFileSync(join(__dirname, "../../../public/exemplos/casa-terrea-aldeia.csv")));
  const r = importarCsv({ nome: "casa-terrea-aldeia.csv", bytes });
  if (ehErro(r)) throw new Error("exemplo não leu");
  let n = 0;
  return importacaoParaLinhas(r, () => `casa-${++n}`);
}

const comLista = (linhas: Linha[]): EstadoLista => ({ ...estadoInicial, linhas });
const rodar = (e: EstadoLista, acoes: Acao[]) => acoes.reduce(reduzir, e);

describe("Casa Térrea (unidades sc e br)", () => {
  const { entrada, resposta } = fixture("casa-terrea");

  it("a fixture corresponde ao que o leitor entrega hoje", () => {
    expect(paraItensRevisao(listaCasaTerrea())).toEqual(entrada);
  });

  it("o backend propôs trocar sc e br por un, e o clique aplica só isso", () => {
    const erros = resposta.erros.filter((e) => e.regra === "unidade");
    expect(erros).toHaveLength(4);
    expect(new Set(erros.map((e) => e.valor_atual))).toEqual(new Set(["sc", "br"]));

    const antes = comLista(listaCasaTerrea());
    expect(contarErros(errosPorId(antes.linhas))).toBeGreaterThanOrEqual(4); // sc/br bloqueiam o envio

    // as propostas sozinhas não mudam nada: o estado só muda no clique
    expect(antes.linhas.filter((l) => l.unidade === "sc" || l.unidade === "br")).toHaveLength(4);

    const depois = rodar(antes, erros.map((e) => ({ tipo: "aceitar_correcao", id: e.id, correcao: e.correcao! }) as Acao));
    expect(depois.linhas.filter((l) => l.unidade === "sc" || l.unidade === "br")).toHaveLength(0);
    for (const e of erros) {
      const a = e.correcao!.alteracoes[0];
      const antesL = antes.linhas.find((l) => l.id === a.item_id)!;
      const depoisL = depois.linhas.find((l) => l.id === a.item_id)!;
      expect(depoisL).toEqual({ ...antesL, unidade: "un" }); // nada além da unidade mudou
    }
    expect(depois.linhas).toHaveLength(antes.linhas.length);
  });

  it("aceitar de novo as mesmas quatro correções não muda mais nada", () => {
    const erros = resposta.erros.filter((e) => e.regra === "unidade");
    const acoes = erros.map((e) => ({ tipo: "aceitar_correcao", id: e.id, correcao: e.correcao! }) as Acao);
    const uma = rodar(comLista(listaCasaTerrea()), acoes);
    expect(rodar(uma, acoes)).toEqual(uma);
  });

  it("recusar as quatro deixa a lista idêntica", () => {
    const antes = comLista(listaCasaTerrea());
    const depois = rodar(antes, resposta.erros.map((e) => ({ tipo: "recusar_sugestao", id: e.id }) as Acao));
    expect(depois.linhas).toEqual(antes.linhas);
  });
});

describe("exemplo do João (porcelanato 48 m2 e tinta 120 m2)", () => {
  const { entrada, resposta } = fixture("joao");

  it("gera argamassa, rejunte e niveladores, além dos complementos de pintura", () => {
    const q = Object.fromEntries(resposta.complementos.map((c) => [c.descricao, c.quantidade]));
    expect(q["Argamassa colante AC-III 20 kg (saco)"]).toBe(15);
    expect(q["Rejunte 5 kg (saco)"]).toBe(5);
    expect(q["Espaçador/nivelador de piso (pacote 100 un)"]).toBe(3);
    expect(Object.keys(q)).toHaveLength(7);
    expect(resposta.erros).toEqual([]);
    expect(resposta.complementos.every((c) => c.estimativa_consumo)).toBe(true);
  });

  it("aceitar vira linha sugerida com regra, motivo, origem e estimativa de consumo; recusar não vira nada", () => {
    const base = comLista(entrada.map((i) => ({ id: i.id, descricao: i.descricao, quantidade: i.quantidade, unidade: i.unidade, categoria: i.categoria })));
    const [arg, rej, niv] = ["Argamassa", "Rejunte", "Espaçador"].map((p) => resposta.complementos.find((c) => c.descricao.startsWith(p))!);
    const e = rodar(base, [
      { tipo: "aceitar_complemento", id: arg.id, linha: complementoParaLinha(arg, "n1") },
      { tipo: "aceitar_complemento", id: niv.id, linha: complementoParaLinha(niv, "n2") },
      { tipo: "recusar_sugestao", id: rej.id },
    ]);
    expect(e.linhas.map((l) => l.descricao)).toEqual([
      "Porcelanato 90x90 acetinado", "Tinta acrilica fosca branca", arg.descricao, niv.descricao,
    ]);
    expect(e.linhas[2].sugerida).toMatchObject({ regra: "porcelanato", origemLinhas: [1], estimativaConsumo: true });
    expect(e.linhas[2].sugerida!.motivo).toMatch(/48 m²/);
    expect(e.linhas[2]).toMatchObject({ quantidade: "15", unidade: "un" });
    expect(e.decisoes[rej.id]).toBe("recusada");
    expect(contarErros(errosPorId(e.linhas))).toBe(0); // linhas aceitas são válidas
  });
});
