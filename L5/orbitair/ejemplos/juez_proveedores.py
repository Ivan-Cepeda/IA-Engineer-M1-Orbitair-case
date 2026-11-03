# ejemplos/juez_proveedores.py — REFERENCIA (no se corre en clase): el mismo juez con OpenAI y con Claude.
# Lo único que cambia entre proveedores es la llamada; el prompt del juez, el parseo y la validación son iguales.
# Para probarlo:  pip install openai anthropic  +  OPENAI_API_KEY / ANTHROPIC_API_KEY en .env
# Ejecutar desde la carpeta orbitair:  python ejemplos/juez_proveedores.py
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar juez.py y llm.py
load_dotenv()

from juez import JUEZ_SYSTEM, parsear_veredicto  # noqa: E402


def armar_prompt(consulta: str, criterio: str, razonamiento: str) -> str:
    return f"CONSULTA: {consulta}\nCRITERIO ESPERADO: {criterio}\nRAZONAMIENTO: {razonamiento}"


# ---------- OpenAI (Chat Completions) ----------
def juzgar_openai(consulta: str, criterio: str, razonamiento: str, modelo: str = "gpt-5-mini") -> dict:
    from openai import OpenAI

    client = OpenAI()  # lee OPENAI_API_KEY
    t0 = time.perf_counter()
    r = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", modelo),
        messages=[{"role": "system", "content": JUEZ_SYSTEM},  # en OpenAI el system va como mensaje
                  {"role": "user", "content": armar_prompt(consulta, criterio, razonamiento)}],
        temperature=0.0,  # algunos modelos de razonamiento solo aceptan el default: si falla, quitar esta línea
        max_completion_tokens=120,
    )
    return {**parsear_veredicto(r.choices[0].message.content),
            "input_tokens": r.usage.prompt_tokens, "output_tokens": r.usage.completion_tokens,
            "latencia_s": time.perf_counter() - t0}


# ---------- Anthropic (Claude, Messages API) ----------
def juzgar_claude(consulta: str, criterio: str, razonamiento: str, modelo: str = "claude-haiku-5-5") -> dict:
    import anthropic

    client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY
    t0 = time.perf_counter()
    r = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", modelo),
        system=JUEZ_SYSTEM,  # en Claude el system es un parámetro aparte, no un mensaje
        messages=[{"role": "user", "content": armar_prompt(consulta, criterio, razonamiento)}],
        temperature=0.0,
        max_tokens=120,  # obligatorio en Claude
    )
    texto = "".join(b.text for b in r.content if b.type == "text")
    return {**parsear_veredicto(texto),
            "input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens,
            "latencia_s": time.perf_counter() - t0}


# ---------- Gemini (lo que usamos en clase) — para comparar las tres formas ----------
def juzgar_gemini(consulta: str, criterio: str, razonamiento: str) -> dict:
    from llm import ask, with_retry

    r = with_retry(lambda: ask(armar_prompt(consulta, criterio, razonamiento), JUEZ_SYSTEM, temperature=0.0, max_tokens=120))
    return {**parsear_veredicto(r.text), "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
            "latencia_s": r.latency_s}


# Buena práctica que esto habilita: el juez de OTRO proveedor que el modelo evaluado
# reduce el sesgo de "un modelo se aprueba a sí mismo".
if __name__ == "__main__":
    caso = ("¿El avión tiene wifi?", "distingue una consulta informativa de un servicio especial que se gestiona",
            "Pregunta por una característica del avión. Es información, no pide gestionar nada.")
    for nombre, fn, key in (("gemini", juzgar_gemini, "GEMINI_API_KEY"), ("openai", juzgar_openai, "OPENAI_API_KEY"),
                            ("claude", juzgar_claude, "ANTHROPIC_API_KEY")):
        if os.getenv(key):
            print(nombre, fn(*caso))
        else:
            print(f"{nombre}: falta {key}, se omite")
