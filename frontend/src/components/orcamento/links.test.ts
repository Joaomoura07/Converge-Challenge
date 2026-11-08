import { describe, it, expect } from "vitest";
import { linkDiretoProduto } from "./formato";

describe("link específico do produto", () => {
  it("recusa Shopping, home e resultados de busca antigos", () => {
    for (const url of ["https://www.google.com/search?ibp=oshop", "https://shopping.google.com/p/123", "https://loja.example/", "https://loja.example/busca?q=tinta", "javascript:alert(1)"])
      expect(linkDiretoProduto(url)).toBe(false);
  });
  it("preserva o endereço direto encontrado na loja", () => {
    expect(linkDiretoProduto("https://loja.example/tinta-branca-18l/p?sku=123")).toBe(true);
  });
});
