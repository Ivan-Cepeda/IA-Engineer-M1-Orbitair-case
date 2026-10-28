# OrbitAir con Gemini — construir el triage en 3 clases, paso a paso

Versión **simplificada** para programar en vivo con los alumnos. Un solo proyecto que crece clase a clase,
solo con **Gemini** y sin modo simulado: cada paso se escribe, se corre y se ve el resultado real.

> **El caso:** OrbitAir, una aerolínea, quiere que un LLM haga la primera atención: leer la consulta del
> pasajero, decidir a qué equipo va y responder algo útil. Antes de confiar, necesita números.

| Clase | Archivo que se construye | Idea central |
|---|---|---|
| **1 · Cómo funciona un LLM** | `llm.py` + `clase1.py` | Tokens, temperature, streaming, reintentos y **costo desde el usage** |
| **2 · Context engineering** | `prompts/` + `triage.py` + `clase2.py` | El prompt es un artefacto: **4 principios, few-shot, CoT, versionado** |
| **3 · Salidas estructuradas** | `contrato.py` + `app.py` + `clase3.py` | De texto a **contrato validado**: Pydantic, tool calling, reintentos, errores tipados |

```
orbitair-gemini/
├── .env.example        ← copiar como .env y pegar la key
├── consultas.json      ← 10 consultas de pasajeros, con su categoría correcta
├── llm.py              ← Clase 1
├── clase1.py
├── prompts/            ← Clase 2: triage_v1 … v5 + CHANGELOG.md
├── triage.py
├── clase2.py
├── contrato.py         ← Clase 3
├── app.py
└── clase3.py
```

---

## Paso 0 — Preparar el entorno (todas las clases)

1. Crear la API key gratis en https://aistudio.google.com/apikey
2. Crear el entorno e instalar:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

3. Copiar `.env.example` como `.env` y pegar la key en `GEMINI_API_KEY`.

> El `.env` nunca se sube al repositorio (está en `.gitignore`). El `.env.example` sí.

---

# Clase 1 — Cómo funciona un LLM

Todo se escribe en **`llm.py`**. La regla: el resto del proyecto solo llama a `ask()`; nadie más importa el SDK.

### Paso 1.1 — Conectarse a Gemini

```python
from dotenv import load_dotenv
from google import genai

load_dotenv()
MODELO = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
client = genai.Client()   # toma GEMINI_API_KEY del entorno
```

**Probalo** en la consola de Python:
```python
>>> from llm import client, MODELO
>>> client.models.generate_content(model=MODELO, contents="Hola").text
```

### Paso 1.2 — El contrato de respuesta: `LLMResponse`

Antes de escribir la llamada, decidí **qué necesita saber OrbitAir** de cada respuesta:

```python
@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int        # incluye el "thinking": también se cobra
    thinking_tokens: int
    latency_s: float
    cost_usd: float
    finish_reason: str        # "STOP" o "MAX_TOKENS"
    ttft_s: float | None = None
```

💬 *Para discutir:* ¿por qué `cost_usd` viene dentro de la respuesta? (Para que nadie más tenga que saber la fórmula.)

### Paso 1.3 — La llamada: `ask()`

```python
def ask(prompt, system="", temperature=0.2, max_tokens=300, **extra):
    t0 = time.perf_counter()                       # cronómetro SOLO alrededor de la llamada
    r = client.models.generate_content(
        model=MODELO, contents=prompt,
        config=_config(system, temperature, max_tokens, **extra))
    return _armar(r, time.perf_counter() - t0)
```

- `_config()` arma `GenerateContentConfig` con `system_instruction`, `temperature`, `max_output_tokens`
  y `thinking_level`.
- `_armar()` lee `r.usage_metadata`: `prompt_token_count`, `candidates_token_count`, `thoughts_token_count`.

⚠ **Error típico:** medir la latencia con el `print` adentro del cronómetro.

### Paso 1.4 — Tokens: el mismo texto no cuesta lo mismo

