"use client";

// Fundo do hero (protótipo OrçaAI): uma planta baixa em 3D feita de pontos de luz, com a câmera voando
// pelos ambientes. Implementação própria em canvas 2D, sem biblioteca.
// - Intro: a câmera desce do alto e a planta aparece do centro para fora.
// - Voo: avança sozinho devagar; rolar a página acelera o caminho.
// - Mouse: empurra os pontos perto do cursor (que acendem em azul) e inclina a câmera.
// - Foco: passar o mouse em [data-planta-foco] desacelera o voo e desmancha a planta em partículas.
// - Movimento reduzido: um quadro parado. Fora da tela ou com a aba oculta: pausa.

import { useEffect, useRef } from "react";

const ALTURA_PAREDE = 260;
const ALTURA_VOO = 340; // no topo da página: um pouco acima das paredes (pé-direito 260)
const ALTURA_ROLADA = 150; // no fim da rolagem: altura dos olhos…
const PITCH_TOPO = 0.5, PITCH_ROLADO = 0.12; // …e levanta o olhar (rad abaixo do horizonte)
const ALTURA_INICIAL = 1700;
const DURACAO_INTRO = 3.4; // s
const VELOCIDADE = 0.0075; // voltas do caminho por segundo
const RAIO_MOUSE = 150; // px CSS
const EMPURRAO = 46; // px CSS

// tipos de ponto: parede, fino (móveis, portas, janelas), cota, piso, poeira
const PAREDE = 0, FINO = 1, COTA = 2, PISO = 3, POEIRA = 4;
const ALFA = [0.62, 0.38, 0.5, 0.16, 0.3];
const TAMANHO = [2.6, 2.0, 2.0, 1.6, 2.2];
const OPACIDADE_LINHA = 0.38; // traço fino e discreto entre os pontos
const OPACIDADE_PONTO = 1.35; // pontilhado da planta mais forte que a linha

type Rotulo = { x: number; y: number; texto: string; cota?: boolean };
/** Móvel 3D: caixa (x1,y1)-(x2,y2) ou cilindro (cx,cy,r); z0 = altura da base, h = altura do volume. */
type Movel =
  | { tipo: "caixa"; x1: number; y1: number; x2: number; y2: number; z0: number; h: number }
  | { tipo: "cilindro"; cx: number; cy: number; r: number; z0: number; h: number };

const caixa = (x1: number, y1: number, x2: number, y2: number, h: number, z0 = 0): Movel => ({ tipo: "caixa", x1, y1, x2, y2, z0, h });
const cilindro = (cx: number, cy: number, r: number, h: number, z0 = 0): Movel => ({ tipo: "cilindro", cx, cy, r, z0, h });

// Móveis montados com as partes reais (tampo + pés, assento + encosto + braços, laterais + prateleiras…),
// encostados em parede e fora do giro das portas. Unidade: centímetros (pé-direito 260).
// Cômodos: estar x -1200..-300 y -800..200 · jantar x -1200..-300 y 200..800 · escritório x -300..400 y -800..100
// banho x 400..800 y -800..250 · cozinha x 800..1200 y -800..250 · suíte x 400..1200 y 250..800 · circulação x -300..400 y 100..800
type Lado = "n" | "s" | "l" | "o"; // para onde a pessoa sentada olha: n = -y, s = +y, l = +x, o = -x
function pesMesa(x1: number, y1: number, x2: number, y2: number, h: number, e = 5): Movel[] {
  return [caixa(x1 + 3, y1 + 3, x1 + 3 + e, y1 + 3 + e, h), caixa(x2 - 3 - e, y1 + 3, x2 - 3, y1 + 3 + e, h),
    caixa(x1 + 3, y2 - 3 - e, x1 + 3 + e, y2 - 3, h), caixa(x2 - 3 - e, y2 - 3 - e, x2 - 3, y2 - 3, h)];
}
function cadeira(cx: number, cy: number, olha: Lado, t = 35): Movel[] {
  const assento = caixa(cx - t, cy - t, cx + t, cy + t, 44);
  const encosto = {
    n: caixa(cx - t, cy + t - 12, cx + t, cy + t, 46, 44), s: caixa(cx - t, cy - t, cx + t, cy - t + 12, 46, 44),
    l: caixa(cx - t, cy - t, cx - t + 12, cy + t, 46, 44), o: caixa(cx + t - 12, cy - t, cx + t, cy + t, 46, 44),
  }[olha];
  return [assento, encosto];
}
function planta(cx: number, cy: number): Movel[] {
  return [cilindro(cx, cy, 22, 42), cilindro(cx, cy, 38, 50, 42)];
}

