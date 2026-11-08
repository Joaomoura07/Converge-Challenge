import { importarSkp } from "./skp";

self.onmessage = ({ data }: MessageEvent<{ nome: string; bytes: Uint8Array }>) => {
  self.postMessage(importarSkp(data.nome, data.bytes));
};
