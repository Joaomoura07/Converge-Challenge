import Link from "next/link";
import "./inicio.css";
import { Contador, Revelar } from "./Animacoes";
import { PlantaViva } from "./PlantaViva";

// Página inicial (protótipo OrçaAI, referência Mercury): hero em tela cheia com planta baixa 3D viva (PlantaViva),
// prévia do produto, como funciona, regras do agente, números do ensaio e chamada final.
// Dados da prévia são fictícios e rotulados. Números do ensaio: orçamento real de 07/11 (16 itens, cozinha 03).

const ITENS_PREVIA = [
  { nome: "Porcelanato Portobello Cimento 90×90", qtd: "24 m², 11 caixas", min: 89.9, med: 104.5, max: 129.0, loja: "Leroy Merlin", status: "definido" },
  { nome: "Argamassa AC-III Quartzolit 20 kg", qtd: "15 sacos, sugerido", min: 38.9, med: 42.0, max: 49.9, loja: "Telhanorte", status: "definido" },
  { nome: "Tinta acrílica branca fosca", qtd: "120 m²", min: 0, med: 0, max: 0, loja: "", status: "pendente" },
] as const;

const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function Cota({ min, med, max }: { min: number; med: number; max: number }) {
  const pos = ((med - min) / (max - min)) * 100;
  return (
    <div className="in-cota-preco" aria-label={`Preço de ${reais.format(min)} a ${reais.format(max)}, médio ${reais.format(med)}`}>
      <span>{reais.format(min)}</span>
      <span className="trilho">
        <i className="ponto" style={{ left: `${pos}%` }} />
      </span>
      <span>{reais.format(max)}</span>
    </div>
  );
}

function Previa() {
  return (
    <div className="in-previa" data-revelar role="img" aria-label="Exemplo da tela de estimativa da OrçaAI com dados fictícios">
      <div className="in-previa__topo">
        <div>
          <p className="in-previa__trilha">Residência Aurora, cozinha</p>
          <p className="in-previa__titulo">Estimativa preliminar</p>
        </div>
        <div className="in-previa__total">
          <span className="rotulo">Subtotal estimado</span>
          <strong>
            <Contador ate={18420.35} formato="reais" duracao={2200} atraso={500} />
          </strong>
        </div>
      </div>
      <div className="in-previa__resumo">
        <span className="ok">✓ 14 itens com preço</span>
        <span className="pend">? 2 pendentes de especificação</span>
        <span>Cabe no orçamento do cliente</span>
      </div>
      <ul className="in-previa__itens">
        {ITENS_PREVIA.map((i, n) => (
          <li key={i.nome} style={{ "--i": n } as React.CSSProperties}>
            <span className="foto" aria-hidden="true" />
            <span className="nome">
              {i.nome}
              <small>{i.qtd}</small>
            </span>
            {i.status === "definido" ? (
              <>
                <Cota min={i.min} med={i.med} max={i.max} />
                <span className="loja">
                  <span className="selo ok">✓ Definido</span>
                  <small>{i.loja}</small>
                </span>
              </>
            ) : (
              <>
                <span className="pergunta">Qual marca e linha? Sem isso, não há preço.</span>
                <span className="loja">
                  <span className="selo pend">? Pendente</span>
                </span>
              </>
            )}
          </li>
        ))}
      </ul>
      <p className="in-previa__nota">Exemplo com dados fictícios.</p>
    </div>
  );
}

