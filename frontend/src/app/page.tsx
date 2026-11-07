import Link from "next/link";
import "./inicio.css";
import { Contador, Revelar } from "./Animacoes";

// Página inicial (protótipo OrçaAI, referência Mercury): hero em tela cheia com planta baixa em SVG,
// prévia do produto, como funciona, regras do agente, números do ensaio e chamada final.
// Dados da prévia são fictícios e rotulados. Números do ensaio: orçamento real de 07/11 (16 itens, cozinha 03).

function PlantaBaixa() {
  return (
    <svg className="in-planta" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <pattern id="piso" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0V24" fill="none" stroke="currentColor" strokeWidth="0.6" />
        </pattern>
        <radialGradient id="esmaecer" cx="50%" cy="50%" r="60%">
          <stop offset="55%" stopColor="#fff" stopOpacity="1" />
          <stop offset="100%" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <mask id="borda-suave">
          <rect width="1440" height="900" fill="url(#esmaecer)" />
        </mask>
      </defs>
      <g mask="url(#borda-suave)">
        {/* piso de porcelanato num ambiente */}
        <rect className="in-piso" x="912" y="572" width="316" height="176" fill="url(#piso)" />
        {/* paredes externas (duas linhas) */}
        <g className="in-parede">
          <rect pathLength={1} x="200" y="160" width="1040" height="600" />
          <rect pathLength={1} x="212" y="172" width="1016" height="576" />
          {/* paredes internas */}
          <path pathLength={1} d="M560 172V420M560 500V748M560 460H900M900 172V380M900 440V748M900 560H1228M212 380H480" />
        </g>
        {/* portas */}
        <g className="in-fino">
          <path pathLength={1} d="M560 500H640M560 420A80 80 0 0 1 640 500" />
          <path pathLength={1} d="M900 440H960M900 380A60 60 0 0 1 960 440" />
          <path pathLength={1} d="M480 380V320M540 380A60 60 0 0 0 480 320" />
        </g>
        {/* janelas */}
        <g className="in-fino">
          <path pathLength={1} d="M300 160V172M420 160V172M300 164H420M300 168H420" />
          <path pathLength={1} d="M680 160V172M820 160V172M680 164H820M680 168H820" />
          <path pathLength={1} d="M1040 748V760M1160 748V760M1040 752H1160M1040 756H1160" />
          <path pathLength={1} d="M200 560H212M200 680H212M204 560V680M208 560V680" />
        </g>
        {/* mobiliário */}
        <g className="in-fino">
          <rect pathLength={1} x="920" y="196" width="292" height="44" />
          <rect pathLength={1} x="1150" y="250" width="62" height="120" />
          <circle pathLength={1} cx="380" cy="600" r="54" />
          <rect pathLength={1} x="250" y="210" width="190" height="120" rx="6" />
          <rect pathLength={1} x="640" y="560" width="200" height="90" rx="8" />
          <circle pathLength={1} cx="1060" cy="300" r="20" />
        </g>
        {/* cotas */}
        <g className="in-cota">
          <path pathLength={1} d="M200 112H560M560 112H900M900 112H1240M200 104V120M560 104V120M900 104V120M1240 104V120" />
          <path pathLength={1} d="M196 116l8-8M556 116l8-8M896 116l8-8M1236 116l8-8" />
          <path pathLength={1} d="M152 160V460M152 460V760M144 160H160M144 460H160M144 760H160" />
          <text x="380" y="100">5,40</text>
          <text x="730" y="100">4,80</text>
          <text x="1070" y="100">5,10</text>
          <text x="128" y="316" transform="rotate(-90 128 316)">4,20</text>
          <text x="128" y="616" transform="rotate(-90 128 616)">4,00</text>
        </g>
        {/* nomes dos ambientes */}
        <g className="in-ambiente">
          <text x="300" y="440">Estar</text>
          <text x="700" y="320">Jantar</text>
          <text x="1010" y="480">Cozinha</text>
          <text x="1010" y="660">Área de serviço</text>
          <text x="680" y="700">Suíte</text>
        </g>
      </g>
    </svg>
  );
}

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
      <section className="in-hero" aria-labelledby="in-titulo">
        <div className="in-brilho" aria-hidden="true" />
        <PlantaBaixa />
        <div className="in-varredura" aria-hidden="true" />
        <div className="in-hero__conteudo">
          <p className="in-selo">Agente de orçamento para escritórios de arquitetura</p>
          <h1 id="in-titulo">Do projeto ao orçamento, com fonte em cada preço.</h1>
          <p className="in-sub">
            A OrçaAI lê a lista de materiais da obra, aponta o que ficou faltando, pesquisa preços em lojas reais e diz
            se cabe no orçamento do cliente.
          </p>
          <div className="in-acoes">
            <Link href="/nova" className="oa-botao oa-botao--principal">
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
