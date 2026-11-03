# registro.py — CLASE 5, paso 5.1: tokens, latencia y costo dejan de ser un print y pasan a ser DATOS.
# Cada fila guarda input + referencia + salida + costo en el mismo lugar: no se pueden desincronizar.
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

RESULTS = Path("results")


@dataclass
class RegistroEval:
    caso_id: str
    version_prompt: str
    texto: str
    categoria_esperada: str
    categoria_obtenida: str | None
    input_tokens: int
    output_tokens: int
    costo_usd: float
    latencia_s: float
    respuesta: str  # la salida cruda: si hay razonamiento (v4), el juez lo lee de acá
    timestamp: float


def registrar(caso: dict, version: str, categoria_obtenida: str | None, r) -> RegistroEval:
    """r es el LLMResponse de llm.py (Clase 1): ya trae tokens, costo y latencia reales."""
    return RegistroEval(
        caso_id=caso["id"], version_prompt=version, texto=caso["texto"],
        categoria_esperada=caso["categoria_esperada"], categoria_obtenida=categoria_obtenida,
        input_tokens=r.input_tokens, output_tokens=r.output_tokens,
        costo_usd=r.cost_usd, latencia_s=r.latency_s,
        respuesta=r.text, timestamp=time.time(),
    )


# Cada corrida es su propio .jsonl (como los prompts v1/v2/v3 de C2): recalcular métricas
# o cambiar el reporte NO obliga a volver a llamar al modelo.
def guardar_corrida(registros: list[RegistroEval], version: str) -> Path:
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"eval_{version}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    return path


def leer_corrida(version: str) -> list[RegistroEval]:
    path = RESULTS / f"eval_{version}.jsonl"
    return [RegistroEval(**json.loads(l)) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
