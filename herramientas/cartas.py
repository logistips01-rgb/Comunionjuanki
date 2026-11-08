#!/usr/bin/env python3
"""
Herramienta para rellenar las fichas del álbum Pokémon desde la línea de comandos.

La clave del álbum se obtiene del PIN (variable de entorno ALBUM_PIN) o directamente
de la clave (ALBUM_CLAVE). Nunca se guarda en el repositorio.

Uso:
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
"""
import base64, hashlib, json, os, re, sys, urllib.parse, urllib.request

DB = "https://juanki-cfec7-default-rtdb.europe-west1.firebasedatabase.app"
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
        "numero": f"{c.get('localId')}/{total}" if c.get("localId") else "",
        "precio": precio(c),
        "tcgdex": c.get("id"),
        "rarezaOriginal": c.get("rarity") or "",
        "ilustrador": c.get("illustrator") or "",
    }


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
    http(f"{b}/meta/{id_carta}.json", "PATCH", f)
    print(f"✔ {id_carta} → {f['nombre']} · {f['set']} {f['numero']} · {f['rareza']} · {f['precio']}€")


def cmd_manual(id_carta, js):
    datos = json.loads(js)
    datos.setdefault("pendiente", None)
    http(f"{base()}/meta/{id_carta}.json", "PATCH", datos)
    print(f"✔ {id_carta} actualizada: {datos}")


if __name__ == "__main__":
    cmds = {"pendientes": cmd_pendientes, "todas": cmd_todas, "buscar": cmd_buscar,
            "ver": cmd_ver, "aplicar": cmd_aplicar, "manual": cmd_manual}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[sys.argv[1]](*sys.argv[2:])
