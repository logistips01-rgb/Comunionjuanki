#!/usr/bin/env python3
"""
Herramienta para rellenar las fichas del álbum Pokémon desde la línea de comandos.

La clave del álbum se obtiene del PIN (variable de entorno ALBUM_PIN) o directamente
de la clave (ALBUM_CLAVE). Nunca se guarda en el repositorio.

Uso:
  ALBUM_PIN=123456 python3 herramientas/cartas.py procesar [carpeta]
      Descarga de Firebase las cartas sin procesar, recorta automáticamente la carta
      de cada foto y deja en la carpeta: <id>_det.jpg (detección) y <id>_rec.jpg (recorte).
  python3 herramientas/cartas.py recortar <id> x1,y1,x2,y2,x3,y3,x4,y4 [carpeta]
      Rehace el recorte con las 4 esquinas indicadas a mano (en píxeles de <id>_orig.jpg).
  ALBUM_PIN=123456 python3 herramientas/cartas.py subir_recorte <id> [carpeta]
      Sube el recorte (guarda antes el original en orig/<id>) y regenera la miniatura.
  ALBUM_PIN=123456 python3 herramientas/cartas.py pendientes [carpeta]
      Lista las cartas pendientes y descarga sus fotos a la carpeta.
  ALBUM_PIN=123456 python3 herramientas/cartas.py todas
      Lista todas las cartas (id, nombre, colección, número).
  python3 herramientas/cartas.py buscar "Pikachu" [numero] [total]
      Busca en TCGdex; filtra por número de carta y total de la colección si se dan.
  python3 herramientas/cartas.py ver <tcgdex_id>
      Muestra la ficha que se rellenaría con esa carta del catálogo.
  ALBUM_PIN=123456 python3 herramientas/cartas.py aplicar <id_carta> <tcgdex_id> [estrellas]
      Rellena la ficha de la carta con los datos del catálogo y quita "pendiente".
  ALBUM_PIN=123456 python3 herramientas/cartas.py manual <id_carta> '<json>'
      Actualiza campos a mano (para cartas que no estén en el catálogo).

Estructura extra en Firebase:
  albumes/{clave}/orig/{id}        foto original sin recortar (copia de seguridad)
  albumes/{clave}/meta/{id}/procesada  marca de carta ya revisada (fecha en ms)
  albumes/{clave}/meta/{id}/recortada  true si la foto se recortó
"""
import base64, hashlib, json, os, re, sys, urllib.parse, urllib.request

DB = os.environ.get("ALBUM_DB", "https://juanki-cfec7-default-rtdb.europe-west1.firebasedatabase.app")
API = "https://api.tcgdex.net/v2/es"

RAREZAS = ['Común', 'Poco común', 'Rara', 'Rara holo', 'Doble rara (ex / V)',
           'Ultra rara', 'Ilustración rara', 'Ilustración especial', 'Secreta / Dorada']
MAP_TIPO = {'Incolora': 'Incoloro', 'Metálica': 'Metálico', 'Oscura': 'Oscuro'}
TIPOS = {'Planta', 'Fuego', 'Agua', 'Rayo', 'Psíquico', 'Lucha', 'Oscuro', 'Metálico',
         'Hada', 'Dragón', 'Incoloro', 'Entrenador', 'Energía'}


