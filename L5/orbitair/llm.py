# llm.py — CLASE 1: el cliente que habla con Gemini.
# Todo el resto del proyecto llama a ask(); nadie más importa el SDK de Google.
import os
import random
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()  # lee GEMINI_API_KEY del archivo .env

MODELO = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
THINKING = os.getenv("GEMINI_THINKING", "minimal")

# USD por 1M de tokens (input, output). Fuente: ai.google.dev/gemini-api/docs/pricing (oct-2026)
PRECIOS = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

client = genai.Client()  # toma la key de la variable de entorno GEMINI_API_KEY


# ---------- Paso 1.2: el contrato de respuesta ----------
@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int  # incluye los tokens de "thinking": también se cobran
    thinking_tokens: int
    latency_s: float
    cost_usd: float
    finish_reason: str  # "STOP" = terminó solo · "MAX_TOKENS" = lo cortó max_tokens
    ttft_s: float | None = None  # solo en streaming


# ---------- Paso 1.5: costo desde el usage real ----------
def calcular_costo(input_tokens: int, output_tokens: int, modelo: str = MODELO) -> float:
    precio_in, precio_out = PRECIOS[modelo]
    return input_tokens / 1_000_000 * precio_in + output_tokens / 1_000_000 * precio_out


def _config(system: str, temperature: float, max_tokens: int, **extra) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_level=THINKING) if THINKING else None,
        **extra,
    )


def _armar(r, latencia: float, ttft: float | None = None, texto: str | None = None) -> LLMResponse:
    um = r.usage_metadata
    thinking = um.thoughts_token_count or 0
    salida = (um.candidates_token_count or 0) + thinking
    return LLMResponse(
        text=texto if texto is not None else (r.text or ""),
        input_tokens=um.prompt_token_count or 0,
        output_tokens=salida,
        thinking_tokens=thinking,
        latency_s=latencia,
        cost_usd=calcular_costo(um.prompt_token_count or 0, salida),
        finish_reason=r.candidates[0].finish_reason.name if r.candidates else "?",
        ttft_s=ttft,
    )


# ---------- Paso 1.3: una llamada ----------
def ask(prompt: str, system: str = "", temperature: float = 0.2, max_tokens: int = 500, **extra) -> LLMResponse:
    t0 = time.perf_counter()  # la latencia se mide SOLO alrededor de la llamada
    r = client.models.generate_content(
        model=MODELO, contents=prompt, config=_config(system, temperature, max_tokens, **extra)
    )
    return _armar(r, time.perf_counter() - t0)


# ---------- Paso 1.6: streaming ----------
def ask_stream(prompt: str, system: str = "", temperature: float = 0.2, max_tokens: int = 500, on_token=None) -> LLMResponse:
    partes, ttft, ultimo = [], None, None
    t0 = time.perf_counter()
    for chunk in client.models.generate_content_stream(
        model=MODELO, contents=prompt, config=_config(system, temperature, max_tokens)
    ):
        if chunk.text:
            if ttft is None:
                ttft = time.perf_counter() - t0  # time-to-first-token
            partes.append(chunk.text)
            if on_token:
                on_token(chunk.text)
        ultimo = chunk  # el usage_metadata del último chunk es el total (acumulado)
    return _armar(ultimo, time.perf_counter() - t0, ttft, "".join(partes))


# ---------- Paso 1.4: contar tokens ANTES de llamar (gratis) ----------
def contar_tokens(texto: str) -> int:
    return client.models.count_tokens(model=MODELO, contents=texto).total_tokens


# ---------- Paso 1.7: reintentos con backoff exponencial ----------
def _espera_sugerida(e: errors.APIError) -> float | None:
    """Gemini manda la espera en el cuerpo del error: RetryInfo → {"retryDelay": "37s"}."""
    for d in (e.details or {}).get("error", {}).get("details", []):
        if d.get("@type", "").endswith("RetryInfo"):
            return float(d["retryDelay"].rstrip("s"))
    return None


def with_retry(fn, max_intentos: int = 4):
    """Reintenta 429 (rate limit) y 5xx (error de Google). Un 400 no se reintenta: no se arregla solo."""
    for intento in range(max_intentos):
        try:
            return fn()
        except errors.APIError as e:
            reintentable = e.code == 429 or e.code >= 500
            if not reintentable or intento == max_intentos - 1:
                raise
            espera = _espera_sugerida(e) or (2**intento + random.uniform(0, 1))
            print(f"  ⚠ error {e.code}, reintento {intento + 1} en {espera:.1f}s")
            time.sleep(espera)
