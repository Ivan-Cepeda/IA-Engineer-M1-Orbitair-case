# L3 · OrbitAir con Gemini — de cero a un triage validado, en 3 clases

> **En una frase:** la versión **simplificada para programar en vivo** de OrbitAir. Un solo proyecto que crece
> clase a clase, solo con **Gemini**, sin modo simulado: cada paso se escribe, se corre y se ve el resultado real.

**El caso:** OrbitAir quiere que un LLM lea la consulta del pasajero, decida a qué equipo va y responda algo útil.
Antes de confiar en él, necesita números.

| Clase | Archivos | Idea central |
|---|---|---|
| **1 · Cómo funciona un LLM** | `llm.py` · `clase1.py` | Tokens, temperature, streaming, reintentos y **costo desde el usage** |
| **2 · Context engineering** | `prompts/` · `triage.py` · `clase2.py` | El prompt se diseña y se mide: **4 principios, few-shot, CoT, versionado** |
| **3 · Salidas estructuradas** | `contrato.py` · `app.py` · `clase3.py` | De texto suelto a un **contrato validado**: Pydantic, tool calling, errores claros |

```
L3/orbitair/
├── .env.example     ← copiar como .env y pegar la key
├── consultas.json   ← 10 consultas, cada una con su categoría correcta
├── llm.py           ← Clase 1: la única puerta al modelo
├── triage.py        ← Clase 2: clasificar y evaluar
├── prompts/         ← Clase 2: triage_v1 … v5 + CHANGELOG.md
├── contrato.py      ← Clase 3: el contrato Pydantic
├── app.py           ← Clase 3: la API
└── clase1.py · clase2.py · clase3.py   ← las demos
```

## Preparar el entorno

1. Crear una API key gratis en https://aistudio.google.com/apikey
2. Instalar:

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

---

# Clase 1 — Cómo funciona un LLM

Todo vive en **`llm.py`**. Regla: el resto del proyecto solo llama a `ask()`; nadie más importa el SDK.

| Paso | Qué se escribe | Lo que hay que entender |
|---|---|---|
| 1.1 | Conectar con `genai.Client()` | La key se lee del `.env` |
| 1.2 | `LLMResponse`: texto, tokens, latencia, costo, `finish_reason` | Decidir **qué necesita saber** el sistema de cada respuesta antes de llamar |
| 1.3 | `ask()` | El cronómetro va **solo** alrededor de la llamada |
| 1.4 | `contar_tokens()` con `count_tokens` (gratis) | Español y emojis cuestan más tokens |
| 1.5 | `calcular_costo()` desde el usage | `max_tokens` **corta** a mitad de frase, no resume |
| 1.6 | Streaming y TTFT | Gemini manda el usage acumulado: quedarse con el **último**, no sumar |
| 1.7 | `with_retry()` | Reintentar 429 y 5xx con espera creciente; un 400 no se reintenta |

El corazón de la clase:

```python
def ask(prompt, system="", temperature=0.2, max_tokens=300, **extra):
    t0 = time.perf_counter()
    r = client.models.generate_content(model=MODELO, contents=prompt,
                                       config=_config(system, temperature, max_tokens, **extra))
    return _armar(r, time.perf_counter() - t0)   # lee tokens del usage y calcula el costo
```

```bash
python clase1.py
```

**Cierre:** costo promedio por consulta × 10.000. Una fracción de centavo se vuelve una decisión de negocio.

---

# Clase 2 — Context engineering

Ahora el modelo no responde: **clasifica** la consulta. Categorías (una sola lista para todo el proyecto, en `triage.py`):

```python
CATEGORIAS = ["equipaje", "cambios", "reembolsos", "servicios_especiales", "otros"]
```

**Cómo funciona `triage.py`:**
1. `cargar_prompt(version)` lee `prompts/triage_<version>.txt` e inserta la empresa y las categorías.
2. `mensaje_usuario(texto)` envuelve la consulta en `<consulta>…</consulta>`, para separar instrucción de contenido.
3. `parsear()` lee la **última línea** `CATEGORIA: <valor>`; así el código sabe dónde buscar aunque el modelo razone antes.
4. `evaluar(version)` compara cada respuesta con la categoría correcta de `consultas.json` y suma el costo.

**Los 4 principios de un buen system prompt** (comparar `triage_v1.txt` con `triage_v2.txt`):

| Principio | En v2 |
|---|---|
| **Rol** | "Eres el agente de triage de OrbitAir… No respondes al pasajero" |
| **Contexto** | "Recibirás UNA consulta entre `<consulta>`… puede tener errores o emojis" |
| **Tarea** | "EXACTAMENTE una de estas categorías… si no encaja, usa *otros*" |
| **Formato** | "Responde SOLO… `CATEGORIA: <categoria>`" |

Sin la categoría cajón (`otros`), el modelo **inventa** una para "¿tienen wifi?".

**Resultado real** (`gemini-3.1-flash-lite`, temperature 0):

