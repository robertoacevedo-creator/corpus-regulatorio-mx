"""Vigilante semanal de las leyes y reglamentos federales del corpus.

Lee los índices de la Cámara de Diputados, que publican la fecha de última
reforma de cada norma, y la compara con el catálogo. No baja nada si no hay
cambios.

    python herramientas/vigilante.py revisar --salida informe.json [--simular CLAVE]
    python herramientas/vigilante.py actualizar --informe informe.json --originales DIR --salida plan.json

`revisar` solo lee los índices. `actualizar` baja el .doc de cada norma con
cambios, lo convierte y decide:

  - "propuesta": el texto cambió y pasa la revisión; se propone como pull request.
  - "pendiente": el índice anuncia una reforma ("Nueva reforma", "En actualización")
    pero el .doc todavía no la trae; solo se avisa.
  - "sin_cambios": el .doc es el mismo texto que ya tenemos.
  - "error": algo falló (descarga, conversión o revisión); se avisa con el detalle.

Los avisos, ramas y pull requests los crea el flujo .github/workflows/vigilante.yml
con estos resultados. Nada entra a main sin que el responsable haga el merge.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = "https://www.diputados.gob.mx"
INDICES = {
    "leyes": BASE + "/LeyesBiblio/index.htm",
    "reglamentos": BASE + "/LeyesBiblio/regla.htm",
}
MARCAS = ["Nueva reforma", "En actualización", "Sentencia SCJN", "Abrogad"]
AGENTE = "Mozilla/5.0 (compatible; corpus-regulatorio-mx/1.0; +https://github.com/robertoacevedo-creator/corpus-regulatorio-mx)"


# ---------------------------------------------------------------- lectura de índices

class Filas(HTMLParser):
    """Junta las filas de tabla que no contienen otras tablas: texto por celda y ligas."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila, self.filas = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            if self.pila:
                self.pila[-1]["anidada"] = True
            self.pila.append({"celdas": [], "ligas": [], "anidada": False})
        elif tag in ("td", "th") and self.pila:
            self.pila[-1]["celdas"].append("")
        elif tag == "a" and self.pila:
            href = dict(attrs).get("href")
            if href:
                self.pila[-1]["ligas"].append(href)

    def handle_endtag(self, tag):
        if tag == "tr" and self.pila:
            fila = self.pila.pop()
            if not fila["anidada"]:
                fila["celdas"] = [re.sub(r"\s+", " ", c).strip() for c in fila["celdas"]]
                self.filas.append(fila)

    def handle_data(self, data):
        if self.pila and self.pila[-1]["celdas"]:
            self.pila[-1]["celdas"][-1] += data


def leer_filas(html):
    p = Filas()
    p.feed(html)
    return p.filas


def iso(ddmmaaaa):
    d, m, a = ddmmaaaa.split("/")
    return f"{a}-{m}-{d}"


def absoluta(href):
    href = href.split("?")[0].split("#")[0]
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return BASE + href
    return BASE + "/LeyesBiblio/" + href.lstrip("./")


def nombre_archivo(href):
    return href.split("?")[0].rstrip("/").rsplit("/", 1)[-1]


def tronco(nombre):
    """'Reg_LGPGIR_311014.doc' -> 'Reg_LGPGIR'; 'LGPGIR.doc' -> 'LGPGIR'."""
    return re.sub(r"_\d{6}$", "", re.sub(r"\.docx?$", "", nombre, flags=re.I))


def buscar_ley(filas, tronco_ley):
    for f in filas:
        docs = [h for h in f["ligas"] if re.search(r"(?:^|/)doc/[^/]+\.doc$", h.split("?")[0], re.I)]
        if any(tronco(nombre_archivo(h)) == tronco_ley for h in docs) and len(f["celdas"]) >= 3:
            nombre, reforma = f["celdas"][1], f["celdas"][2]
            fechas = [iso(x) for x in re.findall(r"\d{2}/\d{2}/\d{4}", reforma)]
            if not fechas and "sin reforma" in reforma.lower():
                fechas = [iso(x) for x in re.findall(r"\d{2}/\d{2}/\d{4}", nombre)][:1]
            texto = nombre + " " + reforma
            return {
                "fecha_indice": max(fechas) if fechas else None,
                "marcas": [m for m in MARCAS if m.lower() in texto.lower()],
                "url_doc": absoluta(next(h for h in docs if tronco(nombre_archivo(h)) == tronco_ley)),
                "texto_fila": texto[:300],
            }
    return None


