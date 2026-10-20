# Caso práctico OrbitAir — M1 · L1 «Cómo funciona un LLM»

> **Lección base:** Tokenización y context window · Sampling · Familias de modelos y APIs ·
> Streaming · Rate limits · Costo por token.
> Esta guía lleva cada concepto de la lección a una línea de código, en 4 Pasos.
> Proveedores soportados: **OpenAI, Anthropic y Gemini**. Alcanza con la key de **uno** (o ninguna, en modo mock).

---

## 0. De qué va el caso y por qué importa

**OrbitAir** es una aerolínea que quiere reemplazar la **primera respuesta humana** de su centro de
atención por un LLM. Antes de firmar con un proveedor necesita **números concretos**:

| Pregunta del negocio | Cómo la respondemos | Paso |
|---|---|---|
| ¿Podemos cambiar de proveedor sin reescribir todo? | Un contrato único `ask(provider, prompt) → LLMResponse` | 1 |
| ¿Por qué la misma consulta cuesta distinto? | Tokenización: idioma, emojis, tokenizador | 2 |
| ¿El pasajero va a sentir que es lento? | Streaming y TTFT | 3a |
| ¿Qué pasa cuando el proveedor nos limita? | Backoff exponencial + Retry-After | 3b |
| **¿Cuánto cuesta, cuánto tarda y qué tan bien responde?** | Tabla comparativa con usage real × 10.000 | 4 |

### El dataset: 10 consultas diseñadas a propósito

Están en [data/consultas.json](data/consultas.json) y **todavía no tienen etiquetas** (eso se hace en C2).

| ID | Por qué está en el dataset |
|---|---|
| **OA-001** | Ancla: español, muy corta. Referencia para todo lo demás. |
| OA-002 | Español medio, con código de vuelo y ciudades. |
| **OA-003** | **Inglés**: el tokenizador está optimizado para ese idioma. |
| **OA-004** | **Emojis**: peor ratio caracteres/token. |
| OA-005 | Política frecuente, respuesta corta. |
| OA-006 | Tildes y paréntesis. |
| **OA-007** | **La más larga, 3 preguntas en una**: para streaming y `max_tokens`. |
| OA-008 | Español informal con errores (“kiero”, “xq”). |
| OA-009 | Marca inventada (OrbitPlus): riesgo de que el modelo invente datos. |
| OA-010 | Consulta sensible (menor de edad): exige cautela. |

### La idea que atraviesa toda la clase

> **El costo se calcula SIEMPRE desde el `usage` real de la API, nunca se estima.**
> Y multiplicar por 10.000 consultas es lo que convierte un «USD 0.0004» en una decisión de negocio.

---

## Mapa: concepto de la lección → archivo

| Concepto | Dónde se ve |
|---|---|
| Token, tokenizador, `tiktoken` | [pasos/paso2_tokens.py](pasos/paso2_tokens.py) |
| Contar tokens por proveedor (tiktoken, LocalTokenizer de Gemini, APIs) | [orbitair/tokenizadores.py](orbitair/tokenizadores.py) · `paso2_tokens.py` 2.6 y 2.7 |
| Thinking tokens (Gemini) | `paso1_cliente.py` sección 1.4 · `LLMResponse.thinking_tokens` |
| Context window y presupuesto | `paso2_tokens.py` sección 2.5 |
| `temperature`, `max_tokens` | [pasos/paso1_cliente.py](pasos/paso1_cliente.py) secciones 1.2 y 1.3 |
| Multi-proveedor / contrato unificado | [orbitair/cliente.py](orbitair/cliente.py) → `LLMResponse`, `ask()` |
| Streaming, TTFT, `include_usage` | `cliente.py` → `ask_stream()` · [pasos/paso3a_streaming.py](pasos/paso3a_streaming.py) |
| 429 / 5xx, backoff, jitter, Retry-After | [orbitair/reintentos.py](orbitair/reintentos.py) · [pasos/paso3b_rate_limits.py](pasos/paso3b_rate_limits.py) |
| Costo por token | [orbitair/costos.py](orbitair/costos.py) · [pricing.json](pricing.json) |
| Tabla comparativa (entregable) | [pasos/paso4_comparativa.py](pasos/paso4_comparativa.py) → `resultados/` |
| Modo sin API keys | [orbitair/mock.py](orbitair/mock.py) |
| Tests | [tests/test_orbitair.py](tests/test_orbitair.py) |

```
orbitair/
├── .env.example          ← copiar como .env
├── pricing.json          ← precios USD / 1M tokens
├── data/consultas.json   ← OA-001 … OA-010
├── orbitair/             ← la librería que construimos
│   ├── config.py         ← lee el .env
│   ├── datos.py          ← dataset + system prompt
│   ├── costos.py         ← calcular_costo(), proyectar()
│   ├── cliente.py        ← LLMResponse, ask(), ask_stream()
│   ├── reintentos.py     ← with_retry()
│   ├── tokenizadores.py  ← tiktoken + tokenizador local de Gemini
│   └── mock.py           ← proveedores simulados
├── pasos/                ← un script por Paso de la clase
└── tests/
```

---

## Paso 0 — Setup (10 min)

> **Antes de arrancar, todos tienen que haber corrido el setup.** Quien no tenga API keys sigue
> la clase entera con `ORBITAIR_MOCK=1`. **La tokenización con tiktoken es real igual en modo mock.**

### Opción A — con `uv` (recomendada)

```bash
uv sync
```

```bash
cp .env.example .env
```

(En PowerShell: `Copy-Item .env.example .env`)

### Opción B — con `pip`

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

(macOS / Linux: `source .venv/bin/activate`)

```bash
pip install -r requirements.txt
```

### Configurar el `.env`

```ini
ORBITAIR_MOCK=1                 # 1 = simulado, 0 = APIs reales
OPENAI_API_KEY=sk-...           # solo si ORBITAIR_MOCK=0
ANTHROPIC_API_KEY=sk-ant-...    # solo si ORBITAIR_MOCK=0
GEMINI_API_KEY=AIza...          # solo si ORBITAIR_MOCK=0 · https://aistudio.google.com/apikey
OPENAI_MODEL=gpt-4.1-mini
ANTHROPIC_MODEL=claude-haiku-4-5
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_THINKING_LEVEL=minimal   # minimal | low | medium | high
ORBITAIR_TEMPERATURE=0.2
ORBITAIR_MAX_TOKENS=300
```

