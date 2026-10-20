"""
PASO 4 — Tabla comparativa: costo, latencia y calidad por proveedor (entregable).

Corre las 10 consultas contra cada proveedor, con streaming (para medir TTFT y usage)
y con reintentos. El costo sale SIEMPRE del usage real.
Ejecutar:
    uv run python -m pasos.paso4_comparativa
    uv run python -m pasos.paso4_comparativa --max-tokens 120 --escala 50000
"""
import argparse
import csv
import statistics
from pathlib import Path

import tiktoken

from orbitair import config
from orbitair.cliente import ask_stream
from orbitair.costos import proyectar
from orbitair.datos import SYSTEM_PROMPT, cargar_consultas
from orbitair.reintentos import with_retry

RESULTADOS = Path(__file__).resolve().parent.parent / "resultados"
O200K = tiktoken.get_encoding("o200k_base")


def correr(proveedores: list[str], temperature: float, max_tokens: int) -> list[dict]:
    filas = []
    for p in proveedores:
        print(f"\n▶ {p} ({config.MODELOS[p]})")
        for c in cargar_consultas():
            r = with_retry(lambda: ask_stream(p, c["texto"], temperature=temperature, max_tokens=max_tokens))
            estimado = len(O200K.encode(SYSTEM_PROMPT)) + len(O200K.encode(c["texto"]))
            filas.append({
                "id": c["id"],
                "proveedor": p,
                "modelo": r.model,
                "tokens_in_estimados_tiktoken": estimado,
                "tokens_in": r.input_tokens,
                "tokens_out": r.output_tokens,
                "tokens_thinking": r.thinking_tokens,  # incluidos en tokens_out (solo Gemini)
                "ttft_s": round(r.ttft_s or 0, 3),
                "latencia_s": round(r.latency_s, 3),
                "costo_usd": round(r.cost_usd, 10),
                "finish_reason": r.finish_reason,
                "calidad_1a5": "",  # ← lo completás vos leyendo la respuesta
                "respuesta": r.text.replace("\n", " "),
            })
            corte = " ✂ cortada" if r.finish_reason == "length" else ""
            print(f"  {c['id']}  {r.input_tokens:>4} in / {r.output_tokens:>4} out  "
                  f"ttft {r.ttft_s or 0:.2f}s  total {r.latency_s:.2f}s  USD {r.cost_usd:.7f}{corte}")
    return filas


def resumir(filas: list[dict], escala: int) -> list[dict]:
    resumen = []
    for p in dict.fromkeys(f["proveedor"] for f in filas):
        fs = [f for f in filas if f["proveedor"] == p]
        costo_total = sum(f["costo_usd"] for f in fs)
        costo_medio = costo_total / len(fs)
        resumen.append({
            "proveedor": p,
            "modelo": fs[0]["modelo"],
            "consultas": len(fs),
            "tokens_in": sum(f["tokens_in"] for f in fs),
            "tokens_out": sum(f["tokens_out"] for f in fs),
            "tokens_thinking": sum(f["tokens_thinking"] for f in fs),
            "ttft_medio_s": statistics.mean(f["ttft_s"] for f in fs),
            "latencia_media_s": statistics.mean(f["latencia_s"] for f in fs),
            "latencia_max_s": max(f["latencia_s"] for f in fs),
            "cortadas": sum(f["finish_reason"] == "length" for f in fs),
            "costo_total_usd": costo_total,
            "costo_medio_usd": costo_medio,
            "proyeccion_usd": proyectar(costo_medio, escala),
        })
    return resumen


