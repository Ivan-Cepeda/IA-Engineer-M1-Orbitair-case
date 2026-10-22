# prompts.py
# Plantillas versionadas (prompts/triage_vX.txt) + variables de contexto que cambian por request.
# Lo que se VERSIONA: el texto de la plantilla. Lo que NO: empresa, categorías y la consulta.
import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Variable de contexto: si mañana se agrega una categoría, cambia este dict, no las plantillas.
CATEGORIAS: dict[str, str] = {
    "equipaje": "maletas, equipaje de mano o de bodega, pérdidas, daños, objetos especiales",
    "cambios_cancelaciones": "modificar la reserva (fecha, ruta, nombre o titular), cancelaciones, reprogramación, conexiones perdidas",
    "reembolsos_cobros": "devoluciones de dinero, cobros duplicados o indebidos, créditos",
    "servicios_especiales": "mascotas, menores no acompañados, movilidad reducida, condiciones médicas, embarazo",
    "millas": "programa OrbitPlus: acumular, canjear o consultar millas/puntos",
    "otro": "cualquier consulta que no encaje en las anteriores",
}

VARIABLES_FIJAS = {"empresa": "OrbitAir"}

# Plantilla del mensaje de usuario: los delimitadores separan instrucción de contenido.
PLANTILLA_USUARIO = "<consulta>{contenido}</consulta>"


def versiones() -> list[str]:
    """Todas las versiones disponibles, en orden: ['v1', 'v2', 'v3', 'v3_obvio', 'v4']."""
    return sorted(p.stem.removeprefix("triage_") for p in PROMPTS_DIR.glob("triage_*.txt"))


def cargar_plantilla(version: str) -> str:
    ruta = PROMPTS_DIR / f"triage_{version}.txt"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta.name}. Versiones: {versiones()}")
    return ruta.read_text(encoding="utf-8")


def formatear_categorias(categorias: dict[str, str] = CATEGORIAS) -> str:
    return "\n".join(f"- {nombre}: {descripcion}" for nombre, descripcion in categorias.items())


def renderizar_system(version: str, **variables) -> str:
    """
    Completa la plantilla con las variables. Ojo: en las plantillas, las llaves literales
    del JSON se escriben dobles ({{ }}) para que .format() no las confunda con variables.

    :raises KeyError: si la plantilla usa una variable que no se pasó.
    """
    valores = {**VARIABLES_FIJAS, "categorias": formatear_categorias(), **variables}
    texto = cargar_plantilla(version).format(**valores)
    sobrantes = re.findall(r"\{[a-z_]+\}", texto)
    if sobrantes:  # una variable mal escrita que quedó sin reemplazar
        raise ValueError(f"Quedaron variables sin completar en {version}: {sobrantes}")
    return texto


def mensaje_usuario(contenido: str) -> str:
    return PLANTILLA_USUARIO.format(contenido=contenido)