def http(url, method="GET", data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json", "User-Agent": "album-pokemon"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "null")


def clave():
    if os.environ.get("ALBUM_CLAVE"):
        return os.environ["ALBUM_CLAVE"]
    pin = os.environ.get("ALBUM_PIN")
    if not pin:
        sys.exit("Falta ALBUM_PIN o ALBUM_CLAVE")
    return hashlib.sha256(("album-pokemon-juanki:" + pin).encode()).hexdigest()


def base():
    k = clave()
    if not http(f"{DB}/albumes/{k}/ok.json"):
        sys.exit("No existe ningún álbum con ese PIN")
    return f"{DB}/albumes/{k}"


# ── Traducción de datos de TCGdex a la ficha del álbum (igual que en subir.html) ──
def map_rareza(r):
    r = (r or "").lower()
    if re.search(r"secreta|h[ií]per|corona|tres estrellas|dorad|rgb|futuristic", r): return 'Secreta / Dorada'
    if re.search(r"ilustraci[oó]n especial|dos estrellas", r): return 'Ilustración especial'
    if re.search(r"ilustraci[oó]n|una estrella|arte completo|pikachu rare", r): return 'Ilustración rara'
    if re.search(r"ultra|vmax|vstar|incre[ií]ble|radiante|t[aá]ctico|shiny|variocolor|cuatro diamantes|mega", r): return 'Ultra rara'
    if re.search(r"doble|holo rara v|tres diamantes", r): return 'Doble rara (ex / V)'
    if "holo" in r: return 'Rara holo'
    if re.search(r"uncommon|poco|dos diamantes", r): return 'Poco común'
    if re.search(r"rara|rare|promo", r): return 'Rara'
    return 'Común'


def map_etapa(c):
    if c.get("category") != "Pokémon": return 'Entrenador / Energía'
    st, suf, nom = (c.get("stage") or "").upper(), c.get("suffix") or "", c.get("name") or ""
    if re.search(r"VMAX|ASTRO|VSTAR|MEGA|UNI[OÓ]N", st) or re.search(r"VMAX|VSTAR|MEGA", suf, re.I): return 'VMAX / VSTAR / Mega'
    if re.match(r"(V|EX|GX|ex|TAG TEAM)", suf, re.I) or re.search(r" (V|EX|GX|ex)$", nom): return 'V / EX / GX / ex'
    if st == "FASE 2": return 'Fase 2'
    if st == "FASE 1": return 'Fase 1'
    return 'Básico'


def map_tipo(c):
    if c.get("category") == "Entrenador": return "Entrenador"
    if c.get("category") == "Energía": return "Energía"
    t = (c.get("types") or [""])[0]
    t = MAP_TIPO.get(t, t)
    return t if t in TIPOS else "Incoloro"


def precio(c):
    cm = (c.get("pricing") or {}).get("cardmarket") or {}
    v = cm.get("trend") or cm.get("avg") or cm.get("trend-holo") or cm.get("avg-holo") or cm.get("low") or 0
    return round(float(v), 2)


def ficha(c):
    total = ((c.get("set") or {}).get("cardCount") or {}).get("official") or "?"
    rar = map_rareza(c.get("rarity"))
    return {
        "nombre": c.get("name") or "",
        "tipo": map_tipo(c),
        "ps": int(c.get("hp") or 0),
        "etapa": map_etapa(c),
        "rareza": rar,
        "set": (c.get("set") or {}).get("name") or "",
        "numero": numero_impreso(c.get("localId"), total),
        "precio": precio(c),
        "tcgdex": c.get("id"),
        "rarezaOriginal": c.get("rarity") or "",
        "ilustrador": c.get("illustrator") or "",
    }


def numero_impreso(local, total):
    """Como viene impreso en la carta: 082/264 (rellena con ceros hasta los dígitos del total)."""
    if not local:
        return ""
    local = str(local)
    if local.isdigit() and str(total).isdigit():
        local = local.zfill(max(3, len(str(total))))
    return f"{local}/{total}"


def num(s):
    m = re.search(r"\d+", str(s or ""))
    return int(m.group()) if m else None


# ── Comandos ──
def cmd_pendientes(carpeta="pendientes"):
    b = base()
    meta = http(f"{b}/meta.json") or {}
    pend = {k: v for k, v in meta.items() if v.get("pendiente")}
    os.makedirs(carpeta, exist_ok=True)
    print(f"{len(pend)} pendientes de {len(meta)} cartas")
    for k, v in sorted(pend.items(), key=lambda x: x[1].get("ts", 0)):
        img = http(f"{b}/img/{k}.json") or v.get("thumb") or ""
        ruta = os.path.join(carpeta, f"{k}.jpg")
        if img.startswith("data:"):
            with open(ruta, "wb") as f:
                f.write(base64.b64decode(img.split(",", 1)[1]))
        print(f"{k}\t{ruta}\tnotas={v.get('notas','')}\tcantidad={v.get('cantidad',1)}")


def cmd_todas():
    meta = http(f"{base()}/meta.json") or {}
    for k, v in sorted(meta.items(), key=lambda x: x[1].get("ts", 0)):
        print(f"{k}\t{'⏳' if v.get('pendiente') else '✔'}\t{v.get('nombre','')}\t{v.get('set','')}\t{v.get('numero','')}\t{v.get('rareza','')}\t{v.get('precio',0)}€")


def cmd_buscar(nombre, numero=None, total=None):
    res = http(f"{API}/cards?name={urllib.parse.quote(nombre)}") or []
    n, t = num(numero), num(total)
    if n is not None:
        res = [c for c in res if num(c.get("localId")) == n or str(c.get("localId")) == str(numero)]
    print(f"{len(res)} candidatos")
    for c in res[:40]:
        linea = f"{c['id']}\t{c.get('name')}\t#{c.get('localId')}"
        if n is not None or len(res) <= 12:
            d = http(f"{API}/cards/{urllib.parse.quote(c['id'])}")
            sc = (d.get("set") or {})
            tot = (sc.get("cardCount") or {}).get("official")
            if t is not None and tot and int(tot) != t:
                continue
            linea += f"/{tot}\t{sc.get('name')}\t{d.get('rarity')}\tPS {d.get('hp')}\t{c.get('image','')}/high.webp"
        print(linea)


def cmd_ver(tid):
    print(json.dumps(ficha(http(f"{API}/cards/{urllib.parse.quote(tid)}")), ensure_ascii=False, indent=2))


def cmd_aplicar(id_carta, tid, estrellas=None):
    b = base()
    actual = http(f"{b}/meta/{id_carta}.json")
    if not actual:
        sys.exit("No existe esa carta en el álbum")
    f = ficha(http(f"{API}/cards/{urllib.parse.quote(tid)}"))
    if estrellas:
        f["estrellas"] = int(estrellas)
    elif actual.get("pendiente"):
        # Estrellas por defecto según la rareza (el niño puede cambiarlas luego)
        f["estrellas"] = min(5, max(1, 1 + RAREZAS.index(f["rareza"]) // 2))
    f["pendiente"] = None
    f["procesada"] = {".sv": "timestamp"}
    http(f"{b}/meta/{id_carta}.json", "PATCH", f)
    print(f"✔ {id_carta} → {f['nombre']} · {f['set']} {f['numero']} · {f['rareza']} · {f['precio']}€")


def cmd_manual(id_carta, js):
    datos = json.loads(js)
    datos.setdefault("pendiente", None)
    datos.setdefault("procesada", {".sv": "timestamp"})
    http(f"{base()}/meta/{id_carta}.json", "PATCH", datos)
    print(f"✔ {id_carta} actualizada: {datos}")


# ── Recorte de la carta ──
CARTA_W, CARTA_H = 900, 1257          # proporción oficial 63 x 88 mm


def _cv():
    import cv2, numpy as np
    return cv2, np


def decodificar(data_url):
    cv2, np = _cv()
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def codificar(img, calidad=88):
    cv2, _ = _cv()
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def ordenar(pts):
    _, np = _cv()
    pts = np.array(pts, dtype="float32").reshape(4, 2)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], dtype="float32")


def _quad_valido(q, area_img):
    cv2, np = _cv()
    a = cv2.contourArea(q.astype("float32"))
    if a < 0.12 * area_img:
        return False
    tl, tr, br, bl = q
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    ratio = min(w, h) / max(w, h)
    return 0.55 <= ratio <= 0.88


def detectar(img):
    """Devuelve las 4 esquinas de la carta (en píxeles de img) o None."""
    cv2, np = _cv()
    H, W = img.shape[:2]
    k = 1000 / max(H, W)
    peq = cv2.resize(img, (int(W * k), int(H * k)))
    area = peq.shape[0] * peq.shape[1]
    candidatos = []

    def de_contornos(binaria):
        cnts, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:5]:
            peri = cv2.arcLength(c, True)
            for eps in (0.02, 0.03, 0.05):
                ap = cv2.approxPolyDP(c, eps * peri, True)
                if len(ap) == 4:
                    q = ordenar(ap)
                    if _quad_valido(q, area):
                        candidatos.append(q); return
            q = ordenar(cv2.boxPoints(cv2.minAreaRect(c)))
            if _quad_valido(q, area):
                candidatos.append(q); return

    gris = cv2.GaussianBlur(cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    # 1) Bordes
    bordes = cv2.dilate(cv2.Canny(gris, 40, 140), np.ones((5, 5), np.uint8), iterations=2)
    de_contornos(bordes)
    # 2) Diferencia de color con el fondo (estimado en el marco exterior de la foto)
    lab = cv2.cvtColor(cv2.GaussianBlur(peq, (7, 7), 0), cv2.COLOR_BGR2LAB).astype("float32")
    m = max(4, int(min(peq.shape[:2]) * 0.03))
    marco = np.concatenate([lab[:m].reshape(-1, 3), lab[-m:].reshape(-1, 3), lab[:, :m].reshape(-1, 3), lab[:, -m:].reshape(-1, 3)])
    fondo = np.median(marco, axis=0)
    dist = np.linalg.norm(lab - fondo, axis=2)
    _, bin2 = cv2.threshold(cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype("uint8"), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bin2 = cv2.morphologyEx(bin2, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8), iterations=2)
    de_contornos(bin2)
    if not candidatos:
        return None
    # El cuadrilátero más grande que sea válido
    mejor = max(candidatos, key=lambda q: cv2.contourArea(q))
    return mejor / k


def enderezar(img, quad):
    cv2, np = _cv()
    q = ordenar(quad)
    tl, tr, br, bl = q
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    if w > h:   # carta en horizontal: rotamos las esquinas para dejarla vertical
        q = np.array([bl, tl, tr, br], dtype="float32")
    dst = np.array([[0, 0], [CARTA_W - 1, 0], [CARTA_W - 1, CARTA_H - 1], [0, CARTA_H - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(q, dst)
    return cv2.warpPerspective(img, M, (CARTA_W, CARTA_H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def miniatura(img):
    cv2, _ = _cv()
    h, w = img.shape[:2]
    k = 320 / max(h, w)
    return codificar(cv2.resize(img, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA), 75)


def _guardar_previas(carpeta, id_carta, img, quad):
    cv2, np = _cv()
    det = img.copy()
    if quad is not None:
        grosor = max(3, img.shape[1] // 200)
        cv2.polylines(det, [quad.astype("int32")], True, (0, 255, 0), grosor)
        for i, (x, y) in enumerate(quad.astype(int)):
            cv2.circle(det, (x, y), grosor * 3, (0, 0, 255), -1)
            cv2.putText(det, str(i + 1), (x + 10, y + 40), cv2.FONT_HERSHEY_SIMPLEX, grosor / 2, (0, 0, 255), grosor)
        cv2.imwrite(os.path.join(carpeta, f"{id_carta}_rec.jpg"), enderezar(img, quad))
    cv2.imwrite(os.path.join(carpeta, f"{id_carta}_det.jpg"), det)


def cmd_procesar(carpeta="procesar"):
    """Descarga las cartas sin procesar y prepara el recorte automático."""
    cv2, _ = _cv()
    b = base()
    meta = http(f"{b}/meta.json") or {}
    todo = {k: v for k, v in meta.items() if v.get("pendiente") or not v.get("procesada")}
    os.makedirs(carpeta, exist_ok=True)
    print(f"{len(todo)} cartas por procesar de {len(meta)}")
    for k, v in sorted(todo.items(), key=lambda x: x[1].get("ts", 0)):
        data = http(f"{b}/orig/{k}.json") or http(f"{b}/img/{k}.json") or v.get("thumb") or ""
        if not data.startswith("data:"):
            print(f"{k}	SIN FOTO"); continue
        img = decodificar(data)
        cv2.imwrite(os.path.join(carpeta, f"{k}_orig.jpg"), img)
        quad = None if v.get("recortada") else detectar(img)
        _guardar_previas(carpeta, k, img, quad)
        estado = "ya recortada" if v.get("recortada") else ("recorte OK" if quad is not None else "NO DETECTADA (recortar a mano)")
        print(f"{k}	{img.shape[1]}x{img.shape[0]}	{estado}	nombre={v.get('nombre','')}	notas={v.get('notas','')}")


def cmd_recortar(id_carta, esquinas, carpeta="procesar"):
    cv2, np = _cv()
    img = cv2.imread(os.path.join(carpeta, f"{id_carta}_orig.jpg"))
    if img is None:
        sys.exit("Primero ejecuta 'procesar'")
    quad = ordenar([float(x) for x in esquinas.split(",")])
    _guardar_previas(carpeta, id_carta, img, quad)
    print(f"✔ recorte rehecho: {carpeta}/{id_carta}_rec.jpg")


def cmd_subir_recorte(id_carta, carpeta="procesar"):
    cv2, _ = _cv()
    b = base()
    rec = cv2.imread(os.path.join(carpeta, f"{id_carta}_rec.jpg"))
    if rec is None:
        sys.exit("No hay recorte para esa carta")
    if not http(f"{b}/orig/{id_carta}.json"):
        original = http(f"{b}/img/{id_carta}.json")
        if original:
            http(f"{b}/orig/{id_carta}.json", "PUT", original)
    http(f"{b}/img/{id_carta}.json", "PUT", codificar(rec))
    http(f"{b}/meta/{id_carta}.json", "PATCH", {"thumb": miniatura(rec), "recortada": True})
    print(f"✔ {id_carta}: foto recortada subida (original guardado en orig/)")


def cmd_hecha(id_carta):
    http(f"{base()}/meta/{id_carta}.json", "PATCH", {"pendiente": None, "procesada": {".sv": "timestamp"}})
    print(f"✔ {id_carta} marcada como procesada")


if __name__ == "__main__":
    cmds = {"pendientes": cmd_pendientes, "todas": cmd_todas, "buscar": cmd_buscar,
            "ver": cmd_ver, "aplicar": cmd_aplicar, "manual": cmd_manual,
            "procesar": cmd_procesar, "recortar": cmd_recortar,
            "subir_recorte": cmd_subir_recorte, "hecha": cmd_hecha}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[sys.argv[1]](*sys.argv[2:])