def tabla_markdown(resumen: list[dict], escala: int) -> str:
    mas_barato = min(r["proyeccion_usd"] for r in resumen)
    lineas = [
        f"| Proveedor | Modelo | Tokens in | Tokens out | (thinking) | TTFT medio | Latencia media | Latencia máx | Cortadas | "
        f"Costo 10 consultas | Costo/consulta | × {escala:,} consultas | vs. más barato | Calidad (1-5) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in resumen:
        lineas.append(
            f"| {r['proveedor']} | {r['modelo']} | {r['tokens_in']} | {r['tokens_out']} | {r['tokens_thinking']} | "
            f"{r['ttft_medio_s']:.2f} s | "
            f"{r['latencia_media_s']:.2f} s | {r['latencia_max_s']:.2f} s | {r['cortadas']} | "
            f"${r['costo_total_usd']:.6f} | ${r['costo_medio_usd']:.7f} | **${r['proyeccion_usd']:.2f}** | "
            f"{r['proyeccion_usd'] / mas_barato:.1f}x | _completar_ |"
        )
    return "\n".join(lineas)


def guardar(filas: list[dict], resumen: list[dict], escala: int, temperature: float, max_tokens: int) -> None:
    RESULTADOS.mkdir(exist_ok=True)
    with open(RESULTADOS / "detalle.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)

    ids = list(dict.fromkeys(f["id"] for f in filas))
    provs = [r["proveedor"] for r in resumen]
    por_consulta = ["| Consulta | " + " | ".join(f"{p} in/out" for p in provs) + " | " + " | ".join(f"{p} USD" for p in provs) + " |",
                    "|---|" + "---:|" * (2 * len(provs))]
    for id_ in ids:
        fs = {f["proveedor"]: f for f in filas if f["id"] == id_}
        celdas_tok = [f"{fs[p]['tokens_in']}/{fs[p]['tokens_out']}" for p in provs]
        celdas_usd = [f"{fs[p]['costo_usd']:.7f}" for p in provs]
        por_consulta.append(f"| {id_} | " + " | ".join(celdas_tok + celdas_usd) + " |")

    md = f"""# OrbitAir — Comparativa de proveedores (entregable C1)

- Modo: {'MOCK (números simulados)' if config.MOCK else 'APIs reales'}
- Parámetros: temperature={temperature}, max_tokens={max_tokens}
- Costo calculado desde el `usage` real de cada respuesta (pricing.json)

## Resumen por proveedor

{tabla_markdown(resumen, escala)}

## Detalle por consulta

{chr(10).join(por_consulta)}

## Calidad

Abrí `detalle.csv`, leé cada respuesta y completá `calidad_1a5` (1 = inútil o inventa datos,
5 = correcta, breve y deriva a un humano cuando corresponde). Pasá el promedio a la tabla.

## Recomendación (completar)

- ¿Qué proveedor elegirías para la primera respuesta de OrbitAir y por qué?
- ¿La diferencia de costo a {escala:,} consultas justifica la diferencia de calidad/latencia?
- ¿Qué consultas se cortaron por max_tokens y qué harías con ellas?
"""
    (RESULTADOS / "comparativa.md").write_text(md, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Paso 4 — comparativa de proveedores")
    ap.add_argument("--proveedores", nargs="+", default=None)
    ap.add_argument("--temperature", type=float, default=config.TEMPERATURE)
    ap.add_argument("--max-tokens", type=int, default=config.MAX_TOKENS)
    ap.add_argument("--escala", type=int, default=10_000, help="consultas para la proyección")
    args = ap.parse_args()

    proveedores = args.proveedores or config.proveedores_disponibles()
    print(f"Modo: {'MOCK (simulado)' if config.MOCK else 'APIs reales'} · temperature={args.temperature} · max_tokens={args.max_tokens}")

    filas = correr(proveedores, args.temperature, args.max_tokens)
    resumen = resumir(filas, args.escala)

    print("\n" + tabla_markdown(resumen, args.escala))
    guardar(filas, resumen, args.escala, args.temperature, args.max_tokens)
    print(f"\n✔ Guardado en {RESULTADOS / 'comparativa.md'} y {RESULTADOS / 'detalle.csv'}")


if __name__ == "__main__":
    main()