En modo real, **los scripts usan solo los proveedores que tienen key**. Con solo `GEMINI_API_KEY`
se puede hacer toda la clase contra Gemini real (las secciones exclusivas de OpenAI/Anthropic se saltean solas).

> **¿Por qué `gemini-3.1-flash-lite`?** Es el Gemini más barato de la familia 3.x (USD 0.25 / 1.50 por 1M),
> tiene tier gratuito y el SDK trae su **tokenizador local**. Para comparar contra un modelo “flash” completo:
> `GEMINI_MODEL=gemini-3.8-flash` (ojo: su tokenizador no está en el SDK, el Paso 2 lo avisa).

### Verificar que todo anda

```bash
uv run pytest -q
```

Esperado: `21 passed`. (Con pip: `python -m pytest -q`.)

> ⚠ La primera vez que se usa `tiktoken` descarga el archivo del encoding, y el tokenizador local de Gemini
> descarga su vocabulario (necesita internet una vez). Cargar el de Gemini tarda **~15 s por proceso**;
> después cuenta en microsegundos.

> En los comandos de abajo se usa `uv run python ...`. Con pip y el venv activado, reemplazalo por `python ...`.

---

## Paso 1 — Cliente multi-proveedor con contrato unificado (parte A) · *no negociable*

### 🎯 Objetivo
Que el resto de OrbitAir llame a **una sola función** y reciba **siempre el mismo objeto**,
hable con OpenAI, con Anthropic, con Gemini o con el mock.

### 🧠 Lo que dice la lección
- Un sistema de producción **no depende de un solo proveedor** (caídas, deprecaciones, precios).
- El valor del patrón Router **no es la clase Router, es el contrato** que imponen los proveedores.
- En este hands-on el contrato es más simple: **`ask(provider, prompt)` → `LLMResponse`**.

### 1.1 Primero, el contrato: `LLMResponse`

Antes de escribir una sola llamada a una API, decidí **qué necesita saber OrbitAir** de cada respuesta.
Pensá la respuesta 2 minutos y después mirá [orbitair/cliente.py](orbitair/cliente.py):

```python
@dataclass
class LLMResponse:
    provider: str          # "openai" | "anthropic" | "gemini"
    model: str             # el modelo exacto: define el precio
    text: str              # lo que lee el pasajero
    input_tokens: int      # ← del usage de la API
    output_tokens: int     # ← del usage de la API
    latency_s: float       # medida con perf_counter SOLO alrededor de la llamada
    cost_usd: float        # calculado desde el usage, nunca estimado
    finish_reason: str     # normalizado: "stop" | "length"
    ttft_s: float | None = None        # solo streaming (Paso 3a)
    thinking_tokens: int = 0           # Gemini: "razonamiento" interno, YA incluido en output_tokens
    usage_disponible: bool = True      # False = el proveedor no informó usage (Paso 3a)
    mock: bool = False
```

**¿Por qué cada campo?**
- `model` y no solo `provider`: el precio depende del modelo (`gpt-4.1-mini` ≠ `gpt-4.1-nano`).
- `finish_reason` **normalizado**: OpenAI dice `"length"`, Anthropic `"max_tokens"`, Gemini `FinishReason.MAX_TOKENS`.
  Para OrbitAir es lo mismo: *la respuesta quedó cortada*. El contrato absorbe la diferencia.
- `cost_usd` viene incluido: nadie fuera del cliente tiene que saber la fórmula.
- `thinking_tokens` aparece **porque llegó Gemini**: un proveedor nuevo puede obligarte a ampliar el contrato.
  Se agregó con valor por defecto `0`, así que OpenAI y Anthropic no tuvieron que cambiar nada.

### 1.2 Las asimetrías que el cliente tiene que esconder

| | OpenAI | Anthropic | Gemini (`google-genai`) |
|---|---|---|---|
| Método | `client.chat.completions.create(...)` | `client.messages.create(...)` | `client.models.generate_content(...)` |
| Entrada | `messages=[...]` | `messages=[...]` | `contents=...` (texto o partes) |
| System prompt | un mensaje más: `{"role": "system"}` | parámetro aparte: `system=...` | en la config: `system_instruction=...` |
| Parámetros | sueltos | sueltos | agrupados en `config=GenerateContentConfig(...)` |
| Techo de salida | `max_tokens` (opcional) | `max_tokens` (**obligatorio**) | `max_output_tokens` (**incluye thinking**) |
| Texto | `r.choices[0].message.content` | `r.content` = **lista de bloques** | `r.text` |
| Tokens in | `r.usage.prompt_tokens` | `r.usage.input_tokens` | `r.usage_metadata.prompt_token_count` |
| Tokens out | `r.usage.completion_tokens` | `r.usage.output_tokens` | `candidates_token_count` **+ `thoughts_token_count`** |
| Por qué terminó | `finish_reason` (`stop`/`length`) | `stop_reason` (`end_turn`/`max_tokens`) | `candidates[0].finish_reason` (enum `STOP`/`MAX_TOKENS`) |
| Código del error HTTP | `e.status_code` | `e.status_code` | `e.code` |
| Reintentos del SDK por defecto | 2 | 2 | **ninguno** |

Cada fila es un `if` que **no** tiene que aparecer en el código de negocio. Por eso hay un **adaptador**
por proveedor (`_openai()`, `_anthropic()`, `_gemini()`) que traduce todo a un dict común.

El adaptador de Gemini, completo:

```python
def _gemini(model, system, prompt, temperature, max_tokens) -> dict:
    r = _cliente("gemini").models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,                       # incluye el thinking
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
        ),
    )
    um = r.usage_metadata
    thinking = um.thoughts_token_count or 0
    return {
        "text": r.text or "",
        "input_tokens": um.prompt_token_count,
        "output_tokens": (um.candidates_token_count or 0) + thinking,   # el thinking SE COBRA como output
        "thinking_tokens": thinking,
        "finish_reason": r.candidates[0].finish_reason.name,           # enum → "STOP" / "MAX_TOKENS"
    }
```

