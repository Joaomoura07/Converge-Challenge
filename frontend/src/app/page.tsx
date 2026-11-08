import Link from "next/link";
import "./inicio.css";
import { Contador, Revelar } from "./Animacoes";
import { PlantaViva } from "./PlantaViva";

// Página inicial (protótipo OrçaAI, referência Mercury): hero em tela cheia com planta baixa 3D viva (PlantaViva),
// prévia do produto, como funciona, regras do agente, números do ensaio e chamada final.
// Dados da prévia são fictícios e rotulados.

// Números da faixa "Horas viram minutos": orçamento REAL gravado no Supabase ("Teste final Casa Aldeia", 7/11/2026,
// 21h10 em Recife): 53 itens, tempo_ms = 110037 (1 min 50 s), custo_usd = 0,019963 (≈ R$ 0,11 a R$ 5,50 o dólar).
// "À mão" NÃO é medida: 18 min por item é a estimativa do time (src/ganho.py), em validação com arquitetos (Google
// Forms, pergunta 2; 13 respostas em 7/11). Com a contagem do Forms, troque ESTIMATIVA_A_MAO pelo dado com fonte.
const ENSAIO = { itens: 53, segundos: 110, custoReais: 0.11, obra: "uma casa térrea" };
const MINUTOS_POR_ITEM_ESTIMADOS = 18;
const ESTIMATIVA_A_MAO = ENSAIO.itens * MINUTOS_POR_ITEM_ESTIMADOS; // minutos

