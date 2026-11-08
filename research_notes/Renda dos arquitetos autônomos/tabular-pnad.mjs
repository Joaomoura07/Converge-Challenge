import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

// Offsets do input_PNADC_trimestral.txt, contado a partir de 1 no original.
const layout = {
  upa: [12, 9], estrato: [21, 7], peso: [50, 15], ocupacao: [152, 4],
  posicaoOriginal: [156, 1], ocupada: [410, 1], posicao: [417, 2],
  dinheiro: [200, 8], produtos: [210, 8], renda: [427, 8],
};

function campo(linha, nome) {
  const [inicio, largura] = layout[nome];
  return linha.slice(inicio - 1, inicio - 1 + largura).trim();
}

function grupo(posicao) {
  if (posicao === '09') return 'contaPropria';
  if (posicao === '08') return 'empregador';
  if (/^0[1-7]$/.test(posicao)) return 'empregado';
  return 'outro';
}

const [arquivo, entrada] = process.argv.slice(2);
if (!arquivo || !entrada) throw Error('Informe o ZIP oficial e o nome da entrada TXT.');
const extracao = spawn('tar.exe', ['-xOf', arquivo, entrada], { stdio: ['ignore', 'pipe', 'inherit'] });
const encerramento = new Promise((resolve, reject) => {
  extracao.on('error', reject);
  extracao.on('close', code => code === 0 ? resolve() : reject(Error(`tar retornou ${code}`)));
});

const estratos = new Map();
const totais = {};
const rendasPorGrupo = {};
const controles = {
  linhas: 0, ocupadasPonderadas: 0, comRendaPonderadas: 0,
  massaRendaTrabalhoPrincipal: 0, divergenciasPosicao: 0, divergenciasRenda: 0,
};

function novoTotal() {
  return { n: 0, nComRenda: 0, ocupados: 0, ocupadosComRenda: 0, massa: 0 };
}

function acrescentar(grupos, chave, peso, renda) {
  const total = grupos[chave] ??= novoTotal();
  total.n++;
  total.ocupados += peso;
  if (renda === null) return;
  total.nComRenda++;
  total.ocupadosComRenda += peso;
  total.massa += peso * renda;
}

for await (const linha of createInterface({ input: extracao.stdout, crlfDelay: Infinity })) {
  controles.linhas++;
  const estrato = campo(linha, 'estrato');
  const upa = campo(linha, 'upa');
  if (!estratos.has(estrato)) estratos.set(estrato, new Map());
  const conglomerados = estratos.get(estrato);
  if (!conglomerados.has(upa)) conglomerados.set(upa, {});
  if (campo(linha, 'ocupada') !== '1') continue;

  const peso = Number(campo(linha, 'peso'));
  if (!(peso > 0)) throw Error(`Peso inválido na linha ${controles.linhas}`);
  const bruto = campo(linha, 'renda');
  const renda = bruto === '' ? null : Number(bruto);
  controles.ocupadasPonderadas += peso;
  if (renda !== null) {
    if (!(renda >= 0)) throw Error(`Renda inválida na linha ${controles.linhas}`);
    controles.comRendaPonderadas += peso;
    controles.massaRendaTrabalhoPrincipal += peso * renda;
  }

  if (campo(linha, 'ocupacao') !== '2161') continue;
  const posicao = grupo(campo(linha, 'posicao'));
  const posicaoOriginal = campo(linha, 'posicaoOriginal');
  const esperado = { '1': 'empregado', '2': 'empregado', '3': 'empregado',
    '4': 'empregado', '5': 'empregador', '6': 'contaPropria', '7': 'outro' }[posicaoOriginal];
  if (esperado !== posicao) controles.divergenciasPosicao++;
  if (renda !== null && renda !== Number(campo(linha, 'dinheiro')) + Number(campo(linha, 'produtos'))) {
    controles.divergenciasRenda++;
  }
  const chaves = ['todos', posicao];
  if (posicao === 'empregado' || posicao === 'empregador') chaves.push('naoContaPropria');
  for (const chave of chaves) {
    acrescentar(totais, chave, peso, renda);
    acrescentar(conglomerados.get(upa), chave, peso, renda);
    if (renda !== null) (rendasPorGrupo[chave] ??= []).push({ peso, renda });
  }
}

