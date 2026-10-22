"""
PASO 3 — Few-shot: los ejemplos salen de los errores reales, no de la intuición.

Ejecutar:
    uv run python -m pasos.paso3_few_shot
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orbitair.datos import cargar_consultas, cargar_etiquetas
from orbitair.evaluacion import evaluar, resumir
from pasos.comun import mostrar_errores, proveedor, tabla_resumen, titulo


def main() -> None:
    p = proveedor()
    dev, etiquetas = cargar_consultas("dev"), cargar_etiquetas()

    titulo("3.1 ¿Dónde se equivoca v2? (los candidatos a ejemplo few-shot)")
    v2 = evaluar("v2", p, dev, etiquetas)
    mostrar_errores(v2)
    for f in v2:
        if not f["acierto"]:
            print(f"    {f['id']}: {etiquetas[f['id']]['justificacion']}")

    titulo("\n3.2 Dos maneras de agregar ejemplos: obvios vs. sacados de los errores")
    resultados = {"v2": v2}
    for v in ("v3_obvio", "v3"):
        resultados[v] = evaluar(v, p, dev, etiquetas)
    print(tabla_resumen([resumir(f) for f in resultados.values()]))

    for v in ("v3_obvio", "v3"):
        print(f"\n  Errores de {v}:")
        mostrar_errores(resultados[v])

    r2, r3 = resumir(resultados["v2"]), resumir(resultados["v3"])
    print(f"\n  → v3_obvio paga tokens extra y no corrige nada: sus ejemplos eran casos que v2 ya acertaba.")
    print(f"  → v3 corrige los errores de v2 a cambio de +{r3['tokens_in_medio'] - r2['tokens_in_medio']:.0f} tokens "
          f"de input por consulta ({r3['tokens_in_medio'] / r2['tokens_in_medio']:.1f}x).")


if __name__ == "__main__":
    main()
