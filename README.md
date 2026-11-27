# corpus-regulatorio-mx

Texto de leyes, reglamentos, normas oficiales mexicanas (NOM), acuerdos y normas de Durango y Gómez Palacio. Está partido por artículo (o por numeral, en las NOM) y lleva huellas que permiten comprobar que nada cambió sin quedar registrado.

Sirve para citar una disposición letra por letra y saber de dónde salió y en qué fecha estaba vigente.

## Qué no es

- **No es la fuente oficial.** El texto oficial es el que publica el Diario Oficial de la Federación o el Periódico Oficial del Estado de Durango. Las compilaciones de la Cámara de Diputados y del Congreso de Durango son informativas. Ante cualquier duda, se consulta el original.
- **No contiene información de clientes.** Ni nombres, ni asuntos, ni expedientes.
- **No contiene los archivos originales.** Los .doc, .docx y PDF se guardan aparte. Aquí solo va su huella SHA-256, para saber exactamente de qué archivo salió cada texto.

## Cómo se consulta

1. Descarga el repositorio (no pide credenciales).
2. Comprueba que llegó completo: la huella SHA-256 de cada archivo debe coincidir con la que trae `manifest.json`.
3. Busca la norma en `catalogo.json` por su clave (por ejemplo `LGPGIR` o `NOM-052-SEMARNAT-2005`).
4. Abre `corpus/<clave>/articulos.jsonl` y busca el registro por su `id`.

Ejemplo, el artículo 1 de la LGPGIR:

```json
{"ley": "LGPGIR", "id": "1", "tipo": "articulo", "estado": "vigente",
 "ubicacion": "TÍTULO PRIMERO DISPOSICIONES GENERALES > CAPÍTULO ÚNICO OBJETO Y ÁMBITO DE APLICACIÓN DE LA LEY",
 "texto": "Artículo 1.- La presente Ley es reglamentaria de ...",
 "anotaciones": ["Párrafo reformado DOF 05-11-2013, 08-05-2023", "..."],
 "ultima_reforma_articulo": "2023-05-08", "ultima_reforma_ley": "2026-01-19", "linea_fuente": 28}
```

Un renglón del Listado 3 de la NOM-052:

```json
{"ley": "NOM-052-SEMARNAT-2005", "id": "Listado 3 H012", "tipo": "renglon",
 "texto": "1327-53-3 | Arsénico, óxido As2O3 | (Th) | H012", "linea_fuente": 14, "...": "..."}
```

### Consulta con verificación de citas

`herramientas/consulta.py` hace lo mismo sin escribir código y verifica citas. Es lo que usa la skill de consulta.

```
python3 -I herramientas/consulta.py comprobar                                  # huellas y lista de normas
python3 -I herramientas/consulta.py buscar "gran generador toneladas" --norma LGPGIR
python3 -I herramientas/consulta.py ver "nom 052" "listado 3 h012"
python3 -I herramientas/consulta.py remisiones Reg_LGPGIR 35                   # artículos a los que remite
python3 -I herramientas/consulta.py decretos LGPGIR 5                          # decretos que lo reformaron
python3 -I herramientas/consulta.py verificar borrador.md                      # coteja cada cita letra por letra
```

En el borrador, cada cita va marcada como `[[CITA norma=CLAVE id=ID]]texto literal[[/CITA]]`. El verificador la marca VERDE si el texto está tal cual en el registro, o ROJO con el texto real si no, y lista las menciones de artículos sin cita. Normaliza solo espacios, comillas y guiones; nunca palabras.

## Qué contiene

| Archivo | Qué guarda |
| --- | --- |
| `catalogo.json` | Índice maestro. Por cada norma: clave, nombre oficial, tipo, fuente y liga oficial, fecha de publicación y de última reforma, fecha de carga, huella del original y conteo de registros. |
| `corpus/<clave>/articulos.jsonl` | Una línea por artículo, numeral, transitorio, preámbulo, cierre, tabla o renglón de listado. |
| `corpus/<clave>/decretos.jsonl` | Decretos de reforma con sus transitorios (solo leyes y reglamentos de Diputados). |
| `corpus/<clave>/ficha.json` | La ficha de esa norma en el catálogo. |
| `manifest.json` | Versión del corpus y huella SHA-256, tamaño y líneas de cada archivo publicado: corpus, catálogo, código y documentación. |
| `CAMBIOS.md` | Historial de versiones. |
| `convertidores/` | Los scripts que convierten cada tipo de original. |
| `herramientas/` | Carga, revisión automática, publicación, fuentes de cada norma y artículos de control. |
| `pruebas/` | Pruebas de los convertidores con casos difíciles. |

