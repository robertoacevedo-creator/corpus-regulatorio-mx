"""Revisión automática del corpus. Corre en cada pull request y antes de publicar.

    python herramientas/validar.py

Falla (código de salida 1) si encuentra cualquiera de estos problemas:
  1. Una norma del catálogo sin carpeta o sin registros, o una carpeta fuera del catálogo.
  2. Registros vacíos o con id repetido dentro de una norma.
  3. Campos faltantes, con tipo equivocado o con valores no válidos (también en decretos).
  4. Conteos del catálogo que no cuadran con los registros.
  5. Notas de reforma ("Fracción reformada DOF ...") que se quedaron dentro del texto.
  6. Huellas del manifiesto que no cuadran, o archivos publicados fuera del manifiesto.
  7. Artículos de control (herramientas/control.json) que ya no dicen lo mismo.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus"
sys.path.insert(0, str(RAIZ / "herramientas"))
from publicar import archivos_publicados  # noqa: E402

CAMPOS = {
    "ley": str, "id": str, "tipo": str, "estado": str, "ubicacion": str, "texto": str,
    "anotaciones": list, "ultima_reforma_articulo": (str, type(None)),
    "ultima_reforma_ley": (str, type(None)), "linea_fuente": int,
}
CAMPOS_DECRETO = {"ley": str, "titulo": str, "fecha_dof": (str, type(None)), "linea_fuente": int, "texto": str}
TIPOS = {"articulo", "numeral", "transitorio", "preambulo", "cierre", "anexo", "renglon"}
ESTADOS = {"vigente", "derogado"}
FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NOTA_EN_TEXTO = re.compile(
    r"^(?:P[áa]rrafo|Fracci[óo]n|Inciso|Art[íi]culo|Apartado|Fe de erratas)\b.{0,120}"
    r"(?:reformad|adicionad|derogad|recorrid|erratas).{0,80}DOF \d{2}-\d{2}-\d{4}", re.I)


def leer_jsonl(ruta):
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    errores = []
    catalogo = json.loads((RAIZ / "catalogo.json").read_text(encoding="utf-8"))
    claves = [n["clave"] for n in catalogo["normas"]]
    textos = {}

    for ficha in catalogo["normas"]:
        clave = ficha["clave"]
        ruta = CORPUS / clave / "articulos.jsonl"
        if not ruta.exists():
            errores.append(f"{clave}: está en el catálogo pero no tiene corpus/{clave}/articulos.jsonl")
            continue
        filas = leer_jsonl(ruta)
        if not filas:
            errores.append(f"{clave}: articulos.jsonl está vacío")
        vistos = set()
        for n, f in enumerate(filas, 1):
            for campo, tipo in CAMPOS.items():
                if campo not in f or not isinstance(f[campo], tipo):
                    errores.append(f"{clave} línea {n}: campo '{campo}' falta o tiene tipo equivocado")
            if f.get("ley") != clave:
                errores.append(f"{clave} línea {n}: 'ley' dice {f.get('ley')!r}")
            if f.get("tipo") not in TIPOS:
                errores.append(f"{clave} {f.get('id')}: tipo {f.get('tipo')!r} no válido")
            if f.get("estado") not in ESTADOS:
                errores.append(f"{clave} {f.get('id')}: estado {f.get('estado')!r} no válido")
            if not (f.get("ubicacion") or "").strip():
                errores.append(f"{clave} {f.get('id')}: ubicación vacía")
            for campo in ("ultima_reforma_articulo", "ultima_reforma_ley"):
                if f.get(campo) is not None and not FECHA.match(f[campo]):
                    errores.append(f"{clave} {f.get('id')}: {campo} no es AAAA-MM-DD")
            texto = f.get("texto") or ""
            if len(texto.strip()) < 3:
                errores.append(f"{clave} {f.get('id')}: texto vacío")
            for linea in texto.split("\n"):
                if NOTA_EN_TEXTO.match(linea):
                    errores.append(f"{clave} {f.get('id')}: nota de reforma dentro del texto: {linea[:80]}")
            if f.get("id") in vistos:
                errores.append(f"{clave}: id repetido {f.get('id')!r}")
            vistos.add(f.get("id"))
            textos[(clave, f.get("id"))] = texto

        conteo = ficha.get("conteo", {})
        reales = {
            "articulos": sum(1 for f in filas if f["tipo"] in ("articulo", "numeral")),
            "renglones": sum(1 for f in filas if f["tipo"] == "renglon"),
            "registros": len(filas),
            "derogados": sum(1 for f in filas if f["estado"] == "derogado"),
            "transitorios": sum(1 for f in filas if f["tipo"] == "transitorio"),
        }
        ruta_d = CORPUS / clave / "decretos.jsonl"
        decretos = leer_jsonl(ruta_d) if ruta_d.exists() else []
        reales["decretos"] = len(decretos)
        for k, v in reales.items():
            if conteo.get(k) != v:
                errores.append(f"{clave}: el catálogo dice {k}={conteo.get(k)} y hay {v}")
        for n, d in enumerate(decretos, 1):
            for campo, tipo in CAMPOS_DECRETO.items():
                if campo not in d or not isinstance(d[campo], tipo):
                    errores.append(f"{clave} decreto {n}: campo '{campo}' falta o tiene tipo equivocado")
            if d.get("fecha_dof") and not FECHA.match(d["fecha_dof"]):
                errores.append(f"{clave} decreto {n}: fecha_dof no es AAAA-MM-DD")

    carpetas = {p.parent.name for p in CORPUS.glob("*/articulos.jsonl")}
    for sobra in sorted(carpetas - set(claves)):
        errores.append(f"corpus/{sobra}/ existe pero no está en el catálogo")

    manifest = json.loads((RAIZ / "manifest.json").read_text(encoding="utf-8"))
    for rel, esperado in manifest["archivos"].items():
        ruta = RAIZ / rel
        if not ruta.exists():
            errores.append(f"manifest: falta {rel}")
        elif hashlib.sha256(ruta.read_bytes()).hexdigest() != esperado["sha256"]:
            errores.append(f"manifest: la huella de {rel} no cuadra (corre herramientas/publicar.py)")
    en_disco = {p.relative_to(RAIZ).as_posix() for p in archivos_publicados()}
    for falta in sorted(en_disco - set(manifest["archivos"])):
        errores.append(f"manifest: {falta} no está en el manifiesto")

    control = json.loads((RAIZ / "herramientas" / "control.json").read_text(encoding="utf-8"))
    for c in control:
        texto = textos.get((c["clave"], c["id"]))
        if texto is None:
            errores.append(f"control: no existe {c['clave']} {c['id']}")
        elif c["fragmento"] not in texto:
            errores.append(f"control: {c['clave']} {c['id']} ya no contiene «{c['fragmento']}»")

    if errores:
        print(f"REVISIÓN CON ERRORES ({len(errores)}):")
        for e in errores:
            print(" -", e)
        sys.exit(1)
    print(f"Revisión correcta: {len(claves)} normas, {len(textos)} registros, "
          f"{len(manifest['archivos'])} archivos con huella, {len(control)} artículos de control.")


if __name__ == "__main__":
    main()
