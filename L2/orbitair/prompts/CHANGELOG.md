# CHANGELOG — prompt de triage de OrbitAir

> Regla: **nunca se edita una versión anterior**. Cada cambio es un archivo nuevo.
> Cada entrada registra **qué cambió**, **por qué** y **qué resultado se midió** (Paso 5).
> Las mediciones de abajo son de modo MOCK: reemplazalas con las tuyas al correr con APIs reales.

## v1 — triage_v1.txt
- Qué: una línea con la tarea y 5 categorías.
- Por qué: línea base “lo primero que se le ocurre a cualquiera” (zero-shot).
- Resultado: _completar con el Paso 5_ (esperado: formato impredecible y categorías inventadas para lo que no encaja).

## v2 — triage_v2.txt
- Qué: los 4 principios (rol, contexto, tarea, formato). Categorías como variable `{categorias}` con descripción,
  categoría cajón `otro`, delimitadores `<consulta>` y salida JSON de una línea.
- Por qué: v1 devolvía texto libre que el código no podía parsear y no tenía dónde poner consultas
  como “¿tienen wifi?”.
- Resultado: _completar_.

## v3_obvio — triage_v3_obvio.txt (EXPERIMENTO DESCARTADO)
- Qué: v2 + 3 ejemplos few-shot “representativos” (maleta, millas, cambio de fecha).
- Por qué: probar si cualquier ejemplo mejora.
- Resultado: _completar_ (esperado: no cambia nada: los ejemplos eran casos que v2 ya acertaba).
- Decisión: descartado. Se conserva el archivo para que el experimento sea reproducible.

## v3 — triage_v3.txt
- Qué: v2 + 3 ejemplos few-shot construidos a partir de los **errores reales de v2** en el lote dev
  (reglas R1 cobro, R2 cambio de datos de la reserva, R3 varias preguntas). Redactados de nuevo, no copiados
  del dataset, para no contaminar la evaluación.
- Por qué: v2 confundía OA-006 y OA-007 (ver Paso 3).
- Resultado: _completar_.

## v4 — triage_v4.txt
- Qué: v3 + chain-of-thought en 3 líneas (Tema / Pide / Decisión) y última línea parseable `CATEGORIA: x`.
- Por qué: la regla R4 (“clasificar lo que pide, no lo que menciona”) no se puede mostrar bien con un solo ejemplo.
- Resultado: _completar_ (mirar exactitud **y** costo × 10.000).
