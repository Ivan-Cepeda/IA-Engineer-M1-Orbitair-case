"""
PASO 5 — Comparativa de todas las versiones + changelog (entregable).

Ejecutar:
    uv run python -m pasos.paso5_comparativa
    uv run python -m pasos.paso5_comparativa --repeticiones 3 --temperature 1.0
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orbitair import config
from orbitair.datos import cargar_consultas, cargar_etiquetas
from orbitair.evaluacion import evaluar, resumir
from orbitair.prompts import versiones
from pasos.comun import proveedor, tabla_resumen, titulo

RESULTADOS = Path(__file__).resolve().parent.parent / "resultados"


def main() -> None:
    ap = argparse.ArgumentParser(description="Paso 5 — comparativa de versiones del prompt")
    ap.add_argument("--versiones", nargs="+", default=None)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--repeticiones", type=int, default=1, help=">1 para medir consistencia")
    ap.add_argument("--escala", type=int, default=10_000)
    args = ap.parse_args()

    p = proveedor()
    etiquetas = cargar_etiquetas()
    todas = []
    resumenes = {"dev": [], "holdout": []}
    for v in args.versiones or versiones():
        for lote in ("dev", "holdout"):
            filas = evaluar(v, p, cargar_consultas(lote), etiquetas,
                            temperature=args.temperature, repeticiones=args.repeticiones)
            todas += filas
            resumenes[lote].append(resumir(filas, args.escala))
            print(f"  ✔ {v:<9} {lote:<8} exactitud {resumenes[lote][-1]['exactitud']:.0%}")

    md = [f"# OrbitAir — Comparativa de versiones del prompt de triage (entregable C2)\n",
          f"- Modo: {'MOCK (simulado)' if config.MOCK else 'APIs reales'} · proveedor: {p} ({config.MODELOS[p]})",
          f"- temperature={args.temperature} · repeticiones={args.repeticiones}\n"]
    for lote in ("dev", "holdout"):
        titulo(f"\nLote {lote}")
        tabla = tabla_resumen(resumenes[lote], args.escala)
        print(tabla)
        md += [f"## Lote {lote}\n", tabla, ""]

    md += ["## Decisión (completar)\n",
           "- ¿Qué versión pasa a producción y por qué (exactitud en holdout × costo × consistencia)?",
           "- ¿La diferencia entre la mejor y la segunda justifica su costo a la escala de OrbitAir?",
           "- ¿Qué error sigue sin resolver y qué cambiarías en la próxima versión?",
           "- Copiá los números al `prompts/CHANGELOG.md` (campo Resultado de cada versión)."]

    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "comparativa_prompts.md").write_text("\n".join(md), encoding="utf-8")
    with open(RESULTADOS / "detalle_prompts.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(todas[0]))
        w.writeheader()
        w.writerows(todas)
    print(f"\n✔ Guardado en {RESULTADOS / 'comparativa_prompts.md'} y detalle_prompts.csv")


if __name__ == "__main__":
    main()