### 1.3 Intentalo vos: completá `ask()`

```python
def ask(provider, prompt, *, system=SYSTEM_PROMPT, temperature=None, max_tokens=None) -> LLMResponse:
    model = _validar(provider)                         # ValueError si no existe
    temperature = config.TEMPERATURE if temperature is None else temperature
    max_tokens = config.MAX_TOKENS if max_tokens is None else max_tokens

    t0 = time.perf_counter()
    # TODO 1: si config.MOCK → mock.completar(...); si no → _ADAPTADORES[provider](...)
    latency = time.perf_counter() - t0

    # TODO 2: armar el LLMResponse. El costo con calcular_costo(model, in, out)
    # TODO 3: normalizar finish_reason con el dict _FINISH
```

<details><summary>Ver solución</summary>

Está en [orbitair/cliente.py](orbitair/cliente.py), función `ask()`. Fijate en dos detalles:
1. Entre `t0` y `latency` **no hay ningún print**: solo la llamada.
2. Los clientes del SDK se crean con `max_retries=0`. Los SDK reintentan solos 2 veces por defecto;
   lo apagamos para que los reintentos los controle **nuestro** `with_retry()` (Paso 3b) y se vean.
</details>

### 1.4 Ejecutar

```bash
uv run python -m pasos.paso1_cliente
```

Salida (modo mock):

```
1.1 Contrato unificado · OA-001: '¿Puedo llevar a mi perro en cabina?'
  [openai · gpt-4.1-mini · MOCK]
  tokens       : 98 in / 43 out
  latencia     : 0.70 s
  costo        : USD 0.0001080
  finish_reason: stop

  [anthropic · claude-haiku-4-5 · MOCK]
  tokens       : 115 in / 64 out
  latencia     : 1.18 s
  costo        : USD 0.0004350
  finish_reason: stop

  [gemini · gemini-3.1-flash-lite · MOCK]
  tokens       : 92 in / 44 out
  latencia     : 0.59 s
  costo        : USD 0.0000890
  finish_reason: stop
```

✅ **Verificá a mano un costo** (la fórmula de la lección):
```
openai    (98/1M × 0.40) + (43/1M × 1.60) = 0.0000392 + 0.0000688 = 0.0001080 ✔
anthropic (115/1M × 1.00) + (64/1M × 5.00) = 0.000115 + 0.000320 = 0.0004350 ✔
gemini    (92/1M × 0.25) + (44/1M × 1.50) = 0.000023 + 0.000066 = 0.0000890 ✔
```

### 1.5 Experimento en vivo: sampling (`temperature`)

La sección 1.2 del script manda OA-001 **3 veces** con `temperature=0.0` y 3 veces con `1.0`:

```
  temperature=0.0
    #1: ¡Hola! Gracias por escribir a OrbitAir. Puedes viajar con tu mascota...
    #2: ¡Hola! Gracias por escribir a OrbitAir. Puedes viajar con tu mascota...
    #3: ¡Hola! Gracias por escribir a OrbitAir. Puedes viajar con tu mascota...
  temperature=1.0
    #1: ¡Hola! Gracias por escribir a OrbitAir. Puedes viajar...
    #2: Entendemos tu consulta y queremos ayudarte. Puedes viajar...
    #3: Entendemos tu consulta y queremos ayudarte. Puedes viajar...
```

**Para discutir:**
- Atender pasajeros **no es una tarea creativa**. ¿Qué pasa si el mismo pasajero pregunta dos veces y recibe
  dos políticas distintas? → por eso el default es `temperature=0.2`.
- La lección dice: cambiá `temperature` **o** `top_p`, **nunca los dos**. ¿Por qué?
- Con APIs reales, `temperature=0` reduce mucho la variación, pero **no garantiza** respuestas idénticas.

### 1.6 Experimento en vivo: `max_tokens`

La sección 1.3 manda OA-007 (3 preguntas) con `max_tokens=40`:

```
  [openai] finish_reason=length · 40 tokens out  ← CORTADA: la respuesta quedó incompleta
    ¡Hola! Gracias por escribir a OrbitAir. Si pierdes una conexión ... recibirás la nueva tarjeta de
```

**Para discutir:** el modelo **no resume para entrar en 40 tokens: corta a la mitad de la frase.**
`max_tokens` es un techo de costo y latencia, no una instrucción de brevedad. La brevedad se pide en el
prompt (“máximo 4 frases”) y `max_tokens` es la red de seguridad. Siempre revisá `finish_reason`.

### 1.7 Experimento en vivo (solo Gemini): los tokens de *thinking*

Los Gemini 3.x **razonan internamente antes de responder**. Ese razonamiento no lo ve el pasajero, pero:
1. **se cobra como output** (el token más caro), y
2. **consume `max_output_tokens`** antes de que empiece la respuesta.

La sección 1.4 del script manda OA-001 con distintos `thinking_level`:

```
  thinking_level=minimal  max_tokens=300  →  44 out (  0 thinking) · USD 0.0000890 · stop   · texto: '¡Hola! Gracias por...'
  thinking_level=medium   max_tokens=300  → 194 out (150 thinking) · USD 0.0003140 · stop   · texto: '¡Hola! Gracias por...'
  thinking_level=high     max_tokens=60   →  60 out ( 60 thinking) · USD 0.0001130 · length · texto: ''
```

**Para discutir:**
- Misma respuesta visible, **3.5x el costo** con `medium`. ¿Necesita “pensar” un asistente que responde
  “¿puedo llevar a mi perro?”? → por eso el default del proyecto es `GEMINI_THINKING_LEVEL=minimal`.
- La tercera fila es la trampa: **se pagaron 60 tokens y el pasajero recibió un texto vacío.** Con modelos que
  piensan, un `max_tokens` chico no ahorra: rompe.
- ¿Cuándo sí convendría más thinking? (OA-007, con tres preguntas encadenadas, es candidata. Probalo.)