const MOVEIS: Movel[] = [
  // ESTAR: rack com TV na parede esquerda, sofá de frente, mesa de centro, tapete, poltrona, luminária e planta
  caixa(-1195, -560, -1150, -240, 45), caixa(-1180, -520, -1172, -280, 75, 70),
  caixa(-830, -590, -740, -210, 42), caixa(-760, -590, -740, -210, 44, 42),
  caixa(-830, -590, -740, -570, 22, 42), caixa(-830, -230, -740, -210, 22, 42),
  caixa(-1080, -520, -860, -280, 1),
  caixa(-1030, -470, -900, -330, 5, 35), ...pesMesa(-1030, -470, -900, -330, 35),
  caixa(-1000, -775, -920, -695, 40), caixa(-1000, -775, -920, -757, 45, 40),
  caixa(-1000, -775, -985, -695, 20, 40), caixa(-935, -775, -920, -695, 20, 40),
  cilindro(-790, -650, 14, 3), cilindro(-790, -650, 3, 148), cilindro(-790, -650, 26, 28, 148),
  ...planta(-360, -740),
  // JANTAR: mesa redonda com pé central e 4 cadeiras; aparador; pendente sobre a mesa
  cilindro(-750, 520, 120, 6, 72), cilindro(-750, 520, 18, 72),
  ...cadeira(-750, 360, "s"), ...cadeira(-750, 680, "n"), ...cadeira(-910, 520, "l"), ...cadeira(-590, 520, "o"),
  caixa(-1195, 330, -1150, 690, 80),
  cilindro(-750, 520, 32, 16, 192), cilindro(-750, 520, 1.5, 52, 208),
  // ESCRITÓRIO: mesa de trabalho sob a janela com monitor, cadeira giratória, estante vazada na parede, planta
  caixa(-150, -790, 250, -660, 4, 72), ...pesMesa(-150, -790, 250, -660, 72),
  caixa(10, -772, 130, -766, 58, 92), cilindro(70, -760, 4, 20, 76),
  cilindro(70, -600, 30, 4), cilindro(70, -600, 4, 40, 4), cilindro(70, -600, 26, 7, 44), caixa(45, -572, 95, -566, 46, 52),
  caixa(-295, -720, -255, -714, 190), caixa(-295, -306, -255, -300, 190),
  ...[0, 46, 92, 138, 184].map((z) => caixa(-295, -714, -255, -306, 4, z)),
  caixa(-290, -700, -262, -620, 34, 4), caixa(-290, -520, -262, -420, 30, 50), caixa(-290, -660, -262, -560, 32, 96),
  caixa(-290, -440, -262, -330, 34, 142),
  ...planta(-245, 45),
  // BANHO: gabinete com cuba e espelho, vaso com caixa acoplada, box de vidro com chuveiro
  caixa(460, -795, 740, -740, 82), cilindro(600, -767, 18, 4, 80), caixa(490, -799, 710, -795, 80, 110),
  caixa(770, -625, 795, -575, 40, 40), cilindro(745, -600, 22, 40),
  caixa(600, 60, 795, 245, 5), caixa(600, 60, 604, 245, 195, 5), caixa(604, 60, 700, 64, 195, 5),
  cilindro(760, 215, 10, 4, 200),
  // COZINHA: bancada em L com pia e cooktop, geladeira de duas portas, mesinha redonda com 2 cadeiras
  caixa(820, -795, 1190, -735, 90), caixa(1130, -735, 1190, -420, 90), caixa(940, -785, 1020, -745, 3, 88),
  cilindro(1148, -690, 8, 2, 90), cilindro(1172, -690, 8, 2, 90), cilindro(1148, -650, 8, 2, 90), cilindro(1172, -650, 8, 2, 90),
  caixa(1120, -400, 1190, -330, 120), caixa(1120, -400, 1190, -330, 68, 123),
  cilindro(980, 60, 55, 4, 72), cilindro(980, 60, 8, 72),
  ...cadeira(980, -35, "s", 28), ...cadeira(980, 155, "n", 28),
  // SUÍTE: cama de casal com cabeceira, colchão, edredom e travesseiros; criados com abajur; guarda-roupa; tapete; poltrona
  caixa(640, 255, 820, 272, 115), caixa(650, 272, 810, 470, 30), caixa(655, 277, 805, 465, 20, 30),
  caixa(652, 360, 808, 468, 4, 50), caixa(670, 285, 725, 325, 12, 50), caixa(735, 285, 790, 325, 12, 50),
  caixa(585, 258, 635, 300, 50), cilindro(610, 279, 4, 25, 50), cilindro(610, 279, 15, 18, 75),
  caixa(825, 258, 875, 300, 50), cilindro(850, 279, 4, 25, 50), cilindro(850, 279, 15, 18, 75),
  caixa(405, 520, 465, 607, 210), caixa(405, 610, 465, 697, 210), caixa(405, 700, 465, 790, 210),
  caixa(600, 500, 860, 650, 1),
  caixa(1090, 690, 1170, 770, 40), caixa(1090, 752, 1170, 770, 45, 40),
  // CIRCULAÇÃO: aparador com espelho e objeto, planta
  caixa(-60, 755, 200, 795, 80), caixa(-20, 795, 160, 799, 90, 100), cilindro(170, 775, 10, 25, 80),
  ...planta(-250, 740),
];

