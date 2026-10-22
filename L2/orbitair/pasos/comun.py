"""Utilidades compartidas por los Pasos de L2: imprimir tablas y elegir proveedor."""
import sys
from pathlib import Path

# Permite correr los pasos también como `python pasos/pasoX.py` o desde la carpeta pasos/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orbitair import config  # noqa: E402


def proveedor() -> str:
    """El primer proveedor disponible (en mock: openai). Con solo GEMINI_API_KEY: gemini."""
    p = config.proveedores_disponibles()[0]
    print(f"Modo: {'MOCK (simulado)' if config.MOCK else 'APIs reales'} · proveedor: {p} ({config.MODELOS[p]})\n")
    return p


def titulo(texto: str) -> None:
    print("=" * 78)
    print(texto)
    print("=" * 78)


def tabla_resumen(resumenes: list[dict], escala: int = 10_000) -> str:
    lineas = [
        f"| Versión | Exactitud | Inválidas | Parseo frágil | Consistencia | Tokens in | Tokens out | Latencia | Costo/consulta | × {escala:,} |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in resumenes:
        lineas.append(
            f"| {r['version']} | {r['exactitud']:.0%} ({round(r['exactitud'] * r['n'])}/{r['n']}) | {r['invalidas']} | "
            f"{r['parseo_fragil']} | {r['consistencia']:.0%} | {r['tokens_in_medio']:.0f} | {r['tokens_out_medio']:.0f} | "
            f"{r['latencia_media_s']:.2f} s | ${r['costo_medio_usd']:.7f} | ${r['proyeccion_usd']:.2f} |"
        )
    return "\n".join(lineas)


def mostrar_errores(filas: list[dict]) -> None:
    errs = [f for f in filas if not f["acierto"]]
    if not errs:
        print("  ✔ sin errores")
    for f in errs:
        regla = f" [{f['regla']}]" if f["regla"] else ""
        print(f"  ✘ {f['id']}{regla}: esperada={f['esperada']:<22} obtenida={f['obtenida'] or '(sin parsear)'}")
