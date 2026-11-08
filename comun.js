/* ═══════════════════════════════════════════════════════════
   Álbum Pokémon — código compartido (Firebase + catálogos)
   ═══════════════════════════════════════════════════════════ */

firebase.initializeApp({
  apiKey:            "AIzaSyBpLUV25TLfwmxA4s3KoxIPnzJaK4b4LH0",
  authDomain:        "juanki-cfec7.firebaseapp.com",
  databaseURL:       "https://juanki-cfec7-default-rtdb.europe-west1.firebasedatabase.app",
  projectId:         "juanki-cfec7",
  storageBucket:     "juanki-cfec7.firebasestorage.app",
  messagingSenderId: "23536544926",
  appId:             "1:23536544926:web:f782678cfba696a8c50428"
});
const db = firebase.database();

/* Estructura en Realtime Database:
   pokemon/meta/{id} → datos de la carta + miniatura (ligero, se carga entero en el álbum)
   pokemon/img/{id}  → foto grande (solo se carga al abrir la carta o en el pase) */
const REF_META = 'pokemon/meta';
const REF_IMG  = 'pokemon/img';

/* ── Catálogos ─────────────────────────────────────────── */
const TIPOS = [
  { id: 'Planta',     ico: '🌿', color: '#5fb04a' },
  { id: 'Fuego',      ico: '🔥', color: '#e8542f' },
  { id: 'Agua',       ico: '💧', color: '#3d8fe0' },
  { id: 'Rayo',       ico: '⚡', color: '#f2c218' },
  { id: 'Psíquico',   ico: '🔮', color: '#a55bc9' },
  { id: 'Lucha',      ico: '👊', color: '#b8663a' },
  { id: 'Oscuro',     ico: '🌑', color: '#3f4a5a' },
  { id: 'Metálico',   ico: '⚙️', color: '#8c9aa6' },
  { id: 'Hada',       ico: '🧚', color: '#e57fb5' },
  { id: 'Dragón',     ico: '🐉', color: '#b39228' },
  { id: 'Incoloro',   ico: '⭐', color: '#b5aa96' },
  { id: 'Entrenador', ico: '🎒', color: '#6d7b8c' },
  { id: 'Energía',    ico: '🔋', color: '#2bb3a3' },
];
const TIPO = Object.fromEntries(TIPOS.map(t => [t.id, t]));

// El orden importa: de "peor" a "mejor"
const RAREZAS = [
  'Común', 'Poco común', 'Rara', 'Rara holo', 'Doble rara (ex / V)',
  'Ultra rara', 'Ilustración rara', 'Ilustración especial', 'Secreta / Dorada'
];
const RAREZA_ICO = ['●', '◆', '★', '★✨', '★★', '★★★', '🎨', '🎨✨', '👑'];

const ETAPAS = [
  'Entrenador / Energía', 'Básico', 'Fase 1', 'Fase 2',
  'V / EX / GX / ex', 'VMAX / VSTAR / Mega'
];

/* ── Puntuación para ordenar de peor a mejor ───────────── */
function puntuacion(c) {
  const est = Number(c.estrellas) || 0;
  const rar = Math.max(0, RAREZAS.indexOf(c.rareza));
  const eta = Math.max(0, ETAPAS.indexOf(c.etapa));
  const ps  = Number(c.ps) || 0;
  return est * 100 + rar * 30 + eta * 15 + ps / 10;
}

/* ── Utilidades ────────────────────────────────────────── */
function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function euros(v) {
  return (Number(v) || 0).toLocaleString('es-ES', { style: 'currency', currency: 'EUR' });
}

function estrellasTxt(n) {
  n = Number(n) || 0;
  return '★'.repeat(n) + '☆'.repeat(5 - n);
}

function tipoBadge(tipo) {
  const t = TIPO[tipo] || { ico: '❔', color: '#999', id: tipo || 'Sin tipo' };
  return `<span class="badge-tipo" style="--tc:${t.color}">${t.ico} ${esc(t.id)}</span>`;
}

/* Redimensiona una imagen (File, Blob o URL) a JPEG base64.
   rot = grados de giro (0, 90, 180, 270) */
function imagenABase64(src, max, calidad, rot = 0) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      let w = img.naturalWidth, h = img.naturalHeight;
      const k = Math.min(1, max / Math.max(w, h));
      w = Math.round(w * k); h = Math.round(h * k);
      const girado = rot % 180 !== 0;
      const c = document.createElement('canvas');
      c.width = girado ? h : w; c.height = girado ? w : h;
      const ctx = c.getContext('2d');
      ctx.translate(c.width / 2, c.height / 2);
      ctx.rotate(rot * Math.PI / 180);
      ctx.drawImage(img, -w / 2, -h / 2, w, h);
      try { resolve(c.toDataURL('image/jpeg', calidad)); } catch (e) { reject(e); }
    };
    img.onerror = () => reject(new Error('No se pudo leer la imagen'));
    img.src = (src instanceof Blob) ? URL.createObjectURL(src) : src;
  });
}
