/**
 * Endereço da API a partir de NEXT_PUBLIC_API_URL, tolerante ao jeito como a variável foi digitada na Vercel.
 *
 * Medido em 07/11: a variável foi salva como "orca-api-x7k2.vercel.app" (sem https://). O navegador trata isso como
 * caminho do próprio site e a revisão chamava https://<site>/orca-api-x7k2.vercel.app/revisao/... (404).
 * Aqui: tira espaços, aspas e barras do fim; sem protocolo, usa https:// (http:// só para localhost).
 * Vazio continua vazio: quem chama decide o que fazer sem API.
 */
export function normalizarApiUrl(bruto: string | null | undefined): string {
  let url = (bruto ?? "").trim().replace(/^["']+|["']+$/g, "").trim().replace(/\/+$/, "");
  if (url && !/^https?:\/\//i.test(url)) {
    url = (/^(localhost|127\.0\.0\.1|\[::1\])(:|$)/i.test(url) ? "http://" : "https://") + url;
  }
  return url;
}
