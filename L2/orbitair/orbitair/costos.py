# costos.py
# El costo se calcula SIEMPRE desde el usage real que devuelve la API. Nunca se estima.
import json
from pathlib import Path

PRICING_PATH = Path(__file__).resolve().parent.parent / "pricing.json"
PRICING: dict = {k: v for k, v in json.loads(PRICING_PATH.read_text(encoding="utf-8")).items() if not k.startswith("_")}

CONSULTAS_ESCALA = 10_000  # volumen mensual que usa OrbitAir para decidir


def calcular_costo(modelo: str, input_tokens: int, output_tokens: int) -> float:
    """
    costo = input_tokens / 1M × precio_input + output_tokens / 1M × precio_output

    :raises KeyError: si el modelo no está en pricing.json. Mejor explotar que
        devolver 0 en silencio y subestimar el presupuesto.
    """
    if modelo not in PRICING:
        raise KeyError(f"El modelo '{modelo}' no está en pricing.json. Opciones: {list(PRICING)}")
    precio = PRICING[modelo]
    return (input_tokens / 1_000_000 * precio["input_per_1m"]) + (
        output_tokens / 1_000_000 * precio["output_per_1m"]
    )


def proyectar(costo_promedio: float, consultas: int = CONSULTAS_ESCALA) -> float:
    """Lleva el costo promedio por consulta a la escala real del negocio."""
    return costo_promedio * consultas