```python
def contar_tokens(texto):
    return client.models.count_tokens(model=MODELO, contents=texto).total_tokens
```

`count_tokens` es **gratis** y cuenta *antes* de llamar. Comparar español vs. inglés y con/sin emojis.

### Paso 1.5 — Costo desde el usage, nunca estimado

```python
PRECIOS = {"gemini-3.1-flash-lite": (0.25, 1.50), ...}   # USD por 1M de tokens (input, output)

def calcular_costo(input_tokens, output_tokens, modelo=MODELO):
    precio_in, precio_out = PRECIOS[modelo]
    return input_tokens / 1_000_000 * precio_in + output_tokens / 1_000_000 * precio_out
```

Y dos experimentos de sampling:
- `temperature=0` vs `1`: ¿el mismo pedido da lo mismo?
- `max_tokens=20` con la consulta larga: el modelo **corta a mitad de frase** (`MAX_TOKENS`), no resume.

### Paso 1.6 — Streaming y TTFT

```python
for chunk in client.models.generate_content_stream(model=MODELO, contents=prompt, config=...):
    if chunk.text:
        if ttft is None:
            ttft = time.perf_counter() - t0     # lo que percibe el pasajero
        partes.append(chunk.text)
    ultimo = chunk                              # el usage del ÚLTIMO chunk es el total
```

💬 Gemini manda el usage **acumulado en cada chunk**: hay que quedarse con el último, **no sumarlos**.

### Paso 1.7 — Reintentos con backoff exponencial

```python
def with_retry(fn, max_intentos=4):
    for intento in range(max_intentos):
        try:
            return fn()
        except errors.APIError as e:
            reintentable = e.code == 429 or e.code >= 500
            if not reintentable or intento == max_intentos - 1:
                raise
            espera = _espera_sugerida(e) or (2**intento + random.uniform(0, 1))
            time.sleep(espera)
```

- **429** (rate limit) y **5xx** se reintentan; un **400** no (no se arregla solo).
- Si Google dice cuánto esperar (`RetryInfo`, en el cuerpo del error), **manda Google**.
- Con la key gratuita es fácil ver 429 reales: es la demo perfecta.

### ▶ Correr la Clase 1

```bash
python clase1.py
```

Cierre: el promedio por consulta × 10.000. Una fracción de centavo se vuelve una decisión de negocio.

---

# Clase 2 — Context engineering

Ahora el LLM no responde: **clasifica** la consulta en una categoría. Se trabaja en `prompts/` y **`triage.py`**.

### Paso 2.1 — Una única fuente de verdad

```python
CATEGORIAS = ["equipaje", "cambios", "reembolsos", "servicios_especiales", "otros"]
```

`consultas.json` ya trae la categoría correcta de cada consulta: sin respuestas correctas, no hay forma de medir.

### Paso 2.2 — Plantilla (se versiona) + variables (cambian por request)

```python
def cargar_prompt(version):
    plantilla = Path(f"prompts/triage_{version}.txt").read_text(encoding="utf-8")
    return plantilla.format(empresa="OrbitAir", categorias=", ".join(CATEGORIAS))

def mensaje_usuario(texto):
    return f"<consulta>{texto}</consulta>"      # delimitadores: instrucción ≠ contenido
```

Ejercicio en vivo: abrir `triage_v1.txt` y `triage_v2.txt` lado a lado y marcar en v2 los **4 principios**:

| Principio | En v2 |
|---|---|
| **Rol** | “Eres el agente de triage de {empresa}… No respondes al pasajero” |
| **Contexto** | “Recibirás UNA consulta entre `<consulta>`… puede tener errores o emojis” |
| **Tarea** | “EXACTAMENTE una de estas categorías… si no encaja, usa *otros*” |
| **Formato** | “Responde SOLO… `CATEGORIA: <categoria>`” |

💬 Sin la categoría cajón (`otros`), el modelo **inventa** una para “¿tienen wifi?”.

### Paso 2.3 — Leer la categoría