> En modo mock los tokens de thinking son simulados (0 / 40 / 150 / 250 según nivel). Con la API real,
> `usage_metadata.thoughts_token_count` trae el número verdadero.

### ❌ Errores comunes del Paso 1
| Síntoma | Causa |
|---|---|
| `anthropic` explota pidiendo `max_tokens` | Es obligatorio en Anthropic. |
| Gemini devuelve `text` vacío o `None` con `MAX_TOKENS` | El thinking se comió el `max_output_tokens`. Bajá `thinking_level` o subí el techo. |
| Gemini: `400 INVALID_ARGUMENT` por `thinking_level` | Ese modelo no acepta ese nivel (ej.: `minimal` no existe en todos). Probá `low` o dejalo vacío. |
| Gemini: `TypeError` al comparar `finish_reason` | Es un **enum** (`FinishReason.STOP`), no un string: usá `.name`. |
| El system prompt se ignora en Claude | Se mandó como `{"role": "system"}` dentro de `messages`. Va en `system=`. |
| `KeyError: 'gpt-4o' no está en pricing.json` | Cambiaste el modelo en `.env` y no su precio. **Mejor explotar que costear 0.** |
| `AttributeError: 'list' object has no attribute 'text'` | En Anthropic `r.content` es una lista de bloques. |

### ✔ Checkpoint
- [ ] `ask("openai", ...)`, `ask("anthropic", ...)` y `ask("gemini", ...)` devuelven el mismo tipo de objeto.
- [ ] Sé por qué en Gemini `output_tokens` = respuesta + thinking.
- [ ] Sé explicar por qué `finish_reason` se normaliza.
- [ ] Verifiqué a mano el costo de una llamada.

---

## Paso 2 — Tokenización: idiomas y emojis (parte B)

### 🎯 Objetivo
Entender **qué ve el modelo** antes de cualquier parámetro, y por qué la misma idea cuesta distinto.

### 🧠 Lo que dice la lección
- Un token es una **sub-palabra**: palabra entera, pedazo de palabra o signo.
- Input **y** output cuentan tokens, y ambos suman contra la **context window**.
- `tiktoken` sirve **solo para OpenAI**. La lección dice que Anthropic y Google no tienen equivalente
  local y que sus tokens se leen del `usage` **después** de la llamada.
- **Actualización para Gemini:** hoy el SDK `google-genai` **sí** trae un tokenizador local (experimental).
  El panorama real, por proveedor:

| Proveedor | ¿Contar ANTES de llamar? | ¿Exacto DESPUÉS? |
|---|---|---|
| OpenAI | `tiktoken` (local) | `r.usage` |
| Gemini | `LocalTokenizer` (local, experimental) **o** `client.models.count_tokens()` (API, gratis) | `r.usage_metadata` |
| Anthropic | `client.messages.count_tokens()` (solo API) | `r.usage` |

```bash
uv run python -m pasos.paso2_tokens
```

### 2.1 Las 10 consultas

```
id       chars palabras  tokens chars/tok  cl100k  gemini
OA-001      35        7      11      3.18      13      11
OA-002     112       20      27      4.15      31      28
OA-003     109       22      26      4.19      26      28
OA-004      89       17      34      2.62      42      35   ← el peor ratio: emojis
OA-007     547      100     141      3.88     161     142
OA-009      90       15      22      4.09      26      21
OA-010     129       23      28      4.61      34      29
```

- **`cl100k` vs `o200k`**: el mismo texto, distinto tokenizador (GPT-4 viejo vs GPT-4.1) → distinto conteo.
  OA-004 pasa de 42 a 34 tokens. *Cambiar de modelo puede cambiar tu factura aunque el precio sea igual.*
- **Columna `gemini`**: conteo **real** del tokenizador local de `gemini-3.1-flash-lite` (funciona también en mock).
  Queda muy cerca de `o200k`, pero no igual: a veces más (OA-003), a veces menos (OA-009).
- ⚠ **Trampa de análisis:** OA-010 (español) tiene **mejor** ratio que OA-003 (inglés). ¿Contradice la teoría?
  No: son **textos distintos**. Para comparar idiomas hay que comparar **el mismo significado** → 2.3.

### 2.2 Desarmar las consultas

```
OA-001 (11 tokens): [¿][P][uedo][ llevar][ a][ mi][ perro][ en][ cab][ina][?]
OA-003 (26 tokens): [Hi][,][ I][ was][ charged][ twice][ for][ my][ seat][ upgrade]...
OA-004 (34 tokens): [Per][d][ieron][ mi][ mal][eta]<20 F0 9F 98><A1><F0 9F 98><A1>...
```

- `¿Puedo` se parte en 3 (`¿` `P` `uedo`); en inglés casi cada palabra es **un** token.
- Los `<F0 9F 98>` son **bytes sueltos**: el emoji 😡 no está en el vocabulario y se arma con pedazos
  que, solos, ni siquiera son un carácter válido.

### 2.3 Mismo significado, distinto idioma

```
EN   6 tokens | The payment failed at checkout.
ES   8 tokens | El pago falló en el checkout.            → 1.33x
EN  26 tokens | Hi, I was charged twice for my seat upgrade on flight OA455...
ES  29 tokens | Hola, me cobraron dos veces la mejora de asiento en el vuelo OA455...  → 1.12x
```

El tokenizador se entrenó con un corpus mayormente en inglés → sus sub-palabras “calzan” mejor en inglés.
**Para un centro de atención hispanohablante, cada consulta paga un 10–35 % extra** solo por el idioma.

### 2.4 Emojis

```
  😡    bytes UTF-8= 4  tokens= 2
  🧳    bytes UTF-8= 4  tokens= 3
  ✈️   bytes UTF-8= 6  tokens= 3      ← ✈ + un selector de variación invisible
  a    bytes UTF-8= 1  tokens= 1

  OA-004 con emojis: 34 tokens · sin emojis: 19 tokens
```

Los emojis casi **duplican** el costo de input de OA-004. No es motivo para borrarlos (¡transmiten que el
pasajero está furioso!), pero sí para saber de dónde sale el número.

### 2.5 Estimar antes de llamar y presupuesto de contexto