// Fotos: as mesmas que a pesquisa escolheu para esses produtos (cache de preços); o item pendente mostra um parecido.
const ITENS_PREVIA = [
  { nome: "Porcelanato Portobello Cimento 90×90", qtd: "24 m², 11 caixas", min: 89.9, med: 104.5, max: 129.0, loja: "Leroy Merlin", status: "definido",
    foto: "https://cdn.leroymerlin.com.br/products/porcelanato_acetinado_interno_90x90cm_nord_portobello_92308265_88df_1800x1800.png" },
  { nome: "Argamassa AC-III Quartzolit 20 kg", qtd: "15 sacos, sugerido", min: 38.9, med: 42.0, max: 49.9, loja: "Telhanorte", status: "definido",
    foto: "https://telhanorte.vtexassets.com/arquivos/ids/1320983-400-auto" },
  { nome: "Tinta acrílica branca fosca", qtd: "120 m², 2 latas 18 L", min: 289.9, med: 339.9, max: 389.9, loja: "", status: "pendente",
    foto: "https://telhanorte.vtexassets.com/arquivos/ids/360263/Tinta--acrilica-Prolar-18-litros-branco-Sherwin-Williams-1024327.jpg?v=637069382597770000" },
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
        <span className="ok">
          <i className="in-ico" aria-hidden="true">✓</i>14 itens com preço
        </span>
        <span className="pend">
          <i className="in-ico" aria-hidden="true">?</i>2 com preço aproximado
        </span>
        <span>Cabe no orçamento do cliente</span>
      </div>
      <ul className="in-previa__itens">
        {ITENS_PREVIA.map((i, n) => (
          <li key={i.nome} style={{ "--i": n } as React.CSSProperties}>
            <span className="foto">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={i.foto} alt={i.nome} loading="lazy" />
            </span>
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
                <span className="pergunta">
                  <strong>≈ {reais.format(i.med)} a lata</strong>, pela média de produtos parecidos. Quer especificar marca
                  e linha?
                </span>
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
          <h1 id="in-titulo">
            Menos tempo cotando material.
            <br />
            Mais tempo projetando.
          </h1>
          <p className="in-sub">
            A OrçaAI é um <strong>AI Agent</strong> que pesquisa os preços da sua obra e entrega o plano de compra pronto.
          </p>
          <div className="in-acoes">
            <Link href="/demo" className="oa-botao oa-botao--principal" data-planta-foco>
              Visualizar Demo
            </Link>
            <a href="#sobre" className="oa-botao oa-botao--fantasma">
              Conhecer projeto
            </a>
          </div>
          <p className="in-formatos">Funciona com Excel, CSV, TXT do Revit, PDF com texto e planta em DXF.</p>
        </div>
      </section>

      <div className="in-faixa in-faixa--previa">
        <Previa />
      </div>
      </div>

      <section id="sobre" className="in-faixa in-sobre" aria-labelledby="in-sobre">
        <div className="in-cabeca" data-revelar>
          <h2 id="in-sobre">Sobre o projeto</h2>
          <p>A OrçaAI foi criada no Converge Challenge, em Recife, em novembro de 2026, pelo time Avisa que é Agente.</p>
        </div>
        <div className="in-sobre__grade" data-revelar>
          <div>
            <h3>O problema</h3>
            <p>
              Montar o orçamento de uma obra é cotar dezenas de itens loja por loja, conferir embalagens e refazer contas.
              É lento, repetitivo, e é aí que o projeto estoura o orçamento do cliente sem ninguém perceber a tempo.
            </p>
          </div>
          <div>
            <h3>Para quem</h3>
            <p>
              Arquitetos autônomos e escritórios de arquitetura e interiores que precisam de um preço de referência
              confiável antes de falar com as lojas e com o cliente.
            </p>
          </div>
          <div>
            <h3>A solução</h3>
            <p>
              Um AI Agent que lê a lista de materiais do projeto, revisa, pesquisa o preço de cada item em lojas reais e
              entrega o plano de compra, sempre com a fonte de cada valor.
            </p>
          </div>
        </div>

        <h3 className="in-sobre__sub" data-revelar>
          Como o agente trabalha
        </h3>
        <ol className="in-passos in-agente" data-revelar>
          <li>
            <span className="n">1</span>
            <h3>Lê a lista</h3>
            <p>Planilha, CSV, tabela do Revit, PDF com texto ou planta: tudo vira a mesma lista editável.</p>
          </li>
          <li>
            <span className="n">2</span>
            <h3>Revisa antes de pesquisar</h3>
            <p>Aponta unidade errada e item duplicado e sugere o que costuma faltar. Nada entra sem o seu clique.</p>
          </li>
          <li>
            <span className="n">3</span>
            <h3>Pesquisa em lojas reais</h3>
            <p>Busca cada item em lojas de construção, com as lojas da região da obra primeiro.</p>
          </li>
          <li>
            <span className="n">4</span>
            <h3>Confere o anúncio</h3>
            <p>É o mesmo produto? O preço está escrito no anúncio? Sem fonte, o preço é descartado.</p>
          </li>
          <li>
            <span className="n">5</span>
            <h3>Refaz a busca sozinho</h3>
            <p>Achou poucas lojas com o produto certo? O agente reescreve a consulta e procura de novo.</p>
          </li>
          <li>
            <span className="n">6</span>
            <h3>Pergunta em vez de chutar</h3>
            <p>Item genérico ganha um preço aproximado, marcado como tal, e uma pergunta para você especificar.</p>
          </li>
        </ol>
        <p className="in-sobre__tec" data-revelar>
          Feito com Featherless (GLM-5.2 e Qwen3), Tavily, Supabase Realtime, Langfuse, FastAPI e Next.js na Vercel. Cada
          passo do agente fica registrado no Langfuse para auditoria.
        </p>
      </section>

      <section id="como-funciona"className="in-faixa in-faixa--grade" aria-labelledby="in-como">
        <div className="in-cabeca" data-revelar>
          <h2 id="in-como">Como funciona</h2>
          <p>Três passos. Você confere cada decisão; o agente faz a busca.</p>
        </div>
        <ol className="in-passos" data-revelar>
          <li>
            <span className="n">1</span>
            <h3>Envie a lista da obra</h3>
            <p>
              Informe o nome da obra, o CEP e o orçamento do cliente. Depois envie a lista (Excel, CSV, TXT do Revit, PDF ou planta em DXF)
              ou use um exemplo. O CEP define a cidade da busca e põe primeiro as lojas com unidade na região.
            </p>
          </li>
          <li>
            <span className="n">2</span>
            <h3>Feche a lista completa de primeira</h3>
            <p>
              Antes de pesquisar, a IA revisa a lista: aponta unidades erradas e itens duplicados e sugere o que costuma
              faltar, como argamassa e rejunte para o porcelanato. O orçamento sai completo de primeira, e nada entra sem
              o seu clique.
            </p>
          </li>
          <li>
            <span className="n">3</span>
            <h3>Receba o plano de compra</h3>
            <p>
              Preço mínimo, médio e máximo com a loja e o link, quantas embalagens comprar, onde comprar e se cabe no
              orçamento. O plano de compra também sai em planilha do Excel, para mandar às lojas ou ao cliente.
            </p>
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
              <strong>Pergunta em vez de chutar.</strong> Item genérico ganha um preço aproximado, marcado como tal, e
              uma pergunta para você especificar.
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
          <p>
            Orçamento real de {ENSAIO.obra}, {ENSAIO.itens} itens, pesquisado pela OrçaAI em 7 de novembro de 2026.
          </p>
        </div>
        <div className="in-numeros" data-revelar>
          <div>
            <strong>
              <Contador ate={ENSAIO.segundos} formato="tempo" />
            </strong>
            <span>para pesquisar os {ENSAIO.itens} itens com a OrçaAI</span>
          </div>
          <div>
            <strong>
              <Contador ate={ESTIMATIVA_A_MAO} formato="horas" atraso={150} />
            </strong>
            <span>à mão, numa estimativa de {MINUTOS_POR_ITEM_ESTIMADOS} min por item (em validação com arquitetos)</span>
          </div>
          <div>
            <strong>
              <Contador ate={ENSAIO.custoReais} formato="reais" atraso={300} />
            </strong>
            <span>de custo de IA no orçamento inteiro</span>
          </div>
        </div>
      </section>

      <section className="in-faixa in-final" data-revelar aria-labelledby="in-final">
        <h2 id="in-final">Veja o agente cotando ao vivo.</h2>
        <p>Deixe a busca de preços com o agente e chegue à reunião com o orçamento pronto.</p>
        <Link href="/demo" className="oa-botao oa-botao--principal">
          Visualizar Demo
        </Link>
      </section>
      <Revelar />
    </main>
  );
}
