"""Convierte el resultado del vigilante en avisos (issues) y en un pull request.

    python herramientas/avisos.py --informe informe.json --plan plan.json

Corre dentro de GitHub Actions con el CLI `gh` y la variable GH_TOKEN.
No repite un aviso que ya está abierto con el mismo título, y no abre un
pull request nuevo mientras haya otro del vigilante sin resolver.
"""
import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = ["corpus", "catalogo.json", "manifest.json", "CAMBIOS.md", "herramientas/fuentes.json"]


def gh(*args, salida=False):
    r = subprocess.run(["gh", *args], cwd=RAIZ, capture_output=True, text=True, check=True)
    return r.stdout if salida else None


def git(*args):
    subprocess.run(["git", *args], cwd=RAIZ, check=True)


def avisos_abiertos():
    datos = json.loads(gh("issue", "list", "--state", "open", "--limit", "300", "--json", "title", salida=True))
    return {d["title"] for d in datos}


def avisar(titulo, cuerpo, abiertos):
    if titulo in abiertos:
        print("Ya abierto:", titulo)
        return
    gh("issue", "create", "--title", titulo, "--body", cuerpo)
    abiertos.add(titulo)
    print("Aviso:", titulo)


def lista(ids):
    return ", ".join(ids) if ids else "ninguno"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--informe", required=True)
    ap.add_argument("--plan", required=True)
    args = ap.parse_args()
    informe = json.loads(Path(args.informe).read_text(encoding="utf-8"))
    plan_ruta = Path(args.plan)
    plan = json.loads(plan_ruta.read_text(encoding="utf-8")) if plan_ruta.exists() else []
    abiertos = avisos_abiertos()

    for i in informe:
        if i["estado"] == "no_encontrada":
            avisar(f"Vigilante: no encontré {i['clave']} en el índice de Diputados",
                   f"No encontré la fila de **{i['clave']}** en el índice de {i['indice']} "
                   f"(archivo `{i['tronco']}`). Puede que Diputados cambió el nombre del archivo o la "
                   "estructura de la página. Hay que revisar el vigilante.", abiertos)

    propuestas = [r for r in plan if r["estado"] == "propuesta"]
    for r in plan:
        if r.get("simulado") and r["estado"] in ("sin_cambios", "pendiente"):
            print(f"Simulación de {r['clave']}: {r['estado']} (sin aviso)")
            continue
        if r["estado"] == "pendiente":
            avisar(f"Reforma anunciada, compilación pendiente: {r['clave']}",
                   f"El índice de Diputados marca **{', '.join(r['marcas'])}** para {r['clave']} "
                   f"(fecha en el índice: {r['fecha_indice']}), pero el texto vigente que publican "
                   f"todavía dice última reforma DOF {r.get('fecha_doc')}.\n\n"
                   "El vigilante lo volverá a revisar cada semana y propondrá el cambio cuando el texto se actualice. "
                   "Mientras tanto, el texto oficial de la reforma está en el DOF.", abiertos)
        elif r["estado"] == "sin_cambios":
            avisar(f"Vigilante: fecha distinta sin cambios de texto en {r['clave']}",
                   f"El índice da {r['fecha_indice']} como última reforma de {r['clave']}, "
                   "pero el texto vigente es igual al que ya tenemos. Conviene revisarlo a mano.", abiertos)
        elif r["estado"] == "error":
            avisar(f"Vigilante: error al actualizar {r['clave']}",
                   f"No pude actualizar **{r['clave']}** desde {r.get('url_doc')}.\n\n```\n{r.get('detalle', '')}\n```\n\n"
                   "No se propuso ningún cambio. Hay que revisar el convertidor o la descarga.", abiertos)

    if not propuestas:
        return
    pendientes = json.loads(gh("pr", "list", "--state", "open", "--json", "headRefName", salida=True))
    if any(p["headRefName"].startswith("vigilante/") for p in pendientes):
        avisar("Vigilante: hay reformas nuevas esperando a que se resuelva el pull request anterior",
               "Detecté reformas para " + ", ".join(r["clave"] for r in propuestas) +
               ", pero hay otro pull request del vigilante abierto. Cuando se integre o se cierre, "
               "la siguiente corrida las propondrá.", abiertos)
        return

    version = propuestas[0]["version"]
    rama = f"vigilante/{date.today().isoformat()}"
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("checkout", "-b", rama)
    git("add", *ARCHIVOS)
    claves = ", ".join(r["clave"] for r in propuestas)
    git("commit", "-m", f"{version}: reforma de {claves} (vigilante)")
    git("push", "origin", rama)

    cuerpo = [f"El vigilante detectó una reforma en el índice de la Cámara de Diputados y preparó la versión **{version}**.", ""]
    for r in propuestas:
        d = r["diferencias"]
        cuerpo += [
            f"### {r['clave']}: última reforma DOF {r['fecha_doc']}",
            f"- Reformados: {lista(d['reformados'])}",
            f"- Adicionados: {lista(d['adicionados'])}",
            f"- Derogados: {lista(d['derogados'])}",
            f"- Eliminados del texto: {lista(d['eliminados'])}",
            f"- Fuente: {r['url_doc']}",
        ]
        cuerpo += [f"- {a}" for a in r.get("avisos_conversion", [])]
        cuerpo.append("")
    cuerpo += ["Antes de integrar, revisa en *Files changed* que el texto de los artículos reformados coincida con el DOF. "
               "Nada entra a `main` hasta que hagas el merge."]
    gh("pr", "create", "--base", "main", "--head", rama, "--title", f"Reforma: {claves} ({version})", "--body", "\n".join(cuerpo))
    # Los cambios que hace este flujo no disparan otros flujos; la revisión obligatoria se lanza a mano.
    gh("workflow", "run", "validar.yml", "--ref", rama)
    print("Pull request abierto:", rama)


if __name__ == "__main__":
    main()
