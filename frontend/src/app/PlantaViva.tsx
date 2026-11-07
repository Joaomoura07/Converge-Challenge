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
const ALTURA_VOO = 680;
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
  // móveis: estar
  ret(-1120, -700, -680, -560); ret(-1120, -560, -1040, -380); ret(-900, -420, -700, -300);
  arco(-500, -650, 70, 0, Math.PI * 2);
  // jantar
  arco(-750, 520, 120, 0, Math.PI * 2); arco(-750, 520, 60, 0, Math.PI * 2);
  for (const [cx, cy] of [[-750, 360], [-750, 680], [-910, 520], [-590, 520]]) ret(cx - 35, cy - 30, cx + 35, cy + 30);
  // escritório
  ret(-240, -760, 340, -660); ret(-60, -620, 60, -520); ret(-220, -200, 0, 40); ret(160, -200, 340, 40);
  // cozinha
  ret(820, -780, 1180, -700); ret(1100, -700, 1180, -380); ret(870, -560, 1080, -440);
  arco(960, -740, 22, 0, Math.PI * 2); arco(1040, -740, 22, 0, Math.PI * 2);
  // banheiro e quarto
  ret(440, -760, 760, -620); arco(520, -420, 40, 0, Math.PI * 2); ret(640, -300, 760, -120);
  ret(520, 380, 900, 720); ret(560, 400, 860, 480); ret(940, 380, 1160, 460); ret(-260, 300, 120, 380);
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
    { x: -900, y: -150, texto: "Estar" }, { x: -750, y: 330, texto: "Jantar" }, { x: 50, y: -300, texto: "Escritório" },
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

// caminho da câmera: laço fechado passando pelos ambientes (Catmull-Rom)
const CAMINHO: [number, number][] = [
  [-820, -420], [-60, -520], [600, -560], [1050, -150], [900, 480], [300, 600], [-300, 480], [-950, 420], [-1050, -40],
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

    let W = 0, H = 0, dpr = 1;
    const medir = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      W = hero.clientWidth; H = hero.clientHeight;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    };
    medir();

    // estado
    let tempo = reduzido ? DURACAO_INTRO : 0, u = 0.02, extra = 0, foco = 0, alvoFoco = 0;
    let mx = -1e5, my = -1e5, tiltX = 0, tiltY = 0;

    const desenhar = (dt: number) => {
      tempo += dt;
      const intro = Math.min(1, tempo / DURACAO_INTRO);
      const ei = 1 - Math.pow(1 - intro, 3);
      foco += (alvoFoco - foco) * Math.min(1, dt * 2.2);
      u += VELOCIDADE * dt * (1 - foco * 0.92) * (0.35 + 0.65 * ei);
      const alvoExtra = (window.scrollY / Math.max(1, H)) * 0.12;
      extra += (alvoExtra - extra) * Math.min(1, dt * 3);

      const temMouse = mx > -1e4 && !reduzido;
      tiltX += ((temMouse ? (mx / W - 0.5) : 0) - tiltX) * Math.min(1, dt * 2);
      tiltY += ((temMouse ? (my / H - 0.5) : 0) - tiltY) * Math.min(1, dt * 2);

      const [cx, cy] = noCaminho(u + extra);
      const [fx, fy] = noCaminho(u + extra + 0.012);
      const cz = ALTURA_INICIAL + (ALTURA_VOO - ALTURA_INICIAL) * ei;
      const yaw = Math.atan2(fy - cy, fx - cx) + tiltX * 0.22;
      const pitch = 1.35 + (0.86 - 1.35) * ei + tiltY * 0.1;
      const cosY = Math.cos(yaw), sinY = Math.sin(yaw), cosP = Math.cos(pitch), sinP = Math.sin(pitch);
      const f = Math.max(W, H) * 0.6 * dpr;
      const meioX = (W * dpr) / 2, meioY = (H * dpr) * 0.46;
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
        const perto = suave(40, 220, prof);
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

      // 3) pontilhado: todos os pontos da planta, poeira, brilho perto do mouse e as partículas do foco
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
