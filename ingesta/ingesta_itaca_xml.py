"""Práctica P1 - Ingesta de las exportaciones XML de ITACA."""
import json
import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingesta_itaca_xml")

# Rutas relativas a la carpeta del proyecto (funciona se lance desde donde se lance)
BASE = Path(__file__).resolve().parent.parent
ORIGEN = BASE / "data" / "exportaciones"
DESTINO = BASE / "data" / "raw"

TABLAS = ["alumnos", "cursos", "calificaciones", "contenidos"]

# Campos que pide el enunciado (sin Anyo: sale de la cabecera <centro curso="...">)
CAMPOS = {
    "alumnos": ["NIA", "sexo", "nacionalidad", "provincia", "municipio", "ensenanza",
                "curso", "grupo", "turno", "linea", "modalidad", "repite",
                "estado_matricula", "tipo_matricula", "fecha_matricula",
                "fecha_ingreso_centro"],
    "cursos": ["codigo", "nombre_cas", "nombre_val", "abreviatura", "ensenanza", "padre"],
    "calificaciones": ["evaluacion", "alumno", "ensenanza", "curso", "contenido",
                       "bloque_contenido", "nota_numerica", "tipo_nota"],
    "contenidos": ["codigo", "nombre_cas", "nombre_val", "ensenanza", "curso"],
}

# En qué campo está el NIA en cada tabla
CAMPO_NIA = {"alumnos": "NIA", "calificaciones": "alumno"}

# Cada NIA se convierte en hash una sola vez y se reutiliza en todas las tablas
_hashes = {}


def anonimizar_nia(nia: str) -> str:
    if nia not in _hashes:
        _hashes[nia] = hashlib.sha256(str(nia).encode()).hexdigest()[:10]
    return _hashes[nia]


def parsear_xml(ruta: Path, tabla: str) -> list[dict]:
    """Lee un XML de ITACA: <centro curso="AAAA"> -> <tabla> -> registros con atributos."""
    raiz = ET.parse(ruta).getroot()
    anyo = raiz.get("curso")
    contenedor = raiz.find(tabla)
    if contenedor is None:
        logger.warning("%s no contiene la etiqueta <%s>", ruta, tabla)
        return []
    registros = []
    for nodo in contenedor:
        registro = {"Anyo": anyo}
        for campo in CAMPOS[tabla]:
            registro[campo] = nodo.get(campo)
        registros.append(registro)
    return registros


def leer_tabla(tabla: str) -> list[dict]:
    """Junta la tabla de todos los cursos escolares (una carpeta por curso)."""
    datos = []
    for carpeta in sorted(p for p in ORIGEN.iterdir() if p.is_dir()):
        ruta = carpeta / f"{tabla}.xml"
        if not ruta.exists():
            logger.warning("No existe %s", ruta)
            continue
        try:
            registros = parsear_xml(ruta, tabla)
        except ET.ParseError as e:
            logger.error("XML mal formado en %s: %s", ruta, e)
            continue
        logger.info("%s %-15s %7d registros", carpeta.name, tabla, len(registros))
        datos.extend(registros)
    return datos


def anonimizar(datos: list[dict], tabla: str) -> list[dict]:
    campo = CAMPO_NIA.get(tabla)
    if campo:
        for r in datos:
            if r.get(campo):
                r[campo] = anonimizar_nia(r[campo])
    return datos


def guardar(datos: list[dict], nombre: str) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    ruta = DESTINO / f"{nombre}_{date.today().isoformat()}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    logger.info("Guardados %d registros en %s", len(datos), ruta.name)


def validar(resultado: dict) -> None:
    """Comprueba que las referencias entre tablas son coherentes (por año)."""
    alumnos = {(r["Anyo"], r["NIA"]) for r in resultado["alumnos"]}
    cursos = {(r["Anyo"], r["codigo"]) for r in resultado["cursos"]}

    sin_alumno = sum(1 for r in resultado["calificaciones"]
                     if (r["Anyo"], r["alumno"]) not in alumnos)
    sin_curso = sum(1 for r in resultado["alumnos"]
                    if (r["Anyo"], r["curso"]) not in cursos)

    logger.info("Validación: %d calificaciones sin alumno en su año", sin_alumno)
    logger.info("Validación: %d alumnos con un curso inexistente en su año", sin_curso)


def main() -> None:
    resultado = {}
    for tabla in TABLAS:
        try:
            datos = anonimizar(leer_tabla(tabla), tabla)
            guardar(datos, tabla)
            resultado[tabla] = datos
        except Exception:
            logger.exception("Fallo procesando la tabla %s", tabla)
    if len(resultado) == len(TABLAS):
        validar(resultado)
    logger.info("NIA distintos anonimizados: %d", len(_hashes))


if __name__ == "__main__":
    main()