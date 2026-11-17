# L1 · Cómo funciona un LLM — OrbitAir

> **En una frase:** construimos un cliente que habla igual con OpenAI, Anthropic y Gemini, y lo usamos para
> medir **cuánto cuesta, cuánto tarda y qué tan bien responde** cada proveedor.

## El caso

OrbitAir quiere que un LLM dé la **primera respuesta** a sus pasajeros. Antes de elegir proveedor necesita números:

| Pregunta del negocio | Cómo la respondemos | Paso |
|---|---|---|
| ¿Puedo cambiar de proveedor sin reescribir todo? | Una sola función `ask(provider, prompt)` que siempre devuelve lo mismo | 1 |
| ¿Por qué la misma consulta cuesta distinto? | Tokens: el idioma, los emojis y el tokenizador cambian la cuenta | 2 |
| ¿El pasajero va a sentir que es lento? | Streaming: medir cuándo aparece la primera palabra (TTFT) | 3a |
| ¿Qué pasa si el proveedor nos limita? | Reintentos con espera creciente (backoff) | 3b |
| **¿Cuál conviene?** | Tabla comparativa con costo real × 10.000 consultas | 4 |

**Dataset:** 10 consultas de pasajeros en [data/consultas.json](data/consultas.json), cada una elegida por un motivo
(OA-003 en inglés, OA-004 con emojis, OA-007 larga con 3 preguntas, OA-009 con una marca inventada, OA-010 sensible).

> **La idea central:** el costo se calcula **siempre** con los tokens que informa la API (`usage`), nunca a ojo.
> Y "USD 0.0004" recién significa algo cuando se multiplica por 10.000 consultas.

---

## Cómo correrlo

```bash
uv sync
```

```bash
cp .env.example .env
```

(Con pip: `python -m venv .venv`, activar y `pip install -r requirements.txt`. En PowerShell: `Copy-Item .env.example .env`.)

En el `.env`:
- `ORBITAIR_MOCK=1` → **todo simulado, sin API keys**. Ideal para seguir la clase.
- `ORBITAIR_MOCK=0` → APIs reales. Se usan solo los proveedores que tengan key; alcanza con `GEMINI_API_KEY`.

```bash
uv run pytest -q
```

Esperado: `21 passed`. Después, un script por paso:

```bash
uv run python -m pasos.paso1_cliente
```

```bash
uv run python -m pasos.paso2_tokens
```

```bash
uv run python -m pasos.paso3a_streaming
```

```bash
uv run python -m pasos.paso3b_rate_limits
```

```bash
uv run python -m pasos.paso4_comparativa
```

> La primera vez se descargan los tokenizadores (necesita internet). El de Gemini tarda ~15 s en cargar.

---

## Paso 1 — Un cliente, tres proveedores

**Qué se construye:** [orbitair/cliente.py](orbitair/cliente.py). La función `ask()` recibe el proveedor y el
prompt, y devuelve siempre un `LLMResponse`:

```python
@dataclass
class LLMResponse:
    provider: str          # "openai" | "anthropic" | "gemini"
    model: str             # el modelo exacto (define el precio)
    text: str              # lo que lee el pasajero
    input_tokens: int      # del usage de la API
    output_tokens: int     # del usage de la API
    latency_s: float       # medida solo alrededor de la llamada
    cost_usd: float        # calculado desde el usage
    finish_reason: str     # "stop" (terminó) | "length" (se cortó)
    ttft_s: float | None = None     # solo en streaming
    thinking_tokens: int = 0        # Gemini: razonamiento interno, se cobra
```

**Por qué hace falta:** cada SDK hace lo mismo de forma distinta. Un **adaptador** por proveedor
(`_openai()`, `_anthropic()`, `_gemini()`) esconde esas diferencias para que el resto del código no las vea:

| | OpenAI | Anthropic | Gemini |
|---|---|---|---|
| System prompt | mensaje `role: system` | parámetro `system=` | `system_instruction=` en el config |
| Límite de salida | `max_tokens` (opcional) | `max_tokens` (**obligatorio**) | `max_output_tokens` (**incluye el thinking**) |
| Texto | `choices[0].message.content` | lista de bloques `content` | `r.text` |
| Se cortó | `"length"` | `"max_tokens"` | `MAX_TOKENS` (enum) |

