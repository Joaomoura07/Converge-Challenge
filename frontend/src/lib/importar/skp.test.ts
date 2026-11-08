import { create, type Point3 } from "openskp";
import { expect, it } from "vitest";
import { montarCorpo } from "../envio/corpo";
import { lerArquivo } from "./arquivo";
import { importacaoParaLinhas } from "./paraLinhas";
import { ehErro, LIMITE_BYTES } from "./tipos";

it("lê um binário SKP, conta ocorrências colocadas e envia a quantidade revisada", async () => {
  const modelo = create();
  const face: Point3[] = [[0, 0, 0], [32, 0, 0], [32, 0, 80], [0, 0, 80]];
  const porta = modelo.addComponentDefinition("Porta de madeira", def => def.addFace(face));
  modelo.addComponentDefinition("Janela não inserida", def => def.addFace(face));
  modelo.addGroup(grupo => {
    grupo.addInstance(porta);
    grupo.addInstance(porta, { translation: [40, 0, 0] });
    grupo.addInstance(porta, { translation: [80, 0, 0], hidden: true });
  }, { name: "Térreo" });

  const resultado = await lerArquivo({ nome: "obra.SKP", bytes: modelo.toBytes() });
  if (ehErro(resultado)) throw new Error(resultado.erro.mensagem);
  expect(resultado.origem).toMatchObject({ formato: "skp", software: "sketchup" });
  expect(resultado.itens).toMatchObject([
    { descricao: "Porta de madeira", quantidade: 2, unidade: "un", categoria: "Esquadrias" },
  ]);
  expect(resultado.itens[0].extras.origem_skp).toMatchObject({ ocorrencias: 2 });
  const linhas = importacaoParaLinhas(resultado, () => "item-1");
  linhas[0].quantidade = "3";
  expect(montarCorpo({
    orcamentoId: "11111111-1111-4111-8111-111111111111",
    obra: { nome: "Teste SKP", cep: "51020000", orcamentoCliente: 1000 },
    linhas,
    modo: "skp",
  })).toMatchObject({ origem: { modo: "skp" }, itens: [{ quantidade: 3, origem_item: "arquivo" }] });
});

it("deixa um grupo de piso pendente quando a geometria não informa a medida de compra", async () => {
  const modelo = create();
  const parede = modelo.addComponentDefinition("Parede de alvenaria", def =>
    def.addFace([[0, 0, 0], [120, 0, 0], [120, 0, 100], [0, 0, 100]]));
  modelo.addGroup(grupo => grupo.addFace([[0, 0, 0], [120, 0, 0], [120, 120, 0], [0, 120, 0]]), { name: "Piso da sala" });
  modelo.addInstance(parede);
  const resultado = await lerArquivo({ nome: "obra.skp", bytes: modelo.toBytes() });
  if (ehErro(resultado)) throw new Error(resultado.erro.mensagem);
  expect(resultado.itens).toHaveLength(2);
  expect(resultado.itens).toEqual(expect.arrayContaining([
    expect.objectContaining({ descricao: "Piso da sala", quantidade: null, unidade: null }),
    expect.objectContaining({ descricao: "Parede de alvenaria", quantidade: null, unidade: null }),
  ]));
  expect(resultado.avisos.map(a => a.codigo)).toEqual(["QUANTIDADE_AUSENTE", "QUANTIDADE_AUSENTE"]);
});

it("recusa arquivo vazio, formato incorreto, contêiner truncado e arquivo acima do limite", async () => {
  for (const [bytes, codigo] of [
    [new Uint8Array(), "ARQUIVO_VAZIO"],
    [new TextEncoder().encode("isto é texto"), "FORMATO_INVALIDO"],
    [new Uint8Array([255, 254, 255, 14]), "ARQUIVO_CORROMPIDO"],
    [new Uint8Array(LIMITE_BYTES + 1), "ARQUIVO_GRANDE_DEMAIS"],
  ] as const) {
    expect(await lerArquivo({ nome: "obra.skp", bytes })).toMatchObject({ erro: { codigo } });
  }
});