| Versión | Qué agrega | Exactitud | Tokens de salida | USD × 10.000 |
|---|---|---:|---:|---:|
| v1 | Una línea | 80 % | 10 | 0.27 |
| v2 | Los 4 principios | 90 % | 5 | 0.46 |
| v3_intuicion | 2 ejemplos que "parecían difíciles" | 90 % | 5 | 0.60 |
| v3 | 1 regla + 1 ejemplo **sacado del error real de v2** | **100 %** | 5 | 0.64 |
| v4 | v3 + razonamiento (chain-of-thought) | 100 % | 44 | 1.32 |

**Qué enseña:** `v3_intuicion` costó 30 % más y no mejoró nada, porque sus ejemplos eran casos que Gemini ya
acertaba. El único error de v2 era OA-007 (varias preguntas en una), y un ejemplo de ese tipo lo resolvió.
El razonamiento de v4 dio la misma exactitud **al doble de costo**. Los ejemplos salen de los errores, y
"pensar más" hay que medirlo. (Tus números pueden variar algo.)

```bash
python clase2.py
```

**Cierre:** completar `prompts/CHANGELOG.md` con qué cambió, por qué y qué resultado se midió. Una versión nunca se edita.

---

# Clase 3 — Salidas estructuradas y tool calling

De "lo que el modelo respondió" (texto) a un **contrato** que el sistema verifica. Todo en **`contrato.py`**.

| Paso | Qué se prueba | Resultado |
|---|---|---|
| 3.1 | Modo JSON (`response_mime_type="application/json"`) | JSON válido, pero con `categoria: "reclamo_millas"` (no existe) y `confianza: "0.98"` (texto). **Sintaxis sí, estructura no** |
| 3.2 | Contrato débil (`categoria: str`, `confianza: float`) | `{"confianza": 47.0, "categoria": "factura"}` **pasa**. Revisa el tipo, no el dominio |
| 3.3 | Contrato fuerte | El mismo dato se **rechaza** y el error dice qué campo falló |
| 3.4 | Tool calling obligatorio | El modelo **tiene que** devolver los campos del contrato |
| 3.5 | Reintento con el error | Si falla, se reintenta diciéndole al modelo qué estuvo mal |
| 3.6 | Errores con nombre | Distinguir "me mandaste algo mal" de "no pude procesarlo" |
| 3.7 | API con FastAPI | Cada error, su código HTTP |

**El contrato fuerte:**

```python
class TriageContrato(BaseModel):
    respuesta: str = Field(min_length=1)
    confianza: float = Field(ge=0.0, le=1.0)                 # entre 0 y 1
    categoria: Literal[tuple(CATEGORIAS)]                    # la MISMA lista de la Clase 2
    acciones: list[Literal[tuple(ACCIONES)]] = Field(min_length=1)
```

Si mañana se agrega una categoría a `CATEGORIAS`, el contrato se actualiza solo.

**Tool calling:** el schema del contrato (`TriageContrato.model_json_schema()`) se le pasa a Gemini como
herramienta con `mode="ANY"`, que lo **obliga** a usarla. El schema se escribe una sola vez. Como la instrucción
"Responde SOLO con la categoría" de v2–v4 ya no tiene sentido, la Clase 3 usa un prompt nuevo: `triage_v5.txt`.

**Reintentos que informan:** repetir la misma llamada es apostar al azar; decirle al modelo qué falló
("confianza debe ser ≤ 1") es información nueva. El error se agrega al system prompt.

**Errores con nombre:**
- `ConsultaInvalidaError` → texto vacío. Es culpa de quien llama: **no se reintenta** y no se gasta ninguna llamada.
- `ContratoInvalidoError` → se agotaron los reintentos.

**La API:**

```bash
uvicorn app:app --reload
```

Abrir http://127.0.0.1:8000/docs y probar `POST /triage`:

| Body | Respuesta |
|---|---|
| `{"texto": ""}` | **400**: revisá lo que enviaste |
| `{"texto": "¿Tienen wifi?"}` | **200** |
| `{"texto": "¿Tienen wifi?", "simular_error": true}` | **200** al segundo intento (el primero se rompe a propósito) |
| Se agotan los reintentos | **502**: el pedido era válido, pero no se pudo procesar |

```bash
python clase3.py
```

---

## Errores comunes

| Síntoma | Causa |
|---|---|
| `No API key was provided` | Falta el `.env` o `GEMINI_API_KEY` |
| `400 API key not valid` | Key mal copiada (espacios, comillas) |
| `429 RESOURCE_EXHAUSTED` | Límite del tier gratuito: `with_retry` espera lo que pide Google |
| `400 INVALID_ARGUMENT` por `thinking_level` | El modelo no acepta `minimal`: usar `GEMINI_THINKING=low` o dejarlo vacío |
| Respuesta vacía con `MAX_TOKENS` | El thinking se comió el límite: bajarlo o subir `max_tokens` |
| `UnicodeEncodeError` con emojis en Windows | Falta `sys.stdout.reconfigure(encoding="utf-8")` |
| `KeyError` al hacer `.format()` del prompt | Llaves `{ }` literales en la plantilla: van dobles `{{ }}` |

**Siguiente clase (L4):** ¿qué pasa cuando el pasajero intenta engañar al modelo?
