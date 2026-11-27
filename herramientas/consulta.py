"""Consulta y verificación de citas sobre el corpus. Sin IA: solo código determinista.

Lo usa la skill de consulta, desde una copia del repositorio ya comprobada:

    python3 -I herramientas/consulta.py comprobar
    python3 -I herramientas/consulta.py buscar "gran generador toneladas" [--norma LGPGIR] [--max 10]
    python3 -I herramientas/consulta.py ver LGPGIR 5
    python3 -I herramientas/consulta.py ver NOM-052-SEMARNAT-2005 "Listado 3 H012"
    python3 -I herramientas/consulta.py remisiones Reg_LGPGIR 35
    python3 -I herramientas/consulta.py decretos LGPGIR 5
    python3 -I herramientas/consulta.py verificar /tmp/borrador.md

`comprobar` sale con código 1 si falta un archivo o una huella no cuadra: en ese caso
no se contesta ninguna consulta con base en el corpus.

En el borrador, cada cita va marcada así:
    [[CITA norma=CLAVE id=ID]]texto literal[[/CITA]]
(también se acepta `ley=` en lugar de `norma=` y `art=` en lugar de `id=`).
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Nombres con que se suele pedir cada norma, además de su clave y su nombre oficial.
ALIAS = {
    "LGPGIR": ["ley general para la prevencion y gestion integral de los residuos", "ley de residuos", "lgpgir"],
    "Reg_LGPGIR": ["reglamento de la lgpgir", "reglamento de la ley general para la prevencion y gestion integral de los residuos",
                   "reglamento de residuos", "rlgpgir"],
    "NOM-052-SEMARNAT-2005": ["nom-052", "nom 052", "nom052", "nom-052-semarnat", "norma de residuos peligrosos"],
}


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_txt(s):
    """Normaliza solo la forma, nunca el contenido: espacios, comillas, guiones y puntos suspensivos."""
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("–", "-").replace("—", "-").replace("…", "...")
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_id(i):
    """'Artículo 62 BIS' -> '62 bis'; 'art. 1o.' -> '1'; 'numeral 5.2' -> '5.2'; 'listado 3 h012' -> 'listado 3 h012'."""
    i = sin_acentos(str(i)).lower().strip()
    i = re.sub(r"^(?:art[ií]culo|art\.?|numeral|num\.?)\s*", "", i)
    i = re.sub(r"^(\d+)\s*(?:o\.?|º|°)(?=\s|$|\.)", r"\1", i)
    i = re.sub(r"\s+", " ", i).strip().rstrip(".")
    return i


def compacto(i):
    return re.sub(r"[^a-z0-9.]", "", norm_id(i))


# ---------------------------------------------------------------- carga y comprobación

def comprobar(raiz=RAIZ):
    """Comprueba el manifiesto. Devuelve (manifest, errores)."""
    man = json.loads((raiz / "manifest.json").read_text(encoding="utf-8"))
    errores = []
    for rel, meta in man["archivos"].items():
        p = raiz / rel
        if not p.exists():
            errores.append(f"falta {rel}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
            errores.append(f"{rel} no coincide con su huella SHA-256 (descarga incompleta o alterada)")
    return man, errores


class Corpus:
    def __init__(self, raiz=RAIZ):
        raiz = Path(raiz)
        self.catalogo = {n["clave"]: n for n in json.loads((raiz / "catalogo.json").read_text(encoding="utf-8"))["normas"]}
        self.regs, self.decretos = [], []
        for clave in self.catalogo:
            carpeta = raiz / "corpus" / clave
            self.regs += [json.loads(l) for l in (carpeta / "articulos.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            d = carpeta / "decretos.jsonl"
            if d.exists():
                self.decretos += [json.loads(l) for l in d.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.idx = {(r["ley"], norm_id(r["id"])): r for r in self.regs}
        self.idx_compacto = {}
        for r in self.regs:
            self.idx_compacto.setdefault((r["ley"], compacto(r["id"])), []).append(r)

    def norma(self, nombre):
        """Clave de la norma a partir de su clave, alias o nombre oficial."""
        n = sin_acentos(nombre).lower().strip()
        for clave, ficha in self.catalogo.items():
            if n in (clave.lower(), sin_acentos(ficha["nombre"]).lower()) or n in ALIAS.get(clave, []):
                return clave
        return None

    def registro(self, norma, id_):
        clave = self.norma(norma) or norma
        r = self.idx.get((clave, norm_id(id_)))
        if r:
            return r
        candidatos = self.idx_compacto.get((clave, compacto(id_)), [])
        return candidatos[0] if len(candidatos) == 1 else None

    def buscar(self, consulta, norma=None, max_res=10):
        terms = [t for t in re.findall(r"[\w\-]+", sin_acentos(consulta).lower()) if len(t) > 2]
        clave = (self.norma(norma) or norma) if norma else None
        res = []
        for r in self.regs:
            if clave and r["ley"] != clave:
                continue
            t = sin_acentos(r["texto"] + " " + r["id"]).lower()
            hits = sum(1 for x in terms if x in t)
            if hits:
                res.append((hits, sum(t.count(x) for x in terms), r))
        res.sort(key=lambda x: (-x[0], -x[1]))
        return [x[2] for x in res[:max_res]]

    def remisiones(self, r):
        """Artículos citados en el texto: misma norma, o la ley que reglamenta un reglamento ("la Ley")."""
        out, externos = [], []
        ley_de_reglamento = r["ley"][4:] if r["ley"].startswith("Reg_") and r["ley"][4:] in self.catalogo else None
        for m in re.finditer(r"art[íi]culos?\s+((?:\d+[\w\s,\-y]*?)+?)(?=\s+(?:de|del|de la|y|o|,|\.|;|en|a|que|al|para)\b|[\.,;])"
                             r"(\s+de\s+(?:la|esta|este|el)\s+[\w\s]{0,60})?", r["texto"], re.I):
            nums = re.findall(r"\d+(?:\s*(?:-\s*[A-Z]|bis(?:\s*\d+)?|ter|[A-Z]\b))?", m.group(1), re.I)
            cola = sin_acentos(m.group(2) or "").lower()
            if cola == "" or "esta ley" in cola or "este ordenamiento" in cola or "presente" in cola or "este reglamento" in cola:
                destino = r["ley"]
            elif ley_de_reglamento and re.search(r"\bla ley\b", cola):
                destino = ley_de_reglamento
            else:
                externos.append(m.group(0).strip())
                continue
            for n in nums:
                x = self.registro(destino, n)
                if x and x is not r and x not in out:
                    out.append(x)
        return out, externos

    def decretos_que_tocan(self, norma, id_):
        """Decretos de reforma cuyo texto menciona el artículo (para revisar transitorios)."""
        clave = self.norma(norma) or norma
        n = re.sub(r"\s.*$", "", norm_id(id_))
        pat = re.compile(r"art[íi]culos?\b[^.]{0,400}?\b" + re.escape(n) + r"\b", re.I)
        return [d for d in self.decretos if d["ley"] == clave and pat.search(d["titulo"] + " " + d["texto"][:4000])]


CITA = re.compile(r"\[\[CITA\s+(?:norma|ley)=(\S+)\s+(?:id|art)=([^\]]+?)\]\](.*?)\[\[/CITA\]\]", re.S)


def verificar(corpus, borrador):
    """Coteja letra por letra cada cita marcada contra el corpus."""
    informe = []
    for m in CITA.finditer(borrador):
        norma, id_, cita = m.group(1), m.group(2).strip(), m.group(3)
        r = corpus.registro(norma, id_)
        fila = {"norma": norma, "id": id_, "cita": norm_txt(cita)[:120]}
        if not r:
            fila["resultado"] = "ROJO: el registro no existe en el corpus"
        else:
            fuente, c = norm_txt(r["texto"]), norm_txt(cita).strip('"').strip()
            if c and c in fuente:
                fila["resultado"] = "VERDE: cita textual exacta"
            else:
                sm = difflib.SequenceMatcher(None, fuente, c, autojunk=False)
                b = sm.find_longest_match(0, len(fuente), 0, len(c))
                ini = max(0, b.a - b.b)
                cand = fuente[ini: ini + len(c) + 20]
                ratio = difflib.SequenceMatcher(None, cand[: len(c)], c).ratio()
                fila["resultado"] = f"ROJO: no coincide (similitud {ratio:.0%})"
                fila["texto_real"] = cand[: len(c) + 20]
            if r["estado"] == "derogado":
                fila["resultado"] += " | AVISO: derogado"
            fila["ultima_reforma_articulo"] = r["ultima_reforma_articulo"]
        informe.append(fila)
    sin_cita = re.findall(r"(?:art[íi]culo|numeral)\s+\d+[^\n]{0,40}", CITA.sub("", borrador), re.I)
    return informe, sin_cita


# ---------------------------------------------------------------- línea de comandos

def mostrar(r, completo=True):
    print(f"== {r['ley']} | {r['id']} | {r['tipo']} | {r['estado']}")
    print(f"   ubicación: {r['ubicacion']}")
    print(f"   última reforma del registro: {r['ultima_reforma_articulo'] or 'sin nota de reforma en la compilación'}"
          f" | de la norma: {r['ultima_reforma_ley']} | línea/página de origen: {r['linea_fuente']}")
    if r["anotaciones"]:
        print("   anotaciones:", " / ".join(r["anotaciones"]))
    print(r["texto"] if completo else "   " + r["texto"][:240].replace("\n", " ⏎ "))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="accion", required=True)
    sub.add_parser("comprobar")
    b = sub.add_parser("buscar")
    b.add_argument("consulta")
    b.add_argument("--norma")
    b.add_argument("--max", type=int, default=10)
    for nombre in ("ver", "remisiones", "decretos"):
        x = sub.add_parser(nombre)
        x.add_argument("norma")
        x.add_argument("id")
    v = sub.add_parser("verificar")
    v.add_argument("borrador")
    args = ap.parse_args()

    if args.accion == "comprobar":
        try:
            man, errores = comprobar()
        except FileNotFoundError as e:
            print("CORPUS NO DISPONIBLE:", e)
            sys.exit(1)
        if errores:
            print("CORPUS NO CONFIABLE:", "; ".join(errores))
            sys.exit(1)
        c = Corpus()
        print(f"CORPUS OK — versión {man['version']} ({man['fecha']}), {len(c.regs)} registros")
        for clave, f in c.catalogo.items():
            print(f"  {clave}: {f['nombre']} — {f['tipo']}, última reforma DOF {f['ultima_reforma_dof']}")
        return

    c = Corpus()
    if args.accion == "buscar":
        for r in c.buscar(args.consulta, args.norma, args.max):
            mostrar(r, completo=False)
    elif args.accion == "ver":
        r = c.registro(args.norma, args.id)
        if not r:
            print(f"NO ESTÁ EN EL CORPUS: {args.norma} {args.id}")
            sys.exit(1)
        mostrar(r)
    elif args.accion == "remisiones":
        r = c.registro(args.norma, args.id)
        if not r:
            print(f"NO ESTÁ EN EL CORPUS: {args.norma} {args.id}")
            sys.exit(1)
        dentro, externos = c.remisiones(r)
        for x in dentro:
            mostrar(x, completo=False)
        if externos:
            print("Remisiones a otras normas (fuera del corpus o sin resolver):", "; ".join(externos))
    elif args.accion == "decretos":
        for d in c.decretos_que_tocan(args.norma, args.id):
            print(f"== {d['fecha_dof']} | {d['titulo']}\n{d['texto'][:3000]}\n")
    elif args.accion == "verificar":
        informe, sin_cita = verificar(c, Path(args.borrador).read_text(encoding="utf-8"))
        for x in informe:
            print(json.dumps(x, ensure_ascii=False))
        verdes = sum(1 for x in informe if x["resultado"].startswith("VERDE"))
        print(f"Citas exactas: {verdes} de {len(informe)}")
        print("Menciones sin cita:", sin_cita)


if __name__ == "__main__":
    main()
