# datos.py
# Dataset de consultas, etiquetas (gold) y system prompt de respuesta de OrbitAir.
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "consultas.json"
ETIQUETAS_PATH = DATA_DIR / "etiquetas.json"

# System prompt de L1 (responder al pasajero). En L2 el foco pasa al prompt de TRIAGE (prompts/).
SYSTEM_PROMPT = (
    "Eres el asistente de primera respuesta del centro de atención de OrbitAir, una aerolínea. "
    "Responde en el mismo idioma que el pasajero, con tono amable y en máximo 4 frases. "
    "Si la consulta requiere datos de la reserva o una excepción a la política, indica que "
    "un agente humano la revisará. No inventes precios, plazos ni políticas que no conozcas."
)


def cargar_consultas(lote: str | None = None) -> list[dict]:
    """
    Devuelve las consultas OA-001..OA-020.

    :param lote: "dev" (OA-001..010, se usan para diseñar el prompt), "holdout"
        (OA-011..020, solo para medir al final) o None (todas).
    """
    consultas = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [c for c in consultas if lote is None or c["lote"] == lote]


def cargar_etiquetas() -> dict[str, dict]:
    """{id: {"categoria": ..., "regla": ..., "justificacion": ...}} — la verdad contra la que se mide."""
    return json.loads(ETIQUETAS_PATH.read_text(encoding="utf-8"))


def consulta(id_: str) -> dict:
    """Busca una consulta por id, por ejemplo consulta('OA-007')."""
    for c in cargar_consultas():
        if c["id"] == id_:
            return c
    raise KeyError(id_)
