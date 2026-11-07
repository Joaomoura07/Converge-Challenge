// Validação da tela Nova obra e do cadastro manual.
// Funções puras: recebem o texto digitado e devolvem o valor limpo ou uma mensagem.

export type Resultado<T> = { ok: true; valor: T } | { ok: false; erro: string };

export const UNIDADES = ["m", "m2", "m3", "un", "kg", "l", "cm", "mm"] as const;
export type Unidade = (typeof UNIDADES)[number];

const LIMITE_REAIS = 1_000_000_000_000; // 1 trilhão, só para barrar lixo
const LIMITE_QUANTIDADE = 1_000_000_000;

/** Interpreta número em formato brasileiro sem usar substituição global de pontos e vírgulas. */
function lerNumeroBR(
  bruto: string,
  opcoes: { maxDecimais: number; pontoUnicoMilhar: boolean },
): Resultado<number> {
  const t = bruto.replace(/\s/g, "");
  if (t === "") return { ok: false, erro: "Preencha o valor." };
  if (/^-/.test(t)) return { ok: false, erro: "O valor não pode ser negativo." };
  if (!/^[\d.,]+$/.test(t)) return { ok: false, erro: "Use apenas números, ponto e vírgula." };

  let inteiro: string;
  let decimal = "";

  if (t.includes(",")) {
    const partes = t.split(",");
    if (partes.length > 2) return { ok: false, erro: "Use uma única vírgula para os decimais." };
    const [parteInteira, parteDecimal] = partes;
    // Antes da vírgula, pontos só como separador de milhar (1.234.567).
    if (parteInteira.includes(".") && !/^\d{1,3}(\.\d{3})+$/.test(parteInteira)) {
      return { ok: false, erro: "Pontos de milhar fora do lugar. Exemplo: 1.234,50." };
    }
    inteiro = parteInteira.replace(/\./g, "");
    decimal = parteDecimal;
  } else if (t.includes(".")) {
    if (/^\d{1,3}(\.\d{3})+$/.test(t)) {
      // "20.000" lê-se como milhar; "1.234" é ambíguo para quantidades.
      if (!opcoes.pontoUnicoMilhar) {
        return { ok: false, erro: 'Ambíguo: escreva "1,234" para decimal ou "1234" para milhar.' };
      }
      inteiro = t.replace(/\./g, "");
    } else if (/^\d+\.\d+$/.test(t)) {
      [inteiro, decimal] = t.split(".");
    } else {
      return { ok: false, erro: "Formato de número inválido." };
    }
  } else {
    inteiro = t;
  }

  if (inteiro === "") inteiro = "0";
  if (!/^\d+$/.test(inteiro) || (decimal !== "" && !/^\d+$/.test(decimal))) {
    return { ok: false, erro: "Formato de número inválido." };
  }
  if (decimal.length > opcoes.maxDecimais) {
    return {
      ok: false,
      erro: `No máximo ${opcoes.maxDecimais} casa${opcoes.maxDecimais > 1 ? "s" : ""} decimal${opcoes.maxDecimais > 1 ? "is" : ""}.`,
    };
  }
  const numero = Number(decimal ? `${inteiro}.${decimal}` : inteiro);
  if (!Number.isFinite(numero)) return { ok: false, erro: "Número inválido." };
  return { ok: true, valor: numero };
}

/** CEP: texto de 8 dígitos depois de tirar a máscara. Preserva zero inicial. */
export function validarCep(bruto: string): Resultado<string> {
  const limpo = bruto.trim().replace(/[\s.\-]/g, "");
  if (limpo === "") return { ok: false, erro: "Informe o CEP." };
  if (!/^\d+$/.test(limpo)) return { ok: false, erro: "O CEP deve ter apenas números." };
  if (limpo.length !== 8) return { ok: false, erro: "O CEP deve ter 8 dígitos." };
  return { ok: true, valor: limpo };
}

export function formatarCep(cep8: string): string {
  return /^\d{8}$/.test(cep8) ? `${cep8.slice(0, 5)}-${cep8.slice(5)}` : cep8;
}

/** Orçamento do cliente em reais. Aceita "20.000,50", "20000,5", "R$ 20.000". */
export function validarReais(bruto: string): Resultado<number> {
  const texto = bruto.trim().replace(/^R\$\s*/i, "");
  const r = lerNumeroBR(texto, { maxDecimais: 2, pontoUnicoMilhar: true });
  if (!r.ok) return r;
  if (r.valor <= 0) return { ok: false, erro: "O orçamento deve ser maior que zero." };
  if (r.valor >= LIMITE_REAIS) return { ok: false, erro: "Valor alto demais." };
  return r;
}

export function validarNomeObra(bruto: string): Resultado<string> {
  const nome = bruto.trim().replace(/\s+/g, " ");
  if (nome === "") return { ok: false, erro: "Dê um nome à obra." };
  if (nome.length > 120) return { ok: false, erro: "Use até 120 caracteres." };
  return { ok: true, valor: nome };
}

/** Quantidade: vírgula decimal vira ponto; vazio, zero, negativo e texto são recusados. */
export function validarQuantidade(bruto: string): Resultado<number> {
  const r = lerNumeroBR(bruto, { maxDecimais: 3, pontoUnicoMilhar: false });
  if (!r.ok) return r;
  if (r.valor <= 0) return { ok: false, erro: "A quantidade deve ser maior que zero." };
  if (r.valor > LIMITE_QUANTIDADE) return { ok: false, erro: "Quantidade alta demais." };
  return r;
}

/** Normaliza a unidade ("M²" → "m2") e confere contra a lista oficial. */
export function validarUnidade(bruto: string): Resultado<Unidade> {
  const t = bruto
    .trim()
    .toLowerCase()
    .replace(/²/g, "2")
    .replace(/³/g, "3");
  if (t === "") return { ok: false, erro: "Escolha a unidade." };
  if ((UNIDADES as readonly string[]).includes(t)) return { ok: true, valor: t as Unidade };
  return { ok: false, erro: `Unidade desconhecida. Use: ${UNIDADES.join(", ")}.` };
}

export function validarDescricao(bruto: string): Resultado<string> {
  const d = bruto.trim().replace(/\s+/g, " ");
  if (d === "") return { ok: false, erro: "Descreva o material." };
  if (d.length > 300) return { ok: false, erro: "Use até 300 caracteres." };
  return { ok: true, valor: d };
}

/** UUID v4 para o orcamento_id. Usa crypto.randomUUID; fallback para contexto não seguro (http). */
export function gerarUuid(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  const b = c.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