### Campos de cada registro

Son los mismos campos, en el mismo orden, que el corpus de leyes federales [`robertoacevedo-creator/corpus-leyes-mx`](https://github.com/robertoacevedo-creator/corpus-leyes-mx). Así el mismo verificador de citas funciona con los dos.

| Campo | Significado |
| --- | --- |
| `ley` | Clave de la norma. |
| `id` | Número del artículo (`1`, `62 Bis`, `4-A`, `3 a 5`), del numeral (`5.2`), del transitorio (`Transitorio Primero`), de la parte (`Preámbulo`, `Prefacio`, `Cierre`, `Tabla 2`) o del renglón (`Listado 3 H012`). |
| `tipo` | `articulo`, `numeral`, `transitorio`, `preambulo`, `cierre`, `anexo` (tabla, figura o encabezado de listado) o `renglon` (un renglón de un listado, con su clave). |
| `estado` | `vigente` o `derogado`. |
| `ubicacion` | Libro, título, capítulo y sección donde está. En las NOM, el capítulo del numeral, o el listado y su grupo. |
| `texto` | Texto completo. Cada párrafo, fracción o renglón va en su propia línea. En tablas y listados, las columnas se separan con ` \| `. |
| `anotaciones` | Notas de reforma que trae el original ("Fracción reformada DOF 08-05-2023"). |
| `ultima_reforma_articulo` | Fecha más reciente de esas notas. Vacío si el artículo no se ha reformado. |
| `ultima_reforma_ley` | Última reforma de la norma completa. |
| `linea_fuente` | Línea del original convertido a texto (en los PDF, la página). |

## Cómo se arma

Hay un convertidor por tipo de original:

| Convertidor | Originales |
| --- | --- |
| `diputados_doc.py` | Leyes y reglamentos federales en .doc de la Cámara de Diputados (LeyesBiblio). |
| `dof_pdf.py` | NOM, acuerdos y otras publicaciones del DOF en PDF (impresión de la nota del DOF desde el navegador). |
| Congreso de Durango (pendiente) | Leyes estatales en .docx o PDF. |

`herramientas/fuentes.json` dice qué convertidor usa cada norma, qué archivo lee y con qué datos. Para reconstruir todo:

```
pip install -r requirements.txt      # además hace falta LibreOffice para los .doc
python herramientas/cargar.py CARPETA_CON_ORIGINALES
python herramientas/publicar.py --version vN
python herramientas/validar.py
python pruebas/test_diputados.py
```

### Reglas de texto

- **Las palabras no se tocan.** Los espacios repetidos y los tabuladores se juntan en un espacio, se quitan los espacios de ancho cero y los acentos se guardan en forma Unicode NFC. Así una cita se compara letra por letra.
  - El corpus de leyes federales conserva los espacios dobles del original. Un verificador que use los dos corpus debe juntar espacios antes de comparar.
- **Notas de reforma.** Salen del texto y pasan a `anotaciones`. Las notas de reforma de encabezados ("Título adicionado DOF ...") no se guardan.
- **Párrafos de los PDF del DOF.** Se rearman por la sangría de su primer renglón.
- **Signos que el PDF trae sin letra.** Se deciden por contexto:
  - entre dígitos es guion (CAS 5344-82-1);
  - antes de guion o de "s" es apóstrofo (2,2'-oxibis, BPC's);
  - en lo demás son comillas.
- **Tablas.** Se leen por la posición de cada carácter y por los bordes de celda que trae el PDF:
  - cada renglón de un listado es un registro con su clave, delimitado por la celda de la clave aunque la clave vaya centrada o el renglón cruce de página;
  - los subíndices de las fórmulas quedan en su lugar (As2O3);
  - una clave que el original repite queda como `Listado 4 T210 (2)`;
  - el registro de cada listado (`Listado 3`, `Anexo 1`) guarda su título, el encabezado de columnas y las notas al pie.

### Cobertura

- El convertidor de Diputados termina con error si alguna línea del original, después del primer artículo, no queda en un registro, en sus anotaciones, en un encabezado o en una firma.
- El convertidor del DOF termina con error si el contenido de algún renglón de listado no cuadra con un segundo armado hecho celda por celda (`extract_tables` de pdfplumber). El cotejo compara las letras de cada renglón sin importar su orden: detecta letras de más, de menos o en el renglón equivocado, pero no palabras cambiadas de lugar dentro del mismo renglón.
- En la NOM-052, todas las palabras del PDF están en algún registro, salvo el índice, que no se guarda porque solo repite los encabezados.
- El lector de ids de artículo se probó contra los 932 artículos del corpus de leyes federales: coinciden todos (`1`, `14 Bis`, `20 Bis 1`, `58-1`...).

## Cómo se mantiene al día

- `main` está protegida: nadie sube directo, ni los administradores. Cada cambio entra como pull request y solo se integra cuando el responsable del repositorio hace el merge, después de que pase la revisión automática.
- Cada pull request pasa la revisión automática:
  - `pruebas/test_diputados.py`;
  - `herramientas/validar.py`: sin registros vacíos ni repetidos, todo lo del catálogo con su texto, conteos del catálogo que cuadran, sin notas de reforma dentro del texto, huellas que cuadran y artículos de control que siguen diciendo lo mismo.
- Cada versión aprobada sube el número (v1, v2...) y deja su línea en `CAMBIOS.md`.
- Un vigilante semanal revisa las leyes y reglamentos federales (ver abajo). El de las leyes de Durango y el de las NOM están pendientes.

## Vigilante semanal

Corre en GitHub Actions (`.github/workflows/vigilante.yml`) cada lunes a las 7:17, hora de la Ciudad de México, y a mano desde la pestaña *Actions* con *Run workflow*.

1. **Lee los índices de la Cámara de Diputados** ([leyes](https://www.diputados.gob.mx/LeyesBiblio/index.htm) y [reglamentos](https://www.diputados.gob.mx/LeyesBiblio/regla.htm)). Encuentra la fila de cada norma del catálogo por el nombre de su archivo vigente y lee su fecha de última reforma y sus marcas ("Nueva reforma", "En actualización", "Sentencia SCJN").
2. **Si la fecha es la misma del catálogo y no hay marcas,** termina sin hacer nada.
3. **Si algo cambió,** baja el texto vigente con la liga del índice (el nombre del archivo de los reglamentos cambia con cada reforma), lo convierte y lo compara artículo por artículo:
   - **Texto nuevo:** abre un pull request con la versión siguiente (v2, v3...), su línea en `CAMBIOS.md` y la lista de artículos reformados, adicionados, derogados y eliminados. La revisión automática corre sobre ese pull request.
   - **Reforma anunciada pero el texto aún no cambia:** abre un aviso (issue) de compilación pendiente y lo vuelve a revisar la semana siguiente.
   - **Falla** (no encuentra la norma, no baja el archivo o no lo puede convertir): abre un aviso con el detalle. No propone nada.
4. **Nada entra a `main` sin el merge del responsable.** El vigilante no repite avisos abiertos y no abre otro pull request mientras haya uno suyo pendiente.

Para probarlo sin esperar una reforma real, en *Run workflow* se escribe una clave en "simular" (por ejemplo `LGPGIR`): la trata como si hubiera cambiado, baja y convierte el texto, y si sale igual al que ya tenemos no abre nada.

Límite: la compilación de Diputados puede ir uno o dos días detrás del DOF, que es el texto oficial.

## Límites conocidos

- Los transitorios usan ids como "Transitorio Décimo Primero". El corpus de leyes federales usa variantes ("Decimoprimero", "Décimo primero").
- En los listados, cuando una categoría tiene dos niveles (LODOS > ACABADO DE METALES), el nivel superior solo se conserva en los renglones que van justo después de él.
- Las figuras y diagramas solo conservan su texto.
- La huella de un PDF impreso desde el navegador cambia cada vez que se vuelve a imprimir (lleva fecha y autor). Para vigilar cambios en una NOM se compara el texto, no la huella del PDF.
