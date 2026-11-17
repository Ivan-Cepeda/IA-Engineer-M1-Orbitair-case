# Módulo 1 · De la llamada al LLM a un triage confiable

Todo el módulo trabaja sobre **un mismo caso**: **OrbitAir**, una aerolínea que quiere que un LLM haga la
primera atención de sus pasajeros. Cada clase agrega una pieza; el Proyecto Integrador las junta todas en
un caso nuevo (**Nubbix**, soporte de un SaaS).

```
L1 llamar al modelo ─► L2 qué decirle ─► L3 salida validada ─► L4 seguridad ─► L5 medir ─► PI todo junto
```

| Carpeta | Tema | Pregunta que responde | Resultado principal |
|---|---|---|---|
| [L1](L1/orbitair/README.md) | Cómo funciona un LLM | ¿Cuánto cuesta, cuánto tarda y qué tan bien responde cada proveedor? | Cliente único para OpenAI, Anthropic y Gemini + tabla de costos × 10.000 consultas |
| [L2](L2/orbitair/README.md) | Context engineering | ¿Qué prompt clasifica mejor, y cómo lo demuestro? | 5 versiones de prompt medidas con exactitud y costo |
| [L3](L3/orbitair/README.md) | Salidas estructuradas | ¿Cómo paso de "texto que hay que adivinar" a datos confiables? | Contrato Pydantic + tool calling + API con FastAPI |
| [L4](L4/orbitair/README.md) | Seguridad | ¿Qué pasa si el pasajero intenta engañar al modelo? | Pipeline con dos compuertas (antes y después del modelo) |
| [L5](L5/orbitair/README.md) | Métricas y evals | ¿Cómo elijo un prompt con datos y no con intuición? | Suite de 30 casos, umbral por categoría, LLM-as-judge y costo por acierto |
| [PI](PI/README.md) | Proyecto integrador | ¿Puedo armar un triage completo de punta a punta? | CLI que devuelve JSON validado, con métricas, guardrails y evals |

## Dos versiones de OrbitAir

- **L1 y L2** son la versión **completa**: tres proveedores, modo simulado (`ORBITAIR_MOCK=1`, sin API keys), tests y guía para docentes.
- **L3, L4 y L5** son la versión **simplificada para programar en vivo**: solo Gemini, sin modo simulado, pocos archivos.

## Las ideas que se repiten en todo el módulo

1. **El costo sale del `usage` real de la API**, nunca se estima. Y se multiplica por el volumen (10.000 consultas) para que sea una decisión de negocio.
2. **Sin respuestas correctas no hay medición.** Primero se etiqueta el dataset, después se compara.
3. **Un prompt es código:** se versiona, nunca se edita una versión vieja, y cada cambio va al `CHANGELOG.md` con su resultado.
4. **No se confía en la salida del modelo:** se valida con un contrato y, si falla, se reintenta diciéndole qué falló.
5. **La seguridad es código, no una frase en el prompt:** filtros antes y después del modelo.
6. **Más caro no es mejor:** few-shot y chain-of-thought se justifican solo si los números lo muestran.

## Requisitos comunes

- Python 3.10+
- Una API key de Gemini (gratis en https://aistudio.google.com/apikey). L1 y L2 también aceptan OpenAI y Anthropic, o ninguna en modo simulado.
- En cada carpeta: copiar `.env.example` como `.env` y pegar la key. El `.env` nunca se sube al repositorio.

Cada carpeta es un proyecto independiente, con su propia guía (`README.md`) y sus dependencias. Para empezar por L1:

```bash
cd L1/orbitair
```

```bash
uv sync
```

```bash
uv run pytest -q
```
