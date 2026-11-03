# Reporte de evaluación · Triage OrbitAir

## 1. Qué se evaluó
- Dataset: `data/eval_dataset.json` · 30 casos · 15 ambiguos o difíciles · 6 por categoría.
- Versiones: v1, v2, v3, v4 · temperature 0 · umbral mínimo por categoría: 70%.

## 2. Score por categoría (exact match)

| Versión | equipaje | cambios | reembolsos | servicios_especiales | otros | Total |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 67% ⚠ | 83% | 83% | 83% | 0% ⚠ | **63%** |
| v2 | 83% | 83% | 100% | 100% | 100% | **93%** |
| v3 | 83% | 100% | 100% | 100% | 100% | **97%** |
| v4 | 83% | 83% | 83% | 83% | 100% | **87%** |

## 3. Umbral, costo y decisión

| Versión | Categorías bajo umbral | Costo por acierto | USD / mes a escala | Tokens out | Latencia |
|---|---|---:|---:|---:|---:|
| v1 | equipaje (67%), otros (0%) | $0.000039 | $2.48 | 9 | 0.75s |
| v2 | ninguna | $0.000048 | $4.51 | 5 | 1.02s |
| v3 | ninguna | $0.000065 | $6.28 | 5 | 0.74s |
| v4 | ninguna | $0.000149 | $12.89 | 43 | 0.87s |

## 4. Razonamiento (LLM-as-judge, solo versiones con razonamiento)

- Juez validado contra 6 casos humanos: acuerdo **100%**.
- v4: razonamiento aplica el criterio en **83%** de los casos.
- Discrepancias exact match vs. juez: EVAL-004 (EM ✔, juez no), EVAL-005 (EM ✘, juez si), EVAL-015 (EM ✘, juez si), EVAL-025 (EM ✔, juez no), EVAL-026 (EM ✔, juez no).

## Conclusión

- Pasan el umbral: v2, v3, v4. Mejor score: **v3**. Mejor costo por acierto: **v2**.
- Elegir v3 sobre v2 cuesta $1.77/mes más por +3% de score.
- **Decisión (completar a mano):** qué versión queda vigente y por qué, citando los números de arriba.