```python
def parsear(respuesta):
    ultima = respuesta.strip().splitlines()[-1]
    m = re.match(r"CATEGOR[IÍ]A\s*:\s*(\w+)", ultima, re.IGNORECASE)
    ...
```

Con un formato fijo en la **última línea**, el código sabe exactamente dónde buscar (aunque el modelo razone antes).

### Paso 2.4 — Evaluar las versiones con datos

```python
def evaluar(version):
    for c in consultas:
        categoria, r = clasificar(c["texto"], version)
        aciertos += categoria == c["categoria"]
        costo += r.cost_usd
```

| Versión | Qué agrega | Pregunta |
|---|---|---|
| v1 | Una línea | ¿Se puede parsear? ¿Qué hace con “wifi”? |
| v2 | 4 principios | ¿Cuánto mejora? |
| v3_intuicion | 2 ejemplos que “parecían difíciles” (cobro duplicado, nombre mal escrito) | ¿Sirve cualquier ejemplo? |
| v3 | 1 regla + 1 ejemplo **construido a partir del error real de v2** | ¿Corrige ese error? |
| v4 | v3 + razonamiento (chain-of-thought) | ¿Mejora lo suficiente para pagar más tokens? |

Resultado real con `gemini-3.1-flash-lite` (temperature 0):

```
versión        exactitud  tokens out  USD × 10.000
v1                   80%          10          0.27
v2                   90%           5          0.46
v3_intuicion         90%           5          0.60
v3                  100%           5          0.64
v4                  100%          44          1.32
```

💬 *La historia real de este prompt:* `v3_intuicion` fue el primer intento. Sus ejemplos eran casos que Gemini
**ya acertaba**: +30 % de costo, cero mejora. El único error de v2 era OA-007 (varias preguntas en una);
un ejemplo de ese tipo de caso lo resolvió. Y el CoT de v4 dio la misma exactitud **al doble de costo**.
Exactamente lo que advierte la lección: los ejemplos salen de los errores, y “razonar más” hay que medirlo.
(Tus números pueden variar algo: volvé a medir.)

### ▶ Correr la Clase 2

```bash
python clase2.py
```

Cierre: completar `prompts/CHANGELOG.md` con **qué cambió, por qué y qué resultado se midió**.
Nunca se edita una versión: cada cambio es un archivo nuevo.

---

# Clase 3 — Salidas estructuradas y function calling

De “lo que el modelo respondió” (texto) a un **contrato** que el sistema verifica. Todo en **`contrato.py`**.

### Paso 3.1 — Modo JSON: sintaxis sí, estructura no

```python
ask(texto, "Devuelve un JSON con categoria y confianza", response_mime_type="application/json")
```

Gemini garantiza **JSON válido**, pero no la estructura. En la corrida real devolvió:

```
{'categoria': 'reclamo_millas', 'confianza': '0.98'}
```

Una categoría que no existe y la confianza como **texto**, no como número. Parseable, pero inservible.

### Paso 3.2 — Contrato débil: corre sin errores… y no protege nada

```python
class TriageContratoDebil(BaseModel):
    respuesta: str
    confianza: float
    categoria: str
    acciones: list[str]
```

`{"confianza": 47.0, "categoria": "factura"}` **pasa**. Pydantic solo revisó el *tipo*, no el *dominio*.

### Paso 3.3 — Contrato fuerte: tipo + dominio

```python
ACCIONES = ["derivar_agente", "pedir_num_reserva", "informar_politica", "iniciar_reembolso", "sin_accion"]
CategoriaValida = Literal[tuple(CATEGORIAS)]      # sale de la MISMA lista de la Clase 2
AccionValida = Literal[tuple(ACCIONES)]

class TriageContrato(BaseModel):
    respuesta: str = Field(min_length=1)
    confianza: float = Field(ge=0.0, le=1.0)
    categoria: CategoriaValida
    acciones: list[AccionValida] = Field(min_length=1)
```