```
OA-007: system+consulta ≈ 221 tokens + max_tokens 300 = 521 (0.407% de una ventana de 128,000)
        costo máximo estimado en gpt-4.1-mini: USD 0.0005684
```

- Esto es una **cota** (peor caso), útil para **validar antes de enviar** y para presupuestar.
- **No es el costo.** En el Paso 4, el CSV tiene la columna `tokens_in_estimados_tiktoken` al lado de
  `tokens_in` real: el real siempre es un poco mayor (los roles y separadores del formato chat también son tokens).
- Hoy entramos sobradísimos en la ventana. ¿Y si OrbitAir mandara el historial completo del pasajero y
  los 500 artículos de ayuda en cada llamada? → resúmenes, RAG (M2), ventana deslizante.

### 2.6 Gemini: tres formas de contar tokens

**a) Local, sin key y sin costo** — `LocalTokenizer` del SDK (requiere el extra `google-genai[local-tokenizer]`,
ya incluido en las dependencias):

```python
from google.genai.local_tokenizer import LocalTokenizer

tk = LocalTokenizer(model_name="gemini-3.1-flash-lite")
tk.count_tokens("¿Puedo llevar a mi perro en cabina?").total_tokens        # → 11
tk.compute_tokens("¿Puedo llevar a mi perro en cabina?").tokens_info[0].tokens  # → las piezas, en bytes
```

Salida del script:
```
  OA-001 · Gemini 11 tokens vs o200k 11
    gemini: [¿][Pued][o][ llevar][ a][ mi][ perro][ en][ cab][ina][?]
    o200k : [¿][P][uedo][ llevar][ a][ mi][ perro][ en][ cab][ina][?]

  OA-004 · Gemini 35 tokens vs o200k 34
    gemini: [Per][d][ieron][ mi][ mal][eta][ ][😡][😡][ llevo]...[ vuelo][ OA][7][7][8][ ][✈][️]...
    o200k : [Per][d][ieron][ mi][ mal][eta]<20 F0 9F 98><A1><F0 9F 98><A1>[ llevo]...[ vuelo][ OA][778]...
```

**Para discutir:** mismo total en OA-001, pero **cortes distintos** (`Pued|o` vs `P|uedo`). En OA-004,
Gemini tiene 😡 como **un** token (su vocabulario es más grande), pero parte los números **dígito a dígito**
(`7|7|8`). Cada tokenizador gana y pierde en lugares distintos → no hay “factor de conversión” universal.

Limitaciones: es **experimental**, solo texto, solo los modelos que el SDK conoce (por ejemplo
`gemini-3.8-flash` todavía no está; el script lo avisa), y la primera carga tarda ~15 s.

**b) Vía API, exacto y gratis** — con `ORBITAIR_MOCK=0` y `GEMINI_API_KEY`:

```python
client.models.count_tokens(model="gemini-3.1-flash-lite", contents=texto).total_tokens
```

Es una llamada de red (latencia, y cuenta para el rate limit de requests), pero no cobra tokens.
El script compara API vs local vs tiktoken para OA-001, OA-003 y OA-004.

**c) Después de la llamada** — `r.usage_metadata`: `prompt_token_count` (incluye el system prompt),
`candidates_token_count` (la respuesta) y `thoughts_token_count` (el thinking). **Esta es la única fuente
para facturar.** Las dos anteriores sirven para validar y presupuestar *antes* de gastar.

### 2.7 Anthropic: contar vía API

Con `ORBITAIR_MOCK=0` y `ANTHROPIC_API_KEY`, el script llama a `client.messages.count_tokens(...)` para
OA-001, OA-003 y OA-004 y lo compara con tiktoken: **el mismo texto da otro número**. Esa asimetría
(uno estima local, otro vía API, todos informan después) es justo lo que el cliente unificado tiene que absorber.

### ✔ Checkpoint
- [ ] Sé explicar por qué OA-004 tiene el peor ratio chars/token.
- [ ] Sé por qué comparar OA-003 contra OA-010 es un error de análisis.
- [ ] Sé por qué `tiktoken` no sirve para estimar el costo en Claude ni en Gemini.
- [ ] Sé las 3 formas de contar tokens en Gemini y cuál es la que vale para facturar.

---

## Paso 3a — Streaming (parte C)

> ⏱ Si el tiempo aprieta, el Paso 3 es el más recortable. Pero el error de `include_usage` (3a.3) **sí** hay que verlo.

### 🎯 Objetivo
Separar **latencia percibida (TTFT)** de **latencia real**, y no perder el costo en el camino.

### 🧠 Lo que dice la lección
- `stream=True` entrega **deltas**: fragmentos incrementales que hay que **concatenar**.
- Una respuesta de 8 s que empieza a los 400 ms **se siente rápida**.
- **OpenAI no manda `usage` en streaming salvo que se pida** `stream_options={"include_usage": True}`.
- **Anthropic** entrega el usage **al cerrar el stream** (`get_final_message()`).
- **Gemini** (`generate_content_stream`) manda `usage_metadata` en **cada** chunk, acumulado:
  vale el del último. No hace falta pedir nada, pero tampoco hay que **sumar** los de cada chunk.

| | Cómo llega el usage en streaming | Si te olvidás de algo… |
|---|---|---|
| OpenAI | Último chunk (con `choices` vacío), **solo si** `include_usage` | costo 0 sin error |
| Anthropic | Al cerrar: `stream.get_final_message().usage` | no hay usage si no cerrás el stream |
| Gemini | En cada chunk, acumulado | si los sumás, cobrás de más |

### 3a.1 Intentalo vos: el adaptador de OpenAI en streaming

```python
def _openai_stream(model, system, prompt, temperature, max_tokens, incluir_usage):
    kwargs = dict(model=model, messages=[...], temperature=temperature,
                  max_tokens=max_tokens, stream=True)
    # TODO 1: si incluir_usage, agregar stream_options

    usage, finish = None, None
    for chunk in _cliente("openai").chat.completions.create(**kwargs):
        # TODO 2: si chunk.choices no está vacío → yield {"delta": ...} y guardar finish_reason
        # TODO 3: si chunk.usage → guardarlo (llega en el ÚLTIMO chunk, que viene con choices vacío)
    yield {"usage": usage, "finish_reason": finish}
```

