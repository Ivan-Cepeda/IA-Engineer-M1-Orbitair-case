# cliente.py
# PASO 1 — Contrato unificado: ask(provider, prompt) devuelve SIEMPRE un LLMResponse,
# sin importar si habló con OpenAI, con Anthropic, con Gemini o con el mock.
# PASO 3a — ask_stream(): la misma idea, pero recibiendo la respuesta en partes.
import time
from dataclasses import asdict, dataclass
from typing import Callable, Iterator

from orbitair import config, mock
from orbitair.costos import calcular_costo
from orbitair.datos import SYSTEM_PROMPT


@dataclass
class LLMResponse:
    """El contrato: todo proveedor se traduce a esta misma forma."""

    provider: str
    model: str
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float  # latencia REAL: desde que sale el request hasta el último token
    cost_usd: float  # calculado desde el usage de la API, nunca estimado
    finish_reason: str  # normalizado: "stop" | "length" | otro
    ttft_s: float | None = None  # time-to-first-token (solo streaming)
    thinking_tokens: int = 0  # Gemini: tokens de "razonamiento" (ya incluidos en output_tokens)
    usage_disponible: bool = True  # False si el proveedor no informó el usage
    mock: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# Cada proveedor llama distinto al "por qué terminó". Lo normalizamos.
_FINISH = {
    "stop": "stop", "end_turn": "stop", "stop_sequence": "stop", "STOP": "stop",  # terminó solo
    "length": "length", "max_tokens": "length", "MAX_TOKENS": "length",  # lo cortó max_tokens
}

_clientes: dict = {}


def _cliente(provider: str):
    """Crea (una sola vez) el cliente del SDK. Import diferido: en modo mock no hace falta."""
    if provider not in _clientes:
        # max_retries=0: los SDK reintentan solos 2 veces por defecto. Lo apagamos para que
        # los reintentos sean visibles y los controle NUESTRO with_retry() (Paso 3b).
        if provider == "openai":
            import openai

            _clientes[provider] = openai.OpenAI(api_key=config.OPENAI_API_KEY, max_retries=0)
        elif provider == "anthropic":
            import anthropic

            _clientes[provider] = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=0)
        elif provider == "gemini":
            from google import genai

            # El SDK de Gemini NO reintenta por defecto (retry_options=None): no hay nada que apagar.
            _clientes[provider] = genai.Client(api_key=config.GEMINI_API_KEY)
    return _clientes[provider]


# ---------------------------------------------------------------------------
# Adaptadores SIN streaming: hablan el idioma de cada SDK y devuelven un dict común
# ---------------------------------------------------------------------------
def _openai(model: str, system: str, prompt: str, temperature: float, max_tokens: int) -> dict:
    r = _cliente("openai").chat.completions.create(
        model=model,
        # OpenAI: el system prompt es un mensaje más, con role "system"
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,  # opcional en OpenAI
    )
    return {
        "text": r.choices[0].message.content or "",
        "input_tokens": r.usage.prompt_tokens,
        "output_tokens": r.usage.completion_tokens,
        "finish_reason": r.choices[0].finish_reason,
    }


