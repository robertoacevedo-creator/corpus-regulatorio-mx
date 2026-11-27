# Historial de versiones

Las entradas nuevas van arriba.

## v2 (27-nov-2026)

Tanda 1: leyes y reglamentos federales de la compilación de la Cámara de Diputados (.doc).

- LFT: 1266 artículos, 13 transitorios y 32 decretos de reforma (148 registros derogados). Última reforma: DOF 14-05-2026.
- CFF: 421 artículos, 11 transitorios y 76 decretos de reforma (84 registros derogados). Última reforma: DOF 09-04-2026.
- LAdua: 277 artículos, 0 transitorios y 41 decretos de reforma (16 registros derogados). Última reforma: DOF 23-10-2026.
- LAN: 215 artículos, 13 transitorios y 12 decretos de reforma (21 registros derogados). Última reforma: DOF 11-12-2025.
- LCE: 109 artículos, 4 transitorios y 7 decretos de reforma (1 registros derogados). Última reforma: DOF 01-05-2026.
- LGPC: 94 artículos, 13 transitorios y 9 decretos de reforma (1 registros derogados). Última reforma: DOF 21-12-2023.
- LGS: 733 artículos, 7 transitorios y 149 decretos de reforma (42 registros derogados). Última reforma: DOF 15-01-2026.
- LIVA: 80 artículos, 5 transitorios y 52 decretos de reforma (15 registros derogados). Última reforma: DOF 12-11-2021.
- LFSA: 177 artículos, 10 transitorios y 4 decretos de reforma (0 registros derogados). Última reforma: DOF 21-05-2024.
- LFCPQ: 31 artículos, 4 transitorios y 9 decretos de reforma (0 registros derogados). Última reforma: DOF 03-05-2023.
- Reg_CFF: 113 artículos, 7 transitorios y 0 decretos de reforma (0 registros derogados). Última reforma: DOF 02-04-2014.
- Reg_LAdua: 282 artículos, 6 transitorios y 8 decretos de reforma (10 registros derogados). Última reforma: DOF 23-02-2026.
- Reg_LAN: 202 artículos, 14 transitorios y 5 decretos de reforma (2 registros derogados). Última reforma: DOF 25-08-2014.
- Reg_LFCPrecQuim: 18 artículos, 1 transitorios y 0 decretos de reforma (0 registros derogados). Última reforma: DOF 15-09-1999.
- Reg_LFSA: 373 artículos, 8 transitorios y 0 decretos de reforma (0 registros derogados). Última reforma: DOF 21-05-2012.
- Reg_LGEEPA_MRETC: 32 artículos, 7 transitorios y 1 decretos de reforma (0 registros derogados). Última reforma: DOF 31-10-2014.
- Reg_LGPC: 114 artículos, 6 transitorios y 1 decretos de reforma (0 registros derogados). Última reforma: DOF 09-12-2015.
- Reg_LGS_MCSAEPS: 1356 artículos, 4 transitorios y 3 decretos de reforma (1014 registros derogados). Última reforma: DOF 28-12-2004.

Convertidor de Diputados: al cargar esta tanda la prueba de cobertura rechazó 13 normas y se ajustó el convertidor (sin tocar la prueba): ids con ordinal y letra ("1o.-A"), letra Ñ y letra con número ("174-L-1"), sufijos en minúscula ("bis") y con número pegado por guion ("268 Bis-1"), "Artículo. 88.", ordinales compuestos y "ÚNICA" en encabezados, nombres largos de encabezado, encabezados derogados, apartados con número romano, notas partidas en dos renglones y notas largas, firmas de cierre en minúscula, y fecha de encabezado con "Últimas reformas" o con "1º". Lo ya cargado (LGPGIR, su Reglamento y la NOM-052) quedó idéntico.

Pendientes de esta tanda: la Ley Federal de Derechos (LFD) no se cargó porque el archivo de la carpeta es de la reforma DOF 07-11-2025 y el índice de Diputados marca DOF 13-11-2026 ("En actualización"). La LIGIE queda para una tanda aparte.

## v1.2 (27-nov-2026)

- Consulta y verificador de citas (`herramientas/consulta.py`) para la skill de consulta, con su prueba. Sin cambios en el corpus.

## v1.1 (27-nov-2026)

- Vigilante semanal de las leyes y reglamentos federales (GitHub Actions), con su prueba de lectura de índices. Sin cambios en el corpus.

## v1 (26-nov-2026)

Primera publicación: estructura, convertidores, revisión automática y primera tanda.

- LGPGIR: 126 artículos, 13 transitorios y 15 decretos de reforma. Última reforma: DOF 19-01-2026.
- Reglamento de la LGPGIR: 164 artículos, 12 transitorios y 1 decreto de reforma. Última reforma: DOF 31-10-2014.
- NOM-052-SEMARNAT-2005: preámbulo, prefacio, 76 numerales, 3 transitorios, cierre, 9 tablas, listados, figura y anexo, y 705 renglones de listado con su clave. Publicada: DOF 23-06-2006.

Esta versión se corrigió antes de darse por buena, tras dos revisiones independientes: renglones de listado delimitados por los bordes de celda y cotejados celda por celda, signos que el PDF trae sin letra, notas al pie de los listados, cobertura total del original, ids de artículo probados contra el corpus de leyes federales y manifiesto de todos los archivos.
