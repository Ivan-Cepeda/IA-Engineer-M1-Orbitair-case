"""
PASO 4 — Chain-of-thought con última línea parseable: ¿mejora lo suficiente para pagar su costo?

Ejecutar:
    uv run python -m pasos.paso4_chain_of_thought
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orbitair.clasificacion import clasificar, parsear
from orbitair.datos import cargar_consultas, cargar_etiquetas, consulta
from orbitair.evaluacion import evaluar, resumir
from pasos.comun import mostrar_errores, proveedor, tabla_resumen, titulo


def main() -> None:
    p = proveedor()

    titulo("4.1 Una respuesta con razonamiento (OA-007, la de 3 preguntas)")
    r = clasificar(p, "v4", consulta("OA-007")["texto"])
    print(r.respuesta.text)
    print(f"\n  → el código solo lee la última línea: categoria={r.categoria} (método: {r.metodo})")

    titulo("\n4.2 El parser frente a salidas reales (y mal formadas)")
    for salida in [
        '{"categoria": "equipaje"}',
        "Tema: ...\nPide: ...\nDecisión: ...\nCATEGORIA: millas",
        "Tema: ...\nCATEGORIA: millas\nEspero haber ayudado 😊",
        "Diría que es un tema de equipaje o quizás de reembolsos_cobros",
    ]:
        print(f"  {salida!r:<70} → {parsear(salida)}")
    print("  → Si el modelo agrega texto DESPUÉS de la línea CATEGORIA, el contrato se rompe y solo lo")
    print("    'salva' la heurística (frágil). Por eso el prompt exige 'la ÚLTIMA línea debe ser")
    print("    exactamente…', y en C3 la salida pasa a validarse con un contrato de datos.")

    titulo("\n4.3 v3 vs v4 en dev y en holdout")
    etiquetas = cargar_etiquetas()
    resumenes = []
    for lote in ("dev", "holdout"):
        for v in ("v3", "v4"):
            filas = evaluar(v, p, cargar_consultas(lote), etiquetas)
            resumen = resumir(filas)
            resumen["version"] = f"{v} · {lote}"
            resumenes.append(resumen)
            print(f"  Errores {v} · {lote}:")
            mostrar_errores(filas)
    print()
    print(tabla_resumen(resumenes))

    v3, v4 = resumenes[2], resumenes[3]  # holdout
    print(f"\n  → v4 usa {v4['tokens_out_medio'] / v3['tokens_out_medio']:.0f}x tokens de salida y cuesta "
          f"{v4['proyeccion_usd'] / v3['proyeccion_usd']:.1f}x a 10.000 consultas.")
    print("  → La pregunta no es '¿mejoró?' sino '¿mejoró lo suficiente para justificar el costo?'")


if __name__ == "__main__":
    main()