def buscar_reglamento(filas, tronco_reg):
    for f in filas:
        docs = [h for h in f["ligas"] if h.split("?")[0].lower().endswith(".doc")]
        if not docs:
            continue
        vigente = docs[-1]  # la liga WORD de la columna "TEXTO VIGENTE" es la última de la fila
        if tronco(nombre_archivo(vigente)) != tronco_reg:
            continue
        texto = " ".join(f["celdas"][1:3])
        fechas = [iso(x) for x in re.findall(r"\d{2}/\d{2}/\d{4}", texto)]
        return {
            "fecha_indice": max(fechas) if fechas else None,
            "marcas": [m for m in MARCAS if m.lower() in texto.lower()],
            "url_doc": absoluta(vigente),
            "texto_fila": texto[:300],
        }
    return None


def descargar(url, destino=None):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=120) as r:
        datos = r.read()
    if destino:
        Path(destino).write_bytes(datos)
    return datos


def html_de(url):
    datos = descargar(url)
    m = re.search(rb'charset=["\']?([\w-]+)', datos[:3000], re.I)
    return datos.decode(m.group(1).decode() if m else "windows-1252", errors="replace")


def vigiladas():
    """Normas de Diputados del catálogo, con su índice y su tronco de archivo."""
    catalogo = json.loads((RAIZ / "catalogo.json").read_text(encoding="utf-8"))
    fichas = {n["clave"]: n for n in catalogo["normas"]}
    fuentes = json.loads((RAIZ / "herramientas" / "fuentes.json").read_text(encoding="utf-8"))
    salida = []
    for f in fuentes:
        if f["convertidor"] != "diputados_doc" or f["clave"] not in fichas:
            continue
        tipo = f["args"][f["args"].index("--tipo") + 1] if "--tipo" in f["args"] else "ley"
        salida.append({
            "clave": f["clave"],
            "indice": "reglamentos" if tipo == "reglamento" else "leyes",
            "tronco": tronco(f["archivo"]),
            "fecha_catalogo": fichas[f["clave"]]["ultima_reforma_dof"],
            "sha_catalogo": fichas[f["clave"]]["original"]["sha256"],
        })
    return salida


