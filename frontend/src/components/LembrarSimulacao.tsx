"use client";

import { useEffect } from "react";
import { simulacaoAtiva } from "@/lib/simulacao";

/** Lê `?simular=1` / `?simular=0` assim que qualquer página abre (o parâmetro some na navegação seguinte). */
export function LembrarSimulacao() {
  useEffect(() => {
    if (simulacaoAtiva()) console.info("[OrçaAI] modo gravação ligado: ?simular=0 desliga");
  }, []);
  return null;
}