<details><summary>Ver solución y la trampa</summary>

Está en [orbitair/cliente.py](orbitair/cliente.py) (`_openai_stream`). La trampa: el chunk final que trae
el `usage` llega con `choices = []`, así que `chunk.choices[0]` sin el `if chunk.choices:` explota con
`IndexError` **justo cuando activás `include_usage`**.
</details>

La versión Gemini (`_gemini_stream`) es más corta, porque no hay que pedir el usage:

```python
for chunk in client.models.generate_content_stream(model=model, contents=prompt, config=cfg):
    if chunk.text:
        yield {"delta": chunk.text}
    if chunk.usage_metadata:
        usage = _usage_gemini(chunk.usage_metadata)   # se PISA: es acumulado, no se suma
```

Y en `ask_stream()`, el TTFT se toma con el **primer** delta:

```python
t0 = time.perf_counter()
for ev in eventos:
    if "delta" in ev:
        if ttft is None:
            ttft = time.perf_counter() - t0      # ← primer token visible
        ...
latency = time.perf_counter() - t0 - tiempo_en_callbacks   # ← sin contar nuestros prints
```

### 3a.2 Ejecutar

```bash
uv run python -m pasos.paso3a_streaming
```

```
3a.1 Streaming de OA-007 con openai
¡Hola! Gracias por escribir a OrbitAir. Si pierdes una conexión ...   (aparece de a poco)
  TTFT (lo que percibe el pasajero) : 0.29 s
  Latencia total (respuesta entera) : 0.99 s
  Usage: 228 in / 111 out · costo USD 0.0002688

3a.1 Streaming de OA-007 con gemini
  TTFT (lo que percibe el pasajero) : 0.60 s
  Latencia total (respuesta entera) : 1.17 s
  Usage: 223 in / 110 out · costo USD 0.0002207

3a.2 La misma consulta SIN streaming (openai)
  Primer texto visible a los 0.95 s (= latencia total)

3a.3 Error típico: stream=True SIN stream_options={'include_usage': True}
  usage_disponible=False · tokens 0/0 · costo USD 0.0000000
  ⚠ El costo dio CERO y no hubo ningún error. En un dashboard esto parece 'gratis'.

3a.4 Medir mal vs medir bien
  Cronómetro alrededor de TODO (incluye la UI): 2.83 s  ← mal
  latency_s del cliente (solo el proveedor)   : 1.19 s  ← bien
```

### 3a.3 Lo que hay que llevarse
1. **Streaming no hace más rápida la respuesta; hace más rápido el primer indicio.** La latencia total es la misma.
2. **El bug silencioso:** sin `include_usage`, OpenAI devuelve costo 0 **sin error**. Por eso el contrato
   tiene `usage_disponible`: el Paso 4 puede detectar y alertar en vez de sumar ceros.
3. **Medir la latencia SIEMPRE con `time.perf_counter()` alrededor de la llamada, nunca incluyendo el print.**
   En 3a.4 la “UI lenta” infla la medición a más del doble. (`time.time()` tampoco: puede saltar si el reloj del sistema se ajusta.)
   Mismo principio en el mock de Gemini: la carga del tokenizador local (~15 s) se hace **antes** de arrancar
   el cronómetro (`mock.preparar()`); si no, la primera llamada “tardaría” 20 s.
4. La sección 3a.3 solo corre si hay key de OpenAI (o en mock): el bug de `include_usage` es **exclusivo** de OpenAI.

### ❌ Errores comunes del Paso 3a
| Síntoma | Causa |
|---|---|
| Costo = 0 en todas las llamadas con streaming | Falta `stream_options={"include_usage": True}` en OpenAI. |
| `IndexError` en el último chunk | El chunk del usage trae `choices` vacío. |
| La respuesta sale repetida/rara | Se reemplazó en vez de **concatenar** los deltas. |
| Latencia “alta” sospechosa | Se midió con el `print` adentro del cronómetro. |

---

## Paso 3b — Rate limits y backoff exponencial (parte C)

> ⏱ Recortable: se puede hacer solo la demostración y que cada uno complete `with_retry()` después (async).

### 🎯 Objetivo
Que un 429 no tire abajo la atención de OrbitAir, **sin** martillar al proveedor.

### 🧠 Lo que dice la lección
- **429** = rate limit → esperar y reintentar con **backoff exponencial + jitter**.
- **5xx** = error del proveedor → reintentos **limitados** (y circuit breaker).
- **4xx** (salvo 429) = tu request está mal → **reintentar no lo arregla**.
- Si viene **`Retry-After`, manda él**: el proveedor conoce su carga mejor que vos.

### 3b.1 Intentalo vos: `with_retry()`

```python
def with_retry(fn, *, max_retries=5, base=1.0, sleep=time.sleep, log=print):
    for intento in range(max_retries):
        try:
            return fn()
        except Exception as e:
            # TODO 1: si NO es 429/5xx → raise (sale al primer intento)
            # TODO 2: si es el último intento → raise ReintentosAgotados(...) from e
            # TODO 3: espera = Retry-After si existe;
            #         si no, min(30, base * 2**intento) + random.uniform(0, base)
            # TODO 4: log + sleep(espera)
```

Pistas:
- `getattr(e, "status_code", None)` funciona con OpenAI, Anthropic y el mock… **pero no con Gemini**,
  que lo guarda en `e.code`. Por eso la solución tiene `codigo_http(e)`, que mira los dos.
- En OpenAI/Anthropic la espera viene en el **header** `e.response.headers.get("retry-after")`.
- En **Gemini** viene en el **cuerpo JSON** del error, como un detalle `google.rpc.RetryInfo`:
  ```json
  {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
             "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}]}}
  ```
  El SDK lo deja en `e.details`. Mismo concepto (“esperá X”), otro formato → otro adaptador.
- `sleep` es un **parámetro** para poder testear sin esperar de verdad (mirá los tests).

<details><summary>Ver solución</summary>

[orbitair/reintentos.py](orbitair/reintentos.py): `es_reintentable()`, `leer_retry_after()`, `calcular_espera()`, `with_retry()`.
</details>

