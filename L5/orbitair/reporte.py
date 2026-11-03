# reporte.py — CLASE 5, paso 5.6: un reporte que se lee sin correr nada.
# Responde tres preguntas: ¿qué se evaluó? ¿quién queda descartado por el umbral? ¿el mejor score es el mejor costo?
from metricas import UMBRAL_MINIMO, chequear_regresion

VOLUMEN_MENSUAL = 100_000  # consultas/mes de OrbitAir: el costo se decide a escala, no por llamada


def generar_reporte(resultados: dict[str, dict], dataset: list[dict], juez: dict | None = None) -> str:
    n = len(dataset)
    dificiles = sum(c["dificultad"] != "facil" for c in dataset)
    cats = list(next(iter(resultados.values()))["scores_por_categoria"])
    lines = [
        "# Reporte de evaluación · Triage OrbitAir",
        "",
        "## 1. Qué se evaluó",
        f"- Dataset: `data/eval_dataset.json` · {n} casos · {dificiles} ambiguos o difíciles · "
        f"{n // len(cats)} por categoría.",
        f"- Versiones: {', '.join(resultados)} · temperature 0 · umbral mínimo por categoría: {UMBRAL_MINIMO:.0%}.",
        "",
        "## 2. Score por categoría (exact match)",
        "",
        "| Versión | " + " | ".join(cats) + " | Total |",
        "|---|" + "---:|" * (len(cats) + 1),
    ]
    for v, r in resultados.items():
        celdas = [f"{r['scores_por_categoria'][c]:.0%}" + (" ⚠" if r["scores_por_categoria"][c] < UMBRAL_MINIMO else "")
                  for c in cats]
        lines.append(f"| {v} | " + " | ".join(celdas) + f" | **{r['score_total']:.0%}** |")

    lines += ["", "## 3. Umbral, costo y decisión", "",
              "| Versión | Categorías bajo umbral | Costo por acierto | USD / mes a escala | Tokens out | Latencia |",
              "|---|---|---:|---:|---:|---:|"]
    for v, r in resultados.items():
        bajo = chequear_regresion(r["scores_por_categoria"])
        marca = ", ".join(f"{c} ({r['scores_por_categoria'][c]:.0%})" for c in bajo) if bajo else "ninguna"
        mes = r["costo_total"] / r["n"] * VOLUMEN_MENSUAL
        lines.append(f"| {v} | {marca} | ${r['costo_por_acierto']:.6f} | ${mes:,.2f} | "
                     f"{r['tokens_out_prom']:.0f} | {r['latencia_prom']:.2f}s |")

    if juez:
        lines += ["", "## 4. Razonamiento (LLM-as-judge, solo versiones con razonamiento)", "",
                  f"- Juez validado contra {juez['validacion_n']} casos humanos: acuerdo **{juez['validacion']:.0%}**.",
                  f"- {juez['version']}: razonamiento aplica el criterio en **{juez['tasa']:.0%}** de los casos.",
                  f"- Discrepancias exact match vs. juez: {juez['discrepancias'] or 'ninguna'}."]

    candidatas = {v: r for v, r in resultados.items() if not chequear_regresion(r["scores_por_categoria"])}
    lines += ["", "## Conclusión", ""]
    if candidatas:
        mejor_score = max(candidatas, key=lambda v: candidatas[v]["score_total"])
        mas_barata = min(candidatas, key=lambda v: candidatas[v]["costo_por_acierto"])
        lines.append(f"- Pasan el umbral: {', '.join(candidatas)}. Mejor score: **{mejor_score}**. "
                     f"Mejor costo por acierto: **{mas_barata}**.")
        if mejor_score != mas_barata:
            a, b = candidatas[mejor_score], candidatas[mas_barata]
            extra = (a["costo_total"] / a["n"] - b["costo_total"] / b["n"]) * VOLUMEN_MENSUAL
            lines.append(f"- Elegir {mejor_score} sobre {mas_barata} cuesta ${extra:,.2f}/mes más por "
                         f"{a['score_total'] - b['score_total']:+.0%} de score.")
    else:
        lines.append("- Ninguna versión pasa el umbral en todas las categorías.")
    lines.append("- **Decisión (completar a mano):** qué versión queda vigente y por qué, citando los números de arriba.")
    return "\n".join(lines) + "\n"
