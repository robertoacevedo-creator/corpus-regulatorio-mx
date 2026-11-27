"""Convertidor de los .doc de la compilación de la Cámara de Diputados.

Sirve para leyes federales (LeyesBiblio/doc/<CLAVE>.doc) y sus reglamentos
(LeyesBiblio/regley/Reg_<CLAVE>_<fecha>.doc). El texto de Diputados sigue
siempre el mismo orden:

    encabezado (nombre, publicación original, "Última reforma publicada DOF")
    decreto de promulgación
    LIBRO / TÍTULO / CAPÍTULO / SECCIÓN y artículos
    TRANSITORIOS de la publicación original
    ARTÍCULOS TRANSITORIOS DE DECRETOS DE REFORMA (un bloque por decreto)

Las notas de reforma que Diputados pone debajo de cada párrafo
("Fracción reformada DOF 08-05-2023") salen del texto y se guardan en
"anotaciones" del artículo.

Cobertura: cada línea del original, después del primer artículo, tiene que
terminar en un registro, en sus anotaciones, en un encabezado o en una firma.
Si alguna no tiene lugar, el convertidor termina con ERROR y la lista de esas
líneas, para que nada se pierda en silencio.

Uso:
    python convertidores/diputados_doc.py ORIGINAL.doc --clave LGPGIR --fuente URL
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun  # noqa: E402

SUFIJOS = (r"(?i:Bis|Ter|Qu[áa]ter|Quintus|Sextus|Septimus|Quinquies|Sexies|Septies|Octies|Nonies|Decies)")
# Número, con letra o número pegado por guion ("4-A", "58-1") o letra suelta solo si
# enseguida viene el separador o un sufijo ("69 C Bis", "4 A.-"). Una letra o un
# romano después del separador ("Artículo 11.- I. Las...") ya es texto.
LETRA = (r"(?:-[A-ZÑ](?![A-Za-zÁÉÍÓÚáéíóúÑñ])(?:-\d+(?!\d))?|-\d+(?!\d)|\s+[A-Z](?=\s*\.\s*[-–]|\s*[-–]|\s+" + SUFIJOS + r"))")
ORD_ANTES_DE_LETRA = r"(?:(?:o|º|°)\.?(?=-[A-ZÑ]|-\d))"  # "1o.-A": el punto del ordinal va antes de la letra
NUM = r"\d+" + ORD_ANTES_DE_LETRA + r"?(?:" + LETRA + r")?\s*(?:o|º|°)?\.?"
ID_ART = NUM + r"(?:(?:\s*|-)" + SUFIJOS + r"(?:\s*\d+|-\d+)?(?:\s+[A-Z](?=\s*\.\s*[-–]|\s*[-–]))?)*"
SEP = r"\s*(?:\.\s*-|\.\s*–|\.|-|–)\s*"

RE_ARTICULO = re.compile(r"^(?:ART[ÍI]CULO|Art[íi]culo)\.?\s+(" + ID_ART + r")" + SEP)
RE_RANGO = re.compile(r"^(?:ART[ÍI]CULOS|Art[íi]culos)\s+(" + ID_ART + r")\s+(?:a|al|y)\s+(" + ID_ART + r")" + SEP)

ORDINALES = (
    r"(?:(?:D[ÉE]CIMO|VIG[ÉE]SIMO|TRIG[ÉE]SIMO|CUADRAG[ÉE]SIMO)\s*"
    r"(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO)?"
    r"|PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO"
    r"|UND[ÉE]CIMO|DUOD[ÉE]CIMO|[ÚU]NICO)"
)
RE_TRANSITORIO = re.compile(r"^(?:ART[ÍI]CULO\s+)?(" + ORDINALES + r"(?:\s+BIS)?)" + SEP, re.I)

_UNIDAD = r"(?:PRIMER[OA]?|SEGUND[OA]|TERCER[OA]?|CUART[OA]|QUINT[OA]|SEXT[OA]|S[ÉE]PTIM[OA]|OCTAV[OA]|NOVEN[OA])"
ORDINAL_ENCABEZADO = (r"(?:[IVXLC]+|\d+|[ÚU]NIC[OA]|ONCE|DOCE|TRECE|CATORCE|QUINCE|DIECIS[ÉE]IS|DIECISIETE|DIECIOCHO|DIECINUEVE|VEINTE|" + _UNIDAD + r"|UND[ÉE]CIM[OA]|DUOD[ÉE]CIM[OA]|"
                      r"(?:D[ÉE]CIM[OA]|VIG[ÉE]SIM[OA]|TRIG[ÉE]SIM[OA]|CUADRAG[ÉE]SIM[OA])\w*(?:\s+" + _UNIDAD + r")?)")
RE_ENCABEZADO = re.compile(
    r"^(LIBRO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|Libro|T[íi]tulo|Cap[íi]tulo|Secci[óo]n)\s+("
    + ORDINAL_ENCABEZADO + r")(?:\s+(?:BIS|Bis))?(?=\s|$|\.)", re.I
)
NIVEL = {"libro": 0, "titulo": 1, "capitulo": 2, "seccion": 3}

RE_ANOTACION = re.compile(
    r"^(?:Fe de erratas\b|Aclaraci[óo]n\b.*\bDOF\b|(?:P[áa]rrafos?|Fracci[óo]n(?:es)?|Incisos?|Subincisos?|Apartados?|Art[íi]culos?|"
    r"Cap[íi]tulos?|T[íi]tulos?|Secci[óo]n(?:es)?|Libros?|Denominaci[óo]n|Numerales?|"
    r"Reforma|Fe de erratas|[ÚU]ltimo|Pen[úu]ltimo|Bases?|Puntos?|Definici[óo]n|Notas?|"
    r"Anexos?|Tablas?|Cuadros?|Listas?|Se\s|Aclaraci[óo]n|Primer|Segundo|Tercer|Cuarto|Quinto|"
    r"Porci[óo]n|Declaratoria)\b"
    r".*(?:reformad|adicionad|derogad|recorrid|abrogad|reubicad|erratas|Aclaraci|Derog[óo]|Reform[óo]|"
    r"Adicion[óo]|inv[áa]lid|SCJN|Suprema Corte))",
    re.I,
)

RE_CIERRE = re.compile(
    r"^(?:M[ée]xico,\s*(?:D\.?\s*F\.?|Distrito Federal)|Ciudad de M[ée]xico,\s*a|Dado en (?i:la residencia|el palacio)|"
    r"En cumplimiento de lo dispuesto por la fracci[óo]n I del [Aa]rt[íi]culo 89|SAL[ÓO]N DE SESIONES|Sal[óo]n de Sesiones)",
)

RE_SECCION_DECRETOS = re.compile(r"^(?:ART[ÍI]CULOS\s+)?TRANSITORIOS\s+DE\s+DECRETOS\s+DE\s+REFORMA", re.I)
RE_TITULO_TRANSITORIOS = re.compile(r"^(?:ART[ÍI]CULOS\s+)?TRANSITORIOS?\.?$", re.I)
RE_INICIO_DECRETO = re.compile(r"^(?:DECRETO|ACUERDO|ACLARACI[ÓO]N|FE DE ERRATAS|RESOLUCI[ÓO]N|SENTENCIA|DECLARATORIA)\b")
RE_DEROGADO = re.compile(r"^\(?\s*(?:se derogan?|derogad[oa]s?)\s*\)?\s*\.?$", re.I)


RE_NOTA_LARGA = re.compile(r"^(?:Nota:|Reforma DOF \d{2}-\d{2}-\d{4}:)")
RE_FECHA_SUELTA = re.compile(r"^DOF\s+\d{2}-\d{2}-\d{4}(?:\s*[,.]\s*|\s*$)")
RE_MARCA_ANIO = re.compile(r"^A partir de \d{4}$")  # separador de años que Diputados pone antes de los decretos


def es_anotacion(linea):
    if not comun.RE_FECHA_DOF.search(linea):
        return False
    if RE_NOTA_LARGA.match(linea):
        return len(linea) < 2500
    return len(linea) < 400 and bool(RE_ANOTACION.match(linea))


def normalizar_id(crudo):
    """'1o.' -> '1'; '62 BIS' -> '62 Bis'; '4-A' -> '4-A'; '58-1' -> '58-1'; '69 C Bis' -> '69 C Bis'."""
    m = re.match(r"(\d+)" + ORD_ANTES_DE_LETRA + r"?((?:-[A-ZÑ](?![A-Za-zÁÉÍÓÚáéíóúÑñ])(?:-\d+)?|-\d+)?)"
                 r"(?:\s+([A-Z])(?![A-Za-zÁÉÍÓÚáéíóúÑñ]))?\s*(?:o|º|°)?\.?\s*(.*)$", crudo.strip())
    partes = [m.group(1) + m.group(2)]
    if m.group(3):
        partes.append(m.group(3))
    resto = m.group(4)
    for pieza in re.findall(SUFIJOS + r"|\d+|(?<![A-Za-zÁÉÍÓÚáéíóúÑñ])[A-Z](?![A-Za-zÁÉÍÓÚáéíóúÑñ])", resto):
        partes.append(pieza if (pieza.isdigit() or len(pieza) == 1) else pieza.capitalize())
    return " ".join(partes)


def normalizar_ordinal(texto):
    palabras = re.sub(r"\s+", " ", texto.strip()).lower().split(" ")
    return " ".join(p.capitalize() for p in palabras)


def tipo_encabezado(palabra):
    p = palabra.lower().replace("í", "i").replace("ó", "o")
    return {"libro": "libro", "titulo": "titulo", "capitulo": "capitulo", "seccion": "seccion"}[p]


def numero_de(id_):  # "58-1" -> 58
    m = re.match(r"\d+", id_)
    return int(m.group()) if m else None


def convertir(ruta, clave, fuente, tipo_norma):
    crudas = comun.doc_a_texto(ruta)
    lineas = [(i + 1, comun.limpiar_linea(t)) for i, t in enumerate(crudas)]
    no_vacias = [(n, t) for n, t in lineas if t]
    avisos, errores = [], []

    nombre = no_vacias[0][1]
    ultima_reforma = None
    publicacion = None
    for _, t in no_vacias[:12]:
        if re.match(r"^[ÚU]ltimas? reformas? publicadas?", t, re.I):
            ultima_reforma = comun.fecha_dof_a_iso(t)
        if publicacion is None and "Diario Oficial de la Federación" in t and "publicad" in t.lower():
            publicacion = comun.fecha_larga_a_iso(t)
    if not ultima_reforma:
        ultima_reforma = publicacion  # sin reformas: vale la publicación original

    inicio_decretos = next((k for k, (_, t) in enumerate(no_vacias) if RE_SECCION_DECRETOS.match(t)), len(no_vacias))
    cuerpo, seccion_decretos = no_vacias[:inicio_decretos], no_vacias[inicio_decretos + 1:]

    articulos = []
    actual = None
    jerarquia = {}
    en_transitorios = False
    cerrado = False
    esperando_nombre = None
    visto_articulo = False
    anotaciones_sueltas = 0
    sin_lugar = []  # líneas que no quedaron en ninguna parte

    def cerrar():
        nonlocal actual
        if actual:
            articulos.append(actual)
        actual = None

    def nuevo(id_, tipo, ubicacion, t, n):
        return {"ley": clave, "id": id_, "tipo": tipo, "estado": "vigente", "ubicacion": ubicacion,
                "_lineas": [t], "anotaciones": [], "linea_fuente": n}

    previa_fue_nota = False
    for n, t in cuerpo:
        if previa_fue_nota and RE_FECHA_SUELTA.match(t):
            # Continuación de una nota que Word partió en dos renglones: se pega a la nota.
            if actual and not cerrado and actual["anotaciones"]:
                actual["anotaciones"][-1] += " " + t
            continue
        previa_fue_nota = es_anotacion(t)
        if previa_fue_nota:
            if actual and not cerrado:
                actual["anotaciones"].append(t)
            else:
                anotaciones_sueltas += 1
            esperando_nombre = None
            continue

        if not en_transitorios and visto_articulo and RE_TITULO_TRANSITORIOS.match(t):
            cerrar()
            en_transitorios = True
            cerrado = False
            continue

        if not en_transitorios:
            m_enc = RE_ENCABEZADO.match(t)
            # Un encabezado es corto, no termina en puntuación de oración y no es un artículo.
            if (m_enc and len(t) < 200 and not RE_ARTICULO.match(t)
                    and (not t.endswith((";", ",", ":", ".")) or len(t) < 40)):
                cerrar()
                nivel = NIVEL[tipo_encabezado(m_enc.group(1))]
                jerarquia = {k: v for k, v in jerarquia.items() if k < nivel}
                jerarquia[nivel] = t
                # "CAPÍTULO I" solo: el nombre viene en la línea siguiente.
                esperando_nombre = nivel if len(t) <= m_enc.end() + 4 else None
                continue
            if esperando_nombre is not None:
                if not RE_ARTICULO.match(t) and not RE_RANGO.match(t) and len(t) < 600:
                    jerarquia[esperando_nombre] += " " + t
                    esperando_nombre = None
                    continue
                esperando_nombre = None

            ubicacion = " > ".join(jerarquia[k] for k in sorted(jerarquia))
            m_rango = RE_RANGO.match(t)
            if m_rango:
                cerrar()
                visto_articulo = True
                actual = nuevo(f"{normalizar_id(m_rango.group(1))} a {normalizar_id(m_rango.group(2))}",
                               "articulo", ubicacion, t, n)
                continue
            m_art = RE_ARTICULO.match(t)
            if m_art:
                cerrar()
                visto_articulo = True
                actual = nuevo(normalizar_id(m_art.group(1)), "articulo", ubicacion, t, n)
                continue
            if actual:
                actual["_lineas"].append(t)
            elif visto_articulo and jerarquia and RE_DEROGADO.match(t):
                # "(Se deroga)" bajo un capítulo o sección derogado: queda en el encabezado.
                nivel_bajo = max(jerarquia)
                jerarquia[nivel_bajo] += " " + t
            elif visto_articulo and jerarquia and re.fullmatch(r"[IVXLC]+", t):
                # Apartado numerado con romano ("I" / "Disposiciones generales") dentro de una sección.
                jerarquia[4] = t
                esperando_nombre = 4
            elif visto_articulo:
                sin_lugar.append((n, t))
            continue

        # Transitorios de la publicación original
        if RE_CIERRE.match(t):
            cerrar()
            cerrado = True
            continue
        m_tr = RE_TRANSITORIO.match(t)
        m_tr_num = RE_ARTICULO.match(t)
        if m_tr or m_tr_num:
            cerrar()
            cerrado = False
            id_ = normalizar_ordinal(m_tr.group(1)) if m_tr else normalizar_id(m_tr_num.group(1))
            actual = nuevo("Transitorio " + id_, "transitorio", "Transitorios", t, n)
            continue
        if actual and not cerrado:
            actual["_lineas"].append(t)
        elif not cerrado:
            sin_lugar.append((n, t))
        # lo que sigue a un cierre (firmas, promulgación) se descarta a propósito
    cerrar()

    # Texto, estado y fechas
    for a in articulos:
        a["texto"] = "\n".join(a.pop("_lineas"))
        if a["tipo"] == "articulo":
            cuerpo_txt = (RE_RANGO.sub("", a["texto"], count=1) if " a " in a["id"]
                          else RE_ARTICULO.sub("", a["texto"], count=1))
        else:
            cuerpo_txt = RE_ARTICULO.sub("", RE_TRANSITORIO.sub("", a["texto"], count=1), count=1)
        primera, *resto_l = cuerpo_txt.strip().split("\n")
        if RE_DEROGADO.match(primera.strip()) and all(
                re.search(r"(?i)derogad|\bDOF\b|^[\d,\s.\-]+", r.strip()) for r in resto_l):
            a["estado"] = "derogado"
        fechas = [f for nota in a["anotaciones"] for f in comun.fechas_dof(nota)]
        a["ultima_reforma_articulo"] = max(fechas) if fechas else None
        a["ultima_reforma_ley"] = ultima_reforma

    campos = ["ley", "id", "tipo", "estado", "ubicacion", "texto", "anotaciones",
              "ultima_reforma_articulo", "ultima_reforma_ley", "linea_fuente"]
    articulos = [{k: a[k] for k in campos} for a in articulos]

    # Decretos de reforma: un bloque empieza con su título (DECRETO, ACUERDO, ACLARACIÓN...)
    # o con cualquier línea seguida de "Publicado en el Diario Oficial...".
    decretos = []
    k = 0

    def es_inicio(j):
        t = seccion_decretos[j][1]
        sig = seccion_decretos[j + 1][1] if j + 1 < len(seccion_decretos) else ""
        return sig.lower().startswith("publicad") or bool(RE_INICIO_DECRETO.match(t))

    while k < len(seccion_decretos):
        if not es_inicio(k):
            if not RE_MARCA_ANIO.match(seccion_decretos[k][1]):
                sin_lugar.append(seccion_decretos[k])
            k += 1
            continue
        n, titulo = seccion_decretos[k]
        j = k + 1
        fecha = None
        if j < len(seccion_decretos) and seccion_decretos[j][1].lower().startswith("publicad"):
            fecha = comun.fecha_larga_a_iso(seccion_decretos[j][1])
            j += 1
        texto = []
        while j < len(seccion_decretos) and not es_inicio(j):
            texto.append(seccion_decretos[j][1])
            j += 1
        decretos.append({"ley": clave, "titulo": titulo, "fecha_dof": fecha, "linea_fuente": n,
                         "texto": "\n".join(texto)})
        k = j

    # Revisiones propias del convertidor
    ids = [a["id"] for a in articulos]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        errores.append(f"ids repetidos: {repetidos}")
    nums = [numero_de(a["id"]) for a in articulos if a["tipo"] == "articulo"]
    saltos = [(x, y) for x, y in zip(nums, nums[1:]) if y < x or y > x + 1]
    rangos = [a["id"] for a in articulos if " a " in a["id"]]
    if saltos and not rangos:
        avisos.append(f"saltos en la numeración: {saltos[:20]}")
    con_firma = [a["id"] for a in articulos if a["tipo"] == "transitorio" and re.search(r"R[úu]brica", a["texto"])]
    if con_firma:
        errores.append(f"transitorios con firmas pegadas (revisar RE_CIERRE): {con_firma}")
    vacios = [a["id"] for a in articulos if len(a["texto"]) < 15]
    if vacios:
        avisos.append(f"artículos casi vacíos: {vacios}")
    sin_fecha = [d["titulo"][:60] for d in decretos if not d["fecha_dof"]]
    if sin_fecha:
        avisos.append(f"decretos sin fecha de publicación: {sin_fecha}")
    if anotaciones_sueltas:
        avisos.append(f"{anotaciones_sueltas} notas de reforma de encabezados (capítulo, título) no se guardan")
    if sin_lugar:
        errores.append(f"{len(sin_lugar)} líneas del original sin lugar: " +
                       "; ".join(f"línea {n}: {t[:110]}" for n, t in sin_lugar[:25]))

    original = Path(ruta)
    ficha = {
        "clave": clave,
        "nombre": nombre,
        "tipo": tipo_norma,
        "ambito": "federal",
        "fuente": {"emisor": "Cámara de Diputados, compilación LeyesBiblio", "url": fuente, "formato": "doc"},
        "publicacion_original_dof": publicacion,
        "ultima_reforma_dof": ultima_reforma,
        "fecha_carga": comun.hoy(),
        "original": {"archivo": original.name, "sha256": comun.sha256_archivo(original), "bytes": original.stat().st_size},
        "convertidor": "diputados_doc",
    }
    return articulos, decretos, ficha, avisos, errores


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("--clave", required=True)
    ap.add_argument("--fuente", required=True, help="liga oficial de descarga")
    ap.add_argument("--tipo", default="ley", choices=["ley", "reglamento", "codigo", "constitucion"])
    args = ap.parse_args()
    articulos, decretos, ficha, avisos, errores = convertir(args.original, args.clave, args.fuente, args.tipo)
    for a in avisos:
        print("AVISO:", a, file=sys.stderr)
    for e in errores:
        print("ERROR:", e, file=sys.stderr)
    if errores:
        sys.exit(1)
    ficha = comun.escribir_norma(args.clave, articulos, decretos, ficha)
    print(json.dumps(ficha, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
