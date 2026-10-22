# mock.py
# Proveedores SIMULADOS para seguir la clase sin API keys (ORBITAIR_MOCK=1).
# Imitan lo que importa para la clase: usage, latencia, TTFT, truncado por max_tokens,
# variación con temperature y errores 429. Los números son verosímiles, NO reales.
import math
import random
import re
import time
from typing import Iterator

import tiktoken

from orbitair import config

from orbitair.tokenizadores import contar_gemini

_ENC = tiktoken.get_encoding("o200k_base")

# Claude no expone un tokenizador local. En el mock lo imitamos como "~20% más tokens
# que o200k" para que se note que cada proveedor cuenta distinto. Es una simulación.
# Gemini SÍ tiene tokenizador local: el mock lo usa, así que esos conteos son reales.
_FACTOR_TOKENS = {"openai": 1.0, "anthropic": 1.2, "gemini": 1.1}  # gemini: solo si falla el local
_OVERHEAD_MENSAJES = {"openai": 7, "anthropic": 5, "gemini": 3}  # tokens de "formato chat" (roles, separadores)
_TTFT = {"openai": (0.25, 0.50), "anthropic": (0.35, 0.70), "gemini": (0.30, 0.60)}  # segundos
_SEG_POR_TOKEN = {"openai": 0.006, "anthropic": 0.008, "gemini": 0.005}
# Tokens de "thinking" simulados por nivel (Gemini 3.x). Se cobran como output y comen max_tokens.
_THINKING = {"minimal": 0, "low": 40, "medium": 150, "high": 250, "": 250}


class MockRateLimitError(Exception):
    """Imita el 429 de los SDK reales: tiene status_code y, a veces, retry_after."""

    status_code = 429

    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(f"429 Too Many Requests (simulado). Retry-After={retry_after}")


# (palabras clave, respuesta) — cada tema detectado en la consulta suma un párrafo.
_TEMAS = [
    (("perro", "gato", "mascota"), "Puedes viajar con tu mascota en cabina si pesa menos de 8 kg junto con su transportín y lo reservas con al menos 48 horas de anticipación."),
    (("cancelad", "reprogram"), "Lamentamos la cancelación. Puedes reprogramar sin costo en el siguiente vuelo disponible o solicitar el reembolso desde 'Mis viajes'."),
    (("perdieron mi maleta", "maleta"), "Sentimos mucho lo de tu maleta. Con el número de reclamo (PIR) un agente revisará el estado de la búsqueda y los gastos de primera necesidad que puedes reclamar."),
    (("equipaje de mano",), "En la tarifa Light puedes llevar un artículo personal de hasta 40 x 30 x 15 cm; el equipaje de mano de 10 kg se agrega como servicio adicional."),
    (("apellido", "nombre"), "Las correcciones menores de hasta 3 letras en el nombre no tienen costo. Un agente validará el cambio con tu documento."),
    (("conexión", "escala"), "Si pierdes una conexión por un retraso de OrbitAir, te reubicamos automáticamente en el siguiente vuelo disponible y recibirás la nueva tarjeta de embarque por correo."),
    (("hotel", "comida"), "Si la espera supera las 8 horas, te corresponden vouchers de comida y hotel; solicítalos en el mostrador de transferencias."),
    (("silla de ruedas", "asistencia especial"), "La asistencia especial con silla de ruedas se solicita sin costo desde 'Mis viajes' con al menos 48 horas de anticipación y cubre todos los aeropuertos del itinerario."),
    (("cambiar la fecha", "fecha d"), "Por motivos de salud puedes cambiar la fecha sin multa presentando un certificado médico; un agente revisará tu caso."),
    (("millas", "orbitplus"), "No tengo la tabla vigente de canje de millas OrbitPlus para esa ruta; un agente te confirmará la cantidad exacta."),
    (("menor no acompañado", "viaja sola"), "Los menores de 5 a 14 años que viajan solos deben usar el servicio de menor no acompañado. Un agente te confirmará la documentación y el costo para esa ruta."),
]
_TEMA_EN = (("refund", "charged"), "We're sorry about the duplicate charge. Please share your booking code and an agent will review it and issue the refund for the extra payment.")

_APERTURAS_ES = ["¡Hola! Gracias por escribir a OrbitAir.", "Gracias por contactarte con OrbitAir.", "Entendemos tu consulta y queremos ayudarte."]
_APERTURAS_EN = ["Hi! Thanks for contacting OrbitAir.", "Thank you for reaching out to OrbitAir.", "We understand your concern."]