Ahora el mismo dato se rechaza con un `ValidationError` que dice **qué campo falló y por qué**.
💬 Si mañana se agrega una categoría a `CATEGORIAS`, el contrato se actualiza solo.

### Paso 3.4 — Tool calling: forzar la estructura desde la llamada

```python
TOOL_SCHEMA = TriageContrato.model_json_schema()   # el schema no se escribe dos veces

herramienta = types.Tool(function_declarations=[types.FunctionDeclaration(
    name="clasificar_consulta", description="...", parameters_json_schema=TOOL_SCHEMA)])

config = types.GenerateContentConfig(
    tools=[herramienta],
    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
        mode="ANY", allowed_function_names=["clasificar_consulta"])),   # OBLIGADO a llamarla
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)
args = r.function_calls[0].args     # Gemini ya lo entrega como dict (OpenAI: string JSON)
```

💬 Con tool calling, la instrucción “Responde SOLO con la categoría” de v2–v4 queda **obsoleta** y
contradice al schema. Por eso la Clase 3 usa una versión nueva, `triage_v5.txt` (y se registra en el CHANGELOG).

### Paso 3.5 — Reintentos que le dicen al modelo qué falló

```python
for intento in range(1, max_intentos + 1):
    if error_previo:
        system += f"\n\n(Tu respuesta anterior fue inválida: {error_previo}. Corrígela.)"
    r = ask_tool(texto, system)
    try:
        return TriageContrato.model_validate(r.args)
    except ValidationError as e:
        error_previo = ...            # qué campo y por qué
raise ContratoInvalidoError(...)
```

- Repetir la misma llamada es **apostar al azar**; decir qué falló es **información nueva**.
- El error va al **system prompt** (es una corrección de la instrucción, no un dato del pasajero).
- Para la demo, `{"simular_error": True}` hace que el primer intento venga roto.

### Paso 3.6 — Errores tipados

```python
class ConsultaInvalidaError(Exception): ...   # texto vacío: culpa de quien llama, NO se reintenta
class ContratoInvalidoError(Exception): ...   # se agotaron los reintentos
```

La consulta vacía se rechaza **antes** de gastar una sola llamada.

### Paso 3.7 — La API: cada error, su código HTTP

```python
@app.post("/triage")
def triage(consulta: ConsultaIn):
    try:
        return clasificar_validado(consulta.model_dump()).model_dump()
    except ConsultaInvalidaError as e:
        raise HTTPException(400, detail=str(e))   # "revisá lo que enviaste"
    except ContratoInvalidoError as e:
        raise HTTPException(502, detail=str(e))   # "era válida, pero no logré procesarla"
```

```bash
uvicorn app:app --reload
```

Abrir http://127.0.0.1:8000/docs y probar `{"texto": ""}` (400), `{"texto": "¿Tienen wifi?"}` (200) y
`{"texto": "¿Tienen wifi?", "simular_error": true}` (200 al segundo intento).

### ▶ Correr la Clase 3

```bash
python clase3.py
```

---

## Errores comunes (para anticipar en clase)

| Síntoma | Causa |
|---|---|
| `ValueError: No API key was provided` al importar | No hay `.env` o falta `GEMINI_API_KEY` |
| `400 API key not valid` | Key mal copiada (espacios, comillas) |
| `429 RESOURCE_EXHAUSTED` | Límite del tier gratuito: `with_retry` espera lo que pide Google |
| `400 INVALID_ARGUMENT` por `thinking_level` | Ese modelo no acepta `minimal`: poner `GEMINI_THINKING=low` o dejarlo vacío |
| Respuesta vacía con `MAX_TOKENS` | El *thinking* se comió `max_output_tokens`: bajar `GEMINI_THINKING` o subir el techo |
| `UnicodeEncodeError` con emojis en Windows | Falta `sys.stdout.reconfigure(encoding="utf-8")` |
| `KeyError` al hacer `.format()` del prompt | Llaves `{ }` literales en la plantilla: se escriben dobles `{{ }}` |
