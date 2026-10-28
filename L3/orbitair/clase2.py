# clase2.py — CLASE 2: context engineering (system prompt, few-shot, chain-of-thought, versionado)
# Ejecutar:  python clase2.py
import sys

from triage import cargar_prompt, clasificar, evaluar

sys.stdout.reconfigure(encoding="utf-8")

# 2.2 — La plantilla renderizada (lo que recibe el modelo)
print("=== 2.2 System prompt v2 renderizado ===")
print(cargar_prompt("v2"))

# 2.3 — v1 vs v2 con una consulta que no encaja en ninguna categoría
print("=== 2.3 La prueba del cajón: '¿Tienen wifi a bordo?' ===")
for v in ("v1", "v2"):
    categoria, r = clasificar("¿Tienen wifi a bordo?", v)
    print(f"{v}: respuesta={r.text.strip()!r} → categoria={categoria}")
print()

# 2.4 — Comparar todas las versiones contra las etiquetas
print("=== 2.4 Evaluación de todas las versiones ===")
resultados = []
for v in ("v1", "v2", "v3_intuicion", "v3", "v4"):
    print(f"-- {v}")
    resultados.append(evaluar(v))

print(f"\n{'versión':<14}{'exactitud':>10}{'tokens out':>12}{'USD × 10.000':>14}")
for r in resultados:
    print(f"{r['version']:<14}{r['exactitud']:>10.0%}{r['tokens_out']:>12.0f}{r['costo_10k']:>14.2f}")
print("\n→ Copiá estos números a prompts/CHANGELOG.md y elegí una versión con criterio: exactitud × costo.")