### 3b.2 Ejecutar

```bash
uv run python -m pasos.paso3b_rate_limits
```

```
3b.1 Esperas calculadas (base=1s)
  intento     sin Retry-After   otra vez (jitter)   con Retry-After=1.5
  0                     1.37s               1.29s                 1.50s
  1                     2.86s               2.52s                 1.50s
  2                     4.19s               4.89s                 1.50s
  3                     8.19s               8.91s                 1.50s

3b.2 429 sin Retry-After, 429 con Retry-After=1.5, luego OK
  t= 0.00s → llamada #1
  ⚠ intento 1/5 falló (429). Esperando 0.72s (backoff)
  t= 0.72s → llamada #2
  ⚠ intento 2/5 falló (429). Esperando 1.50s (Retry-After)
  t= 2.22s → llamada #3
  resultado: respuesta OK

3b.2b 429 de Gemini (google.genai.errors.ClientError real, armado a mano)
  error.code=429 (no status_code) · retryDelay en el JSON, no en un header
  ⚠ intento 1/5 falló (429). Esperando 1.20s (Retry-After)
  resultado: respuesta OK

3b.3 Error 400 (request mal formada): no se reintenta
  Salió al primer intento con HTTP 400 (1 llamada)

3b.4 503 sostenido: se agotan los intentos
  Se agotaron los 3 intentos → acá un Router derivaría el tráfico al otro proveedor
```

**Para discutir:**
- Columna 2 vs 3: **mismo intento, distinta espera**. Ese es el jitter: si 1.000 pasajeros fallan a la vez,
  no reintentan todos en el mismo milisegundo.
- 3b.4 es el punto de unión con el **Router** de la lección: cuando un proveedor falla sostenidamente,
  seguir reintentando solo **retrasa** el fallback al otro.
- ¿Por qué apagamos los reintentos internos del SDK (`max_retries=0`)? Si no, cada intento nuestro serían
  3 llamadas reales y el log mentiría. El SDK de Gemini, en cambio, **no reintenta por defecto**
  (`HttpOptions.retry_options=None`): no hay nada que apagar. Otra asimetría más.
- **Con la key gratuita de Gemini los 429 son reales:** el tier gratuito tiene pocas requests por minuto,
  así que el Paso 4 (10 consultas seguidas) puede chocar con el límite. Es la mejor demo de 3b: vas a ver
  el `retryDelay` que manda Google y a `with_retry` respetándolo.

### 3b.3 Probarlo en el Paso 4

En el `.env`, en modo mock: `ORBITAIR_MOCK_FAIL_RATE=0.2` → el 20 % de las llamadas devuelve un 429 simulado
y vas a ver los reintentos en vivo durante la comparativa.

---

## Paso 4 — Tabla comparativa y entregable · *no negociable*

### 🎯 Objetivo
Responder la pregunta de OrbitAir con **evidencia**: cuánto cuesta, cuánto tarda y qué tan bien responde.

### 4.1 Qué hace el script
Para cada proveedor y cada una de las 10 consultas:
1. `with_retry(lambda: ask_stream(...))` → streaming (TTFT) **con** `include_usage` **y** reintentos.
2. Guarda tokens **reales** del usage, la estimación de tiktoken, TTFT, latencia, costo y `finish_reason`.
3. Resume por proveedor y **proyecta a 10.000 consultas**.

```bash
uv run python -m pasos.paso4_comparativa
```

### 4.2 Resultado (modo mock)

```
▶ openai (gpt-4.1-mini)
  OA-001    98 in /   43 out  ttft 0.27s  total 0.54s  USD 0.0001080
  ...
  OA-007   228 in /  111 out  ttft 0.38s  total 1.07s  USD 0.0002688
▶ anthropic (claude-haiku-4-5)
  OA-001   115 in /   64 out  ttft 0.47s  total 1.00s  USD 0.0004350
  ⚠ intento 1/5 falló (429). Esperando 1.88s (backoff)
  ...
```

| Proveedor | Modelo | Tokens in | Tokens out | (thinking) | TTFT medio | Latencia media | Cortadas | Costo/consulta | **× 10.000** | vs. más barato |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai | gpt-4.1-mini | 1225 | 473 | 0 | 0.35 s | 0.66 s | 0 | $0.0001247 | **$1.25** | 1.2x |
| anthropic | claude-haiku-4-5 | 1441 | 692 | 0 | 0.50 s | 1.07 s | 0 | $0.0004901 | **$4.90** | 4.9x |
| gemini | gemini-3.1-flash-lite | 1170 | 474 | 0 | 0.40 s | 0.65 s | 0 | $0.0001003 | **$1.00** | 1.0x |

> ⚠ En modo mock las respuestas, las latencias, los tokens de Claude y el thinking son **simulados**.
> Los tokens de Gemini sí salen de su tokenizador real. Para el entregable final, corré con `ORBITAIR_MOCK=0`
> y la(s) key(s) que tengas: con solo Gemini, la tabla tendrá una fila, y la comparación se hace entre
> **modelos** de Gemini (ver 4.4).

Se generan:
- `resultados/comparativa.md` → tabla resumen + detalle por consulta + preguntas de recomendación.
- `resultados/detalle.csv` → una fila por consulta y proveedor, con la respuesta completa y la columna
  **`calidad_1a5` vacía para que la completes vos**.

### 4.3 Leer la tabla como negocio

1. **¿De dónde sale cada número?** Del `usage`. Elegí una fila del CSV y recalculá el costo a mano.
2. **¿Por qué Anthropic usa más tokens de input para el mismo texto?** Otro tokenizador (Paso 2).
   *El precio por token no alcanza para comparar: hay que comparar costo por consulta.*
3. **¿Por qué el output pesa tanto?** El token de salida es 4–5x más caro que el de entrada. Una respuesta
   más charlatana (la frase extra “¿Hay algo más…?”) se paga en **cada una** de las 10.000 consultas.
4. **De “$0.0004” a decisión:** a 10.000 consultas/mes la diferencia es ~USD 3.65/mes. ¿Y si son 10.000 **por día**?
   ```bash
   uv run python -m pasos.paso4_comparativa --escala 300000
   ```