**Tres experimentos del script:**
- **`temperature`:** con 0 las respuestas casi no cambian; con 1 varían. Atender pasajeros no es creativo → default `0.2`.
- **`max_tokens=40`:** el modelo **no resume, corta a mitad de frase**. La brevedad se pide en el prompt; `max_tokens` es solo un techo. Siempre revisar `finish_reason`.
- **Thinking de Gemini:** con `thinking_level=medium` la misma respuesta cuesta 3.5 veces más. Y con un `max_tokens` chico el razonamiento se come todo el espacio: **se paga y el pasajero recibe un texto vacío**. Por eso el default es `minimal`.

**Comprobá un costo a mano:** `(98 / 1M × 0.40) + (43 / 1M × 1.60) = USD 0.0001080` (OpenAI, modo mock).

---

## Paso 2 — Tokens: por qué la misma idea cuesta distinto

**Qué es un token:** un pedazo de palabra. "¿Puedo" son 3 tokens (`¿` `P` `uedo`); en inglés casi cada palabra es 1.

| Hallazgo | Ejemplo | Consecuencia |
|---|---|---|
| El español usa más tokens que el inglés | La misma frase: 6 tokens en inglés, 8 en español | Un centro de atención en español paga 10–35 % más |
| Los emojis son caros | OA-004: 34 tokens con emojis, 19 sin | Casi duplican el costo de entrada |
| Cada tokenizador corta distinto | Gemini tiene 😡 como 1 token, pero parte "778" en `7` `7` `8` | No hay un factor de conversión universal |
| Comparar textos distintos engaña | OA-010 (español) rinde mejor que OA-003 (inglés) | Para comparar idiomas hay que usar **el mismo significado** |

**Cómo contar tokens en cada proveedor:**

| Proveedor | Antes de llamar (para presupuestar) | Después (para facturar) |
|---|---|---|
| OpenAI | `tiktoken` (local) | `r.usage` |
| Gemini | `LocalTokenizer` (local) o `count_tokens()` (API, gratis) | `r.usage_metadata` |
| Anthropic | `messages.count_tokens()` (API) | `r.usage` |

La cuenta "antes" es una estimación para validar y presupuestar. **La que vale para facturar es la de después.**

---

## Paso 3a — Streaming

**Idea:** el streaming no hace más rápida la respuesta, hace más rápida **la primera palabra**. Una respuesta de
1 s que empieza a mostrarse a los 0.3 s se siente rápida. Eso es el **TTFT** (time to first token).

**Dónde viene el conteo de tokens en streaming:**

| | Cómo llega | Si te equivocás… |
|---|---|---|
| OpenAI | En el último fragmento, **solo si** pedís `stream_options={"include_usage": True}` | **Costo 0 sin ningún error** |
| Anthropic | Al cerrar el stream (`get_final_message()`) | No hay conteo si no lo cerrás |
| Gemini | En cada fragmento, ya acumulado | Si los sumás, cobrás de más |

**El bug silencioso:** sin `include_usage`, OpenAI informa costo cero y un dashboard lo mostraría como "gratis".
Por eso `LLMResponse` tiene `usage_disponible`.

**Medir bien:** el cronómetro (`time.perf_counter()`) va **solo** alrededor de la llamada. Si incluye los
`print`, la latencia se duplica (2.83 s medidos mal contra 1.19 s medidos bien).

---

## Paso 3b — Rate limits y reintentos

**Qué se construye:** `with_retry()` en [orbitair/reintentos.py](orbitair/reintentos.py).

| Error | Qué significa | Qué hacer |
|---|---|---|
| **429** | Demasiadas llamadas | Esperar y reintentar |
| **5xx** | El proveedor falló | Reintentar pocas veces |
| **400, 401…** | Tu pedido está mal | **No reintentar**: no se arregla solo |

- **Backoff exponencial:** esperar 1 s, 2 s, 4 s, 8 s…
- **Jitter:** sumar un poco de azar, para que 1.000 pasajeros no reintenten en el mismo milisegundo.
- **Retry-After:** si el proveedor dice cuánto esperar, **manda él**. (En Gemini viene dentro del JSON del error, no en un header.)
- Se apagan los reintentos internos de los SDK (`max_retries=0`) para controlarlos nosotros y verlos en el log.

