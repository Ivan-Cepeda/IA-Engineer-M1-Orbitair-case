# Guía de etiquetado — triage OrbitAir

Cada consulta lleva **exactamente una** categoría: la del equipo que tiene que actuar.

| Categoría | Equipo / qué cubre |
|---|---|
| `equipaje` | Maletas: medidas, peso, equipaje de mano y de bodega, pérdidas, daños, objetos especiales |
| `cambios_cancelaciones` | Modificar la reserva: fecha, ruta, nombre/titular, cancelaciones, reprogramación, conexiones perdidas |
| `reembolsos_cobros` | Dinero: devoluciones, cobros duplicados o indebidos, créditos |
| `servicios_especiales` | Mascotas, menores no acompañados, movilidad reducida, condiciones médicas, embarazo |
| `millas` | Programa OrbitPlus: acumular, canjear, consultar millas o puntos |
| `otro` | Todo lo que no encaja arriba (información general, servicios a bordo, horarios de atención) |

## Reglas de desempate

- **R1 — El dinero manda.** Si pide devolver dinero o reclama un cobro, va a `reembolsos_cobros`,
  aunque el cobro sea de un asiento o de equipaje.
- **R2 — Cambiar un dato de la reserva es un cambio.** Corregir el nombre, pasar el pasaje a otra persona,
  cambiar la fecha o reprogramar un vuelo cancelado va a `cambios_cancelaciones`, no a `otro`.
- **R3 — Varias preguntas: gana la primera acción operativa.** Si hay que reubicar al pasajero, eso va
  primero; hotel, comida o asistencia son secundarios.
- **R4 — Se clasifica lo que pide, no lo que menciona.** “Viajo con mi gato, ¿la guitarra cuenta como
  equipaje de mano?” es `equipaje`.

Si dos personas etiquetan distinto la misma consulta, **el problema es la guía, no la persona**:
se agrega o ajusta una regla.