def _es_ingles(texto: str) -> bool:
    t = f" {texto.lower()} "
    return sum(p in t for p in (" the ", " my ", " how ", " i ", "hi,")) >= 2


def _redactar(provider: str, prompt: str, temperature: float) -> str:
    """Arma una respuesta por temas. Con temperature alta varía la apertura (sampling)."""
    t = prompt.lower()
    ingles = _es_ingles(prompt)
    aperturas = _APERTURAS_EN if ingles else _APERTURAS_ES
    # temperature baja => siempre la opción "más probable"; alta => elige entre varias
    apertura = random.choice(aperturas) if temperature >= 0.7 else aperturas[0]

    if ingles:
        cuerpo = [_TEMA_EN[1]] if any(k in t for k in _TEMA_EN[0]) else ["An agent will review your request shortly."]
    else:
        cuerpo = [resp for claves, resp in _TEMAS if any(k in t for k in claves)]
        cuerpo = cuerpo or ["Un agente humano revisará tu consulta en breve."]

    partes = [apertura, *cuerpo]
    if provider == "anthropic":  # Claude suele cerrar con una frase extra
        partes.append("Is there anything else I can help with?" if ingles else "¿Hay algo más en lo que pueda ayudarte?")
    return " ".join(partes)


def _contar(provider: str, texto: str) -> int:
    if provider == "gemini":
        try:
            return contar_gemini(config.MODELOS["gemini"], texto)
        except Exception:  # modelo que el tokenizador local no conoce, o sin internet la 1ª vez
            pass
    return math.ceil(len(_ENC.encode(texto)) * _FACTOR_TOKENS[provider])


def _generar(provider: str, system: str, prompt: str, temperature: float, max_tokens: int) -> dict:
    texto = _redactar(provider, prompt, temperature)
    input_tokens = _contar(provider, system) + _contar(provider, prompt) + _OVERHEAD_MENSAJES[provider]
    thinking = _THINKING.get(config.GEMINI_THINKING_LEVEL.lower(), 0) if provider == "gemini" else 0
    thinking = min(thinking, max_tokens)  # el modelo piensa primero: puede agotar el techo él solo
    output_tokens = _contar(provider, texto) + thinking
    finish_reason = "stop"
    if output_tokens > max_tokens:  # el modelo corta cuando llega al techo (thinking incluido)
        disponibles = max(0, max_tokens - thinking)
        ids = _ENC.encode(texto)[: int(disponibles / _FACTOR_TOKENS[provider])]
        texto = _ENC.decode(ids)
        output_tokens = max_tokens
        finish_reason = "length"
    return {"text": texto, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "thinking_tokens": thinking, "finish_reason": finish_reason}


def preparar(provider: str) -> None:
    """Carga el tokenizador local de Gemini (~15 s la 1ª vez) para que NO caiga dentro del cronómetro."""
    if provider == "gemini":
        _contar("gemini", "")


def _quizas_fallar() -> None:
    if random.random() < config.MOCK_FAIL_RATE:
        raise MockRateLimitError(retry_after=random.choice([None, 1.0]))


def completar(provider: str, system: str, prompt: str, temperature: float, max_tokens: int) -> dict:
    """Llamada simulada SIN streaming: espera la respuesta completa."""
    _quizas_fallar()
    r = _generar(provider, system, prompt, temperature, max_tokens)
    time.sleep(random.uniform(*_TTFT[provider]) + r["output_tokens"] * _SEG_POR_TOKEN[provider])
    return r


def stream(provider: str, system: str, prompt: str, temperature: float, max_tokens: int, incluir_usage: bool = True) -> Iterator[dict]:
    """
    Llamada simulada CON streaming. Emite {"delta": "..."} y al final
    {"usage": {...} | None, "finish_reason": ...}.

    Igual que OpenAI real: si incluir_usage=False el usage llega vacío (None).
    """
    _quizas_fallar()
    r = _generar(provider, system, prompt, temperature, max_tokens)
    time.sleep(random.uniform(*_TTFT[provider]))  # tiempo hasta el primer token
    trozos = re.findall(r"\S+\s*", r["text"])
    for trozo in trozos:
        yield {"delta": trozo}
        time.sleep(r["output_tokens"] / max(len(trozos), 1) * _SEG_POR_TOKEN[provider])
    usage = {"input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"], "thinking_tokens": r["thinking_tokens"]}
    yield {"usage": usage if incluir_usage else None, "finish_reason": r["finish_reason"]}
