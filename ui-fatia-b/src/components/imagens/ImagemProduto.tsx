"use client";

import { useState } from "react";
import { desenhoMaterial, normalizarImagem, type DesenhoMaterial } from "./imagem";
import styles from "./imagem.module.css";

const desenhos: Record<DesenhoMaterial, string> = {
  pintura: "M17 20h30v30H17z M17 20c0-5 30-5 30 0s-30 5-30 0 M20 24v-8a12 12 0 0 1 24 0v8 M23 33h18v10H23z",
  piso: "M10 25l22-12 22 12-22 12z M10 25v16l22 12 22-12V25 M32 37v16 M21 19l22 12 M21 31l22-12",
  hidraulica: "M12 49h40 M22 49V30a12 12 0 0 1 24 0v6h-8v-6a4 4 0 0 0-8 0v19 M18 17h16 M26 12v10 M43 42v5",
  luz: "M23 40c0-8-8-10-8-20a17 17 0 0 1 34 0c0 10-8 12-8 20z M24 46h16 M26 52h12 M28 40V28l-5-6 M36 40V28l5-6",
  porta: "M15 54V10h34v44 M21 54V16h22v38 M34 35h3 M11 54h42",
  material: "M12 23l20-11 20 11v26L32 60 12 49z M12 23l20 11 20-11 M32 34v26 M22 17l20 11v10",
};

type Props = { src?: string | null; nome: string; carregando?: boolean; destaque?: boolean };

/** Remonta somente a foto quando Realtime troca a URL ou o produto selecionado. */
export function ImagemProduto({ src, nome, carregando = false, destaque = false }: Props) {
  const url = normalizarImagem(src);
  return <Foto key={`${nome}|${url}|${carregando}`} url={url} nome={nome} carregando={carregando} destaque={destaque} />;
}

function Foto({ url, nome, carregando, destaque }: Omit<Props, "src"> & { url: string | null }) {
  const [estado, setEstado] = useState<"carregando" | "pronta" | "erro">("carregando");
  const pronta = estado === "pronta" && !carregando;
  const rotulo = carregando ? "Buscando foto" : `Foto indisponível de ${nome}. Ilustração do tipo de material.`;
  return (
    <span className={`${styles.quadro}${carregando ? ` ${styles.buscando}` : ""}`}>
      {!pronta && <span className={styles.reserva} role="img" aria-label={rotulo} title={rotulo}>
        <svg viewBox="0 0 64 68" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
          <path d={desenhos[desenhoMaterial(nome)]} />
        </svg>
        <span aria-hidden="true">{carregando ? "Buscando" : "Ilustração"}</span>
      </span>}
      {/* eager: na lista da estimativa o "lazy" deixava fotos sem carregar e a tela mostrava a Ilustração (08/11) */}
      {url && !carregando && estado !== "erro" && <img
        className={styles.foto} src={url} alt={nome} loading="eager"
        decoding="async" referrerPolicy="no-referrer" aria-hidden={!pronta} width={destaque ? 320 : 56} height={destaque ? 200 : 56}
        style={{ opacity: pronta ? 1 : 0 }}
        onLoad={() => setEstado("pronta")} onError={() => setEstado("erro")}
      />}
    </span>
  );
}
