"""Funciones compartidas por todos los convertidores.

Cada convertidor lee un original (.doc, .docx o PDF), lo parte por artículo
(o por numeral, en las NOM) y escribe en corpus/<clave>/ registros con los mismos campos
que usa el corpus de leyes federales (robertoacevedo-creator/corpus-leyes-mx),
para que el mismo verificador de citas funcione con los dos.
"""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

RE_FECHA_DOF = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b")


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def limpiar_linea(linea):
    """Normaliza una línea sin cambiar sus palabras.

    - Unicode en forma NFC (acentos compuestos).
    - Tabuladores y espacios duros pasan a espacio simple; se juntan los
      espacios repetidos. Así una cita se compara letra por letra sin que
      importe cómo venía espaciado el original.
    """
    linea = unicodedata.normalize("NFC", linea)
    linea = linea.replace("\ufeff", "").replace("\u200b", "").replace("\u00a0", " ").replace("\t", " ")
    linea = re.sub(r"[ \u2000-\u200a]+", " ", linea)
    return linea.strip()


def fecha_dof_a_iso(texto):
    """'19-01-2026' -> '2026-01-19'. Devuelve None si no hay fecha."""
    m = RE_FECHA_DOF.search(texto or "")
    if not m:
        return None
    d, mth, y = m.groups()
    return f"{y}-{mth}-{d}"


def fechas_dof(texto):
    return [f"{y}-{m}-{d}" for d, m, y in RE_FECHA_DOF.findall(texto or "")]


def fecha_larga_a_iso(texto):
    """'22 de mayo de 2006' -> '2006-05-22'."""
    m = re.search(r"(\d{1,2})o?\.?\s+de\s+([a-záéíóú]+)\s+(?:de|del)\s+(\d{4})", texto or "", re.I)
    if not m:
        return None
    mes = MESES.get(m.group(2).lower())
    if not mes:
        return None
    return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}"


def doc_a_texto(ruta):
    """Convierte .doc o .docx a texto UTF-8 con LibreOffice y devuelve las líneas."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("Falta LibreOffice (soffice) para leer .doc/.docx")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "txt:Text (encoded):UTF8",
             "--outdir", tmp, str(ruta)],
            check=True, capture_output=True, timeout=600,
        )
        salida = Path(tmp) / (Path(ruta).stem + ".txt")
        return salida.read_text(encoding="utf-8").splitlines()


def escribir_jsonl(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def escribir_norma(clave, articulos, decretos, ficha):
    """Escribe corpus/<clave>/ y devuelve la ficha para el catálogo."""
    carpeta = CORPUS / clave
    if carpeta.exists():
        shutil.rmtree(carpeta)
    escribir_jsonl(carpeta / "articulos.jsonl", articulos)
    if decretos:
        escribir_jsonl(carpeta / "decretos.jsonl", decretos)
    ficha = dict(ficha)
    ficha["conteo"] = {
        "articulos": sum(1 for a in articulos if a["tipo"] in ("articulo", "numeral")),
        "renglones": sum(1 for a in articulos if a["tipo"] == "renglon"),
        "registros": len(articulos),
        "derogados": sum(1 for a in articulos if a["estado"] == "derogado"),
        "transitorios": sum(1 for a in articulos if a["tipo"] == "transitorio"),
        "decretos": len(decretos),
    }
    (carpeta / "ficha.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ficha


def hoy():
    return date.today().isoformat()
