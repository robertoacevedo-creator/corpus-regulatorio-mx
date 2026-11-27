"""Arma catalogo.json y manifest.json a partir de lo que hay en el repositorio.

    python herramientas/publicar.py --version v1

catalogo.json junta la ficha de cada norma (corpus/<clave>/ficha.json).
manifest.json guarda la huella SHA-256, el tamaño y las líneas de cada
archivo del repositorio (corpus, catálogo, código, documentación), para que
quien lo descargue compruebe que llegó completo y sin cambios.
"""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus"
# Lo que entra en el manifiesto: todo lo publicado, salvo el propio manifiesto.
INCLUIR = ["catalogo.json", "README.md", "CAMBIOS.md", "requirements.txt", ".gitignore",
           "corpus", "convertidores", "herramientas", "pruebas", ".github"]


def archivos_publicados():
    salida = []
    for nombre in INCLUIR:
        ruta = RAIZ / nombre
        if ruta.is_file():
            salida.append(ruta)
        elif ruta.is_dir():
            salida += [p for p in ruta.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    return sorted(salida, key=lambda p: p.relative_to(RAIZ).as_posix())


def huella(ruta):
    datos = ruta.read_bytes()
    return {"sha256": hashlib.sha256(datos).hexdigest(), "bytes": len(datos), "lineas": datos.count(b"\n")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--fecha", default=date.today().isoformat())
    args = ap.parse_args()

    fichas = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(CORPUS.glob("*/ficha.json"))]
    catalogo = {"version": args.version, "fecha": args.fecha, "normas": fichas}
    (RAIZ / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    archivos = {p.relative_to(RAIZ).as_posix(): huella(p) for p in archivos_publicados()}
    manifest = {"version": args.version, "fecha": args.fecha, "archivos": archivos,
                "normas": [f["clave"] for f in fichas]}
    (RAIZ / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(fichas)} normas, {len(archivos)} archivos en el manifiesto")


if __name__ == "__main__":
    main()
