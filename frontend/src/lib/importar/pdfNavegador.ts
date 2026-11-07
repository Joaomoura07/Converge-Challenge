// PDF.js no NAVEGADOR: carregado sob demanda (só quando alguém envia um PDF) e com o worker da MESMA versão do pacote
// (pdfjs-dist fixado em package.json; o worker vem de node_modules/pdfjs-dist/build, nunca de CDN com versão diferente).

import type { PdfjsMinimo } from "./pdf";

let promessa: Promise<PdfjsMinimo> | null = null;

export function carregarPdfjs(): Promise<PdfjsMinimo> {
  promessa ??= import("pdfjs-dist").then((m) => {
    m.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
    return m as unknown as PdfjsMinimo;
  });
  return promessa;
}
