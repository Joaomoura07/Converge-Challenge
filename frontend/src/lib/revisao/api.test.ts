import { describe, expect, it, vi } from "vitest";
import { CAMINHO_SUGESTOES, ErroSugestoes, buscarSugestoes } from "./api";
import type { ItemParaRevisao } from "./tipos";

const itens: ItemParaRevisao[] = [
  { id: "a", descricao: "Cimento Votoran", quantidade: "180", unidade: "sc", categoria: "", linhaOrigem: 12 },
];
const corpoOk = { revisao_id: "r", erros: [], complementos: [], complementos_disponiveis: true, complementos_erro: null };
const resposta = (corpo: unknown, status = 200) => new Response(JSON.stringify(corpo), { status });

describe("buscarSugestoes", () => {
  it("o caminho vem de uma constante única e o corpo leva os itens, sem LLM", async () => {
    const fetchImpl = vi.fn(async () => resposta(corpoOk));
    await buscarSugestoes(itens, { fetchImpl: fetchImpl as unknown as typeof fetch, apiUrl: "http://api.teste" });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(CAMINHO_SUGESTOES).toBe("/revisao/sugestoes/completo");
    expect(url).toBe(`http://api.teste${CAMINHO_SUGESTOES}`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ itens, redigir: false });
  });

  it("status de erro vira mensagem amigável", async () => {
    const f = vi.fn(async () => resposta({ detail: "x" }, 500)) as unknown as typeof fetch;
    await expect(buscarSugestoes(itens, { fetchImpl: f })).rejects.toThrow(/500/);
  });

  it("rede fora do ar vira ErroSugestoes", async () => {
    const f = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;
    await expect(buscarSugestoes(itens, { fetchImpl: f })).rejects.toBeInstanceOf(ErroSugestoes);
  });

  it("resposta fora do contrato é recusada", async () => {
    const f = vi.fn(async () => resposta({ erros: [] })) as unknown as typeof fetch;
    await expect(buscarSugestoes(itens, { fetchImpl: f })).rejects.toThrow(/inesperada/);
  });

  it("cancelamento pedido por quem chamou propaga sem virar erro de rede", async () => {
    const ctl = new AbortController();
    const f = vi.fn((_u: string, init: RequestInit) => new Promise<Response>((_ok, no) => {
      init.signal!.addEventListener("abort", () => no(new DOMException("abortado", "AbortError")));
    })) as unknown as typeof fetch;
    const p = buscarSugestoes(itens, { fetchImpl: f, signal: ctl.signal });
    ctl.abort();
    await expect(p).rejects.not.toBeInstanceOf(ErroSugestoes);
  });
});
