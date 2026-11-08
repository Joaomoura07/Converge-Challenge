import { LIMITE_BYTES, type ResultadoImportacao } from "./tipos";

export async function lerSkp(nome: string, bytes: Uint8Array): Promise<ResultadoImportacao> {
  if (bytes.length > LIMITE_BYTES) {
    return { erro: { codigo: "ARQUIVO_GRANDE_DEMAIS", mensagem: "O arquivo SketchUp passa de 20 MB. Divida o modelo em partes." } };
  }
  if (typeof window === "undefined") {
    const { importarSkp } = await import("./skp");
    return importarSkp(nome, bytes);
  }

  return new Promise(resolve => {
    const falha = () => resolve({ erro: {
      codigo: "FORMATO_INVALIDO",
      mensagem: "Não consegui terminar a leitura do SketchUp. Tente um modelo menor ou exporte o quantitativo como CSV.",
    } });
    let worker: Worker;
    try {
      worker = new Worker(new URL("./skp.worker.ts", import.meta.url));
    } catch {
      falha();
      return;
    }
    const encerrar = () => {
      clearTimeout(prazo);
      worker.terminate();
    };
    const prazo = setTimeout(() => { encerrar(); falha(); }, 20_000);
    worker.onmessage = ({ data }: MessageEvent<ResultadoImportacao>) => { encerrar(); resolve(data); };
    const aoFalhar = () => { encerrar(); falha(); };
    worker.onerror = aoFalhar;
    worker.onmessageerror = aoFalhar;
    try {
      const copia = new Uint8Array(bytes);
      worker.postMessage({ nome, bytes: copia }, [copia.buffer]);
    } catch {
      encerrar();
      falha();
    }
  });
}
