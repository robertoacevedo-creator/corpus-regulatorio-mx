"""Reconstruye el corpus desde los originales, con los datos de herramientas/fuentes.json.

    python herramientas/cargar.py CARPETA_DE_ORIGINALES [--solo CLAVE ...]

Cada entrada de fuentes.json dice qué convertidor usar, qué archivo leer y con
qué datos. Así cualquier actualización se repite igual, sin depender de
recordar cómo se hizo la vez anterior.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("originales")
    ap.add_argument("--solo", nargs="*")
    args = ap.parse_args()
    fuentes = json.loads((RAIZ / "herramientas" / "fuentes.json").read_text(encoding="utf-8"))
    fallas = 0
    for f in fuentes:
        if args.solo and f["clave"] not in args.solo:
            continue
        original = Path(args.originales) / f["archivo"]
        if not original.exists():
            print(f"FALTA {f['clave']}: no está {original}", file=sys.stderr)
            fallas += 1
            continue
        cmd = [sys.executable, str(RAIZ / "convertidores" / f"{f['convertidor']}.py"), str(original),
               "--clave", f["clave"], *f["args"]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            print(f"ERROR {f['clave']}:\n{r.stderr}", file=sys.stderr)
            fallas += 1
            continue
        conteo = json.loads(r.stdout)["conteo"]
        print(f"OK {f['clave']}: {conteo}")
        for linea in r.stderr.splitlines():
            print("   ", linea)
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