5. **Calidad:** el costo sin calidad no decide nada. Leé las 20 respuestas y puntuá. Mirá especialmente
   OA-009 (¿inventó una cantidad de millas?) y OA-010 (¿derivó a un humano?).

### 4.4 Variantes para correr

```bash
uv run python -m pasos.paso4_comparativa --max-tokens 60
```
→ ¿Cuántas se cortan? ¿Cuál primero? (pista: OA-007)

```bash
uv run python -m pasos.paso4_comparativa --temperature 1.0
```
→ ¿Cambia el costo? ¿Cambia la consistencia?

**Comparativa con una sola key (Gemini):** corré el Paso 4 una vez por modelo/configuración, cambiando el
`.env` entre corridas y guardando cada `resultados/comparativa.md` con otro nombre:

| Corrida | `.env` | Qué responde |
|---|---|---|
| 1 | `GEMINI_MODEL=gemini-3.1-flash-lite` · `GEMINI_THINKING_LEVEL=minimal` | Línea base barata |
| 2 | `GEMINI_MODEL=gemini-3.1-flash-lite` · `GEMINI_THINKING_LEVEL=medium` | ¿Cuánto cuesta “pensar”? ¿Mejora la calidad? |
| 3 | `GEMINI_MODEL=gemini-3.8-flash` · `GEMINI_THINKING_LEVEL=low` | Modelo más grande (3x precio): ¿lo vale? |

> `gemini-3.8-flash` no acepta `minimal`: usá `low`. Sus precios suben el 2027-01-01 (ver `pricing.json`).

### 📦 Entregable

`resultados/comparativa.md` completo con:

| Criterio | Qué se espera |
|---|---|
| Tabla resumen | Generada por el script, con la columna **Calidad (1-5)** completada |
| Costo verificable | Una fila recalculada a mano desde el usage (mostrá la cuenta) |
| Proyección | Costo a 10.000 consultas por proveedor + qué cambia a otra escala |
| Cortadas | Qué consultas terminaron con `length` y qué harías (subir `max_tokens`, pedir brevedad, partir la consulta) |
| Recomendación | 3–5 líneas: qué proveedor para la primera respuesta de OrbitAir y por qué (costo × latencia × calidad) |

---

## Retos extra (para quien termina antes)

1. **Modelo barato vs. modelo caro:** en `.env` poné `OPENAI_MODEL=gpt-4.1-nano` (y después
   `ANTHROPIC_MODEL=claude-sonnet-4-5`) y repetí el Paso 4. ¿La calidad acompaña la diferencia de precio?
2. **Router con fallback:** escribí `ask_con_fallback(prompt, orden=["openai", "anthropic"])` que use
   `with_retry` y, si recibe `ReintentosAgotados`, pase al siguiente proveedor. Testealo con el mock y
   `ORBITAIR_MOCK_FAIL_RATE=0.9`.
3. **Circuit breaker:** tras N fallas seguidas de un proveedor, no lo llames durante X segundos.
4. **Alerta de costo cero:** en el Paso 4, si alguna respuesta tiene `usage_disponible=False`, que el script
   falle con un mensaje claro en vez de sumar ceros.
5. **Cuarto proveedor:** Gemini se sumó agregando `_gemini()` / `_gemini_stream()` y su precio, y los
   Pasos 3a y 4 **no cambiaron una línea**. Repetí la experiencia con otro proveedor (Mistral, DeepSeek…).
6. **Pre-validación con el tokenizador local:** antes de llamar a Gemini, usá `LocalTokenizer` para rechazar
   consultas que superen N tokens (el “validar el payload antes de enviarlo” de la lección).

---

## Guía para quien da la clase

| Bloque | Tiempo | Notas |
|---|---|---|
| Paso 0 · Setup | 10 min | Confirmar `uv sync` + `.env` **antes** de arrancar. Sin keys → `ORBITAIR_MOCK=1`. |
| Paso 1 · Contrato | 25 min | **No negociable.** Diseñar `LLMResponse` en conjunto antes de mostrar el código. |
| Paso 2 · Tokens | 20 min | Mostrar la “trampa” OA-003 vs OA-010 antes de 2.3. |
| Paso 3a · Streaming | 15 min | Anticipar: **sin `include_usage` el costo da cero**. |
| Paso 3b · Rate limits | 15 min | **Lo más recortable:** hacer solo la demo y dejar `with_retry()` async. |
| Paso 4 · Comparativa | 25 min | **No negociable.** Cerrar con la proyección × 10.000 y la discusión de calidad. |

Errores a anticipar:
- Latencia medida con el `print` adentro → siempre `time.perf_counter()` **solo** alrededor de la llamada.
- Costo cero en streaming → falta `stream_options={"include_usage": True}`.
- Consola de Windows que explota con emojis → resuelto en `orbitair/__init__.py` (fuerza UTF-8).
- Gemini con respuesta vacía → el thinking se comió `max_output_tokens` (Paso 1.7).
- Gemini en tier gratuito → 429 reales en el Paso 4: no es un bug, es la demo del Paso 3b.

---

## Lo que ya deberías poder hacer

- [ ] Explicar qué es un token y por qué el idioma y el proveedor cambian cuántos consume un texto.
- [ ] Elegir `temperature`, `max_tokens` y `top_p` con criterio (y no tocar los dos últimos a la vez).
- [ ] Llamar a OpenAI, Anthropic y Gemini bajo un mismo contrato.
- [ ] Contar tokens en Gemini antes (local o API) y después (`usage_metadata`) de llamar.
- [ ] Explicar cuándo conviene streaming, qué es el TTFT y por qué hay que pedir `include_usage`.
- [ ] Implementar reintentos con backoff exponencial + jitter que respeten `Retry-After`.
- [ ] Calcular el costo real desde el `usage` y compararlo entre proveedores a escala.

**Próxima clase (C2):** el foco pasa de *cómo se llama al modelo* a *qué se le dice*: se etiquetan estas
10 consultas y se diseña y versiona el prompt con el mismo criterio basado en evidencia.
