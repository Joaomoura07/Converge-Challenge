"use client";

import Link from "next/link";
import { useState } from "react";
import { CabecalhoPagina } from "@/components/shell/CabecalhoPagina";
import { MATERIAIS_REVISAO, type MaterialRevisao } from "@/lib/prototipo";

// Tela 03 · Revisar materiais (grade com campos só de linha inferior)
export default function Revisar() {
  const [linhas, setLinhas] = useState<MaterialRevisao[]>(MATERIAIS_REVISAO);
  const incompletas = linhas.filter((l) => !l.especificacao.trim()).length;

  function editar(id: string, campo: keyof MaterialRevisao, valor: string) {
    setLinhas((atual) => atual.map((l) => (l.id === id ? { ...l, [campo]: valor } : l)));
  }

  return (
    <>
      <CabecalhoPagina
        trilha={[{ rotulo: "Nova estimativa", href: "/nova" }, { rotulo: "Revisar materiais" }, { rotulo: "02 de 03" }]}
        etiqueta="Conferência / especificações"
        titulo="O cuidado está nos"
        destaque="detalhes."
        apoio="Revise unidades e quantidades. Quanto mais precisa a descrição, melhor a comparação."
        acao={<span className="sh-apoio">{String(linhas.length).padStart(2, "0")} materiais</span>}
      />

      <table className="sh-grade">
        <thead>
          <tr>
            <th scope="col">Material</th>
            <th scope="col">Especificação</th>
            <th scope="col">Qtd.</th>
            <th scope="col">Unidade</th>
            <th scope="col">
              <span className="sr-only" style={{ position: "absolute", left: -9999 }}>
                Remover
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.id}>
              <td>
                <input aria-label="Material" value={l.material} onChange={(e) => editar(l.id, "material", e.target.value)} />
              </td>
              <td>
                <input
                  aria-label="Especificação"
                  className={l.especificacao.trim() ? undefined : "pendente"}
                  placeholder="Complete modelo e acabamento"
                  value={l.especificacao}
                  onChange={(e) => editar(l.id, "especificacao", e.target.value)}
                />
              </td>
              <td>
                <input aria-label="Quantidade" className="qtd" inputMode="decimal" value={l.quantidade} onChange={(e) => editar(l.id, "quantidade", e.target.value)} />
              </td>
              <td>
                <input aria-label="Unidade" className="un" value={l.unidade} onChange={(e) => editar(l.id, "unidade", e.target.value)} />
              </td>
              <td>
                <button type="button" className="sh-remover" aria-label={`Remover ${l.material || "linha"}`} onClick={() => setLinhas((a) => a.filter((x) => x.id !== l.id))}>
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p style={{ marginTop: 12 }}>
        <button
          type="button"
          className="sh-link"
          onClick={() => setLinhas((a) => [...a, { id: `n${Date.now()}`, material: "", especificacao: "", quantidade: "1", unidade: "un" }])}
        >
          + Adicionar material
        </button>
      </p>

      {incompletas > 0 && (
        <div className="sh-nota" role="status">
          <span className="n">{String(incompletas).padStart(2, "0")}</span>
          <p>
            <strong>{incompletas === 1 ? "Uma especificação pede atenção." : `${incompletas} especificações pedem atenção.`}</strong>
            Itens incompletos podem continuar pendentes. Eles ficam fora do subtotal até receberem uma referência confiável.
          </p>
        </div>
      )}

      <div className="sh-rodape-acoes">
        <Link href="/nova" className="sh-botao claro">
          ← Voltar ao envio
        </Link>
        <Link href="/pesquisa" className="sh-botao">
          Iniciar pesquisa <span aria-hidden="true">→</span>
        </Link>
      </div>
    </>
  );
}
