# AI Engineer · M1 — Caso OrbitAir

Casos prácticos guiados, paso a paso, sobre **OrbitAir**: una aerolínea que quiere reemplazar la primera
respuesta humana de su centro de atención por un LLM. Cada lección agrega una capa sobre la anterior.

| Lección | Carpeta | Qué se construye |
|---|---|---|
| **L1 · Cómo funciona un LLM** | [L1/orbitair](L1/orbitair) | Cliente multi-proveedor (OpenAI, Anthropic, Gemini), tokenización, streaming, rate limits y costo por token |
| **L2 · Context engineering** | [L2/orbitair](L2/orbitair) | Prompt de triage versionado: system prompt (4 principios), few-shot, chain-of-thought, plantillas y evaluación |
| **L3 · Structured outputs y function calling** | [L3/orbitair](L3/orbitair) | Versión simple L1→L3 con Gemini: cliente, prompts versionados, contrato Pydantic, tool calling, reintentos con validación y API FastAPI. Incluye guion de clase |

Cada carpeta es un proyecto independiente con su propia guía (`README.md`), dependencias y tests.
Todo corre **sin API keys** con `ORBITAIR_MOCK=1`.

```bash
cd L1/orbitair
```

```bash
uv sync
```

```bash
uv run pytest -q
```
