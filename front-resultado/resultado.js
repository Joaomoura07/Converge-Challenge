/* Tela de resultado (Fatia C). JS puro, sem build: o Samuel pode portar para o componente do site.
 *
 * Contrato: renderResultado(orcamento), com orcamento = linha de `orcamentos` + `itens`:
 *   { id, nome, cep, orcamento_cliente, itens: [...], logistica, viabilidade, ganho }
 * (os três últimos são os JSON gravados por calcular_logistica / calcular_viabilidade / calcular_ganho).
 * Textos que vêm do arquivo do usuário entram SEMPRE por textContent (nunca innerHTML).
 */
(function () {
  "use strict";

  var API_BASE = window.API_BASE || ""; // ex.: "https://converge-challenge.vercel.app"

  // ---------- utilidades ----------
  function el(tag, props) {
    var n = document.createElement(tag);
    var p = props || {};
    Object.keys(p).forEach(function (k) {
      if (k === "class") n.className = p[k];
      else if (k === "text") n.textContent = p[k];
      else n.setAttribute(k, p[k]);
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null || c === false) continue;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return n;
  }
  function brl(v) {
    return (v < 0 ? "-" : "") + "R$ " + Math.abs(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function brlCurto(v) {
    return "R$ " + Math.round(v).toLocaleString("pt-BR");
  }
  function linkSeguro(url) { return typeof url === "string" && /^https?:\/\//i.test(url); }
  function plural(n, um, varios) { return n + " " + (n === 1 ? um : varios); }

  // ---------- selo de status (nunca só cor: ícone + texto) ----------
  var SELOS = {
    definido: ["definido", "✓", "Definido"],
    pendente_especificacao: ["pendente", "⚠", "Pendente de especificação"],
    nao_encontrado: ["erro", "✕", "Não encontrado"],
    erro: ["erro", "✕", "Erro na pesquisa"],
    buscando: ["pendente", "…", "Buscando"],
  };
  function selo(status) {
    var s = SELOS[status] || SELOS.erro;
    return el("span", { class: "selo " + s[0] },
      el("span", { "aria-hidden": "true", text: s[1] }), el("span", { class: "t", text: s[2] }));
  }

  // ---------- a "cota de preço" (SVG: linha + 2 ticks + ponto médio) ----------
  var NS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs, text) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text != null) n.textContent = text;
    return n;
  }
  function cota(min, med, max, estimado) {
    var x0 = 8, x1 = 352, y = 12;
    var pos = max > min ? x0 + ((med - min) / (max - min)) * (x1 - x0) : (x0 + x1) / 2;
    var g = svg("g", { class: estimado ? "estim" : "" });
    g.appendChild(svg("line", { x1: x0, y1: y, x2: x1, y2: y }));
    g.appendChild(svg("line", { x1: x0, y1: y - 6, x2: x0, y2: y + 6 }));
    g.appendChild(svg("line", { x1: x1, y1: y - 6, x2: x1, y2: y + 6 }));
    g.appendChild(svg("circle", { cx: pos, cy: y, r: 4.5, class: "medio" }));
    g.appendChild(svg("text", { x: x0, y: 31, "text-anchor": "start" }, brlCurto(min)));
    g.appendChild(svg("text", { x: x1, y: 31, "text-anchor": "end" }, brlCurto(max)));
    g.appendChild(svg("text", { x: Math.min(Math.max(pos, 60), 300), y: 4, "text-anchor": "middle" },
      (estimado ? "estimado " : "médio ") + brlCurto(med)));
    var s = svg("svg", { viewBox: "0 0 360 36", role: "img", "aria-label":
      (estimado ? "Faixa estimada" : "Faixa de preço") + ": de " + brl(min) + " a " + brl(max) + ", médio " + brl(med) });
    s.appendChild(g);
    return el("div", { class: "cota" }, s);
  }

  // ---------- linhas de item ----------
  var jaVistos = {};
  function itemRow(it, idx) {
    var temPreco = it.preco_emb_med != null && it.qtd_embalagens;
    var li = el("li", { class: "item" + (jaVistos[it.descricao] ? "" : " novo"), "data-indice": idx });
    jaVistos[it.descricao] = true;
    var cab = el("div", {}, el("div", { class: "nome", text: it.descricao || "Item " + (idx + 1) }),
      el("div", { class: "qtd" },
        it.qtd_embalagens ? it.qtd_embalagens + " × " + (it.embalagem || "unidade") : "Sem quantidade definida"));
    li.appendChild(cab);
    var dir = el("div", { class: "num" });
    if (temPreco) {
      dir.appendChild(el("div", { class: "subtotal", text: brl(it.preco_emb_med * it.qtd_embalagens) }));
    }
    dir.appendChild(selo(it.status));
    li.appendChild(dir);
    if (temPreco) {
      li.appendChild(cota(it.preco_emb_min != null ? it.preco_emb_min : it.preco_emb_med, it.preco_emb_med,
        it.preco_emb_max != null ? it.preco_emb_max : it.preco_emb_med, !!it.estimativa));
    }
    var fontes = (it.fontes || []).filter(function (f) { return linkSeguro(f.url); });
    if (fontes.length) {
      var p = el("div", { class: "fontes" }, "Fontes: ");
      fontes.forEach(function (f, i) {
        if (i) p.appendChild(document.createTextNode(" · "));
        var a = el("a", { href: f.url, target: "_blank", rel: "noopener noreferrer",
          text: (f.loja || f.dominio) + " " + brl(f.preco_embalagem) });
        p.appendChild(a);
      });
      if (it.confianca) p.appendChild(document.createTextNode(" — confiança " + it.confianca));
      li.appendChild(p);
    }
    if (it.status === "pendente_especificacao") {
      if (it.pergunta) li.appendChild(el("div", { class: "pergunta", text: it.pergunta }));
      var b = el("button", { type: "button", class: "baixar", text: "Especificar" });
      b.style.cssText = "justify-self:start;border:0;font:inherit;cursor:pointer;padding:6px 12px;grid-column:1/-1";
      b.addEventListener("click", function () {
        document.dispatchEvent(new CustomEvent("especificar", { detail: { indice: idx, item: it } }));
      });
      li.appendChild(b);
    }
    return li;
  }

  // ---------- painel de resumo ----------
  function bloco(titulo) {
    var b = el("div", { class: "bloco" });
    if (titulo) b.appendChild(el("h3", { text: titulo }));
    for (var i = 1; i < arguments.length; i++) b.appendChild(arguments[i]);
    return b;
  }

  function veredito(v) {
    if (!v.completo) return ["talvez", "⚠", "Ainda não dá para afirmar"];
    if (v.cabe) return ["sim", "✓", "Cabe no orçamento"];
    if (v.cabe_no_minimo) return ["talvez", "⚠", "Cabe só no menor preço"];
    return ["nao", "✕", "Não cabe no orçamento"];
  }

  function painel(o) {
    var v = o.viabilidade, lg = o.logistica, g = o.ganho;
    var raiz = document.getElementById("painel");
    raiz.textContent = "";

    // 1) total
    raiz.appendChild(bloco("Total estimado (preço médio, com frete)",
      el("p", { class: "total", text: brl(v.total_med) }),
      el("p", { class: "faixa", text: "Faixa: " + brl(v.total_min) + " a " + brl(v.total_max) +
        (v.inclui_estimativas ? " · inclui itens com preço estimado" : "") })));

    // 2) cabe?
    var ver = veredito(v);
    var b2 = bloco("Orçamento do cliente: " + brl(v.orcamento_cliente),
      el("p", { class: "veredito " + ver[0] }, el("span", { "aria-hidden": "true", text: ver[1] }), el("span", { class: "t", text: ver[2] })),
      el("p", { class: "nota", text: v.resumo }));
    if (v.sugestoes && v.sugestoes.length && !v.cabe) {
      var ul = el("ul", { class: "sugestoes" });
      v.sugestoes.forEach(function (s) { ul.appendChild(el("li", { text: s.texto })); });
      b2.appendChild(el("h3", { text: "Onde economizar", style: "margin-top:12px" }));
      b2.appendChild(ul);
    }
    raiz.appendChild(b2);

    // 3) melhor compra
    if (lg) {
      var titulo = lg.estrategia === "loja_unica" ? "Loja única" : "Dividir em " + plural(lg.lojas.length, "loja", "lojas");
      var b3 = bloco("Melhor compra", el("p", { class: "veredito", style: "font-size:1.0625rem" }, el("span", { class: "t", text: titulo })));
      lg.lojas.forEach(function (l) {
        b3.appendChild(el("div", { class: "loja" },
          el("span", {}, l.nome, el("small", { text: plural(l.itens.length, "item", "itens") + " · " + l.distancia_km.toString().replace(".", ",") + " km" +
            (l.abaixo_do_minimo ? " · abaixo do pedido mínimo" : "") })),
          el("span", { class: "num" }, brl(l.subtotal), el("small", { text: "frete " + brl(l.frete) }))));
      });
      b3.appendChild(el("div", { class: "loja" }, el("strong", { text: "Frete total" }), el("strong", { class: "num", text: brl(lg.frete_total) })));
      var alt = lg.alternativa || {};
      if (lg.economia_estimada > 0) {
        b3.appendChild(el("p", { class: "nota", text: "Economia de " + brl(lg.economia_estimada) + " em relação a " +
          (lg.estrategia === "dividir" ? "comprar em loja única." : "dividir a compra.") }));
      } else if (lg.estrategia === "dividir" && alt.loja_unica != null && alt.loja_unica < lg.total) {
        b3.appendChild(el("p", { class: "nota", text: "Nenhuma loja tem todos os itens, por isso a compra é dividida." }));
      }
      b3.appendChild(el("p", { class: "nota", text: "Menor preço de cada loja + frete: " + brl(lg.total) + "." }));
      if (lg.itens_sem_loja && lg.itens_sem_loja.length) {
        b3.appendChild(el("p", { class: "aviso", role: "status",
          text: plural(lg.itens_sem_loja.length, "item não está", "itens não estão") + " em nenhuma loja cadastrada." }));
      }
      raiz.appendChild(b3);
    }

    // 4) ganho de tempo
    if (g) {
      raiz.appendChild(bloco("Ganho de tempo", el("p", { class: "ganho", text: g.resumo }),
        g.reducao_pct > 0 ? el("p", { class: "nota", text: "Cerca de " + Math.round(g.reducao_pct) + "% menos tempo que fazer à mão." }) : null));
    }

    // 5) exportar
    var url = API_BASE && o.id ? API_BASE + "/orcamentos/" + encodeURIComponent(o.id) + "/exportar.xlsx" : null;
    var botao = url
      ? el("a", { class: "baixar", href: url, download: "plano-de-compra.xlsx", text: "Baixar plano de compra" })
      : el("a", { class: "baixar", href: "#", "aria-disabled": "true", title: "Disponível quando a API estiver ligada", text: "Baixar plano de compra" });
    if (!url) { botao.style.opacity = ".5"; botao.addEventListener("click", function (e) { e.preventDefault(); }); }
    raiz.appendChild(botao);
  }

  // ---------- página ----------
  function renderResultado(o) {
    document.getElementById("titulo").textContent = o.nome || "Resultado da obra";
    document.getElementById("subtitulo").textContent =
      "CEP " + o.cep + " · " + plural((o.itens || []).length, "item", "itens");

    var lista = document.getElementById("lista"), pend = document.getElementById("pendentes");
    lista.textContent = ""; pend.textContent = "";
    var okItens = [], precisam = [];
    (o.itens || []).forEach(function (it, i) {
      (it.status === "definido" ? okItens : precisam).push([it, i]);
    });
    if (!okItens.length) lista.appendChild(el("li", { class: "vazio", text: "Os itens aparecem aqui conforme a IA os encontra." }));
    okItens.forEach(function (p) { lista.appendChild(itemRow(p[0], p[1])); });
    precisam.forEach(function (p) { pend.appendChild(itemRow(p[0], p[1])); });
    document.getElementById("pendentes-bloco").hidden = !precisam.length;

    painel(o);
  }
  window.renderResultado = renderResultado;

  // ---------- boot (protótipo com dados fictícios) ----------
  var q = new URLSearchParams(location.search);
  if (q.get("demo") === "1") document.body.classList.add("demo");
  var mocks = window.MOCKS || {};
  var atual = mocks[q.get("cenario")] ? q.get("cenario") : "cabe";
  if (q.get("dev") === "1" && Object.keys(mocks).length) {
    var dev = document.getElementById("dev"), sel = document.getElementById("cenario");
    dev.hidden = false; sel.value = atual;
    sel.addEventListener("change", function () { jaVistos = {}; renderResultado(mocks[sel.value]); });
  }
  if (mocks[atual]) renderResultado(mocks[atual]);
})();
