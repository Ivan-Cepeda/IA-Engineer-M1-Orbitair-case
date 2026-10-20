"""
PASO 1 — Cliente multi-proveedor con contrato unificado (parte A de la consigna).

Ejecutar desde la carpeta orbitair/:
    uv run python -m pasos.paso1_cliente
"""
from orbitair import config
from orbitair.cliente import LLMResponse, ask
from orbitair.datos import consulta


def mostrar(r: LLMResponse) -> None:
    print(f"  [{r.provider} · {r.model}{' · MOCK' if r.mock else ''}]")
    print(f"  texto        : {r.text}")
    thinking = f" (de los cuales {r.thinking_tokens} son thinking)" if r.thinking_tokens else ""
    print(f"  tokens       : {r.input_tokens} in / {r.output_tokens} out{thinking}")
    print(f"  latencia     : {r.latency_s:.2f} s")
    print(f"  costo        : USD {r.cost_usd:.7f}")
    print(f"  finish_reason: {r.finish_reason}\n")


def main() -> None:
    proveedores = config.proveedores_disponibles()
    print(f"Modo: {'MOCK (simulado)' if config.MOCK else 'APIs reales'} · proveedores: {proveedores}\n")

    oa001 = consulta("OA-001")["texto"]
    oa007 = consulta("OA-007")["texto"]

    # 1.1 — El contrato: misma función, misma forma de respuesta, distinto proveedor
    print("=" * 70)
    print(f"1.1 Contrato unificado · OA-001: {oa001!r}")
    print("=" * 70)
    for p in proveedores:
        mostrar(ask(p, oa001))

    # 1.2 — Sampling: temperature baja = consistente; alta = variada
    p = proveedores[0]
    print("=" * 70)
    print(f"1.2 Sampling · OA-001 tres veces con cada temperature ({p})")
    print("=" * 70)
    for temperature in (0.0, 1.0):
        print(f"  temperature={temperature}")
        for i in range(3):
            r = ask(p, oa001, temperature=temperature)
            print(f"    #{i + 1}: {r.text[:90]}...")
        print()

    # 1.3 — max_tokens: techo de salida. OA-007 (3 preguntas) no entra en 40 tokens
    print("=" * 70)
    print("1.3 max_tokens=40 sobre OA-007 (la consulta de 3 preguntas)")
    print("=" * 70)
    for p in proveedores:
        r = ask(p, oa007, max_tokens=40)
        aviso = "  ← CORTADA: la respuesta quedó incompleta" if r.finish_reason == "length" else ""
        print(f"  [{p}] finish_reason={r.finish_reason} · {r.output_tokens} tokens out{aviso}")
        print(f"    {r.text}\n")

    # 1.4 — Solo Gemini: el "thinking" se cobra como output y se come max_tokens
    if "gemini" in proveedores:
        print("=" * 70)
        print(f"1.4 Gemini thinking_level · OA-001 ({config.MODELOS['gemini']})")
        print("=" * 70)
        original = config.GEMINI_THINKING_LEVEL
        for nivel, techo in (("minimal", 300), ("medium", 300), ("high", 60)):
            config.GEMINI_THINKING_LEVEL = nivel
            r = ask("gemini", oa001, max_tokens=techo)
            print(f"  thinking_level={nivel:<8} max_tokens={techo:<4} → {r.output_tokens:>3} out "
                  f"({r.thinking_tokens:>3} thinking) · USD {r.cost_usd:.7f} · {r.finish_reason} · "
                  f"texto: {r.text[:45]!r}")
        config.GEMINI_THINKING_LEVEL = original
        print("  → El pasajero no ve el thinking, pero se paga. Y con poco max_tokens puede quedar SIN respuesta.")


if __name__ == "__main__":
    main()