await encerramento;
if (controles.divergenciasPosicao || controles.divergenciasRenda || !totais.todos) {
  throw Error(`Verificação de layout falhou: ${JSON.stringify(controles)}`);
}

// Linearização de Taylor de primeira etapa, sem correção de população finita.
// Para grupos, preservar os conglomerados fora do domínio com contribuição zero.
function erroPadraoEstratificado(contribuicao) {
  let variancia = 0;
  for (const conglomerados of estratos.values()) {
    const n = conglomerados.size;
    if (n < 2) continue;
    const residuos = [...conglomerados.values()].map(contribuicao);
    const media = residuos.reduce((a, b) => a + b, 0) / n;
    variancia += n / (n - 1) * residuos.reduce((s, x) => s + (x - media) ** 2, 0);
  }
  return Math.sqrt(variancia);
}

function estimativa(chave, medida, base, denominadorMedida) {
  const numerador = grupos => grupos[chave]?.[medida] ?? 0;
  const denominador = base ? grupos => grupos[base]?.[denominadorMedida] ?? 0 : null;
  const divisor = denominador ? denominador(totais) : 1;
  if (!divisor) return null;
  const valor = numerador(totais) / divisor;
  const erro = erroPadraoEstratificado(grupos => (
    (numerador(grupos) - (denominador ? valor * denominador(grupos) : 0)) / divisor
  ));
  return { valor, erroPadrao: erro, cv: erro / valor, ic95: [valor - 1.96 * erro, valor + 1.96 * erro] };
}

function mediana(chave) {
  const observacoes = rendasPorGrupo[chave];
  if (!observacoes) return null;
  observacoes.sort((a, b) => a.renda - b.renda);
  const metade = totais[chave].ocupadosComRenda / 2;
  let acumulado = 0;
  for (const { peso, renda } of observacoes) {
    acumulado += peso;
    if (acumulado >= metade) return renda;
  }
}

const resultados = Object.fromEntries(Object.entries(totais).map(([chave, total]) => [chave, {
  ...total,
  participacaoOcupados: estimativa(chave, 'ocupados', 'todos', 'ocupados'),
  mediaComRenda: estimativa(chave, 'massa', chave, 'ocupadosComRenda'),
  medianaComRenda: mediana(chave),
  massaEstimativa: estimativa(chave, 'massa'),
  participacaoMassa: estimativa(chave, 'massa', 'todos', 'massa'),
}]));

const razaoMedia = resultados.contaPropria.mediaComRenda.valor / resultados.naoContaPropria.mediaComRenda.valor;
const diferencaMedia = resultados.contaPropria.mediaComRenda.valor - resultados.naoContaPropria.mediaComRenda.valor;
function residuoMedia(grupos, chave) {
  const total = resultados[chave];
  const grupo = grupos[chave];
  return ((grupo?.massa ?? 0) - total.mediaComRenda.valor * (grupo?.ocupadosComRenda ?? 0)) / total.ocupadosComRenda;
}
const erroDiferencaMedia = erroPadraoEstratificado(
  grupos => residuoMedia(grupos, 'contaPropria') - residuoMedia(grupos, 'naoContaPropria'),
);
const icDiferencaMedia = [diferencaMedia - 1.96 * erroDiferencaMedia, diferencaMedia + 1.96 * erroDiferencaMedia];
const razaoMassa = estimativa('contaPropria', 'massa', 'naoContaPropria', 'massa');
const estratosUnicos = [...estratos.values()].filter(ups => ups.size < 2).length;
console.log(JSON.stringify({ controles, desenho: { estratos: estratos.size, estratosUnicos },
  resultados, razaoMedia, diferencaMedia, icDiferencaMedia, razaoMassa }, null, 2));
