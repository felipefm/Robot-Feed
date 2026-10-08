/* cifras_teclado.js
 * Calcula e desenha diagramas de teclado para acordes, sem depender de
 * nenhuma imagem externa. Lida com acordes com baixo (ex: D/F#).
 */

const NOTE_BASE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

const CHORD_INTERVALS = {
  '':      [0, 4, 7],
  'm':     [0, 3, 7],
  '7':     [0, 4, 7, 10],
  'm7':    [0, 3, 7, 10],
  'maj7':  [0, 4, 7, 11],
  'mmaj7': [0, 3, 7, 11],
  'dim':   [0, 3, 6],
  'dim7':  [0, 3, 6, 9],
  'm7b5':  [0, 3, 6, 10],
  'aug':   [0, 4, 8],
  '7+':    [0, 4, 8, 10],   // dominante com 5ª aumentada
  '6':     [0, 4, 7, 9],
  'm6':    [0, 3, 7, 9],
  '9':     [0, 4, 7, 10, 2],
  'add9':  [0, 4, 7, 2],
  'sus2':  [0, 2, 7],
  'sus4':  [0, 5, 7],
};

// Tensões que podem se somar a uma base acima (ex: "7+" + "9" = "7+/9")
const TENSAO_INTERVALO = {
  '9': 2, '#9': 3, 'b9': 1,
  '11': 5, '#11': 6,
  '13': 9, 'b13': 8,
};

function normalizarSufixo(sufixo) {
  let s = sufixo.replace(/\(|\)/g, '').replace(/°/g, 'dim').trim();
  // Notação brasileira comum: "7M"/"M7" = sétima maior; "m7M" = menor com sétima maior
  if (s === 'm7M' || s === 'mM7') s = 'mmaj7';
  else if (s === '7M' || s === 'M7' || s === 'Maj7' || s === 'MAJ7') s = 'maj7';
  return s;
}

