// Dados e texto das lojas perto da obra (sem JSX, para os testes importarem).

export interface LojaProxima {
  nome: string;
  endereco: string | null;
  km: number | null;
  minutos_aprox: number | null;
  site: string | null;
  mapa: string;
}

export interface RespostaLojas {
  origem: { cidade: string; uf: string } | null;
  lojas: LojaProxima[];
  aviso: string | null;
}

/** "a 1,4 km · cerca de 3 min de carro" (aproximado), ou null quando não há distância. */
export function trajeto(l: Pick<LojaProxima, "km" | "minutos_aprox">): string | null {
  if (l.km == null || l.km <= 0) return null;
  const km = `a ${l.km.toFixed(1).replace(".", ",")} km`;
  return l.minutos_aprox ? `${km} · cerca de ${l.minutos_aprox} min de carro` : km;
}
