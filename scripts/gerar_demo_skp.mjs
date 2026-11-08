// Modelos esquemáticos: componentes com geometria simples, sem simular um projeto executivo.
import { readFileSync, writeFileSync } from "node:fs";
import { create } from "../frontend/node_modules/openskp/dist/index.mjs";
const dados = JSON.parse(readFileSync(new URL("../docs/arquivos-teste/demo-jurados.json", import.meta.url), "utf8"));
for (const [arquivo, itens] of [
  ["teste_1", dados.componentes],
  ["teste_2", [["Piso de porcelanato Portobello 60x60cm polido", 1], ...dados.componentes.slice(0, 3), ["Torneira cromada", 1]]],
  ["MODELO", dados.componentes],
]) {
  const modelo = create();
  const definicoes = itens.map(([nome]) => modelo.addComponentDefinition(nome, d => d.addFace([[0,0,0],[8,0,0],[8,8,0],[0,8,0]])));
  itens.forEach(([nome, qtd], linha) => {
    const def = definicoes[linha];
    for (let i=0; i<qtd; i++) modelo.addInstance(def, { translation: [i*12, linha*12, 0] });
  });
  writeFileSync(new URL(`../frontend/public/exemplos/demo/${arquivo}.skp`, import.meta.url), modelo.toBytes());
}
console.log("Três modelos SKP sintéticos gerados.");
