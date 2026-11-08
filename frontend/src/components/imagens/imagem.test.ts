import { describe, expect, it } from "vitest";
import { desenhoMaterial, normalizarImagem } from "./imagem";

describe("fotos antigas e ilustração de reserva", () => {
  it("corrige o template do Magalu sem perder a query", () => {
    expect(normalizarImagem("http://a-static.mlcdn.com.br/%7Bw%7Dx%7Bh%7D/p.jpg?v=a%2Fb"))
      .toBe("https://a-static.mlcdn.com.br/600x600/p.jpg?v=a%2Fb");
  });
  it("aceita URL sem protocolo explícito e recusa protocolos perigosos", () => {
    expect(normalizarImagem("//cdn.example/foto.webp")).toBe("https://cdn.example/foto.webp");
    for (const url of [null, "", "javascript:alert(1)", "data:image/png;base64,abc", "arquivo.jpg", "https://user:pass@loja.example/foto.jpg"]) {
      expect(normalizarImagem(url)).toBeNull();
    }
  });
  it("oferece desenho do material sem depender de uma imagem remota", () => {
    expect(desenhoMaterial("Tinta acrílica" )).toBe("pintura");
    expect(desenhoMaterial("Porcelanato 60x60")).toBe("piso");
    expect(desenhoMaterial("Cuba inox")).toBe("hidraulica");
    expect(desenhoMaterial("Luminária")).toBe("luz");
    expect(desenhoMaterial("Janela de alumínio")).toBe("porta");
    expect(desenhoMaterial("Material sem especificação")).toBe("material");
  });
});
