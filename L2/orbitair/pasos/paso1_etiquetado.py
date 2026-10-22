"""
PASO 1 — Etiquetar el dataset: sin respuestas correctas no hay forma de medir un prompt.

Ejecutar:
    uv run python -m pasos.paso1_etiquetado
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orbitair.datos import cargar_consultas, cargar_etiquetas
from orbitair.prompts import CATEGORIAS
from pasos.comun import titulo


def main() -> None:
    consultas = cargar_consultas()
    etiquetas = cargar_etiquetas()

    titulo("1.1 Categorías (variable de contexto, no parte de la plantilla)")
    for nombre, descripcion in CATEGORIAS.items():
        print(f"  {nombre:<22} {descripcion}")

    titulo("\n1.2 Validación de las etiquetas")
    faltan = [c["id"] for c in consultas if c["id"] not in etiquetas]
    invalidas = [i for i, e in etiquetas.items() if e["categoria"] not in CATEGORIAS]
    print(f"  consultas sin etiqueta: {faltan or 'ninguna'}")
    print(f"  etiquetas fuera de CATEGORIAS: {invalidas or 'ninguna'}")

    titulo("\n1.3 Dataset etiquetado")
    for lote in ("dev", "holdout"):
        print(f"\n  Lote {lote} {'(se usa para DISEÑAR el prompt)' if lote == 'dev' else '(se usa SOLO para medir al final)'}")
        for c in cargar_consultas(lote):
            e = etiquetas[c["id"]]
            regla = f"[{e['regla']}]" if e["regla"] else "    "
            print(f"  {c['id']} {regla} {e['categoria']:<22} {c['texto'][:60]}...")

    titulo("\n1.4 Distribución por categoría")
    for lote in ("dev", "holdout"):
        conteo = Counter(etiquetas[c["id"]]["categoria"] for c in cargar_consultas(lote))
        print(f"  {lote:<8} " + " · ".join(f"{k}={conteo.get(k, 0)}" for k in CATEGORIAS))
    print("\n  → El lote dev NO tiene ningún 'otro': un prompt sin cajón puede parecer perfecto en dev")
    print("    y fallar en producción. Por eso existe el holdout.")

    titulo("\n1.5 Casos ambiguos (los que van a decidir qué versión del prompt gana)")
    for c in consultas:
        e = etiquetas[c["id"]]
        if e["regla"]:
            print(f"  {c['id']} {e['regla']} → {e['categoria']:<22} {e['justificacion']}")


if __name__ == "__main__":
    main()
