# config.py
# Toda la configuración sale del .env: credenciales, modelos y parámetros de sampling.
import os

from dotenv import load_dotenv

load_dotenv()

MOCK = os.getenv("ORBITAIR_MOCK", "0") == "1"
MOCK_FAIL_RATE = float(os.getenv("ORBITAIR_MOCK_FAIL_RATE", "0"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

MODELOS = {
    "openai": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
    "gemini": os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
}

# Los Gemini 3.x "piensan" antes de responder. Esos tokens se cobran como output y
# consumen max_tokens. "minimal" casi lo apaga; vacío = default del modelo.
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "minimal")

# Atención al cliente NO es una tarea creativa: temperature baja = respuestas consistentes.
TEMPERATURE = float(os.getenv("ORBITAIR_TEMPERATURE", "0.2"))
# Techo de salida: controla costo y latencia (y obliga a respuestas cortas).
MAX_TOKENS = int(os.getenv("ORBITAIR_MAX_TOKENS", "300"))


class ConfiguracionError(Exception):
    """Falta una variable obligatoria del .env."""


def _key_valida(key: str) -> bool:
    return bool(key) and not key.startswith("pon-aqui")


def proveedores_disponibles() -> list[str]:
    """
    Devuelve los proveedores que se pueden usar con la configuración actual.

    En modo mock están todos; en modo real, solo los que tienen API key.
    """
    if MOCK:
        return ["openai", "anthropic", "gemini"]
    keys = {"openai": OPENAI_API_KEY, "anthropic": ANTHROPIC_API_KEY, "gemini": GEMINI_API_KEY}
    disponibles = [p for p, key in keys.items() if _key_valida(key)]
    if not disponibles:
        raise ConfiguracionError(
            "No hay API keys en el .env. Completa OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY "
            "o usa ORBITAIR_MOCK=1 para seguir la clase sin gastar."
        )
    return disponibles
