# OrbitAir · Clase 5 — Métricas y evals: elegir el prompt con datos

En C2 elegimos entre v1, v2, v3 y v4 mirando una tabla de 10 consultas y con "esta parece mejor".
Hoy esa decisión se toma con una **suite de evaluación**: dataset curado, exact match, LLM-as-judge,
umbral por categoría y un reporte con costo por acierto. Es la última clase de M1.

```
registro (5.1) → dataset (5.2) → exact match (5.3) ─┐
                                  LLM-as-judge (5.4) ┼→ umbral (5.5) → reporte + costo por acierto (5.6)
```

| Archivo | Qué hace | ¿Llama a la API? |
|---|---|---|
| `llm.py`, `triage.py`, `prompts/` | Copiados de L4 (C1 y C2): `ask()` ya mide tokens, costo y latencia | sí |
| `registro.py` | `RegistroEval`, `registrar`, `guardar_corrida` / `leer_corrida` (.jsonl por versión) | no |
| `data/eval_dataset.json` | 30 casos, 6 por categoría, 50 % ambiguos o difíciles, con `nota` y `criterio` | — |
| `metricas.py` | `exact_match`, desglose por categoría, `UMBRAL_MINIMO`, `chequear_regresion`, `costo_por_acierto` | no |
| `juez.py` + `data/juez_humano.json` | LLM-as-judge (Gemini, temperature 0) + validación contra 6 casos puntuados por un humano | sí |
| `reporte.py` | `results/reporte_eval.md`: qué se evaluó, quién queda bajo el umbral y costo por acierto | no |
| `clase5.py` | La demo, pasos 5.1 a 5.6 | sí (o `--sin-api`) |
| `test_metricas.py` | 6 tests sin API | no |
| `ejemplos/juez_proveedores.py` | El mismo juez con **OpenAI** y **Claude** (referencia) | opcional |

## Cómo se corre

```bash
pip install -r requirements.txt
```

Copiar `.env.example` como `.env` y pegar la key (igual que en L1–L4).

```bash
python test_metricas.py
```

```bash
python clase5.py --hasta=5.1
```

`--hasta=5.x` corta después de ese paso, para avanzar de a uno en clase. Sin el flag corre todo:
150 llamadas, alrededor de 2 minutos y menos de USD 0.01. `--sin-api` recalcula todo desde
`results/*.jsonl` sin llamar al modelo. Es el plan B si falla la red o la cuota.

## Corrida real (`gemini-3.1-flash-lite`, temperature 0)

| Versión | equipaje | cambios | reembolsos | serv. especiales | otros | Total | Costo por acierto | USD/mes (100k) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v1 | 67 % ⚠ | 83 % | 83 % | 83 % | **0 % ⚠** | 63 % | $0.000039 | $2.48 |
| v2 | 83 % | 83 % | 100 % | 100 % | 100 % | 93 % | $0.000048 | $4.51 |
| v3 | 83 % | 100 % | 100 % | 100 % | 100 % | **97 %** | $0.000065 | $6.28 |
| v4 (CoT) | 83 % | 83 % | 83 % | 83 % | 100 % | 87 % | $0.000149 | $12.89 |

Qué muestra la corrida:
- **v1 queda descartada por el umbral**, no por el promedio. Su prompt no tiene "otros", así que esa categoría da 0 %.
- **v3 tiene el mejor score y v2 el mejor costo por acierto.** Pasar de v2 a v3 cuesta USD 1.77/mes más por +3 puntos. La lección no dice cuál elegir: dice que se decide mirando los dos números juntos.
- **v4, con chain-of-thought, es más cara (43 tokens de salida contra 5) y acierta menos.** "Pensar" no mejoró este triage.
- **El juez coincide 100 % con el humano** en los 6 casos de validación. Juzga que el razonamiento de v4 aplica el criterio en el 83 % de los casos.
- **Hay 5 discrepancias entre exact match y el juez.** Por ejemplo, EVAL-005 (cochecito) falla en exact match, pero el razonamiento es defendible.
- **EVAL-005 lo fallan todas las versiones.** No hay que cambiar la referencia ahora que vimos la salida: esa es la trampa de la sección "Datasets".

## Pasos

| Paso | Archivo | Idea |
|---|---|---|
| 5.1 | `registro.py` | Input, referencia, salida y costo van en la misma fila. Cada versión tiene su propio `.jsonl`, que no se pisa. |
| 5.2 | `data/eval_dataset.json` | Una referencia humana fijada antes de correr. Casos difíciles, tamaño suficiente y categorías parejas. |
| 5.3 | `metricas.py` | Exact match para salidas cerradas. Hay que mirar el desglose por categoría, no solo el total. |
| 5.4 | `juez.py` | LLM-as-judge solo para el razonamiento de v4, contra un `criterio`. Primero se valida el juez. |
| 5.5 | `metricas.py` | `UMBRAL_MINIMO = 0.70` por categoría. Regresión = una categoría bajo el piso. |
| 5.6 | `reporte.py` | Responde tres preguntas: qué se evaluó, quién queda descartado y si el mejor score es también el mejor costo. |

## Otros proveedores

`ejemplos/juez_proveedores.py` tiene el mismo juez escrito para tres SDKs. El prompt, el parseo y la validación
no cambian. Solo cambia la llamada:

| | Gemini (clase) | OpenAI | Claude |
|---|---|---|---|
| system | `system_instruction=` en el config | mensaje `{"role": "system"}` | parámetro `system=` |
| límite de salida | `max_output_tokens` | `max_completion_tokens` | `max_tokens` (obligatorio) |
| texto | `r.text` | `r.choices[0].message.content` | bloques `r.content` de tipo `text` |
| tokens | `usage_metadata.prompt_token_count` | `usage.prompt_tokens` | `usage.input_tokens` |

Una buena práctica es usar como juez un modelo de **otro proveedor** que el evaluado, para reducir el sesgo de que un modelo se apruebe a sí mismo.

## Frameworks (para después)

**promptfoo** y **OpenAI Evals** corren la suite y comparan versiones con exact match y LLM-as-judge.
**RAGAS** formaliza *faithfulness* y *answer relevancy*. Conviene armarlo a mano primero: un framework esconde
qué cuenta como coincidencia, qué juez usa y con qué prompt.
