"""
PASO 3b — Rate limits: backoff exponencial con jitter y Retry-After (parte C).

Todo este paso usa errores SIMULADOS: no hace falta (ni conviene) provocar 429 reales.
Ejecutar:
    uv run python -m pasos.paso3b_rate_limits
"""
import time

from orbitair import config
from orbitair.cliente import ask
from orbitair.datos import consulta
from orbitair.reintentos import ReintentosAgotados, calcular_espera, with_retry


class ErrorHTTP(Exception):
    """Error falso con la misma forma que los de los SDK: status_code y retry_after."""

    def __init__(self, status_code: int, retry_after: float | None = None):
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"HTTP {status_code}")


class ProveedorInestable:
    """Falla con los errores de la lista, en orden, y después responde bien."""

    def __init__(self, errores: list[ErrorHTTP]):
        self.errores = list(errores)
        self.llamadas = 0
        self.t0 = time.perf_counter()

    def llamar(self) -> str:
        self.llamadas += 1
        print(f"  t={time.perf_counter() - self.t0:5.2f}s → llamada #{self.llamadas}")
        if self.errores:
            raise self.errores.pop(0)
        return "respuesta OK"


def main() -> None:
    # 3b.1 — Cuánto se espera en cada intento
    print("=" * 70)
    print("3b.1 Esperas calculadas (base=1s)")
    print("=" * 70)
    print(f"  {'intento':<9}{'sin Retry-After':>18}{'otra vez (jitter)':>20}{'con Retry-After=1.5':>22}")
    for i in range(5):
        print(f"  {i:<9}{calcular_espera(i, None):>17.2f}s{calcular_espera(i, None):>19.2f}s{calcular_espera(i, 1.5):>21.2f}s")
    print("  → El jitter hace que dos clientes que fallan juntos NO reintenten en el mismo instante.\n")

    # 3b.2 — Dos 429 seguidos y después éxito
    print("=" * 70)
    print("3b.2 429 sin Retry-After, 429 con Retry-After=1.5, luego OK")
    print("=" * 70)
    prov = ProveedorInestable([ErrorHTTP(429), ErrorHTTP(429, retry_after=1.5)])
    print(f"  resultado: {with_retry(prov.llamar, base=0.5)}\n")

    # 3b.2b — El 429 de Gemini: otra forma, mismo significado
    print("=" * 70)
    print("3b.2b 429 de Gemini (google.genai.errors.ClientError real, armado a mano)")
    print("=" * 70)
    from google.genai import errors as genai_errors

    error_gemini = genai_errors.ClientError(429, {"error": {
        "code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded (simulado)",
        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1.2s"}],
    }})
    print(f"  error.code={error_gemini.code} (no status_code) · retryDelay en el JSON, no en un header")
    prov = ProveedorInestable([error_gemini])
    print(f"  resultado: {with_retry(prov.llamar)}\n")

    # 3b.3 — Un 400 NO se reintenta
    print("=" * 70)
    print("3b.3 Error 400 (request mal formada): no se reintenta")
    print("=" * 70)
    prov = ProveedorInestable([ErrorHTTP(400)])
    try:
        with_retry(prov.llamar)
    except ErrorHTTP as e:
        print(f"  Salió al primer intento con {e} ({prov.llamadas} llamada)\n")

    # 3b.4 — 503 sostenido: se agotan los intentos
    print("=" * 70)
    print("3b.4 503 sostenido: se agotan los intentos")
    print("=" * 70)
    prov = ProveedorInestable([ErrorHTTP(503)] * 10)
    try:
        with_retry(prov.llamar, max_retries=3, base=0.2)
    except ReintentosAgotados as e:
        print(f"  {e} → acá un Router derivaría el tráfico al otro proveedor\n")

    # 3b.5 — El cliente real (mock) con 50% de 429 simulados
    if config.MOCK:
        print("=" * 70)
        print("3b.5 ask() en mock con ORBITAIR_MOCK_FAIL_RATE=0.5")
        print("=" * 70)
        config.MOCK_FAIL_RATE = 0.5
        p = config.proveedores_disponibles()[0]
        for i in range(4):
            r = with_retry(lambda: ask(p, consulta("OA-001")["texto"]), base=0.3)
            print(f"  consulta #{i + 1} OK · USD {r.cost_usd:.7f}")
        config.MOCK_FAIL_RATE = 0.0


if __name__ == "__main__":
    main()
