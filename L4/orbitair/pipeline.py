# pipeline.py — CLASE 4, paso 4.7: las dos compuertas alrededor del triage de la Clase 3.
#   entrada → [compuerta 1: moderar + redactar] → triage (LLM) → [compuerta 2: redactar + moderar] → pasajero
import uuid

from contrato import clasificar_validado
from moderacion import Motivo, moderar
from seguridad import CONTROL, neutralizar, redactar

RESPUESTA_BLOQUEO = "No podemos procesar este mensaje. Si necesitás ayuda con tu viaje, escribinos tu consulta."
RESPUESTA_REVISION = "Recibimos tu consulta. Un agente la va a revisar y te responde a la brevedad."


def atender(texto: str, user_id: str = "anonimo", externo: str | None = None, modo: str = "reglas+llm") -> dict:
    request_id = uuid.uuid4().hex[:8]  # una sola clave que une todas las líneas de log de este pedido

    # --- Defensa de diseño PRIMERO: ni el moderador (que también es un LLM) necesita ver la tarjeta ---
    texto_limpio, pii = redactar(texto)

    # --- Compuerta 1 (entrada): ¿el pasajero intenta romper algo? ---
    entrada = moderar(texto_limpio, user_id, modo, request_id, etapa="entrada")
    if entrada.action == "bloquear":
        return {"estado": "bloqueada", "respuesta": RESPUESTA_BLOQUEO, "moderacion": entrada.model_dump()}
    if entrada.action == "marcar":  # zona gris: no se responde automático, va a una persona
        return {"estado": "en_revision", "respuesta": RESPUESTA_REVISION, "moderacion": entrada.model_dump()}

    # --- Contenido externo: se trata con la MISMA sospecha que el texto del pasajero ---
    if externo:
        if CONTROL.search(externo):  # inyección indirecta: no es culpa del pasajero, se neutraliza y se sigue
            entrada.reasons.append(Motivo(code="inyeccion_indirecta", source="regla",
                                          description="instrucción oculta en contenido externo, neutralizada"))
        externo, pii_ext = redactar(neutralizar(externo))
        pii += pii_ext

    # --- El triage de la Clase 3, ahora con canales separados y el prompt v6 ---
    contrato = clasificar_validado({"texto": texto_limpio, "externo": externo, "prompt": "v6"})

    # --- Compuerta 2 (salida): lo que el modelo dijo tampoco es confiable hasta revisarlo ---
    respuesta, pii_salida = redactar(contrato.respuesta)
    salida = moderar(respuesta, user_id, "reglas", request_id, etapa="salida")  # reglas: barato y suficiente
    if salida.action != "permitir":
        respuesta = RESPUESTA_REVISION

    return {
        "estado": "atendida" if salida.action == "permitir" else "en_revision",
        "respuesta": respuesta,
        "categoria": contrato.categoria,
        "acciones": contrato.acciones,
        "pii_redactada": {"entrada": pii, "salida": pii_salida},  # tipos, nunca valores
        "moderacion": entrada.model_dump(),
    }
