"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import type { Linha } from "../lista";
import { criarRevisor, type EstadoRevisor, type Revisor } from "./revisor";

export function useSugestoes(linhas: Linha[]): { estado: EstadoRevisor; repetir: () => void } {
  const [revisor] = useState<Revisor>(() => criarRevisor());
  const estado = useSyncExternalStore(revisor.assinar, revisor.estado, revisor.estado);

  useEffect(() => {
    revisor.atualizar(linhas);
  }, [revisor, linhas]);

  useEffect(() => () => revisor.parar(), [revisor]);

  return { estado, repetir: revisor.repetir };
}
