# reintentos.py
# PASO 3b — Rate limits: reintentar con backoff exponencial + jitter, respetando Retry-After.
import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


class ReintentosAgotados(Exception):
    """Se intentó max_retries veces y el proveedor siguió fallando."""


def codigo_http(error: Exception) -> int | None:
    """
    Cada SDK guarda el código HTTP en un lugar distinto:
    OpenAI / Anthropic / mock → error.status_code · Gemini (google.genai.errors.APIError) → error.code
    """
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(error, "code", None)
    return status if isinstance(status, int) else None


def es_reintentable(error: Exception) -> bool:
    """
    429 (rate limit) y 5xx (error del proveedor) se reintentan.
    4xx (request mal formada, API key inválida...) NO: reintentar no lo arregla.

    Funciona con openai.RateLimitError, anthropic.RateLimitError, sus InternalServerError
    (y el 529 "overloaded" de Anthropic), google.genai.errors.ClientError/ServerError
    (429 RESOURCE_EXHAUSTED, 503 UNAVAILABLE) y con el MockRateLimitError.
    """
    status = codigo_http(error)
    return status == 429 or (status is not None and status >= 500)


def _retry_delay_gemini(error: Exception) -> str | None:
    """
    Gemini no usa el header Retry-After: manda la espera dentro del JSON del error,
    en un detalle google.rpc.RetryInfo → {"retryDelay": "37s"}.
    """
    detalles = getattr(error, "details", None)
    if not isinstance(detalles, dict):
        return None
    for d in detalles.get("error", {}).get("details", []):
        if isinstance(d, dict) and d.get("@type", "").endswith("google.rpc.RetryInfo"):
            return str(d.get("retryDelay", "")).rstrip("s") or None
    return None


def leer_retry_after(error: Exception) -> float | None:
    """Devuelve los segundos que pide el proveedor, si los informa."""
    valor = getattr(error, "retry_after", None)  # mock
    if valor is None:
        respuesta = getattr(error, "response", None)  # OpenAI / Anthropic: header HTTP
        headers = getattr(respuesta, "headers", None)
        if headers is not None:
            valor = headers.get("retry-after")
    if valor is None:
        valor = _retry_delay_gemini(error)  # Gemini: RetryInfo en el cuerpo del error
    try:
        return float(valor) if valor is not None else None
    except ValueError:  # Retry-After también puede venir como fecha HTTP; la ignoramos
        return None


def calcular_espera(intento: int, retry_after: float | None, base: float = 1.0, tope: float = 30.0) -> float:
    """
    Prioridad 1: Retry-After (el proveedor conoce su propia carga mejor que nosotros).
    Prioridad 2: backoff exponencial base·2^intento (1, 2, 4, 8...) + jitter aleatorio.
    """
    if retry_after is not None:
        return retry_after
    return min(tope, base * 2**intento) + random.uniform(0, base)


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 5,
    base: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> T:
    """
    Ejecuta fn() y la reintenta ante 429/5xx.

    :param fn: función SIN argumentos, por ejemplo lambda: ask("openai", texto).
    :param sleep: inyectable para testear sin esperar de verdad.
    :raises ReintentosAgotados: si falla max_retries veces seguidas.
    :raises Exception: cualquier error NO reintentable sale tal cual, al primer intento.
    """
    for intento in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if not es_reintentable(e):
                raise
            if intento == max_retries - 1:  # último intento: no tiene sentido esperar
                raise ReintentosAgotados(f"Se agotaron los {max_retries} intentos") from e
            retry_after = leer_retry_after(e)
            espera = calcular_espera(intento, retry_after, base)
            origen = "Retry-After" if retry_after is not None else "backoff"
            log(f"  ⚠ intento {intento + 1}/{max_retries} falló ({codigo_http(e)}). "
                f"Esperando {espera:.2f}s ({origen})")
            sleep(espera)
    raise ReintentosAgotados("max_retries debe ser >= 1")
