"""Tests en modo mock: no llaman a ninguna API. Ejecutar: uv run pytest -v"""
import pytest

from orbitair import config
from orbitair.cliente import LLMResponse, ask, ask_stream
from orbitair.costos import calcular_costo, proyectar
from orbitair.reintentos import ReintentosAgotados, calcular_espera, with_retry


@pytest.fixture(autouse=True)
def modo_mock(monkeypatch):
    monkeypatch.setattr(config, "MOCK", True)
    monkeypatch.setattr(config, "MOCK_FAIL_RATE", 0.0)


class ErrorHTTP(Exception):
    def __init__(self, status_code, retry_after=None):
        self.status_code = status_code
        self.retry_after = retry_after


# --- Costos -----------------------------------------------------------------
def test_costo_ejemplo_de_la_leccion():
    # (42/1M × 0.40) + (58/1M × 1.60) = 0.0001096
    assert calcular_costo("gpt-4.1-mini", 42, 58) == pytest.approx(0.0001096)


def test_modelo_desconocido_no_devuelve_cero():
    with pytest.raises(KeyError):
        calcular_costo("gpt-inventado", 10, 10)


def test_proyeccion_a_escala():
    assert proyectar(0.0004, 10_000) == pytest.approx(4.0)


# --- Contrato unificado -----------------------------------------------------
@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_ask_devuelve_siempre_el_mismo_contrato(provider):
    r = ask(provider, "¿Puedo llevar a mi perro en cabina?")
    assert isinstance(r, LLMResponse)
    assert r.input_tokens > 0 and r.output_tokens > 0
    assert r.cost_usd == pytest.approx(calcular_costo(r.model, r.input_tokens, r.output_tokens))
    assert r.finish_reason == "stop"


def test_proveedor_desconocido():
    with pytest.raises(ValueError):
        ask("mistral", "hola")


# --- Gemini -----------------------------------------------------------------
def test_gemini_thinking_se_cobra_como_output(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_THINKING_LEVEL", "minimal")
    sin = ask("gemini", "¿Puedo llevar a mi perro en cabina?")
    monkeypatch.setattr(config, "GEMINI_THINKING_LEVEL", "medium")
    con = ask("gemini", "¿Puedo llevar a mi perro en cabina?")
    assert sin.thinking_tokens == 0 and con.thinking_tokens > 0
    assert con.output_tokens == sin.output_tokens + con.thinking_tokens
    assert con.cost_usd > sin.cost_usd


def test_gemini_thinking_puede_dejar_la_respuesta_vacia(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_THINKING_LEVEL", "high")
    r = ask("gemini", "¿Puedo llevar a mi perro en cabina?", max_tokens=60)
    assert r.finish_reason == "length" and r.text == ""


def test_finish_reason_de_gemini_se_normaliza():
    from types import SimpleNamespace

    from google.genai import types

    from orbitair.cliente import _FINISH, _finish_gemini

    cand = [SimpleNamespace(finish_reason=types.FinishReason.MAX_TOKENS)]
    assert _FINISH[_finish_gemini(cand)] == "length"


def test_retry_lee_el_retry_delay_de_gemini():
    from google.genai import errors

    e = errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}]}})
    esperas = []
    llamadas = [e]

    def fn():
        if llamadas:
            raise llamadas.pop()
        return "ok"

    assert with_retry(fn, sleep=esperas.append, log=lambda _: None) == "ok"
    assert esperas == [37.0]


def test_gemini_400_no_se_reintenta():
    from google.genai import errors

    def fn():
        raise errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT"}})

    with pytest.raises(errors.ClientError):
        with_retry(fn, sleep=lambda _: None, log=lambda _: None)


def test_max_tokens_corta_la_respuesta():
    r = ask("openai", "pierdo la conexión, ¿hotel y comida?, silla de ruedas", max_tokens=10)
    assert r.finish_reason == "length"
    assert r.output_tokens == 10


# --- Streaming --------------------------------------------------------------
def test_stream_con_usage_tiene_costo():
    r = ask_stream("openai", "¿Puedo llevar a mi perro en cabina?")
    assert r.usage_disponible and r.cost_usd > 0
    assert 0 < r.ttft_s <= r.latency_s


def test_stream_openai_sin_include_usage_da_costo_cero():
    r = ask_stream("openai", "¿Puedo llevar a mi perro en cabina?", incluir_usage=False)
    assert not r.usage_disponible
    assert r.cost_usd == 0


def test_stream_anthropic_siempre_trae_usage():
    r = ask_stream("anthropic", "¿Puedo llevar a mi perro en cabina?", incluir_usage=False)
    assert r.usage_disponible and r.cost_usd > 0


# --- Reintentos -------------------------------------------------------------
def test_retry_after_tiene_prioridad():
    assert calcular_espera(intento=4, retry_after=1.5) == 1.5


def test_backoff_crece_exponencialmente():
    # sin jitter: 1, 2, 4, 8 — con jitter suma entre 0 y base
    for i in range(4):
        assert 2**i <= calcular_espera(i, None) <= 2**i + 1


def test_with_retry_reintenta_429_y_respeta_retry_after():
    errores = [ErrorHTTP(429, retry_after=2.0), ErrorHTTP(503)]
    esperas = []

    def fn():
        if errores:
            raise errores.pop(0)
        return "ok"

    assert with_retry(fn, sleep=esperas.append, log=lambda _: None) == "ok"
    assert esperas[0] == 2.0  # usó Retry-After
    assert 2.0 <= esperas[1] <= 3.0  # backoff del intento 1


def test_with_retry_no_reintenta_400():
    llamadas = []

    def fn():
        llamadas.append(1)
        raise ErrorHTTP(400)

    with pytest.raises(ErrorHTTP):
        with_retry(fn, sleep=lambda _: None, log=lambda _: None)
    assert len(llamadas) == 1


def test_with_retry_se_agota():
    def fn():
        raise ErrorHTTP(429)

    with pytest.raises(ReintentosAgotados):
        with_retry(fn, max_retries=3, sleep=lambda _: None, log=lambda _: None)