Con la key gratuita de Gemini los 429 aparecen de verdad en el Paso 4. En modo mock se simulan con `ORBITAIR_MOCK_FAIL_RATE=0.2`.

---

## Paso 4 — La comparativa (entregable)

Corre las 10 consultas con cada proveedor (streaming + reintentos) y proyecta a 10.000 consultas.

Resultado en modo mock:

| Proveedor | Modelo | TTFT medio | Latencia media | Costo/consulta | **× 10.000** |
|---|---|---:|---:|---:|---:|
| openai | gpt-4.1-mini | 0.35 s | 0.66 s | $0.0001247 | **$1.25** |
| anthropic | claude-haiku-4-5 | 0.50 s | 1.07 s | $0.0004901 | **$4.90** |
| gemini | gemini-3.1-flash-lite | 0.40 s | 0.65 s | $0.0001003 | **$1.00** |

Genera `resultados/comparativa.md` (tablas) y `resultados/detalle.csv` (una fila por consulta, con una
columna `calidad_1a5` para puntuar a mano).

**Cómo leer la tabla:**
- El precio por token no alcanza: Anthropic usa más tokens para el mismo texto. **Hay que comparar costo por consulta.**
- El token de salida cuesta 4–5 veces más que el de entrada: una frase de cortesía extra se paga 10.000 veces.
- El costo sin calidad no decide nada: revisar OA-009 (¿inventó datos?) y OA-010 (¿derivó a un humano?).

Variantes: `--escala 300000` (otro volumen), `--max-tokens 60` (¿cuáles se cortan?), `--temperature 1.0`.

**El entregable** es `resultados/comparativa.md` con: la calidad puntuada, un costo recalculado a mano,
la proyección, qué consultas se cortaron y una recomendación de 3–5 líneas (costo × latencia × calidad).

---

## Errores comunes

| Síntoma | Causa |
|---|---|
| Anthropic pide `max_tokens` | Es obligatorio en Anthropic |
| Gemini devuelve texto vacío con `MAX_TOKENS` | El thinking se comió el límite: bajar `thinking_level` o subir el techo |
| El costo da 0 en streaming | Falta `include_usage` en OpenAI |
| `KeyError: ... no está en pricing.json` | Se cambió el modelo en `.env` y no su precio (mejor que falle a que cueste 0) |
| Latencia sospechosamente alta | El `print` quedó adentro del cronómetro |
| Claude ignora el system prompt | Se mandó dentro de `messages` en vez de `system=` |

## Archivos

```
orbitair/
├── pricing.json          ← precios en USD por 1M de tokens
├── data/consultas.json   ← OA-001 … OA-010
├── orbitair/             ← la librería: cliente, costos, reintentos, tokenizadores, mock
├── pasos/                ← un script por paso
├── resultados/           ← lo que genera el Paso 4
└── tests/
```

## Para practicar

1. Probar un modelo más barato (`gpt-4.1-nano`) o más caro (`claude-sonnet-4-5`). ¿La calidad acompaña el precio?
2. Escribir `ask_con_fallback()`: si un proveedor agota sus reintentos, pasar al siguiente.
3. Hacer que el Paso 4 falle si alguna respuesta llegó sin `usage`, en vez de sumar ceros.

## Para quien da la clase

| Bloque | Tiempo | Clave |
|---|---|---|
| Setup | 10 min | Sin keys → `ORBITAIR_MOCK=1` |
| Paso 1 | 25 min | **Imprescindible.** Diseñar `LLMResponse` en grupo antes de mostrar el código |
| Paso 2 | 20 min | Mostrar la trampa OA-003 vs OA-010 |
| Paso 3a | 15 min | No saltear el bug de `include_usage` |
| Paso 3b | 15 min | El más recortable: alcanza con la demo |
| Paso 4 | 25 min | **Imprescindible.** Cerrar con × 10.000 y la discusión de calidad |

**Siguiente clase (L2):** de *cómo se llama* al modelo a *qué se le dice*: el prompt.
