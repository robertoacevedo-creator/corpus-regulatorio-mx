"""Prueba de la consulta y del verificador de citas contra el corpus publicado.

    python pruebas/test_consulta.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "herramientas"))
import consulta as q  # noqa: E402


def main():
    fallas = []

    def esperar(cond, msg):
        if not cond:
            fallas.append(msg)

    man, errores = q.comprobar()
    esperar(not errores, f"huellas: {errores}")
    c = q.Corpus()
    esperar(c.norma("ley de residuos") == "LGPGIR", "alias de la LGPGIR")
    esperar(c.norma("NOM 052") == "NOM-052-SEMARNAT-2005", "alias de la NOM-052")
    esperar(c.norma("reglamento de la lgpgir") == "Reg_LGPGIR", "alias del Reglamento")
    esperar(c.registro("LGPGIR", "Artículo 62 BIS")["id"] == "62 Bis", "artículo con sufijo")
    esperar(c.registro("LGPGIR", "art. 1o.")["id"] == "1", "artículo con ordinal")
    esperar(c.registro("nom 052", "numeral 5.2")["id"] == "5.2", "numeral")
    esperar(c.registro("nom 052", "1.1") is None or c.registro("nom 052", "1.1")["id"] == "1.1", "numeral no se confunde con otro")
    esperar(c.registro("nom 052", "listado 3 h012")["texto"].endswith("H012"), "renglón de listado")
    esperar(c.registro("Reg_LGPGIR", "transitorio primero")["tipo"] == "transitorio", "transitorio")
    esperar(c.registro("LGPGIR", "999") is None, "artículo inexistente")
    esperar(any(r["id"] == "5" for r in c.buscar("gran generador toneladas", "LGPGIR", 3)), "búsqueda")

    borrador = ("[[CITA norma=LGPGIR id=5]]XII. Gran Generador: Persona física o moral que genere una cantidad igual "
                "o superior a 10 toneladas en peso bruto total de residuos al año[[/CITA]] "
                "[[CITA ley=NOM-052-SEMARNAT-2005 art=5.2]]corrosivo, reactivo, explosivo, tóxico, inflamable[[/CITA]] "
                "y el artículo 47 también.")
    informe, sin_cita = q.verificar(c, borrador)
    esperar([x["resultado"][:5] for x in informe] == ["VERDE", "ROJO:"], f"verificar: {informe}")
    esperar(sin_cita and sin_cita[0].startswith("artículo 47"), f"mención sin cita: {sin_cita}")

    if fallas:
        print("FALLAS:")
        for f in fallas:
            print(" -", f)
        sys.exit(1)
    print("Prueba de consulta correcta.")


if __name__ == "__main__":
    main()
