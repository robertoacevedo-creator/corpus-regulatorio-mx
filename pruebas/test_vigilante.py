"""Prueba de la lectura de los índices de Diputados y de la comparación de versiones.

    python pruebas/test_vigilante.py

Las filas reproducen la estructura de index.htm y regla.htm vista en noviembre de 2026.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "herramientas"))
import vigilante as v  # noqa: E402

LEYES = """<html><head><meta charset="windows-1252"></head><body><table>
<tr><td><table><tr><td>buscar</td></tr></table></td></tr>
<tr><td>No.</td><td>LEY / Página de Reformas</td><td>Última Reforma</td><td>TEXTO VIGENTE</td></tr>
<tr><td>001</td><td><a href="ref/cpeum.htm">CONSTITUCIÓN Política de los Estados Unidos Mexicanos</a> DOF 05/02/1917 Nueva reforma</td>
<td>DOF 07/10/2026</td><td><a href="pdf/CPEUM.pdf">pdf</a><a href="doc/CPEUM.doc">doc</a></td></tr>
<tr><td>012</td><td><a href="ref/lisipl.htm">IMPUESTO sobre Servicios</a> DOF 31/12/1968</td><td>Sin reforma</td>
<td><a href="pdf/79.pdf">pdf</a><a href="doc/79.doc">doc</a></td></tr>
<tr><td>238</td><td><a href="ref/lgpgir.htm">LEY General para la Prevención y Gestión Integral de los Residuos</a> DOF 08/10/2003</td>
<td>DOF 19/01/2026</td><td><a href="/LeyesBiblio/pdf/LGPGIR.pdf">pdf</a><a href="/LeyesBiblio/doc/LGPGIR.doc?v=1">doc</a></td></tr>
<tr><td>005</td><td>CÓDIGO Federal de Procedimientos Civiles DOF 24/02/1943</td><td>Notificación 17/06/2025 Sentencia SCJN</td>
<td><a href="doc/CFPC.doc">doc</a></td></tr>
</table></body></html>"""

REGLAS = """<table>
<tr><td>No.</td><td>Reglamento</td><td>Publicación DOF</td><td>TEXTO VIGENTE</td></tr>
<tr><td>114</td><td>REGLAMENTO de la LGEEPA en Materia de Registro de Emisiones Original DOF 03/06/2004 Reforma DOF 31/10/2014</td>
<td>03/06/2004</td><td><a href="regley/Reg_LGEEPA_MRETC_311014.pdf">PDF</a></td><td><a href="regley/Reg_LGEEPA_MRETC_311014.doc">WORD</a></td></tr>
<tr><td>119</td><td>REGLAMENTO de la Ley General para la Prevención y Gestión Integral de los Residuos
<a href="regley/Reg_LGPGIR_orig_30nov06.doc">Original</a> DOF 30/11/2006 <a href="regley/Reg_LGPGIR_ref01_31oct14.doc">Reforma</a> DOF 31/10/2014</td>
<td>30/11/2006</td><td><a href="regley/Reg_LGPGIR_311014.pdf">PDF</a></td><td><a href="regley/Reg_LGPGIR_311014.doc">WORD</a></td></tr>
<tr><td>82</td><td>REGLAMENTO de la Ley Federal del Derecho de Autor Nueva reforma Original DOF 22/05/1998 Reformas DOF 14/09/2005, 24/09/2026</td>
<td>22/05/1998</td><td><a href="regley/Reg_LFDA_ref02_24sep26.doc">r</a><a href="regley/Reg_LFDA.pdf">PDF</a><a href="regley/Reg_LFDA.doc">WORD</a></td></tr>
</table>"""


def main():
    fallas = []

    def esperar(cond, msg):
        if not cond:
            fallas.append(msg)

    leyes = v.leer_filas(LEYES)
    lg = v.buscar_ley(leyes, "LGPGIR")
    esperar(lg and lg["fecha_indice"] == "2026-01-19", f"LGPGIR fecha: {lg}")
    esperar(lg and lg["url_doc"] == "https://www.diputados.gob.mx/LeyesBiblio/doc/LGPGIR.doc", f"LGPGIR liga: {lg}")
    esperar(lg and lg["marcas"] == [], "LGPGIR sin marcas")
    cp = v.buscar_ley(leyes, "CPEUM")
    esperar(cp and cp["marcas"] == ["Nueva reforma"] and cp["fecha_indice"] == "2026-10-07", f"CPEUM: {cp}")
    sr = v.buscar_ley(leyes, "79")
    esperar(sr and sr["fecha_indice"] == "1968-12-31", f"Sin reforma usa la publicación: {sr}")
    sc = v.buscar_ley(leyes, "CFPC")
    esperar(sc and "Sentencia SCJN" in sc["marcas"], f"Sentencia SCJN: {sc}")
    esperar(v.buscar_ley(leyes, "NOEXISTE") is None, "ley inexistente")

    reglas = v.leer_filas(REGLAS)
    rg = v.buscar_reglamento(reglas, "Reg_LGPGIR")
    esperar(rg and rg["fecha_indice"] == "2014-10-31", f"Reg_LGPGIR fecha: {rg}")
    esperar(rg and rg["url_doc"].endswith("/LeyesBiblio/regley/Reg_LGPGIR_311014.doc"), f"Reg_LGPGIR liga vigente: {rg}")
    esperar(v.buscar_reglamento(reglas, "Reg_LGEEPA") is None, "un tronco no debe confundirse con otro más largo")
    fd = v.buscar_reglamento(reglas, "Reg_LFDA")
    esperar(fd and fd["fecha_indice"] == "2026-09-24" and fd["marcas"] == ["Nueva reforma"], f"Reg_LFDA: {fd}")
    esperar(v.tronco("Reg_LGPGIR_311014.doc") == "Reg_LGPGIR" and v.tronco("LGPGIR.doc") == "LGPGIR", "tronco")

    esperar([v.siguiente_version(x) for x in ("v1", "v1.1", "v9", "v10.2")] == ["v2", "v2", "v10", "v11"], "siguiente_version")

    previos = [{"id": "1", "texto": "a", "estado": "vigente", "anotaciones": []},
               {"id": "2", "texto": "b", "estado": "vigente", "anotaciones": []},
               {"id": "3", "texto": "c", "estado": "vigente", "anotaciones": []}]
    nuevos = [{"id": "1", "texto": "a2", "estado": "vigente", "anotaciones": ["Párrafo reformado DOF 01-01-2027"]},
              {"id": "2", "texto": "Se deroga.", "estado": "derogado", "anotaciones": []},
              {"id": "3", "texto": "c", "estado": "vigente", "anotaciones": []},
              {"id": "3 Bis", "texto": "nuevo", "estado": "vigente", "anotaciones": []}]
    d = v.comparar(previos, nuevos)
    esperar(d == {"reformados": ["1"], "derogados": ["2"], "adicionados": ["3 Bis"], "eliminados": []}, f"comparar: {d}")

    if fallas:
        print("FALLAS:")
        for f in fallas:
            print(" -", f)
        sys.exit(1)
    print("Prueba del vigilante correcta.")


if __name__ == "__main__":
    main()
