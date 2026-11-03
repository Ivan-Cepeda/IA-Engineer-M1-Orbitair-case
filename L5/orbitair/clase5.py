# clase5.py — CLASE 5: métricas y evals. Elegir la versión de prompt con DATOS, no a ojo.
# Ejecutar:  python clase5.py            (corre la suite contra Gemini y guarda results/)
#            python clase5.py --sin-api  (recalcula todo desde los .jsonl guardados, costo 0)
#            python clase5.py --hasta=5.3 (se detiene después de ese paso; combinable con --sin-api)
import json
import sys
from collections import Counter
from pathlib import Path

from juez import extraer_razonamiento, juzgar_razonamiento, validar_juez
from metricas import UMBRAL_MINIMO, chequear_regresion, exact_match, resumir
from registro import RESULTS, guardar_corrida, leer_corrida, registrar
from reporte import generar_reporte
from triage import clasificar

sys.stdout.reconfigure(encoding="utf-8")
SIN_API = "--sin-api" in sys.argv
HASTA = next((a.split("=")[1] for a in sys.argv if a.startswith("--hasta=")), "9")


def fin(paso: str):
    """--hasta=5.3 corta después de ese paso: en clase se avanza de a uno."""
    if paso >= HASTA:
        sys.exit(0)


VERSIONES = ["v1", "v2", "v3", "v4"]  # v4 = v3 + chain-of-thought: la única con razonamiento para juzgar
dataset = json.loads(Path("data/eval_dataset.json").read_text(encoding="utf-8"))

# 5.1 — Un registro: la misma llamada de siempre, guardada como dato
print("=== 5.1 Registro estructurado ===")
if not SIN_API:
    caso = dataset[0]
    categoria, r = clasificar(caso["texto"], "v2")
    fila = registrar(caso, "v2", categoria, r)
    print(json.dumps({k: v for k, v in vars(fila).items() if k != "timestamp"}, ensure_ascii=False, indent=2))
print("→ input + referencia + salida + costo en la MISMA fila: exact match y el juez leen de acá.\n")
fin("5.1")

# 5.2 — El dataset: ¿sirve para medir o solo para probar que el código corre?
print("=== 5.2 Dataset de evaluación ===")
print(f"casos: {len(dataset)}")
print(f"por categoría : {dict(Counter(c['categoria_esperada'] for c in dataset))}")
print(f"por dificultad: {dict(Counter(c['dificultad'] for c in dataset))}")
print(f"ejemplo: {dataset[24]['id']} · {dataset[24]['texto']!r} → {dataset[24]['categoria_esperada']} "
      f"(nota: {dataset[24]['nota']})")
print("→ Referencia fijada ANTES de correr, categorías parejas, más difíciles que en producción.\n")
fin("5.2")

# 5.3 — La suite: cada versión contra todo el dataset, exact match por categoría
print("=== 5.3 Suite · exact match ===")
resultados = {}
for v in VERSIONES:
    if SIN_API:
        registros = leer_corrida(v)
    else:
        registros = [registrar(c, v, *clasificar(c["texto"], v)) for c in dataset]
        guardar_corrida(registros, v)
    resultados[v] = resumir(registros)
    errores = [f"{r.caso_id}→{r.categoria_obtenida}" for r in registros if not exact_match(r.categoria_obtenida, r.categoria_esperada)]
    print(f"{v}: {resultados[v]['score_total']:.0%}  errores={errores}")
print()
cats = list(resultados["v1"]["scores_por_categoria"])
print(f"{'':<4}" + "".join(f"{c[:12]:>14}" for c in cats))
for v, r in resultados.items():
    print(f"{v:<4}" + "".join(f"{r['scores_por_categoria'][c]:>14.0%}" for c in cats))
print("→ Mirá la columna, no solo el total: el promedio esconde la categoría floja.\n")
fin("5.3")

# 5.4 — LLM-as-judge: primero se valida el juez, después se juzga el razonamiento de v4
print("=== 5.4 LLM-as-judge ===")
path_juez = RESULTS / "juez_v4.jsonl"
if SIN_API:
    meta, *juicios = [json.loads(l) for l in path_juez.read_text(encoding="utf-8").splitlines()]
else:
    val = validar_juez()
    for d in val["detalle"]:
        print(f"  {d['id']}: humano={d['humano']:<3} juez={d['juez']}  {'✔' if d['humano'] == d['juez'] else '✘'}  {d['motivo'][:70]}")
    meta = {"validacion": val["acuerdo"], "validacion_n": len(val["detalle"])}
    juicios = []
    for reg, caso in zip(leer_corrida("v4"), dataset):
        j = juzgar_razonamiento(caso["texto"], caso["criterio"], extraer_razonamiento(reg.respuesta))
        juicios.append({"caso_id": reg.caso_id, "exact_match": exact_match(reg.categoria_obtenida, reg.categoria_esperada), **j})
    path_juez.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [meta, *juicios]) + "\n", encoding="utf-8")
print(f"acuerdo juez vs. humano: {meta['validacion']:.0%} ({meta['validacion_n']} casos)")
tasa = sum(j["veredicto"] == "si" for j in juicios) / len(juicios)
discrepancias = [f"{j['caso_id']} (EM {'✔' if j['exact_match'] else '✘'}, juez {j['veredicto']})"
                 for j in juicios if j["exact_match"] != (j["veredicto"] == "si")]
print(f"v4 · razonamiento aplica el criterio: {tasa:.0%}")
for j in juicios:
    if j["exact_match"] != (j["veredicto"] == "si"):
        print(f"  discrepancia {j['caso_id']}: exact_match={j['exact_match']} juez={j['veredicto']} · {j['motivo'][:80]}")
print("→ Que no coincidan no es un bug: acertó 'por patrón', o falló con un razonamiento defendible.\n")
fin("5.4")

# 5.5 — Umbral: ¿alguna versión queda descartada?
print(f"=== 5.5 Umbral mínimo por categoría: {UMBRAL_MINIMO:.0%} ===")
for v, r in resultados.items():
    bajo = chequear_regresion(r["scores_por_categoria"])
    print(f"{v}: {'✔ candidata' if not bajo else '✘ descartada · ' + ', '.join(bajo)}  (total {r['score_total']:.0%})")
print()
fin("5.5")

# 5.6 — Reporte: costo por acierto y decisión
print("=== 5.6 Reporte ===")
juez_info = {"version": "v4", "tasa": tasa, "discrepancias": ", ".join(discrepancias), **meta}
reporte = generar_reporte(resultados, dataset, juez_info)
(RESULTS / "reporte_eval.md").write_text(reporte, encoding="utf-8")
print(reporte)
print(f"→ Guardado en {RESULTS / 'reporte_eval.md'}")
