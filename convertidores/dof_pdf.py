"""Convertidor de NOM, acuerdos y demás publicaciones del DOF en PDF.

Pensado para el PDF que sale al imprimir la nota del DOF (dof.gob.mx o
sidof.segob.gob.mx) desde el navegador. En ese PDF cada párrafo empieza con
sangría y sus renglones siguientes no, así que los párrafos se rearman por
la posición de la primera letra de cada renglón.

Partes que reconoce:
    preámbulo (fundamento y considerandos)  -> registro "Preámbulo"
    título en mayúsculas y prefacio         -> registro "Prefacio" (el índice no se guarda)
    numerales 1, 1.1, 1.1.1...              -> un registro por numeral
    TRANSITORIOS                            -> un registro por transitorio
    "Provéase..." y firmas                  -> registro "Cierre"
    TABLA / FIGURA sin columna "Clave"      -> un registro por tabla; columnas con " | "
    LISTADO / ANEXO con columna "Clave"     -> un registro por renglón, id "<Listado N> <clave>"

Las tablas se leen por la posición de cada carácter: las columnas son los
huecos verticales que ningún carácter ocupa, y los subíndices de las fórmulas
(As2O3) se acomodan en su renglón.

Uso:
    python convertidores/dof_pdf.py ORIGINAL.pdf --clave NOM-052-SEMARNAT-2005 \
        --fuente URL --publicacion 2006-06-23
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun  # noqa: E402
from diputados_doc import RE_TRANSITORIO, normalizar_ordinal  # noqa: E402

RE_NUMERAL = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\.?\s+(?=\S)")
RE_ANEXO = re.compile(r"^(TABLA|LISTADO|ANEXO|AP[ÉE]NDICE|FIGURA)\s+([0-9IVXLA-Z]+)\.?(?:\s*\((?:Normativo|Informativo)\))?$", re.I)
RE_CIERRE = re.compile(r"^(?:Prov[ée]ase|M[ée]xico,\s*(?:D\.?\s*F|Distrito Federal)|Ciudad de M[ée]xico,\s*a|Dado en)")
SANGRIA_MINIMA = 8  # puntos de diferencia entre renglón con sangría y sin ella


def resolver_cid(texto):
    """El PDF impreso del DOF guarda algunos signos como '(cid:0)'. Se deciden por contexto:

    - entre dígitos es guion: números CAS 5344-82-1;
    - entre dígito y guion es apóstrofo (prima): 2,2'-oxibis;
    - entre letra y "s" es apóstrofo: BPC's;
    - en lo demás son comillas: "Fuente Específica".
    """
    texto = re.sub(r"(?<=\d)\(cid:0\)(?=\d)", "-", texto)
    texto = re.sub(r"(?<=\d)\(cid:0\)(?=-)", "'", texto)
    texto = re.sub(r"(?<=[A-Za-z])\(cid:0\)(?=s\b)", "'", texto)
    return texto.replace("(cid:0)", '"')


def renglones_pdf(ruta):
    """Devuelve [(pagina, x0, texto)] de todo el PDF."""
    salida = []
    with pdfplumber.open(ruta) as pdf:
        for num, pagina in enumerate(pdf.pages, 1):
            for r in pagina.extract_text_lines():
                texto = comun.limpiar_linea(resolver_cid(r["text"]))
                if texto:
                    salida.append((num, r["x0"], texto))
    return salida


def margen_izquierdo(renglones):
    """El margen de los renglones de continuación es el x0 más frecuente y menor."""
    conteo = {}
    for _, x0, _ in renglones:
        conteo[round(x0)] = conteo.get(round(x0), 0) + 1
    frecuentes = sorted(conteo, key=lambda x: -conteo[x])[:3]
    return min(frecuentes)


def parrafos(renglones):
    margen = margen_izquierdo(renglones)
    salida = []
    for pagina, x0, texto in renglones:
        if salida and x0 < margen + SANGRIA_MINIMA / 2:
            previo = salida[-1]
            union = "" if previo["texto"].endswith("-") else " "
            previo["texto"] += union + texto
        else:
            salida.append({"pagina": pagina, "texto": texto})
    return salida


def es_siguiente(previo, nuevo):
    """¿'nuevo' puede seguir a 'previo' en el árbol de numerales?"""
    if previo is None:
        return nuevo == [1]
    if nuevo == previo + [1]:
        return True
    for corte in range(len(previo), 0, -1):
        base = previo[:corte]
        if nuevo == base[:-1] + [base[-1] + 1]:
            return True
    return False


def lineas_visuales(pagina):
    """Agrupa los caracteres de una página en renglones visuales.

    Los subíndices y superíndices (As2O3, CAS1) caen unos puntos arriba o abajo
    del renglón; se juntan con él y se ordenan por su posición horizontal.
    """
    chars = sorted((c for c in pagina.chars if c["text"].strip()), key=lambda c: (c["top"], c["x0"]))
    grupos = []
    for c in chars:
        if grupos and c["top"] - grupos[-1][0]["top"] <= 4.5:
            grupos[-1].append(c)
        else:
            grupos.append([c])
    salida = []
    for g in grupos:
        g.sort(key=lambda c: c["x0"])
        negritas = sum("Bold" in c["fontname"] for c in g) / len(g)
        salida.append({"top": g[0]["top"], "chars": g, "negrita": negritas > 0.5,
                       "pagina": pagina.page_number, "texto": texto_de(g)})
    return salida


def texto_de(chars):
    partes, previo = [], None
    for c in chars:
        if previo is not None and c["x0"] - previo["x1"] > 1.5:
            partes.append(" ")
        partes.append(c["text"])
        previo = c
    return comun.limpiar_linea(resolver_cid("".join(partes)))


def segmentos(linea, hueco=8):
    """Parte un renglón visual donde hay un espacio horizontal grande (cambio de columna)."""
    segs, actual = [], []
    for c in linea["chars"]:
        if actual and c["x0"] - actual[-1]["x1"] > hueco:
            segs.append(actual)
            actual = []
        actual.append(c)
    if actual:
        segs.append(actual)
    return [(s_[0]["x0"], s_) for s_ in segs]


def referencias(encabezado, datos):
    """Borde izquierdo de cada columna, aprendido de los renglones que traen todas las columnas."""
    n = len(segmentos(encabezado))
    completos = [segmentos(l) for l in datos]
    completos = [s_ for s_ in completos if len(s_) == n]
    if not completos:
        return [x for x, _ in segmentos(encabezado)]
    return [min(s_[k][0] for s_ in completos) for k in range(n)]


def celdas(lineas, refs):
    """Texto de cada columna para un grupo de renglones visuales."""
    porcol = [[] for _ in refs]
    for l in sorted(lineas, key=lambda l: (l["pagina"], l["top"])):
        for x0, chars in segmentos(l):
            k = max([j for j, r in enumerate(refs) if r <= x0 + 6] or [0])
            porcol[k].append(texto_de(chars))
    salida = []
    for partes in porcol:
        texto = ""
        for p_ in partes:
            texto += ("" if not texto or texto.endswith("-") else " ") + p_
        salida.append(texto)
    return salida


def columna_de(x0, refs):
    return max([j for j, r in enumerate(refs) if r <= x0 + 6] or [0])


def tablas(ruta, pagina_inicio):
    """Tablas, listados y anexos que van después de los transitorios."""
    with pdfplumber.open(ruta) as pdf:
        paginas = pdf.pages[pagina_inicio - 1:]
        lineas = [l for p in paginas for l in lineas_visuales(p)]
        # Celdas dibujadas de cada página (bordes de la tabla): (x0, top, x1, bottom)
        celdas_pag = {p.page_number: [c for t in p.find_tables() for c in t.cells] for p in paginas}
    bloques, actual = [], None
    for l in lineas:
        m = RE_ANEXO.match(l["texto"])
        if m and l["negrita"]:
            actual = {"id": f"{m.group(1).capitalize()} {m.group(2)}", "lineas": [], "pagina": l["pagina"]}
            bloques.append(actual)
        elif actual is not None:
            actual["lineas"].append(l)
    return [armar_tabla(b, celdas_pag) for b in bloques]


def renglones_por_bordes(lineas_datos, celdas_pag, x_clave):
    """Renglones según las celdas dibujadas de la columna de la clave.

    Cada celda de esa columna (con su altura completa, aunque la clave vaya
    centrada) delimita un renglón. Las líneas de texto se asignan a la celda
    que contiene su centro. Devuelve [(pagina, top, bottom, [lineas])] en orden.
    """
    intervalos = {}
    for pag, celdas in celdas_pag.items():
        propias = sorted({(round(c[1], 1), round(c[3], 1)) for c in celdas
                          if c[0] - 1 <= x_clave <= c[2] + 1 and (c[2] - c[0]) < 150})
        intervalos[pag] = propias
    salida = []
    for l in lineas_datos:
        centro = l["top"] + 4
        caja = next(((t, b_) for t, b_ in intervalos.get(l["pagina"], []) if t - 0.5 <= centro <= b_ + 0.5), None)
        clave = (l["pagina"],) + (caja if caja else (None, None))
        if salida and salida[-1][0] == clave and caja is not None:
            salida[-1][1].append(l)
        else:
            salida.append((clave, [l]))
    return salida


def armar_tabla(b, celdas_pag):
    lineas = b["lineas"]
    # Título: renglones en negrita hasta el encabezado de columnas (negrita con varios segmentos)
    k_enc = next((k for k, l in enumerate(lineas) if l["negrita"] and len(segmentos(l)) >= 2), None)
    if k_enc is None:  # figura o texto sin columnas
        return {"id": b["id"], "titulo": "\n".join(l["texto"] for l in lineas if l["negrita"]),
                "encabezado": [], "renglones": [], "texto_libre": [l["texto"] for l in lineas if not l["negrita"]],
                "pagina": b["pagina"], "clave_col": None, "sueltos": 0}
    titulo = " ".join(l["texto"] for l in lineas[:k_enc])
    datos = [l for l in lineas[k_enc + 1:] if not l["negrita"]]
    refs = referencias(lineas[k_enc], datos)
    segs_enc = segmentos(lineas[k_enc])
    encabezado = [texto_de(ch) for _, ch in segs_enc]
    clave_col = next((k for k, t in enumerate(encabezado) if t.strip().lower() == "clave"), None)
    ancla = clave_col if clave_col is not None else 0

    # Notas al pie: desde la primera línea "NOTAS" o "1.- ..." hasta el final
    cuerpo, notas = [], []
    for l in lineas[k_enc + 1:]:
        if notas or re.match(r"^(?:NOTAS?\b|N\.A\.:|\d+\.-\s)", l["texto"], re.I):
            if not re.fullmatch(r"_+", l["texto"]):
                notas.append(l["texto"])
        elif not re.fullmatch(r"_+", l["texto"]):
            cuerpo.append(l)

    renglones, grupo, encabezados_pend, sueltos = [], "", [], 0
    if clave_col is not None:
        ch = segs_enc[clave_col][1]
        x_clave = (ch[0]["x0"] + ch[-1]["x1"]) / 2
        # Agrupar por celda dibujada, respetando los encabezados de grupo (negrita)
        tramo = []

        def vaciar():
            """Una celda sin clave es un renglón partido por el cambio de página.

            Si es la última celda de su página y la primera de la página siguiente
            trae clave, la clave quedó del otro lado: se une al renglón siguiente.
            En cualquier otro caso (normalmente la primera celda de la página),
            se une al renglón anterior.
            """
            nonlocal tramo, sueltos
            piezas = [(ls, celdas(ls, refs)[ancla].strip()) for _, ls in renglones_por_bordes(tramo, celdas_pag, x_clave)]
            adelante = []
            for k, (ls, clave_txt) in enumerate(piezas):
                if clave_txt:
                    renglones.append({"grupo": grupo, "lineas": adelante + ls, "pagina": (adelante + ls)[0]["pagina"]})
                    adelante = []
                    continue
                sueltos += 1
                sig = piezas[k + 1] if k + 1 < len(piezas) else None
                ultima_de_pagina = sig is not None and sig[0][0]["pagina"] != ls[0]["pagina"]
                if (ultima_de_pagina and sig[1]) or not renglones:
                    adelante += ls
                else:
                    renglones[-1]["lineas"] += ls
            if adelante:
                renglones[-1]["lineas"] += adelante
            tramo = []

        for l in cuerpo:
            if l["negrita"]:
                vaciar()
                encabezados_pend.append(l["texto"])
                continue
            if encabezados_pend:
                vaciar()
                grupo = " > ".join(encabezados_pend)
                encabezados_pend = []
            tramo.append(l)
        vaciar()
    else:
        grupos_, previo = [], None
        for l in cuerpo:
            if l["negrita"]:
                encabezados_pend.append(l["texto"])
                continue
            if encabezados_pend:
                grupo = " > ".join(encabezados_pend)
                encabezados_pend = []
            nuevo = (previo is None or l["pagina"] != previo["pagina"] or l["top"] - previo["top"] > 13
                     or any(columna_de(x0, refs) == ancla for x0, _ in segmentos(l)))
            if nuevo:
                renglones.append({"grupo": grupo, "lineas": [l], "pagina": l["pagina"]})
            else:
                renglones[-1]["lineas"].append(l)
            previo = l
    notas = encabezados_pend + notas  # negritas sin renglones después (p. ej. "N.A.: No Aplica...")
    for r in renglones:
        r["celdas"] = celdas(r["lineas"], refs)
    return {"id": b["id"], "titulo": titulo, "encabezado": encabezado, "renglones": renglones,
            "texto_libre": notas, "pagina": b["pagina"], "clave_col": clave_col, "sueltos": sueltos}


def cotejar_renglones(ruta, pagina_inicio, registros):
    """Cotejo independiente de los renglones de listado contra las celdas de pdfplumber.

    Arma los renglones de otra forma (extract_tables, que lee celda por celda)
    y compara las letras de cada renglón, sin importar espacios ni el orden en
    que salen las columnas. Devuelve la lista de ids que no cuadran.
    """
    renglones = {r["id"]: r for r in registros if r["tipo"] == "renglon"}
    claves = {}
    for id_ in renglones:
        tabla, clave_r = re.match(r"^(\S+ \S+) (.+?)(?: \(\d+\))?$", id_).groups()
        claves.setdefault(clave_r, []).append(id_)
    grupos = {g for r in renglones.values() for g in r["ubicacion"].split(" > ")[1:]}

    def letras(t):
        return sorted(re.sub(r"[\s|\"'\-]", "", t))

    # Filas de todas las tablas, con su página: (pagina, celdas llenas, clave o None)
    filas = []
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages[pagina_inicio - 1:]:
            for tabla in pagina.extract_tables():
                for fila in tabla:
                    celdas_f = [comun.limpiar_linea(resolver_cid(c or "").replace("\n", " ")) for c in fila]
                    llenas = [c for c in celdas_f if c]
                    if not llenas:
                        continue
                    if "Clave" in celdas_f:
                        filas.append((pagina.page_number, None, "ENCABEZADO"))
                        continue
                    if len(llenas) == 1 and (llenas[0] in grupos or llenas[0].startswith("GIRO ")):
                        continue
                    en_fila = [c for c in llenas if c in claves]
                    filas.append((pagina.page_number, llenas, en_fila[0] if en_fila else None))

    vistos, actual, armado, adelante = {}, None, {}, []
    for k, (pag, llenas, clave_f) in enumerate(filas):
        if clave_f == "ENCABEZADO":
            actual, adelante = None, []
            continue
        if clave_f:
            n = vistos.get(clave_f, 0)
            vistos[clave_f] = n + 1
            candidatos = claves[clave_f]
            actual = candidatos[min(n, len(candidatos) - 1)]
            armado.setdefault(actual, []).extend(adelante + llenas)
            adelante = []
            continue
        sig = filas[k + 1] if k + 1 < len(filas) else None
        if sig and sig[0] != pag and sig[2] and sig[2] != "ENCABEZADO":
            adelante += llenas  # la clave de este renglón quedó en la página siguiente
        elif actual:
            armado[actual].extend(llenas)
    malos = [i for i, r in renglones.items() if letras(" ".join(armado.get(i, []))) != letras(" ".join(r["partes"]))]
    return malos


def convertir(ruta, clave, fuente, publicacion, tipo_norma, emisor):
    todos = parrafos(renglones_pdf(ruta))
    avisos, errores = [], []

    # La prosa termina donde empieza la primera tabla, listado o anexo
    k_anexo = next((k for k, p in enumerate(todos) if RE_ANEXO.match(p["texto"])), len(todos))
    pars = todos[:k_anexo]

    # Nombre: los párrafos antes de "Al margen un sello..."
    k_margen = next((k for k, p in enumerate(pars[:6]) if p["texto"].lower().startswith("al margen")), None)
    nombre = pars[0]["texto"]
    if k_margen is None:
        k_margen = 1
    elif k_margen > 1:
        nombre = " ".join(p["texto"] for p in pars[:k_margen])
    nombre = re.split(r"\s+Al margen un sello", nombre)[0]

    # Fin del preámbulo: el título de la norma en mayúsculas ("NORMA OFICIAL MEXICANA NOM-...")
    k_titulo = next((k for k, p in enumerate(pars) if k > 0 and re.match(r"^(NORMA OFICIAL MEXICANA|ACUERDO|LINEAMIENTOS|REGLAS)\b", p["texto"]) and p["texto"].isupper()), None)
    if k_titulo is None:
        k_titulo = next((k for k, p in enumerate(pars) if p["texto"].startswith("Por lo expuesto")), 0) + 1
        avisos.append("no se encontró el título en mayúsculas; el preámbulo termina en 'Por lo expuesto'")
    partes_pre = [p["texto"] for p in pars[:k_titulo]]
    partes_pre = [x for t in partes_pre for x in re.split(r"\s+(?=Al margen un sello)", t)]
    registros = [{"id": "Preámbulo", "tipo": "preambulo", "ubicacion": "Preámbulo",
                  "partes": partes_pre, "pagina": pars[0]["pagina"]}]

    # El cuerpo empieza en el "1." que va después del índice (si lo hay)
    k_indice = next((k for k, p in enumerate(pars) if k > k_titulo and p["texto"].upper() in ("INDICE", "ÍNDICE", "CONTENIDO")), None)
    if k_indice is not None:
        primero = next(k for k in range(k_indice + 1, len(pars)) if RE_NUMERAL.match(pars[k]["texto"]))
        titulo_1 = pars[primero]["texto"]
        inicio = next((k for k in range(primero + 1, len(pars)) if pars[k]["texto"] == titulo_1 or pars[k]["texto"].startswith(titulo_1 + " ")), None)
        if inicio is None:
            raise SystemExit(f"ERROR: no encontré el inicio del cuerpo ({titulo_1!r} después del índice)")
        fin_prefacio = k_indice
    else:
        inicio = next(k for k in range(k_titulo + 1, len(pars)) if RE_NUMERAL.match(pars[k]["texto"]) and RE_NUMERAL.match(pars[k]["texto"]).group(1) == "1")
        fin_prefacio = inicio
    # Título y prefacio (participantes). El índice no se guarda: solo repite los encabezados.
    registros.append({"id": "Prefacio", "tipo": "preambulo", "ubicacion": "Prefacio",
                      "partes": [p["texto"] for p in pars[k_titulo:fin_prefacio]], "pagina": pars[k_titulo]["pagina"]})

    previo = None
    capitulos = {}
    en_transitorios = False
    cierre = None
    for p in pars[inicio:]:
        t = p["texto"]
        if not en_transitorios and t in ("TRANSITORIOS", "TRANSITORIO", "ARTÍCULOS TRANSITORIOS"):
            en_transitorios = True
            continue
        if not en_transitorios:
            m = RE_NUMERAL.match(t)
            if m:
                nuevo = [int(x) for x in m.group(1).split(".")]
                if es_siguiente(previo, nuevo):
                    previo = nuevo
                    if len(nuevo) == 1:
                        capitulos[nuevo[0]] = t if len(t) < 160 else m.group(1)
                    registros.append({"id": m.group(1), "tipo": "numeral",
                                      "ubicacion": capitulos.get(nuevo[0], m.group(1)),
                                      "partes": [t], "pagina": p["pagina"]})
                    continue
            registros[-1]["partes"].append(t)
            continue
        if cierre is None and RE_CIERRE.match(t):
            cierre = {"id": "Cierre", "tipo": "cierre", "ubicacion": "Cierre", "partes": [], "pagina": p["pagina"]}
            registros.append(cierre)
        if cierre is not None:
            cierre["partes"].append(t)
            continue
        m = RE_TRANSITORIO.match(t)
        if m:
            registros.append({"id": "Transitorio " + normalizar_ordinal(m.group(1)), "tipo": "transitorio",
                              "ubicacion": "Transitorios", "partes": [t], "pagina": p["pagina"]})
        elif registros[-1]["tipo"] == "transitorio":
            registros[-1]["partes"].append(t)
        else:
            errores.append(f"párrafo sin lugar en transitorios: {t[:80]}")
    if not en_transitorios:
        avisos.append("no se encontraron TRANSITORIOS")

    # Tablas, listados y anexos
    if k_anexo < len(todos):
        sin_clave = 0
        vistos_r = {}
        for tb in tablas(ruta, todos[k_anexo]["pagina"]):
            sin_clave += tb.get("sueltos", 0)
            base = f"{tb['id']} {tb['titulo']}".strip()
            if tb["clave_col"] is None:
                lineas = [tb["titulo"]]
                if tb["encabezado"]:
                    lineas.append(" | ".join(c for c in tb["encabezado"] if c))
                grupo_previo = ""
                for r in tb["renglones"]:
                    if r["grupo"] and r["grupo"] != grupo_previo:
                        lineas.append(r["grupo"])
                        grupo_previo = r["grupo"]
                    lineas.append(" | ".join(c for c in r["celdas"] if c))
                lineas += [t for t in tb["texto_libre"] if not re.fullmatch(r"_+", t)]
                registros.append({"id": tb["id"], "tipo": "anexo", "ubicacion": "Tablas, listados y anexos",
                                  "partes": [x for x in lineas if x], "pagina": tb["pagina"]})
                continue
            # Listados: un registro por clave
            registros.append({"id": tb["id"], "tipo": "anexo", "ubicacion": "Tablas, listados y anexos",
                              "partes": [tb["titulo"], " | ".join(c for c in tb["encabezado"] if c)] + tb["texto_libre"],
                              "pagina": tb["pagina"]})
            for r in tb["renglones"]:
                clave_r = re.sub(r"\s+", " ", r["celdas"][tb["clave_col"]]).strip()
                texto = " | ".join(c for c in r["celdas"] if c)
                if not clave_r:
                    sin_clave += 1
                    registros[-1]["partes"].append(texto)  # continuación del renglón anterior
                    continue
                id_r = f"{tb['id']} {clave_r}"
                vistos_r[id_r] = vistos_r.get(id_r, 0) + 1
                if vistos_r[id_r] > 1:  # el original repite la clave (p. ej. sinónimos del mismo CAS)
                    avisos.append(f"el original repite la clave {id_r}; la repetición queda como '{id_r} ({vistos_r[id_r]})'")
                    id_r += f" ({vistos_r[id_r]})"
                registros.append({"id": id_r, "tipo": "renglon",
                                  "ubicacion": base + (f" > {r['grupo']}" if r["grupo"] else ""),
                                  "partes": [texto], "pagina": r["pagina"]})
        malos = cotejar_renglones(ruta, todos[k_anexo]["pagina"], registros)
        if malos:
            errores.append(f"{len(malos)} renglones de listado no cuadran con el cotejo por celdas: {malos[:10]}")
        if sin_clave:
            avisos.append(f"{sin_clave} celdas sin clave (renglones partidos por cambio de página) se unieron a su renglón")

    articulos = []
    for r in registros:
        articulos.append({
            "ley": clave, "id": r["id"], "tipo": r["tipo"], "estado": "vigente",
            "ubicacion": r["ubicacion"], "texto": "\n".join(r["partes"]), "anotaciones": [],
            "ultima_reforma_articulo": None, "ultima_reforma_ley": publicacion,
            "linea_fuente": r["pagina"],
        })

    ids = [a["id"] for a in articulos]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        errores.append(f"ids repetidos: {repetidos}")
    nones = [a["id"] for a in articulos if a["texto"].count('"') % 2]
    if nones:
        avisos.append(f"comillas sin cerrar (revisar el signo (cid:0)): {nones[:10]}")
    original = Path(ruta)
    ficha = {
        "clave": clave, "nombre": nombre, "tipo": tipo_norma, "ambito": "federal",
        "fuente": {"emisor": emisor, "url": fuente, "formato": "pdf"},
        "publicacion_original_dof": publicacion, "ultima_reforma_dof": publicacion,
        "fecha_carga": comun.hoy(),
        "original": {"archivo": original.name, "sha256": comun.sha256_archivo(original), "bytes": original.stat().st_size},
        "convertidor": "dof_pdf",
        "nota": "linea_fuente es el número de página del PDF",
    }
    return articulos, [], ficha, avisos, errores


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("--clave", required=True)
    ap.add_argument("--fuente", required=True)
    ap.add_argument("--publicacion", required=True, help="fecha DOF AAAA-MM-DD")
    ap.add_argument("--ultima-reforma", help="fecha DOF de la última modificación, si la hay")
    ap.add_argument("--tipo", default="nom", choices=["nom", "acuerdo", "reglamento", "lineamientos"])
    ap.add_argument("--emisor", default="Diario Oficial de la Federación")
    args = ap.parse_args()
    articulos, decretos, ficha, avisos, errores = convertir(args.original, args.clave, args.fuente, args.publicacion, args.tipo, args.emisor)
    for a in avisos:
        print("AVISO:", a, file=sys.stderr)
    for e in errores:
        print("ERROR:", e, file=sys.stderr)
    if errores:
        sys.exit(1)
    if args.ultima_reforma:
        ficha["ultima_reforma_dof"] = args.ultima_reforma
        for a in articulos:
            a["ultima_reforma_ley"] = args.ultima_reforma
    ficha = comun.escribir_norma(args.clave, articulos, decretos, ficha)
    print(json.dumps(ficha, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
