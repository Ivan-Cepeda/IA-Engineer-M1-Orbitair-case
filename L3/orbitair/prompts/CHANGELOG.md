# CHANGELOG del prompt de triage

Nunca se edita una versión: cada cambio es un archivo nuevo. "Resultado" medido con `python clase2.py`
(Gemini `gemini-3.1-flash-lite`, temperature 0, 10 consultas). Volvé a medir con tu corrida.

| Versión | Qué cambió | Por qué | Resultado (exactitud · USD × 10.000) |
|---|---|---|---|
| v1 | Una línea, sin rol, sin formato, sin "otros" | Línea base | 80 % · 0.27 — formato libre ("**equipaje**") y wifi → servicios_especiales |
| v2 | Rol, contexto, tarea con "otros", formato `CATEGORIA:` | v1 no tenía cajón ni formato fijo | 90 % · 0.46 — falla OA-007 (varias preguntas) |
| v3_intuicion | + 2 ejemplos "que parecían difíciles" (cobro duplicado, nombre mal escrito) | Probar ejemplos elegidos por intuición | 90 % · 0.60 — **descartado**: Gemini ya acertaba esos casos; +30 % de costo sin mejora |
| v3 | + regla de varias preguntas y 1 ejemplo construido a partir del error real de v2 (OA-007) | El único error de v2 era una consulta con varias preguntas | 100 % · 0.64 |
| v4 | v3 + razonamiento (chain-of-thought) antes de la última línea | Probar si "pensar" mejora | 100 % · 1.32 — misma exactitud que v3 al doble de costo: no se justifica |
| v5 | Pasa a tool calling (Clase 3): se quita "Responde SOLO con la categoría" y se pide una respuesta al pasajero | El formato ahora lo garantiza el schema; la instrucción vieja lo contradecía | _medir en Clase 3_ |