function resolverIntervalos(sufixo) {
  // 1) combinação exata já conhecida
  if (CHORD_INTERVALS[sufixo] !== undefined) return CHORD_INTERVALS[sufixo];

  // 2) tenta separar uma tensão no final (9, 11, 13, com # ou b opcional)
  //    ex: "79" -> base "7" + tensão "9" | "7+9" -> base "7+" + tensão "9"
  const mTensao = sufixo.match(/(#|b)?(9|11|13)$/);
  if (mTensao) {
    const tensaoStr = mTensao[0];
    const base = sufixo.slice(0, sufixo.length - tensaoStr.length);
    const intervalosBase = CHORD_INTERVALS[base] !== undefined ? CHORD_INTERVALS[base] : CHORD_INTERVALS[''];
    const tensaoIntervalo = TENSAO_INTERVALO[tensaoStr];
    if (tensaoIntervalo !== undefined) {
      return [...intervalosBase, tensaoIntervalo];
    }
  }

  // 3) não reconhecido -> tríade maior como aproximação razoável
  return CHORD_INTERVALS[''];
}

function parseNota(str) {
  const m = str.match(/^([A-G])(#|b)?/);
  if (!m) return null;
  let n = NOTE_BASE[m[1]];
  if (m[2] === '#') n += 1;
  if (m[2] === 'b') n -= 1;
  return ((n % 12) + 12) % 12;
}

function parseAcorde(nomeCompleto) {
  const mRaiz = nomeCompleto.match(/^([A-G])(#|b)?/);
  if (!mRaiz) return null;
  const textoRaiz = mRaiz[0];
  const raizPc = parseNota(textoRaiz);
  const resto = nomeCompleto.slice(textoRaiz.length);

  let baixoPc = raizPc;
  let sufixoBruto = resto;

  const idxBarra = resto.indexOf('/');
  if (idxBarra !== -1) {
    const antesBarra = resto.slice(0, idxBarra);
    const depoisBarra = resto.slice(idxBarra + 1);
    const ehNotaDeBaixo = /^[A-G](#|b)?$/.test(depoisBarra);
    if (ehNotaDeBaixo) {
      // barra indicando baixo de verdade, ex: "D/F#"
      baixoPc = parseNota(depoisBarra);
      sufixoBruto = antesBarra;
    } else {
      // não é uma nota -> é tensão/extensão, ex: "7+/9" (não é "baixo 9", que nem existe)
      sufixoBruto = antesBarra + depoisBarra;
    }
  }

  const sufixo = normalizarSufixo(sufixoBruto);
  const intervalos = resolverIntervalos(sufixo);
  const tonsAcordePc = intervalos.map(i => ((raizPc + i) % 12 + 12) % 12);

  if (baixoPc === null) return null;

  const pcsUnicos = Array.from(new Set([baixoPc, ...tonsAcordePc]));

  const notas = pcsUnicos
    .map(pc => baixoPc + ((pc - baixoPc) % 12 + 12) % 12)
    .sort((a, b) => a - b);

  return { baixo: baixoPc, notas, nomeExibicao: nomeCompleto };
}

const KB_W = 26, KB_H = 88, KB_BW = 16, KB_BH = 54, KB_N_OITAVAS = 2;
const BRANCAS_LOCAL = [0, 2, 4, 5, 7, 9, 11];
const PRETAS_LOCAL = [1, 3, 6, 8, 10];
const PRETA_PARA_PROXIMA_BRANCA_LOCAL = { 1: 1, 3: 2, 6: 4, 8: 5, 10: 6 };

function indiceBrancaGlobal(semitone) {
  const oitava = Math.floor(semitone / 12);
  const local = ((semitone % 12) + 12) % 12;
  return BRANCAS_LOCAL.indexOf(local) + 7 * oitava;
}
function xTeclaBranca(semitone) { return indiceBrancaGlobal(semitone) * KB_W; }
function xTeclaPreta(semitone) {
  const oitava = Math.floor(semitone / 12);
  const local = ((semitone % 12) + 12) % 12;
  const idxGlobal = PRETA_PARA_PROXIMA_BRANCA_LOCAL[local] + 7 * oitava;
  return idxGlobal * KB_W - KB_BW / 2;
}

function desenharTeclado(notas, baixo) {
  const totalW = BRANCAS_LOCAL.length * KB_N_OITAVAS * KB_W;
  let svg = `<svg viewBox="0 0 ${totalW} ${KB_H}" width="${totalW}" height="${KB_H}" xmlns="http://www.w3.org/2000/svg">`;

  for (let oit = 0; oit < KB_N_OITAVAS; oit++) {
    BRANCAS_LOCAL.forEach(local => {
      const x = xTeclaBranca(local + 12 * oit);
      svg += `<rect x="${x}" y="0" width="${KB_W}" height="${KB_H}" fill="#f2f2f2" stroke="#3a3a3c" stroke-width="1"/>`;
    });
  }
  for (let oit = 0; oit < KB_N_OITAVAS; oit++) {
    PRETAS_LOCAL.forEach(local => {
      const x = xTeclaPreta(local + 12 * oit);
      svg += `<rect x="${x}" y="0" width="${KB_BW}" height="${KB_BH}" fill="#1a1a1a"/>`;
    });
  }

  notas.forEach(s => {
    const local = ((s % 12) + 12) % 12;
    const isBranca = BRANCAS_LOCAL.includes(local);
    const isBaixo = s === baixo;
    const x = isBranca ? xTeclaBranca(s) + KB_W / 2 : xTeclaPreta(s) + KB_BW / 2;
    const cy = isBranca ? KB_H - 20 : KB_BH - 14;
    const r = isBaixo ? 7 : 5.5;
    const fill = isBaixo ? '#ff9f43' : '#fff';
    const stroke = isBaixo ? '#ff9f43' : '#444';
    svg += `<circle cx="${x}" cy="${cy}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2.5"/>`;
  });

  svg += '</svg>';
  return svg;
}

function criarCardAcorde(nomeAcorde) {
  const acorde = parseAcorde(nomeAcorde);
  const card = document.createElement('div');
  card.className = 'cifra-chord-card';
  if (!acorde) {
    card.innerHTML = `<div class="cifra-chord-label">${nomeAcorde}</div><div style="color:#888;font-size:12px;">não reconhecido</div>`;
    return card;
  }
  card.innerHTML = `<div class="cifra-chord-label">${acorde.nomeExibicao}</div>${desenharTeclado(acorde.notas, acorde.baixo)}`;
  return card;
}

/**
 * Ponto de entrada: renderiza os diagramas de uma lista de acordes
 * dentro do elemento de id `trackId`, e liga o botão de avançar (opcional).
 */
function renderizarDiagramasAcordes(trackId, listaAcordes, nextBtnId) {
  const track = document.getElementById(trackId);
  if (!track) return;
  track.innerHTML = '';
  (listaAcordes || []).forEach(nome => track.appendChild(criarCardAcorde(nome)));

  if (nextBtnId) {
    const btn = document.getElementById(nextBtnId);
    if (btn) {
      btn.addEventListener('click', () => track.scrollBy({ left: 140, behavior: 'smooth' }));
    }
  }
}