def revisar(args):
    normas = vigiladas()
    filas = {nombre: leer_filas(html_de(url)) for nombre, url in INDICES.items()}
    informe = []
    for n in normas:
        buscar = buscar_reglamento if n["indice"] == "reglamentos" else buscar_ley
        fila = buscar(filas[n["indice"]], n["tronco"])
        item = dict(n)
        if fila is None:
            item.update(estado="no_encontrada")
        else:
            item.update(fila)
            cambio = fila["fecha_indice"] != n["fecha_catalogo"]
            anuncio = any(m in fila["marcas"] for m in ("Nueva reforma", "En actualización"))
            if args.simular and n["clave"] in args.simular:
                cambio = True
                item["simulado"] = True
            item["estado"] = "revisar" if (cambio or anuncio) else "al_dia"
        informe.append(item)
    Path(args.salida).write_text(json.dumps(informe, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for i in informe:
        print(f"{i['clave']}: {i['estado']} (catálogo {i['fecha_catalogo']}, índice {i.get('fecha_indice')}, marcas {i.get('marcas', [])})")


# ---------------------------------------------------------------- actualización

def leer_jsonl(ruta):
    if not ruta.exists():
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def comparar(previos, nuevos):
    a = {r["id"]: r for r in previos}
    b = {r["id"]: r for r in nuevos}
    cambiados = [i for i in b if i in a and (a[i]["texto"], a[i]["estado"], a[i]["anotaciones"]) !=
                 (b[i]["texto"], b[i]["estado"], b[i]["anotaciones"])]
    return {
        "reformados": [i for i in cambiados if b[i]["estado"] == a[i]["estado"]],
        "derogados": [i for i in cambiados if b[i]["estado"] == "derogado" and a[i]["estado"] != "derogado"],
        "adicionados": [i for i in b if i not in a],
        "eliminados": [i for i in a if i not in b],
    }


def siguiente_version():
    m = json.loads((RAIZ / "manifest.json").read_text(encoding="utf-8"))
    n = int(re.sub(r"\D", "", m["version"]) or 1)
    return f"v{n + 1}"


def correr(cmd):
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def actualizar(args):
    informe = json.loads(Path(args.informe).read_text(encoding="utf-8"))
    originales = Path(args.originales)
    originales.mkdir(parents=True, exist_ok=True)
    fuentes_ruta = RAIZ / "herramientas" / "fuentes.json"
    plan = []
    propuestas = []
    for item in informe:
        if item["estado"] != "revisar":
            continue
        clave = item["clave"]
        res = {"clave": clave, "fecha_indice": item.get("fecha_indice"), "marcas": item.get("marcas", []),
               "url_doc": item.get("url_doc"), "simulado": item.get("simulado", False)}
        try:
            archivo = nombre_archivo(item["url_doc"])
            destino = originales / archivo
            descargar(item["url_doc"], destino)
            previos = leer_jsonl(RAIZ / "corpus" / clave / "articulos.jsonl")
            # Actualizar la fuente (el nombre del archivo de los reglamentos cambia con cada reforma)
            fuentes = json.loads(fuentes_ruta.read_text(encoding="utf-8"))
            for f in fuentes:
                if f["clave"] == clave:
                    f["archivo"] = archivo
                    k = f["args"].index("--fuente")
                    f["args"][k + 1] = item["url_doc"]
            fuentes_ruta.write_text(json.dumps(fuentes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            codigo, salida = correr([sys.executable, "herramientas/cargar.py", str(originales), "--solo", clave])
            if codigo:
                raise RuntimeError("La conversión falló:\n" + salida)
            ficha = json.loads((RAIZ / "corpus" / clave / "ficha.json").read_text(encoding="utf-8"))
            nuevos = leer_jsonl(RAIZ / "corpus" / clave / "articulos.jsonl")
            dif = comparar(previos, nuevos)
            res["fecha_doc"] = ficha["ultima_reforma_dof"]
            res["diferencias"] = dif
            res["avisos_conversion"] = [l.strip() for l in salida.splitlines() if "AVISO" in l]
            hay_cambios = any(dif.values()) or ficha["ultima_reforma_dof"] != item["fecha_catalogo"]
            if not hay_cambios:
                res["estado"] = "pendiente" if res["marcas"] else "sin_cambios"
                correr(["git", "checkout", "--", "corpus", "herramientas/fuentes.json"])
            else:
                res["estado"] = "propuesta"
                propuestas.append(res)
        except Exception as e:  # noqa: BLE001 - cualquier falla se reporta en el aviso
            res["estado"] = "error"
            res["detalle"] = str(e)[:3000]
            correr(["git", "checkout", "--", "corpus", "herramientas/fuentes.json"])
        plan.append(res)

    if propuestas:
        version = siguiente_version()
        lineas = [f"## {version} ({date.today().isoformat()})", ""]
        for r in propuestas:
            d = r["diferencias"]
            partes = [f"{k}: {', '.join(v)}" for k, v in d.items() if v]
            lineas.append(f"- {r['clave']}: reforma DOF {r['fecha_doc']}. " + ("; ".join(partes) if partes else "sin cambios de texto por artículo") + ". Detectada por el vigilante.")
        cambios = (RAIZ / "CAMBIOS.md").read_text(encoding="utf-8")
        marca = "Las entradas nuevas van arriba.\n"
        cambios = cambios.replace(marca, marca + "\n" + "\n".join(lineas) + "\n", 1)
        (RAIZ / "CAMBIOS.md").write_text(cambios, encoding="utf-8")
        for cmd in (["herramientas/publicar.py", "--version", version], ["herramientas/validar.py"]):
            codigo, salida = correr([sys.executable] + cmd)
            if codigo:
                for r in propuestas:
                    r["estado"] = "error"
                    r["detalle"] = "La revisión automática falló:\n" + salida[:3000]
                break
        for r in propuestas:
            r["version"] = version
    Path(args.salida).write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in plan:
        print(f"{r['clave']}: {r['estado']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="accion", required=True)
    a = sub.add_parser("revisar")
    a.add_argument("--salida", required=True)
    a.add_argument("--simular", nargs="*", default=[], help="claves que se tratan como si hubieran cambiado (prueba)")
    b = sub.add_parser("actualizar")
    b.add_argument("--informe", required=True)
    b.add_argument("--originales", required=True)
    b.add_argument("--salida", required=True)
    args = ap.parse_args()
    {"revisar": revisar, "actualizar": actualizar}[args.accion](args)


if __name__ == "__main__":
    main()