def _anthropic(model: str, system: str, prompt: str, temperature: float, max_tokens: int) -> dict:
    r = _cliente("anthropic").messages.create(
        model=model,
        max_tokens=max_tokens,  # OBLIGATORIO en Anthropic
        system=system,  # Anthropic: el system prompt va aparte, no en messages
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return {
        "text": "".join(b.text for b in r.content if b.type == "text"),  # content es una lista de bloques
        "input_tokens": r.usage.input_tokens,
        "output_tokens": r.usage.output_tokens,
        "finish_reason": r.stop_reason,
    }


def _gemini_config(system: str, temperature: float, max_tokens: int):
    from google.genai import types

    return types.GenerateContentConfig(
        system_instruction=system,  # Gemini: el system prompt va en la config
        temperature=temperature,
        max_output_tokens=max_tokens,  # OJO: incluye los tokens de thinking
        thinking_config=types.ThinkingConfig(thinking_level=config.GEMINI_THINKING_LEVEL)
        if config.GEMINI_THINKING_LEVEL else None,
    )


def _usage_gemini(um) -> dict:
    """usage_metadata trae la respuesta y el thinking por separado; ambos se cobran como output."""
    respuesta = um.candidates_token_count or 0
    thinking = um.thoughts_token_count or 0
    return {"input_tokens": um.prompt_token_count or 0, "output_tokens": respuesta + thinking, "thinking_tokens": thinking}


def _finish_gemini(candidates) -> str | None:
    if not candidates or candidates[0].finish_reason is None:
        return None
    fr = candidates[0].finish_reason
    return getattr(fr, "name", fr)  # es un enum (FinishReason.STOP) → "STOP"


def _gemini(model: str, system: str, prompt: str, temperature: float, max_tokens: int) -> dict:
    r = _cliente("gemini").models.generate_content(
        model=model,
        contents=prompt,  # Gemini: "contents" (partes), no "messages"
        config=_gemini_config(system, temperature, max_tokens),
    )
    return {"text": r.text or "", **_usage_gemini(r.usage_metadata), "finish_reason": _finish_gemini(r.candidates)}


_ADAPTADORES = {"openai": _openai, "anthropic": _anthropic, "gemini": _gemini}


def _validar(provider: str) -> str:
    if provider not in _ADAPTADORES:
        raise ValueError(f"Proveedor '{provider}' no soportado. Opciones: {list(_ADAPTADORES)}")
    return config.MODELOS[provider]


def ask(
    provider: str,
    prompt: str,
    *,
    system: str = SYSTEM_PROMPT,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """
    Una llamada completa (sin streaming) a cualquier proveedor.

    :param provider: "openai", "anthropic" o "gemini".
    :param prompt: el texto del pasajero.
    :return: LLMResponse con texto, usage, latencia y costo real.
    """
    model = _validar(provider)
    temperature = config.TEMPERATURE if temperature is None else temperature
    max_tokens = config.MAX_TOKENS if max_tokens is None else max_tokens

    if config.MOCK:
        mock.preparar(provider)  # trabajo local de una sola vez: fuera del cronómetro

    # La latencia se mide SOLO alrededor de la llamada: nada de prints adentro.
    t0 = time.perf_counter()
    if config.MOCK:
        raw = mock.completar(provider, system, prompt, temperature, max_tokens)
    else:
        raw = _ADAPTADORES[provider](model, system, prompt, temperature, max_tokens)
    latency = time.perf_counter() - t0

    return LLMResponse(
        provider=provider,
        model=model,
        text=raw["text"],
        input_tokens=raw["input_tokens"],
        output_tokens=raw["output_tokens"],
        latency_s=latency,
        cost_usd=calcular_costo(model, raw["input_tokens"], raw["output_tokens"]),
        finish_reason=_FINISH.get(raw["finish_reason"], str(raw["finish_reason"])),
        thinking_tokens=raw.get("thinking_tokens", 0),
        mock=config.MOCK,
    )


# ---------------------------------------------------------------------------
# Adaptadores CON streaming: emiten {"delta": ...} y al final {"usage": ..., "finish_reason": ...}
# ---------------------------------------------------------------------------
def _openai_stream(model, system, prompt, temperature, max_tokens, incluir_usage) -> Iterator[dict]:
    kwargs = dict(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    if incluir_usage:
        kwargs["stream_options"] = {"include_usage": True}  # sin esto, el usage llega vacío => costo 0

    usage, finish = None, None
    for chunk in _cliente("openai").chat.completions.create(**kwargs):
        if chunk.choices:  # el último chunk (el del usage) viene con choices vacío
            delta = chunk.choices[0].delta.content
            if delta:
                yield {"delta": delta}
            finish = chunk.choices[0].finish_reason or finish
        if chunk.usage:
            usage = {"input_tokens": chunk.usage.prompt_tokens, "output_tokens": chunk.usage.completion_tokens}
    yield {"usage": usage, "finish_reason": finish}


def _anthropic_stream(model, system, prompt, temperature, max_tokens, incluir_usage) -> Iterator[dict]:
    # incluir_usage no aplica: Anthropic siempre entrega el usage, pero recién al cerrar el stream
    with _cliente("anthropic").messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    ) as s:
        for texto in s.text_stream:
            yield {"delta": texto}
        final = s.get_final_message()
    yield {
        "usage": {"input_tokens": final.usage.input_tokens, "output_tokens": final.usage.output_tokens},
        "finish_reason": final.stop_reason,
    }


def _gemini_stream(model, system, prompt, temperature, max_tokens, incluir_usage) -> Iterator[dict]:
    # incluir_usage no aplica: cada chunk de Gemini trae usage_metadata acumulado; vale el último
    usage, finish = None, None
    for chunk in _cliente("gemini").models.generate_content_stream(
        model=model, contents=prompt, config=_gemini_config(system, temperature, max_tokens)
    ):
        if chunk.text:
            yield {"delta": chunk.text}
        if chunk.usage_metadata:
            usage = _usage_gemini(chunk.usage_metadata)
        finish = _finish_gemini(chunk.candidates) or finish
    yield {"usage": usage, "finish_reason": finish}


_STREAMS = {"openai": _openai_stream, "anthropic": _anthropic_stream, "gemini": _gemini_stream}


def ask_stream(
    provider: str,
    prompt: str,
    *,
    system: str = SYSTEM_PROMPT,
    temperature: float | None = None,
    max_tokens: int | None = None,
    on_token: Callable[[str], None] | None = None,
    incluir_usage: bool = True,
) -> LLMResponse:
    """
    Igual que ask(), pero consumiendo la respuesta en partes y midiendo el TTFT.

    :param on_token: función que recibe cada fragmento (por ejemplo, para imprimirlo).
    :param incluir_usage: solo OpenAI. Ponerlo en False reproduce el error clásico (costo 0).
    """
    model = _validar(provider)
    temperature = config.TEMPERATURE if temperature is None else temperature
    max_tokens = config.MAX_TOKENS if max_tokens is None else max_tokens
    if config.MOCK:
        mock.preparar(provider)
        eventos = mock.stream(provider, system, prompt, temperature, max_tokens,
                              incluir_usage=incluir_usage or provider != "openai")
    else:
        eventos = _STREAMS[provider](model, system, prompt, temperature, max_tokens, incluir_usage)

    partes: list[str] = []
    final: dict = {}
    ttft = None
    tiempo_en_callbacks = 0.0  # lo que tarda NUESTRO print no es latencia del proveedor

    t0 = time.perf_counter()
    for ev in eventos:
        if "delta" in ev:
            if ttft is None:
                ttft = time.perf_counter() - t0
            partes.append(ev["delta"])
            if on_token:
                t_cb = time.perf_counter()
                on_token(ev["delta"])
                tiempo_en_callbacks += time.perf_counter() - t_cb
        else:
            final = ev
    latency = time.perf_counter() - t0 - tiempo_en_callbacks

    usage = final.get("usage")
    in_tok = usage["input_tokens"] if usage else 0
    out_tok = usage["output_tokens"] if usage else 0
    return LLMResponse(
        provider=provider,
        model=model,
        text="".join(partes),
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_s=latency,
        cost_usd=calcular_costo(model, in_tok, out_tok),
        finish_reason=_FINISH.get(final.get("finish_reason"), str(final.get("finish_reason"))),
        ttft_s=ttft,
        thinking_tokens=usage.get("thinking_tokens", 0) if usage else 0,
        usage_disponible=usage is not None,
        mock=config.MOCK,
    )
