"""Prueba del convertidor de Diputados con un texto inventado que reúne los casos difíciles.

    python pruebas/test_diputados.py
"""
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "convertidores"))
import comun  # noqa: E402
import diputados_doc as dd  # noqa: E402

TEXTO = """LEY DE PRUEBA
Nueva Ley publicada en el Diario Oficial de la Federación el 1 de enero de 2000
TEXTO VIGENTE
Última reforma publicada DOF 01-01-2024
LIBRO PRIMERO
DE LO GENERAL
TÍTULO PRIMERO
DISPOSICIONES GENERALES
Capítulo I
Del objeto
Artículo 1o.- Primer artículo.
Fe de erratas al párrafo DOF 05-09-2023
Artículo 2o.- Segundo artículo.
I.\tFracción uno;
Fracción declarada inválida por sentencia de la SCJN a Acción de Inconstitucionalidad notificada DOF 30-09-2022
Título de concesión que otorgue la Secretaría en los términos de esta Ley
II. Fracción dos.
Artículo 2o. Bis.- Artículo bis.
Artículos 3o. a 5o.- Se derogan.
Artículo 6 C Bis.- Artículo con letra.
Artículo 6-A.- Artículo con guion.
Artículo 7.- Se deroga.
Artículo derogado DOF 01-01-2024
Artículo 8.- Último.
Artículo reubicado DOF 02-02-2024
Artículo 9.- I. Las fracciones empiezan con romano.
Artículo 10.- A. Disposición que empieza con letra.
Artículo 11. A. El Estado; letra después de punto.
ARTÍCULO 11-1.- Numerado con guion.
Artículo 11 A.- Letra suelta con separador.
Artículo 12-Bis.- Sufijo pegado con guion.
TRANSITORIOS
PRIMERO.- Esta ley entra en vigor al día siguiente.
En cumplimiento de los programas, la Secretaría informará cada año.
Artículo Segundo.- Se abroga la ley anterior.
Dado en el Palacio Nacional, en la Ciudad de México, a 1 de enero de 1990.- Rúbrica.
México, Distrito Federal, a 26 de abril de 2007.- Dip. Fulano, Presidente.- Rúbricas.
En cumplimiento de lo dispuesto por la fracción I del Artículo 89, expido el presente Decreto.
ARTÍCULOS TRANSITORIOS DE DECRETOS DE REFORMA
DECRETO por el que se reforma el artículo 2o.
Publicado en el Diario Oficial de la Federación el 1 de enero de 2024
Artículo 1o.- Entra en vigor.
ACLARACIÓN al Decreto anterior
ÚNICO.- Texto de aclaración sin línea Publicado.
"""


def main():
    comun.doc_a_texto = lambda ruta: TEXTO.splitlines()
    with tempfile.NamedTemporaryFile(suffix=".doc") as f:
        arts, decs, ficha, avisos, errores = dd.convertir(f.name, "PRUEBA", "url", "ley")
    por_id = {a["id"]: a for a in arts}
    fallas = []

    def esperar(cond, msg):
        if not cond:
            fallas.append(msg)

    esperar(list(por_id) == ["1", "2", "2 Bis", "3 a 5", "6 C Bis", "6-A", "7", "8", "9", "10", "11", "11-1", "11 A", "12 Bis",
                             "Transitorio Primero", "Transitorio Segundo"], f"ids: {list(por_id)}")
    esperar(por_id["9"]["texto"].startswith("Artículo 9.- I. Las"), "romano al inicio del texto")
    esperar("En cumplimiento de los programas" in por_id["Transitorio Primero"]["texto"],
            "un párrafo que empieza con 'En cumplimiento' no es cierre")
    esperar(por_id["1"]["anotaciones"] == ["Fe de erratas al párrafo DOF 05-09-2023"], "fe de erratas")
    esperar("Título de concesión" in por_id["2"]["texto"], "'Título de concesión' debe quedar en el texto")
    esperar(any("SCJN" in x for x in por_id["2"]["anotaciones"]), "nota de invalidez SCJN")
    esperar("I. Fracción uno;" in por_id["2"]["texto"], "tabulador a espacio")
    esperar(por_id["3 a 5"]["estado"] == "derogado", "rango derogado")
    esperar(por_id["7"]["estado"] == "derogado", "artículo derogado")
    esperar(por_id["8"]["anotaciones"] == ["Artículo reubicado DOF 02-02-2024"], "artículo reubicado")
    esperar(por_id["1"]["ubicacion"] == "LIBRO PRIMERO DE LO GENERAL > TÍTULO PRIMERO DISPOSICIONES GENERALES > Capítulo I Del objeto",
            f"ubicación: {por_id['1']['ubicacion']}")
    esperar("México" not in por_id["Transitorio Segundo"]["texto"], "firma pegada al transitorio")
    esperar([d["fecha_dof"] for d in decs] == ["2024-01-01", None], f"decretos: {[(d['titulo'], d['fecha_dof']) for d in decs]}")
    esperar(not errores, f"errores: {errores}")
    esperar(ficha["ultima_reforma_dof"] == "2024-01-01", "última reforma")

    # Una línea suelta antes de cualquier registro del cuerpo debe dar ERROR de cobertura
    comun.doc_a_texto = lambda ruta: (TEXTO.replace("TRANSITORIOS\nPRIMERO", "TRANSITORIOS\nLínea huérfana\nPRIMERO")).splitlines()
    with tempfile.NamedTemporaryFile(suffix=".doc") as f:
        *_, errores2 = dd.convertir(f.name, "PRUEBA", "url", "ley")
    esperar(any("sin lugar" in e for e in errores2), "la cobertura no detectó una línea huérfana")

    if fallas:
        print("FALLAS:")
        for x in fallas:
            print(" -", x)
        sys.exit(1)
    print("Prueba de Diputados correcta.")


def test_ningun_articulo_trae_encabezado_incrustado():
    """Ninguna línea de texto (salvo la primera) arranca como Título/Capítulo/Libro ni como otro artículo."""
    import json, re
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent / "corpus"
    patron = re.compile(r"^(?:T[ÍI]TULO|CAP[ÍI]TULO|LIBRO)\s+[IVXLC\d\wÁÉÍÓÚ]+\s*$|^ART[ÍI]CULO\s+\d+[\w .\-]*\.\s*-", re.I)
    malos = []
    for f in raiz.glob("*/articulos.jsonl"):
        for linea in f.read_text(encoding="utf-8").splitlines():
            a = json.loads(linea)
            for t in a["texto"].split("\n")[1:]:
                if patron.match(t.strip()):
                    malos.append((f.parent.name, a["id"], t[:40]))
    assert not malos, malos[:10]


def main_corpus():
    try:
        test_ningun_articulo_trae_encabezado_incrustado()
    except AssertionError as e:
        print("ERROR encabezados incrustados:", e)
        sys.exit(1)
    print("Prueba de encabezados incrustados correcta.")


if __name__ == "__main__":
    main()
    main_corpus()