function gerarPlanta() {
  const X: number[] = [], Y: number[] = [], Z: number[] = [], K: number[] = [];
  const T: number[] = []; // traços: pares [primeiro ponto, último ponto] ligados por linha
  const add = (x: number, y: number, z: number, k: number) => {
    X.push(x); Y.push(y); Z.push(z); K.push(k);
  };
  const linha = (x1: number, y1: number, x2: number, y2: number, k: number, z = 0, passo = 24, z2 = z) => {
    const n = Math.max(1, Math.round(Math.hypot(x2 - x1, y2 - y1, z2 - z) / passo));
    const ini = X.length;
    for (let i = 0; i <= n; i++) add(x1 + ((x2 - x1) * i) / n, y1 + ((y2 - y1) * i) / n, z + ((z2 - z) * i) / n, k);
    T.push(ini, X.length - 1);
  };
  const parede = (x1: number, y1: number, x2: number, y2: number) => {
    linha(x1, y1, x2, y2, PAREDE, 0, 22);
    linha(x1, y1, x2, y2, PAREDE, ALTURA_PAREDE, 28);
    for (const [x, y] of [[x1, y1], [x2, y2]]) linha(x, y, x, y, PAREDE, 0, 26, ALTURA_PAREDE);
  };
  const ret = (x1: number, y1: number, x2: number, y2: number, k = FINO) => {
    linha(x1, y1, x2, y1, k); linha(x2, y1, x2, y2, k); linha(x2, y2, x1, y2, k); linha(x1, y2, x1, y1, k);
  };
  const arco = (cx: number, cy: number, r: number, a0: number, a1: number, k = FINO) => {
    const n = Math.max(6, Math.round((Math.abs(a1 - a0) * r) / 18));
    const ini = X.length;
    for (let i = 0; i <= n; i++) {
      const a = a0 + ((a1 - a0) * i) / n;
      add(cx + Math.cos(a) * r, cy + Math.sin(a) * r, 0, k);
    }
    T.push(ini, X.length - 1);
  };
  const porta = (x: number, y: number, r: number, a0: number) => {
    arco(x, y, r, a0, a0 + Math.PI / 2);
    linha(x, y, x + Math.cos(a0 + Math.PI / 2) * r, y + Math.sin(a0 + Math.PI / 2) * r, FINO);
  };
  const janelaH = (x1: number, x2: number, y: number) => { linha(x1, y - 6, x2, y - 6, FINO); linha(x1, y + 6, x2, y + 6, FINO); };
  const janelaV = (y1: number, y2: number, x: number) => { linha(x - 6, y1, x - 6, y2, FINO); linha(x + 6, y1, x + 6, y2, FINO); };

  // paredes externas
  parede(-1200, -800, 1200, -800); parede(1200, -800, 1200, 800);
  parede(1200, 800, -1200, 800); parede(-1200, 800, -1200, -800);
  // paredes internas (com vãos de porta)
  parede(-300, -800, -300, -160); parede(-300, -60, -300, 800);
  parede(-300, 100, 280, 100);
  parede(400, -800, 400, -220); parede(400, -120, 400, 300); parede(400, 400, 400, 800);
  parede(400, 250, 1200, 250);
  parede(-1200, 200, -720, 200); parede(-600, 200, -300, 200);
  parede(800, -800, 800, -360); parede(800, -260, 800, 250);
  // portas
  porta(-300, -160, 100, Math.PI / 2); porta(400, -220, 100, Math.PI / 2);
  porta(400, 300, 100, 0); porta(-720, 200, 120, -Math.PI / 2); porta(800, -360, 100, Math.PI / 2);
  // janelas
  janelaH(-1000, -600, -800); janelaH(-100, 250, -800); janelaH(900, 1120, -800);
  janelaH(-1000, -500, 800); janelaH(550, 1050, 800); janelaV(-600, -200, -1200); janelaV(350, 650, 1200);
  // contorno no chão de cada móvel que encosta no piso (os pés e peças pequenas ficam de fora)
  for (const m of MOVEIS) {
    if (m.z0 > 1) continue;
    if (m.tipo === "caixa" && Math.max(m.x2 - m.x1, m.y2 - m.y1) >= 20) ret(m.x1, m.y1, m.x2, m.y2);
    if (m.tipo === "cilindro" && m.r >= 15) arco(m.cx, m.cy, m.r, 0, Math.PI * 2);
  }
  // pisos: porcelanato (grade) na cozinha e tábuas no estar
  for (let x = 860; x < 1200; x += 70) linha(x, -800, x, 250, PISO, 0, 60);
  for (let y = -760; y < 250; y += 70) linha(800, y, 1200, y, PISO, 0, 60);
  for (let y = -780; y < 200; y += 48) linha(-1200, y, -300, y, PISO, 0, 60);
  // cotas: linha, marcas e chamadas
  const cotaH = (x1: number, x2: number, y: number) => {
    linha(x1, y, x2, y, COTA, 0, 30);
    for (const x of [x1, x2]) { linha(x - 14, y + 14, x + 14, y - 14, COTA, 0, 20); linha(x, y + 30, x, y - 30, COTA, 0, 20); }
  };
  const cotaV = (y1: number, y2: number, x: number) => {
    linha(x, y1, x, y2, COTA, 0, 30);
    for (const y of [y1, y2]) { linha(x - 14, y + 14, x + 14, y - 14, COTA, 0, 20); linha(x - 30, y, x + 30, y, COTA, 0, 20); }
  };
  cotaH(-1200, -300, -920); cotaH(-300, 400, -920); cotaH(400, 1200, -920);
  cotaV(-800, 200, -1320); cotaV(200, 800, -1320);

  const rotulos: Rotulo[] = [
    { x: -900, y: -150, texto: "Estar" }, { x: -1010, y: 280, texto: "Jantar" }, { x: 50, y: -300, texto: "Escritório" },
    { x: 1000, y: -120, texto: "Cozinha" }, { x: 600, y: -40, texto: "Banho" }, { x: 760, y: 560, texto: "Suíte" },
    { x: -40, y: 560, texto: "Circulação" },
    { x: -750, y: -960, texto: "9,00", cota: true }, { x: 50, y: -960, texto: "7,00", cota: true },
    { x: 800, y: -960, texto: "8,00", cota: true }, { x: -1380, y: -300, texto: "10,00", cota: true },
    { x: -1380, y: 500, texto: "6,00", cota: true },
  ];

  // poeira de luz no ar
  for (let i = 0; i < 420; i++) add((Math.random() - 0.5) * 3400, (Math.random() - 0.5) * 2400, 30 + Math.random() * 520, POEIRA);

  const n = X.length;
  const S = new Float32Array(n);
  for (let i = 0; i < n; i++) S[i] = Math.random();
  return {
    n, X: Float32Array.from(X), Y: Float32Array.from(Y), Z: Float32Array.from(Z), K: Uint8Array.from(K), S, rotulos,
    T: Uint32Array.from(T),
  };
}

