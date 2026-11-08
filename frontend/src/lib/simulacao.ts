// Modo gravação de vídeo. Ligue com `?simular=1` em qualquer página (fica lembrado neste navegador) e desligue com
// `?simular=0`. Muda só o endereço de duas chamadas lentas: "Enviar para a IA" e "Responder"/"Pesquisar de novo"
// passam a usar /simulacao/..., que reproduz em segundos pesquisas REAIS já feitas dos mesmos itens (src/simulacao.py).
// Revisão, Realtime, estimativa, Excel, PDF e links seguem o caminho de sempre. A tela não mostra nenhum aviso.

const CHAVE = "orca-simulacao";
export const PREFIXO_SIMULACAO = "/simulacao";

export function simulacaoAtiva(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const pedido = new URLSearchParams(window.location.search).get("simular");
    if (pedido === "1") window.localStorage.setItem(CHAVE, "1");
    if (pedido === "0") window.localStorage.removeItem(CHAVE);
    return window.localStorage.getItem(CHAVE) === "1";
  } catch {
    return false;
  }
}

/** Caminho da API: com o modo gravação ligado, a versão /simulacao/... do mesmo pedido. */
export function caminhoSimulavel(caminho: string): string {
  return simulacaoAtiva() ? `${PREFIXO_SIMULACAO}${caminho}` : caminho;
}
