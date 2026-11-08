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

/* Estructura en Realtime Database (protegida por PIN):
   albumes/{clave}/ok         → marca de que el álbum existe
   albumes/{clave}/meta/{id}  → datos de la carta + miniatura (ligero, se carga entero en el álbum)
   albumes/{clave}/img/{id}   → foto grande (solo se carga al abrir la carta o en el pase)
   {clave} = SHA-256 del PIN. El PIN no está en el código: sin él no se sabe dónde están las cartas. */
let REF_BASE = '', REF_META = '', REF_IMG = '';
const LS_CLAVE = 'album_pokemon_clave';

async function claveDePin(pin) {
  const datos = new TextEncoder().encode('album-pokemon-juanki:' + pin);
  const h = await crypto.subtle.digest('SHA-256', datos);
  return Array.from(new Uint8Array(h), b => b.toString(16).padStart(2, '0')).join('');
}
function usarClave(clave) {
  REF_BASE = 'albumes/' + clave;
  REF_META = REF_BASE + '/meta';
  REF_IMG  = REF_BASE + '/img';
}
function cerrarSesion() {
  try { localStorage.removeItem(LS_CLAVE); } catch {}
  location.reload();
}

/* Pide el PIN (o usa el recordado en este dispositivo) y luego llama a alEntrar() */
async function conPin(alEntrar) {
  let guardada = null;
  try { guardada = localStorage.getItem(LS_CLAVE); } catch {}
  if (guardada) {
    try {
      const ok = (await db.ref('albumes/' + guardada + '/ok').get()).val();
      if (ok) { usarClave(guardada); alEntrar(); return; }
    } catch {}
  }
  pantallaPin(alEntrar);
}

function pantallaPin(alEntrar) {
  const capa = document.createElement('div');
  capa.id = 'pin-capa';
  capa.innerHTML = `
    <div class="pin-caja">
      <div class="pin-bola"></div>
      <h2 id="pin-tit">Introduce el PIN</h2>
      <p id="pin-sub">6 números para entrar en el álbum</p>
      <div class="pin-puntos" id="pin-puntos">${'<i></i>'.repeat(6)}</div>
      <p class="pin-err" id="pin-err"></p>
      <div class="pin-teclado" id="pin-teclado">
        ${[1,2,3,4,5,6,7,8,9].map(n => `<button data-k="${n}">${n}</button>`).join('')}
        <button data-k="crear" class="pin-mini" title="Crear un álbum nuevo">＋ Nuevo</button>
        <button data-k="0">0</button>
        <button data-k="borrar" class="pin-mini">⌫</button>
      </div>
      <label class="pin-recordar"><input type="checkbox" id="pin-recordar" checked> Recordar en este dispositivo</label>
    </div>`;
  document.body.appendChild(capa);
  document.body.style.overflow = 'hidden';

  let pin = '', modo = 'entrar', primero = '', ocupado = false;
  const puntos = capa.querySelectorAll('#pin-puntos i');
  const err = capa.querySelector('#pin-err');
  const tit = capa.querySelector('#pin-tit'), sub = capa.querySelector('#pin-sub');

  const pintar = () => puntos.forEach((p, i) => p.classList.toggle('on', i < pin.length));
  const fallo = msg => {
    err.textContent = msg; pin = ''; pintar();
    capa.querySelector('#pin-puntos').classList.remove('vibra'); void capa.offsetWidth;
    capa.querySelector('#pin-puntos').classList.add('vibra');
  };
  const ponerModo = m => {
    modo = m; pin = ''; pintar(); err.textContent = '';
    if (m === 'entrar') { tit.textContent = 'Introduce el PIN'; sub.textContent = '6 números para entrar en el álbum'; }
    if (m === 'crear1') { tit.textContent = 'Nuevo álbum'; sub.textContent = 'Elige un PIN de 6 números'; }
    if (m === 'crear2') { tit.textContent = 'Repite el PIN'; sub.textContent = 'Para asegurarnos de que es correcto'; }
  };

  async function completo() {
    ocupado = true;
    try {
      if (modo === 'crear1') { primero = pin; ponerModo('crear2'); return; }
      if (modo === 'crear2' && pin !== primero) { ponerModo('crear1'); fallo('No coinciden. Vuelve a elegir el PIN.'); return; }
      const clave = await claveDePin(pin);
      const ref = db.ref('albumes/' + clave + '/ok');
      const existe = (await ref.get()).val();
      if (modo === 'entrar' && !existe) { fallo('PIN incorrecto'); return; }
      if (modo === 'crear2') {
        if (existe) { ponerModo('entrar'); fallo('Ese PIN ya existe: introdúcelo para entrar.'); return; }
        await ref.set(true);
      }
      try { if (capa.querySelector('#pin-recordar').checked) localStorage.setItem(LS_CLAVE, clave); } catch {}
      usarClave(clave);
      capa.remove(); document.body.style.overflow = '';
      document.removeEventListener('keydown', teclado);
      alEntrar();
    } catch (e) {
      fallo('Error de conexión: ' + e.message);
    } finally { ocupado = false; }
  }

  function pulsar(k) {
    if (ocupado) return;
    if (k === 'borrar') { pin = pin.slice(0, -1); pintar(); return; }
    if (k === 'crear') {
      if (modo !== 'entrar') { ponerModo('entrar'); return; }
      if (confirm('¿Crear un álbum NUEVO y vacío con otro PIN?\n\nSi ya tenéis álbum, cancela y escribe vuestro PIN.')) ponerModo('crear1');
      return;
    }
    if (pin.length >= 6) return;
    err.textContent = '';
    pin += k; pintar();
    if (pin.length === 6) setTimeout(completo, 120);
  }
  capa.querySelector('#pin-teclado').addEventListener('click', e => {
    const b = e.target.closest('button'); if (b) pulsar(b.dataset.k);
  });
  const teclado = e => {
    if (/^[0-9]$/.test(e.key)) pulsar(e.key);
    else if (e.key === 'Backspace') pulsar('borrar');
  };
  document.addEventListener('keydown', teclado);
}

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