// caminho da câmera: passeio pela casa passando pelas portas, sem atravessar móveis (laço fechado, Catmull-Rom)
const CAMINHO: [number, number][] = [
  [-950, -100], // estar
  [-300, -110], // porta estar → escritório
  [50, -350], // escritório
  [400, -170], // porta escritório → banho
  [600, -300], // banho
  [800, -310], // porta banho → cozinha
  [990, -200], // cozinha
  [1000, 400], // suíte (atravessa a parede da cozinha, sem móveis)
  [950, 600],
  [400, 350], // porta suíte → circulação
  [50, 450], // circulação
  [-300, 450], // parede para o jantar
  [-1000, 330], // jantar
  [-660, 200], // porta jantar → estar
];
function noCaminho(u: number): [number, number] {
  const n = CAMINHO.length;
  const t = (((u % 1) + 1) % 1) * n;
  const i = Math.floor(t), f = t - i;
  const p0 = CAMINHO[(i - 1 + n) % n], p1 = CAMINHO[i % n], p2 = CAMINHO[(i + 1) % n], p3 = CAMINHO[(i + 2) % n];
  const c = (a: number, b: number, c2: number, d: number) =>
    0.5 * (2 * b + (-a + c2) * f + (2 * a - 5 * b + 4 * c2 - d) * f * f + (-a + 3 * b - 3 * c2 + d) * f * f * f);
  return [c(p0[0], p1[0], p2[0], p3[0]), c(p0[1], p1[1], p2[1], p3[1])];
}

function sprite(r: number, g: number, b: number) {
  const c = document.createElement("canvas");
  c.width = c.height = 32;
  const x = c.getContext("2d")!;
  const gr = x.createRadialGradient(16, 16, 0, 16, 16, 16);
  gr.addColorStop(0, `rgba(${r},${g},${b},1)`);
  gr.addColorStop(0.28, `rgba(${r},${g},${b},0.85)`);
  gr.addColorStop(0.55, `rgba(${r},${g},${b},0.22)`);
  gr.addColorStop(1, `rgba(${r},${g},${b},0)`);
  x.fillStyle = gr;
  x.fillRect(0, 0, 32, 32);
  return c;
}

