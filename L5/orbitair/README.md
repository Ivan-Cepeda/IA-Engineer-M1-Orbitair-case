# L5 · Métricas y evals — elegir el prompt con datos

> **En una frase:** armamos una **suite de evaluación** (30 casos, umbral por categoría, un LLM que juzga y costo
> por acierto) para elegir entre v1, v2, v3 y v4 con números, no con "esta parece mejor".

En L2 elegimos el prompt mirando 10 consultas. Hoy esa decisión se toma con método. Es la última clase de M1.

```
registrar (5.1) → dataset (5.2) → exact match (5.3) ─┐
                                  LLM-as-judge (5.4) ┼→ umbral (5.5) → reporte + costo por acierto (5.6)
```

## Vocabulario mínimo

| Término | Qué es |
|---|---|
| **Eval** | Correr el sistema sobre casos con respuesta conocida y medir cuántos acierta |
| **Exact match** | La categoría del modelo es **exactamente** la de referencia. Sirve para salidas cerradas |
| **LLM-as-judge** | Otro LLM puntúa algo que no se puede comparar exacto (por ejemplo, si un razonamiento es correcto) |
| **Umbral por categoría** | Piso mínimo (70 %) que **cada** categoría debe superar, no solo el promedio |
| **Costo por acierto** | Costo total ÷ aciertos. Une calidad y precio en un número |

## Archivos

| Archivo | Qué hace | ¿Llama a la API? |
|---|---|---|
| `llm.py`, `triage.py`, `prompts/` | Copiados de L4 | sí |
| `registro.py` | Guarda cada corrida en `results/eval_<versión>.jsonl` (no se pisan) | no |
| `data/eval_dataset.json` | 30 casos, 6 por categoría, la mitad difíciles, cada uno con su `nota` y `criterio` | — |
| `metricas.py` | Exact match, desglose por categoría, `UMBRAL_MINIMO = 0.70`, regresiones, costo por acierto | no |
| `juez.py` + `data/juez_humano.json` | El juez (Gemini, temperature 0) y 6 casos puntuados por una persona para validarlo | sí |
| `reporte.py` | Escribe `results/reporte_eval.md` | no |
| `clase5.py` | La demo, pasos 5.1 a 5.6 | sí (o `--sin-api`) |
| `test_metricas.py` | 6 tests sin API | no |
| `ejemplos/juez_proveedores.py` | El mismo juez con OpenAI y Claude (referencia) | opcional |

## Cómo correrlo

```bash
pip install -r requirements.txt
```

Copiar `.env.example` como `.env` y pegar la key.

```bash
python test_metricas.py
```

```bash
python clase5.py --hasta=5.1
```

- `--hasta=5.x` corta después de ese paso, para avanzar de a uno en clase.
- Sin el flag corre todo: 150 llamadas, unos 2 minutos, menos de USD 0.01.
- `--sin-api` recalcula todo desde `results/*.jsonl` sin llamar al modelo (plan B si falla la red o la cuota).

## Los 6 pasos

| Paso | Archivo | Idea |
|---|---|---|
| 5.1 | `registro.py` | Entrada, referencia, salida y costo en la misma fila. Cada versión, su archivo |
| 5.2 | `data/eval_dataset.json` | La referencia la fija una persona **antes** de correr. Casos difíciles y categorías parejas |
| 5.3 | `metricas.py` | Exact match, mirando el desglose por categoría y no solo el total |
| 5.4 | `juez.py` | El juez evalúa el razonamiento de v4. **Primero se valida el juez** contra un humano |
| 5.5 | `metricas.py` | Si alguna categoría queda bajo 70 %, la versión se descarta |
| 5.6 | `reporte.py` | Qué se evaluó, quién queda descartado y si el mejor score es también el mejor costo |

## Resultado real (`gemini-3.1-flash-lite`, temperature 0)

| Versión | equipaje | cambios | reembolsos | serv. especiales | otros | Total | Costo por acierto | USD/mes (100k) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v1 | 67 % ⚠ | 83 % | 83 % | 83 % | **0 % ⚠** | 63 % | $0.000039 | $2.48 |
| v2 | 83 % | 83 % | 100 % | 100 % | 100 % | 93 % | $0.000048 | $4.51 |
| v3 | 83 % | 100 % | 100 % | 100 % | 100 % | **97 %** | $0.000065 | $6.28 |
| v4 (CoT) | 83 % | 83 % | 83 % | 83 % | 100 % | 87 % | $0.000149 | $12.89 |

## Qué nos dice

1. **v1 se descarta por el umbral, no por el promedio.** Su prompt no tiene categoría "otros", así que ahí saca 0 %.
2. **v3 tiene el mejor score y v2 el mejor costo por acierto.** Pasar de v2 a v3 cuesta USD 1.77/mes más por 3 puntos. No hay una respuesta única: se decide mirando los dos números juntos.
3. **v4 (chain-of-thought) es la más cara y acierta menos.** "Pensar" no mejoró este triage.
4. **El juez coincide 100 % con el humano** en los 6 casos de control, y considera que el razonamiento de v4 es correcto en el 83 % de los casos.
5. **Exact match y el juez discrepan en 5 casos.** Por ejemplo, EVAL-005 (cochecito) falla en exact match, pero el razonamiento es defendible.
6. **EVAL-005 lo fallan todas las versiones** y aun así **no se cambia la referencia** después de ver los resultados. Hacerlo sería acomodar el examen a las respuestas.

## Otros proveedores

`ejemplos/juez_proveedores.py` tiene el mismo juez para tres SDKs. Solo cambia la llamada:

| | Gemini | OpenAI | Claude |
|---|---|---|---|
| System prompt | `system_instruction=` | mensaje `role: system` | parámetro `system=` |
| Límite de salida | `max_output_tokens` | `max_completion_tokens` | `max_tokens` (obligatorio) |
| Texto | `r.text` | `r.choices[0].message.content` | bloques `r.content` de tipo `text` |
| Tokens | `usage_metadata.prompt_token_count` | `usage.prompt_tokens` | `usage.input_tokens` |

Buena práctica: usar como juez un modelo de **otro proveedor**, para que un modelo no se apruebe a sí mismo.

## Frameworks (para después)

**promptfoo** y **OpenAI Evals** automatizan suites como esta; **RAGAS** agrega métricas para sistemas con
búsqueda de documentos. Conviene armarlo a mano primero: un framework esconde qué cuenta como acierto, qué juez usa y con qué prompt.
