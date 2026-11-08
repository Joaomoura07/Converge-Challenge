// Chips pequenos de download (2 por formato) acima da área de envio da /demo. O jurado baixa e arrasta o arquivo para
// dentro, como um arquiteto faria com a exportação do Revit, do SketchUp ou da planilha.

import { EXEMPLOS_DEMO, FORMATOS_DEMO, MODELOS_DEMO, PASTA_DEMO } from "@/lib/demo/exemplos";

function IconeArquivo() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <path d="M4 1.75h5.25L12.5 5v9.25H4z" strokeLinejoin="round" />
      <path d="M9 1.75V5.25h3.5" strokeLinejoin="round" />
    </svg>
  );
}

function IconeBaixar() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M7 1.5v8M3.5 6.5 7 10l3.5-3.5M2 12.5h10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ExemplosDownload() {
  return (
    <section className="demo-exemplos" aria-labelledby="demo-exemplos-titulo">
      <div className="demo-exemplos__cabeca">
        <h3 id="demo-exemplos-titulo">Não tem uma lista à mão? Baixe um exemplo</h3>
        <p>O arquivo <strong>MODELO</strong> de cada formato mostra o padrão para montar a sua lista. Os testes são obras fictícias de Recife: baixe e arraste para a área abaixo.</p>
      </div>
      <div className="demo-exemplos__grupos">
        {FORMATOS_DEMO.map((f) => (
          <details key={f.modo} className="demo-exemplos__grupo">
            <summary className="demo-exemplos__formato">
              <svg className="demo-exemplos__seta" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                <path d="M3 1.5 7 5 3 8.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {f.rotulo}
            </summary>
            <ul>
              {MODELOS_DEMO.filter((m) => m.modo === f.modo).map((m) => (
                <li key={m.arquivo}>
                  <a className="demo-chip demo-chip--modelo" href={`${PASTA_DEMO}/${m.arquivo}`} download={m.arquivo}
                     title="Use este arquivo como padrão para montar a sua lista"
                     aria-label={`Baixar ${m.arquivo}: modelo para montar a sua lista`}>
                    <IconeArquivo />
                    <span className="demo-chip__nome">{m.arquivo}</span>
                    <span className="demo-chip__selo">padrão</span>
                    <IconeBaixar />
                  </a>
                </li>
              ))}
              {EXEMPLOS_DEMO.filter((e) => e.modo === f.modo).map((e) => (
                <li key={e.arquivo}>
                  <a className="demo-chip" href={`${PASTA_DEMO}/${e.arquivo}`} download={e.arquivo} title={e.obra}
                     aria-label={`Baixar ${e.arquivo}: ${e.obra}`}>
                    <IconeArquivo />
                    <span className="demo-chip__nome">{e.arquivo}</span>
                    <IconeBaixar />
                  </a>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </section>
  );
}