const suave = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

export function PlantaViva() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const hero = canvas?.parentElement;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !hero || !ctx) return;

    const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const P = gerarPlanta();
    const OX = new Float32Array(P.n), OY = new Float32Array(P.n);
    // posição na tela, alfa e brilho de cada ponto no quadro atual (alfa 0 = não desenhar)
    const SX = new Float32Array(P.n), SY = new Float32Array(P.n), AL = new Float32Array(P.n), BR = new Float32Array(P.n);
    const NIVEIS = 10;
    const caminhos = { marfim: [] as Path2D[], azul: [] as Path2D[] };
    const marfim = sprite(237, 237, 243), azul = sprite(143, 156, 255);

    let W = 0, H = 0, V = 0, dpr = 1; // W×H = palco (topo + prévia); V = altura da tela visível
    const medir = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      W = hero.clientWidth; H = hero.clientHeight; V = window.innerHeight || H;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    };
    medir();

    // estado
    let tempo = reduzido ? DURACAO_INTRO : 0, u = 0.02, extra = 0, foco = 0, alvoFoco = 0, rolagem = 0;
    let mx = -1e5, my = -1e5, tiltX = 0, tiltY = 0;
    const cresce = new Float32Array(MOVEIS.length); // 0 = só o contorno no chão, 1 = volume inteiro
    const centro = MOVEIS.map((m) => (m.tipo === "caixa" ? [(m.x1 + m.x2) / 2, (m.y1 + m.y2) / 2] : [m.cx, m.cy]));
    const LADOS_CILINDRO = 18;
    const BX = new Float32Array(40), BY = new Float32Array(40), TX = new Float32Array(40), TY = new Float32Array(40);

    const desenhar = (dt: number) => {
      tempo += dt;
      const intro = Math.min(1, tempo / DURACAO_INTRO);
      const ei = 1 - Math.pow(1 - intro, 3);
      foco += (alvoFoco - foco) * Math.min(1, dt * 2.2);
      u += VELOCIDADE * dt * (1 - foco * 0.92) * (0.35 + 0.65 * ei);
      const alvoExtra = (window.scrollY / Math.max(1, V)) * 0.12;
      extra += (alvoExtra - extra) * Math.min(1, dt * 3);
      // quanto do palco já passou pela tela (px); a câmera acompanha a rolagem
      const deslocado = Math.min(Math.max(0, -hero.getBoundingClientRect().top), Math.max(0, H - V));
      const alvoRolagem = H > V ? deslocado / Math.max(1, H - V * 1.15) : 0;
      rolagem += (Math.min(1, alvoRolagem) - rolagem) * Math.min(1, dt * 4);
      const rl = rolagem * rolagem * (3 - 2 * rolagem);

      const temMouse = mx > -1e4 && !reduzido;
      tiltX += ((temMouse ? (mx / W - 0.5) : 0) - tiltX) * Math.min(1, dt * 2);
      tiltY += ((temMouse ? (Math.min(Math.max(0, my - deslocado), V) / V - 0.5) : 0) - tiltY) * Math.min(1, dt * 2);

      const [cx, cy] = noCaminho(u + extra);
      const [fx, fy] = noCaminho(u + extra + 0.012);
      const cz = ALTURA_INICIAL + (ALTURA_VOO + (ALTURA_ROLADA - ALTURA_VOO) * rl - ALTURA_INICIAL) * ei;
      const yaw = Math.atan2(fy - cy, fx - cx) + tiltX * 0.22;
      const pitch = 1.35 + (PITCH_TOPO + (PITCH_ROLADO - PITCH_TOPO) * rl - 1.35) * ei + tiltY * 0.1;
      const cosY = Math.cos(yaw), sinY = Math.sin(yaw), cosP = Math.cos(pitch), sinP = Math.sin(pitch);
      const f = Math.max(W, V) * 0.6 * dpr;
      // o centro da imagem fica sempre na tela visível (o canvas rola com a página)
      const meioX = (W * dpr) / 2, meioY = (deslocado + V * 0.46) * dpr;
      const raio = RAIO_MOUSE * dpr, empurrao = EMPURRAO * dpr;
      const mxd = mx * dpr, myd = my * dpr;
      const revelar = ei * 2300;
      const mola = Math.min(1, dt * 7);

      ctx.globalCompositeOperation = "source-over";
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = "lighter";

      // 1) projeta todos os pontos
      for (let i = 0; i < P.n; i++) {
        AL[i] = 0;
        const k = P.K[i], s = P.S[i];
        let x = P.X[i], y = P.Y[i], z = P.Z[i];
        if (k !== POEIRA && intro < 1 && Math.hypot(x, y) > revelar) continue;
        if (k === POEIRA) {
          x += Math.sin(tempo * 0.25 + s * 40) * 30;
          z += Math.sin(tempo * 0.4 + s * 60) * 22;
        }
        if (foco > 0.001) {
          const a = s * 6.2832 * 7;
          x += Math.cos(a) * foco * (40 + s * 120);
          y += Math.sin(a) * foco * (40 + s * 120);
          z += foco * (30 + s * 260) + Math.sin(tempo * 1.1 + s * 30) * foco * 18;
        }
        const dx = x - cx, dy = y - cy, dz = z - cz;
        const frente = dx * cosY + dy * sinY;
        const lado = -dx * sinY + dy * cosY;
        const prof = frente * cosP - dz * sinP;
        if (prof < 30) continue;
        const vert = frente * sinP + dz * cosP;
        let sx = meioX + (f * lado) / prof;
        let sy = meioY - (f * vert) / prof;
        if (Math.abs(sx - meioX) > canvas.width * 3 || Math.abs(sy - meioY) > canvas.height * 3) continue;

        // mouse: empurra e acende
        let brilho = 0, alvoOx = 0, alvoOy = 0;
        if (temMouse) {
          const ddx = sx - mxd, ddy = sy - myd;
          const d = Math.hypot(ddx, ddy);
          if (d < raio) {
            const q = 1 - d / raio;
            brilho = q;
            const forca = q * q * empurrao;
            alvoOx = (ddx / (d || 1)) * forca;
            alvoOy = (ddy / (d || 1)) * forca;
          }
        }
        OX[i] += (alvoOx - OX[i]) * mola;
        OY[i] += (alvoOy - OY[i]) * mola;
        sx += OX[i]; sy += OY[i];

        const neblina = 1 - suave(1200, 3800, prof);
        const perto = suave(70, 340, prof);
        SX[i] = sx; SY[i] = sy; BR[i] = brilho;
        AL[i] = Math.min(1, ALFA[k] * neblina * perto * (0.75 + 0.25 * s) + brilho * 0.8);
      }

      // 2) traços: linhas finas entre pontos vizinhos, agrupadas por brilho (poucos stroke por quadro)
      const sumir = 1 - foco; // no foco a planta se desmancha: some a linha, ficam as partículas
      if (sumir > 0.01) {
        for (let n = 0; n < NIVEIS; n++) { caminhos.marfim[n] = new Path2D(); caminhos.azul[n] = new Path2D(); }
        for (let t = 0; t < P.T.length; t += 2) {
          for (let i = P.T[t]; i < P.T[t + 1]; i++) {
            const a = Math.min(AL[i], AL[i + 1]) * sumir;
            if (a < 0.02) continue;
            const nivel = Math.min(NIVEIS - 1, Math.floor(a * NIVEIS));
            const alvo = BR[i] > 0.15 || BR[i + 1] > 0.15 ? caminhos.azul[nivel] : caminhos.marfim[nivel];
            alvo.moveTo(SX[i], SY[i]);
            alvo.lineTo(SX[i + 1], SY[i + 1]);
          }
        }
        ctx.lineCap = "round";
        for (let n = 0; n < NIVEIS; n++) {
          ctx.globalAlpha = ((n + 0.5) / NIVEIS) * OPACIDADE_LINHA;
          ctx.lineWidth = (0.6 + n * 0.07) * dpr;
          ctx.strokeStyle = "rgb(237,237,243)";
          ctx.stroke(caminhos.marfim[n]);
          ctx.globalAlpha = ((n + 0.5) / NIVEIS) * 0.7; // perto do mouse a linha continua acesa
          ctx.strokeStyle = "rgb(143,156,255)";
          ctx.lineWidth = (1.1 + n * 0.12) * dpr;
          ctx.stroke(caminhos.azul[n]);
        }
      }

      // 3) móveis: volumes translúcidos que crescem do chão quando a câmera se aproxima
      const projetar = (x: number, y: number, z: number, saida: Float32Array, sy: Float32Array, j: number) => {
        const dx = x - cx, dy = y - cy, dz = z - cz;
        const frente = dx * cosY + dy * sinY;
        const lado = -dx * sinY + dy * cosY;
        const prof = frente * cosP - dz * sinP;
        if (prof < 40) return false;
        const vert = frente * sinP + dz * cosP;
        saida[j] = meioX + (f * lado) / prof;
        sy[j] = meioY - (f * vert) / prof;
        return prof;
      };
      ctx.setLineDash([0.1, 5 * dpr]);
      ctx.lineCap = "round";
      for (let m = 0; m < MOVEIS.length; m++) {
        const mv = MOVEIS[m];
        const [mcx, mcy] = centro[m];
        // distância até o ponto do chão para onde a câmera olha (~800 à frente)
        const dist = Math.hypot(mcx - (cx + Math.cos(yaw) * 800), mcy - (cy + Math.sin(yaw) * 800));
        const alvo = dist < 950 && (intro >= 1 || Math.hypot(mcx, mcy) < revelar) ? 1 : 0;
        cresce[m] += (alvo - cresce[m]) * Math.min(1, dt * (alvo ? 1.3 : 0.8));
        const c = cresce[m];
        if (c < 0.01) continue;
        const e = c < 1 ? 1 - Math.pow(1 - c, 3) : 1;
        const z0 = mv.z0 * e + foco * 90, z1 = (mv.z0 + mv.h) * e + foco * 90;
        // contorno: 4 cantos da caixa ou N lados do cilindro
        let n = 0, ok = true, profMedia = 0;
        if (mv.tipo === "caixa") {
          const xs = [mv.x1, mv.x2, mv.x2, mv.x1], ys = [mv.y1, mv.y1, mv.y2, mv.y2];
          for (let j = 0; j < 4 && ok; j++) {
            const pb = projetar(xs[j], ys[j], z0, BX, BY, j), pt = projetar(xs[j], ys[j], z1, TX, TY, j);
            ok = !!pb && !!pt; profMedia += (pb || 0) / 4;
          }
          n = 4;
        } else {
          for (let j = 0; j < LADOS_CILINDRO && ok; j++) {
            const a = (j / LADOS_CILINDRO) * Math.PI * 2;
            const x = mv.cx + Math.cos(a) * mv.r, y = mv.cy + Math.sin(a) * mv.r;
            const pb = projetar(x, y, z0, BX, BY, j), pt = projetar(x, y, z1, TX, TY, j);
            ok = !!pb && !!pt; profMedia += (pb || 0) / LADOS_CILINDRO;
          }
          n = LADOS_CILINDRO;
        }
        if (!ok) continue;
        // mouse perto do centro do tampo acende o móvel
        let tcx = 0, tcy = 0;
        for (let j = 0; j < n; j++) { tcx += TX[j] / n; tcy += TY[j] / n; }
        const acende = temMouse ? Math.max(0, 1 - Math.hypot(tcx - mxd, tcy - myd) / (raio * 1.6)) : 0;
        // atrás do título e dos botões (centro da primeira tela) o móvel fica bem mais apagado, para o texto ler bem
        const ex = (tcx - meioX) / (0.36 * W * dpr), ey = (tcy - V * dpr * 0.5) / (0.32 * V * dpr);
        const longeDoTexto = 0.22 + 0.78 * suave(0.55, 1.15, Math.hypot(ex, ey));
        const a = e * longeDoTexto * (1 - suave(1200, 3600, profMedia)) * (1 - foco * 0.85) * (1 + acende * 1.2);
        if (a < 0.02) continue;
        // laterais
        ctx.fillStyle = "rgb(82,102,235)";
        ctx.globalAlpha = 0.07 * a;
        for (let j = 0; j < n; j++) {
          const k2 = (j + 1) % n;
          ctx.beginPath();
          ctx.moveTo(BX[j], BY[j]); ctx.lineTo(BX[k2], BY[k2]); ctx.lineTo(TX[k2], TY[k2]); ctx.lineTo(TX[j], TY[j]);
          ctx.closePath();
          ctx.fill();
        }
        // tampo
        ctx.fillStyle = "rgb(143,156,255)";
        ctx.globalAlpha = 0.2 * a;
        ctx.beginPath();
        ctx.moveTo(TX[0], TY[0]);
        for (let j = 1; j < n; j++) ctx.lineTo(TX[j], TY[j]);
        ctx.closePath();
        ctx.fill();
        // arestas em pontilhado
        ctx.strokeStyle = "rgb(237,237,243)";
        ctx.lineWidth = 1.8 * dpr;
        ctx.globalAlpha = Math.min(1, 0.75 * a);
        ctx.stroke();
        if (mv.tipo === "caixa") {
          ctx.beginPath();
          for (let j = 0; j < 4; j++) { ctx.moveTo(BX[j], BY[j]); ctx.lineTo(TX[j], TY[j]); }
          ctx.stroke();
        }
      }
      ctx.setLineDash([]);

      // 4) pontilhado: todos os pontos da planta, poeira, brilho perto do mouse e as partículas do foco
      for (let i = 0; i < P.n; i++) {
        const a0 = AL[i];
        if (a0 < 0.02) continue;
        const k = P.K[i], s = P.S[i], brilho = BR[i];
        // todo ponto da planta vira pontilhado; alguns (s > 0.86) piscam como faísca
        const faisca = s > 0.86;
        const pulso = k === POEIRA || !faisca ? 1 : 0.7 + 0.6 * Math.sin(tempo * 2 + s * 50);
        const alfa = Math.min(1, (k === POEIRA ? a0 : a0 * OPACIDADE_PONTO * pulso) + foco * 0.35);
        const tam = (TAMANHO[k] * (1 + (faisca ? 0.35 : 0) + brilho * 2.2 + foco * 1.2)) * dpr;
        ctx.globalAlpha = alfa;
        ctx.drawImage(brilho > 0.12 || (foco > 0.3 && s > 0.55) ? azul : marfim, SX[i] - tam, SY[i] - tam, tam * 2, tam * 2);
      }

      // nomes dos ambientes e medidas, deitados na planta
      ctx.globalCompositeOperation = "source-over";
      ctx.textAlign = "center";
      ctx.fillStyle = "rgb(237,237,243)";
      for (const r of P.rotulos) {
        if (intro < 1 && Math.hypot(r.x, r.y) > revelar - 200) continue;
        const dx = r.x - cx, dy = r.y - cy, dz = 2 - cz + foco * 160;
        const frente = dx * cosY + dy * sinY;
        const lado = -dx * sinY + dy * cosY;
        const prof = frente * cosP - dz * sinP;
        if (prof < 80) continue;
        const vert = frente * sinP + dz * cosP;
        const tam = Math.min(20, Math.max(9, (f * (r.cota ? 22 : 30)) / prof / dpr)) * dpr;
        ctx.globalAlpha = (r.cota ? 0.3 : 0.2) * (1 - suave(1100, 3400, prof)) * suave(80, 260, prof) * (1 - foco * 0.8);
        ctx.font = `${r.cota ? 400 : 480} ${tam}px Inter, system-ui, sans-serif`;
        ctx.fillText(r.texto, meioX + (f * lado) / prof, meioY - (f * vert) / prof);
      }
      ctx.globalAlpha = 1;
    };

    let quadro = 0, ultimo = 0, visivel = true;
    const laco = (agora: number) => {
      // segue o relógio mesmo com poucos quadros por segundo (máx. 0,25 s por quadro, para não saltar ao voltar da aba)
      const dt = ultimo ? Math.min(0.25, (agora - ultimo) / 1000) : 0.016;
      ultimo = agora;
      desenhar(dt);
      quadro = requestAnimationFrame(laco);
    };
    const iniciar = () => {
      if (reduzido || quadro || !visivel || document.hidden) return;
      ultimo = 0;
      quadro = requestAnimationFrame(laco);
    };
    const parar = () => {
      cancelAnimationFrame(quadro);
      quadro = 0;
    };

    if (reduzido) desenhar(0);
    else iniciar();

    const aoMover = (e: PointerEvent) => {
      const r = canvas.getBoundingClientRect();
      mx = e.clientX - r.left; my = e.clientY - r.top;
    };
    const aoSair = () => { mx = my = -1e5; };
    const aoRedimensionar = () => { medir(); if (reduzido) desenhar(0); };
    const aoVisibilidade = () => (document.hidden ? parar() : iniciar());
    hero.addEventListener("pointermove", aoMover);
    hero.addEventListener("pointerleave", aoSair);
    window.addEventListener("resize", aoRedimensionar);
    document.addEventListener("visibilitychange", aoVisibilidade);
    const obs = new IntersectionObserver(([e]) => {
      visivel = e.isIntersecting;
      if (visivel) iniciar(); else parar();
    });
    obs.observe(hero);

    const focos = [...hero.querySelectorAll<HTMLElement>("[data-planta-foco]")];
    const ligar = () => { alvoFoco = 1; };
    const desligar = () => { alvoFoco = 0; };
    for (const el of focos) {
      el.addEventListener("pointerenter", ligar); el.addEventListener("pointerleave", desligar);
      el.addEventListener("focus", ligar); el.addEventListener("blur", desligar);
    }

    return () => {
      parar();
      obs.disconnect();
      hero.removeEventListener("pointermove", aoMover);
      hero.removeEventListener("pointerleave", aoSair);
      window.removeEventListener("resize", aoRedimensionar);
      document.removeEventListener("visibilitychange", aoVisibilidade);
      for (const el of focos) {
        el.removeEventListener("pointerenter", ligar); el.removeEventListener("pointerleave", desligar);
        el.removeEventListener("focus", ligar); el.removeEventListener("blur", desligar);
      }
    };
  }, []);

  return <canvas ref={ref} className="in-planta-viva" aria-hidden="true" />;
}