export default function Inicio() {
  return (
    <main className="in">
      {/* palco: a planta viva fica atrás do topo E da prévia, e some devagar no fim dela */}
      <div className="in-palco">
        <div className="in-brilho" aria-hidden="true" />
        <PlantaViva />
      <section className="in-hero" aria-labelledby="in-titulo">
        <div className="in-hero__conteudo">
          <p className="in-selo">Agente de orçamento para escritórios de arquitetura</p>
          <h1 id="in-titulo">
            Menos tempo cotando material.
            <br />
            Mais tempo projetando.
          </h1>
          <p className="in-sub">
            A OrçaAI pesquisa os preços da lista de materiais da obra em lojas reais, aponta o que ficou faltando e
            entrega o plano de compra pronto para o cliente.
          </p>
          <div className="in-acoes">
            <Link href="/nova" className="oa-botao oa-botao--principal" data-planta-foco>
              Criar estimativa
            </Link>
            <Link href="/previa-c?cenario=cabe" className="oa-botao oa-botao--fantasma">
              Ver um exemplo
            </Link>
          </div>
          <p className="in-formatos">Funciona com Excel, CSV, TXT do Revit e PDF com texto.</p>
        </div>
      </section>

      <div className="in-faixa in-faixa--previa">
        <Previa />
      </div>
      </div>

      <section id="como-funciona" className="in-faixa in-faixa--grade" aria-labelledby="in-como">
        <div className="in-cabeca" data-revelar>
          <h2 id="in-como">Como funciona</h2>
          <p>Três passos. Você confere cada decisão; o agente faz a busca.</p>
        </div>
        <ol className="in-passos" data-revelar>
          <li>
            <span className="n">1</span>
            <h3>Envie a lista da obra</h3>
            <p>Arraste a planilha ou o TXT do Revit, ou use um exemplo pronto. Informe o CEP e o orçamento do cliente.</p>
          </li>
          <li>
            <span className="n">2</span>
            <h3>Revise o que a IA apontou</h3>
            <p>
              Unidades erradas, itens duplicados e o que costuma ser esquecido, como argamassa e rejunte. Nada entra sem
              o seu clique.
            </p>
          </li>
          <li>
            <span className="n">3</span>
            <h3>Receba o plano de compra</h3>
            <p>Preço mínimo, médio e máximo com a loja e o link, onde comprar, se cabe no orçamento e o arquivo em Excel.</p>
          </li>
        </ol>
      </section>

      <section className="in-faixa in-dupla" aria-labelledby="in-regras">
        <div data-revelar>
          <h2 id="in-regras">Nunca inventa preço.</h2>
          <p className="in-texto">
            Um chat genérico chuta valores e erra contas em listas longas. A OrçaAI segue regras fixas, e cada passo fica
            registrado para auditoria.
          </p>
          <ul className="in-regras">
            <li>
              <strong>Sem fonte, sem preço.</strong> Todo valor vem com a loja e o link.
            </li>
            <li>
              <strong>Pergunta em vez de chutar.</strong> Item genérico vira pergunta para você.
            </li>
            <li>
              <strong>Sugere, não aplica.</strong> Correções e complementos esperam o seu aceite.
            </li>
            <li>
              <strong>Confere o que achou.</strong> Se o produto não bate, refaz a busca.
            </li>
          </ul>
        </div>
        <div className="in-fontes" data-revelar role="img" aria-label="Exemplo de fontes de preço de um item, com dados fictícios">
          <p className="in-fontes__item">Porcelanato Portobello Cimento 90×90</p>
          <ul>
            <li>
              <span>Leroy Merlin</span>
              <strong>{reais.format(89.9)}</strong>
            </li>
            <li>
              <span>Telhanorte</span>
              <strong>{reais.format(104.5)}</strong>
            </li>
            <li>
              <span>C&amp;C</span>
              <strong>{reais.format(129.0)}</strong>
            </li>
          </ul>
          <p className="in-fontes__rodape">Preço por m², mediana das lojas. Dados fictícios.</p>
        </div>
      </section>

      <section className="in-faixa" aria-labelledby="in-numeros">
        <div className="in-cabeca" data-revelar>
          <h2 id="in-numeros">Horas viram minutos</h2>
          <p>Ensaio real com a lista de uma cozinha, 16 itens, em 7 de novembro de 2026.</p>
        </div>
        <div className="in-numeros" data-revelar>
          <div>
            <strong>
              <Contador ate={75} formato="tempo" />
            </strong>
            <span>para pesquisar os 16 itens com a OrçaAI</span>
          </div>
          <div>
            <strong>
              <Contador ate={288} formato="horas" atraso={150} />
            </strong>
            <span>à mão, estimando 18 minutos por item</span>
          </div>
          <div>
            <strong>
              <Contador ate={0.02} formato="reais" atraso={300} />
            </strong>
            <span>de custo de IA no ensaio inteiro</span>
          </div>
        </div>
      </section>

      <section className="in-faixa in-final" data-revelar aria-labelledby="in-final">
        <h2 id="in-final">Mais tempo para projetar.</h2>
        <p>Deixe a busca de preços com o agente e chegue à reunião com o orçamento pronto.</p>
        <Link href="/nova" className="oa-botao oa-botao--principal">
          Criar estimativa
        </Link>
      </section>
      <Revelar />
    </main>
  );
}
