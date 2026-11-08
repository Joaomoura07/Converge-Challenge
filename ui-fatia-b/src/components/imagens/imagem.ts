/** Também atende fotos antigas já salvas no banco. Não altera o endereço do produto. */
export function normalizarImagem(valor?: string | null): string | null {
  if (!valor?.trim()) return null;
  try {
    const url = new URL(valor.trim().startsWith("//") ? `https:${valor.trim()}` : valor.trim());
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    url.protocol = "https:";
    if (url.hostname === "mlcdn.com.br" || url.hostname.endsWith(".mlcdn.com.br")) {
      url.pathname = url.pathname.replace(/(?:\{w\}|%7bw%7d)x(?:\{h\}|%7bh%7d)/gi, "600x600");
    }
    return url.href;
  } catch {
    return null;
  }
}

export type DesenhoMaterial = "pintura" | "piso" | "hidraulica" | "luz" | "porta" | "material";
export function desenhoMaterial(nome: string): DesenhoMaterial {
  const texto = nome.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (/tinta|selador|verniz|pintura/.test(texto)) return "pintura";
  if (/piso|porcelanato|revestimento|ceramica|azulejo/.test(texto)) return "piso";
  if (/torneira|cuba|chuveiro|ducha|tubo|conexao|hidraulica/.test(texto)) return "hidraulica";
  if (/lampada|luminaria|led|pendente|iluminacao/.test(texto)) return "luz";
  if (/porta|janela|esquadria/.test(texto)) return "porta";
  return "material";
}
