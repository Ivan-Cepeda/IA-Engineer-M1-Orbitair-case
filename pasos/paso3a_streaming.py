"""
PASO 3a — Streaming: TTFT vs latencia total, y el usage que no llega solo (parte C).

Ejecutar:
    uv run python -m pasos.paso3a_streaming
"""
import time

from orbitair import config
from orbitair.cliente import ask, ask_stream
from orbitair.datos import consulta


def imprimir_token(fragmento: str) -> None:
    print(fragmento, end="", flush=True)


def main() -> None:
    proveedores = config.proveedores_disponibles()
    oa007 = consulta("OA-007")["texto"]
    print(f"Modo: {'MOCK (simulado)' if config.MOCK else 'APIs reales'}\n")

    # 3a.1 — Streaming de OA-007: el texto aparece a medida que se genera
    for p in proveedores:
        print("=" * 70)
        print(f"3a.1 Streaming de OA-007 con {p}")
        print("=" * 70)
        r = ask_stream(p, oa007, on_token=imprimir_token)
        print("\n")
        print(f"  TTFT (lo que percibe el pasajero) : {r.ttft_s or 0:.2f} s")
        print(f"  Latencia total (respuesta entera) : {r.latency_s:.2f} s")
        print(f"  Usage: {r.input_tokens} in / {r.output_tokens} out · costo USD {r.cost_usd:.7f}\n")

    # 3a.2 — Sin streaming, el pasajero espera la latencia total mirando la pantalla vacía
    p = proveedores[0]
    print("=" * 70)
    print(f"3a.2 La misma consulta SIN streaming ({p})")
    print("=" * 70)
    r = ask(p, oa007)
    print(f"  Primer texto visible a los {r.latency_s:.2f} s (= latencia total)\n")

    # 3a.3 — El error típico: OpenAI en streaming sin include_usage
    if "openai" in proveedores:
        print("=" * 70)
        print("3a.3 Error típico: stream=True SIN stream_options={'include_usage': True}")
        print("=" * 70)
        r = ask_stream("openai", oa007, incluir_usage=False)
        print(f"  usage_disponible={r.usage_disponible} · tokens {r.input_tokens}/{r.output_tokens} · "
              f"costo USD {r.cost_usd:.7f}")
        if not r.usage_disponible:
            print("  ⚠ El costo dio CERO y no hubo ningún error. En un dashboard esto parece 'gratis'.\n")

    # 3a.4 — Error de medición: cronometrar incluyendo el print
    print("=" * 70)
    print("3a.4 Medir mal vs medir bien")
    print("=" * 70)

    def ui_lenta(fragmento: str) -> None:
        time.sleep(0.02)  # simula una interfaz que tarda en renderizar cada fragmento

    t0 = time.perf_counter()
    r = ask_stream(p, oa007, on_token=ui_lenta)
    mal = time.perf_counter() - t0
    print(f"  Cronómetro alrededor de TODO (incluye la UI): {mal:.2f} s  ← mal")
    print(f"  latency_s del cliente (solo el proveedor)   : {r.latency_s:.2f} s  ← bien")


if __name__ == "__main__":
    main()
