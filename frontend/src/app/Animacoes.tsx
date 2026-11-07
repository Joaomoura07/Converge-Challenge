"use client";

import { useEffect, useRef, useState } from "react";

/** Marca com data-visivel="true" todo elemento [data-revelar] quando ele entra na tela (uma vez só). */
export function Revelar() {
  useEffect(() => {
    const alvos = document.querySelectorAll<HTMLElement>("[data-revelar]");
    if (!("IntersectionObserver" in window)) {
      alvos.forEach((a) => (a.dataset.visivel = "true"));
      return;
    }
    const obs = new IntersectionObserver(
      (entradas) => {
        for (const e of entradas) {
          if (e.isIntersecting) {
            (e.target as HTMLElement).dataset.visivel = "true";
            obs.unobserve(e.target);
          }
        }
      },
      { threshold: 0.18, rootMargin: "0px 0px -6% 0px" },
    );
    alvos.forEach((a) => obs.observe(a));
    return () => obs.disconnect();
  }, []);
  return null;
}

const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const FORMATOS = {
  reais: (n: number) => reais.format(n),
  /** segundos → "1 min 15 s" */
  tempo: (n: number) => {
    const s = Math.round(n);
    return s >= 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s} s`;
  },
  /** minutos → "~4 h 48 min" */
  horas: (n: number) => {
    const m = Math.round(n);
    return `~${Math.floor(m / 60)} h ${m % 60} min`;
  },
};

/** Número que sobe contando quando aparece na tela. Sem animação se o sistema pede movimento reduzido. */
export function Contador({
  ate,
  formato,
  duracao = 1400,
  atraso = 0,
}: {
  ate: number;
  formato: keyof typeof FORMATOS;
  duracao?: number;
  atraso?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [valor, setValor] = useState(ate);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setValor(0);
    let quadro = 0;
    let espera: ReturnType<typeof setTimeout>;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        obs.disconnect();
        espera = setTimeout(() => {
          const inicio = performance.now();
          const passo = (agora: number) => {
            const t = Math.min(1, (agora - inicio) / duracao);
            const suave = 1 - Math.pow(1 - t, 3);
            setValor(ate * suave);
            if (t < 1) quadro = requestAnimationFrame(passo);
          };
          quadro = requestAnimationFrame(passo);
        }, atraso);
      },
      { threshold: 0.4 },
    );
    obs.observe(el);
    return () => {
      obs.disconnect();
      clearTimeout(espera);
      cancelAnimationFrame(quadro);
    };
  }, [ate, duracao, atraso]);

  return <span ref={ref}>{FORMATOS[formato](valor)}</span>;
}
