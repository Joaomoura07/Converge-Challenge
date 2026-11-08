"use client";

// Lojas de material de construção perto da obra (Google Maps pelo CEP): o diferencial do Orça. Aparece mesmo quando a
// loja não tem preço na internet, porque o arquiteto sabe onde ir consultar. Distância e tempo são aproximados.
import { useEffect, useState } from "react";
import { normalizarApiUrl } from "@/lib/apiUrl";
import { trajeto, type RespostaLojas } from "./lojasDados";

export function LojasProximas({ cep, base = process.env.NEXT_PUBLIC_API_URL }: { cep: string; base?: string }) {
  const [dados, setDados] = useState<RespostaLojas | null>(null);
  const [estado, setEstado] = useState<"carregando" | "ok" | "erro">("carregando");

  useEffect(() => {
    const api = normalizarApiUrl(base);
    const digitos = cep.replace(/\D/g, "");
    if (!api || digitos.length !== 8) {
      setEstado("erro");
      return;
    }
    const aborta = new AbortController();
    fetch(`${api}/lojas-proximas?cep=${digitos}&limite=6`, { signal: aborta.signal })
      .then((r) => (r.ok ? (r.json() as Promise<RespostaLojas>) : Promise.reject(new Error(String(r.status)))))
      .then((j) => {
        setDados(j);
        setEstado("ok");
      })
      .catch((e) => {
        if (e?.name !== "AbortError") setEstado("erro");
      });
    return () => aborta.abort();
  }, [cep, base]);

  if (estado === "erro") return null; // sem a lista a estimativa segue igual: não vale mostrar um erro por isso
  return (
    <section className="sh-lojas" aria-labelledby="sh-lojas-titulo">
      <h2 id="sh-lojas-titulo" className="sh-etiqueta">
        Lojas perto da obra{dados?.origem ? ` · ${dados.origem.cidade}/${dados.origem.uf}` : ""}
      </h2>
      {estado === "carregando" ? (
        <p className="sh-apoio">Procurando lojas perto do CEP da obra…</p>
      ) : dados && dados.lojas.length > 0 ? (
        <>
          <ul className="sh-lojas__lista">
            {dados.lojas.map((l) => (
              <li key={`${l.nome}-${l.endereco ?? ""}`}>
                <strong>{l.nome}</strong>
                {trajeto(l) ? <span className="sh-lojas__trajeto">{trajeto(l)}</span> : null}
                {l.endereco ? <span className="sh-lojas__endereco">{l.endereco}</span> : null}
                <span className="sh-lojas__links">
                  <a className="sh-link" href={l.mapa} target="_blank" rel="noopener noreferrer">Ver no mapa ↗</a>
                  {l.site ? (
                    <a className="sh-link" href={`https://${l.site}`} target="_blank" rel="noopener noreferrer">Site ↗</a>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
          {dados.aviso ? <p className="sh-apoio">{dados.aviso}</p> : null}
        </>
      ) : (
        <p className="sh-apoio">{dados?.aviso ?? "Nenhuma loja encontrada perto deste CEP."}</p>
      )}
    </section>
  );
}
