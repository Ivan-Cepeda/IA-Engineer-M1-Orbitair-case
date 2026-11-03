# triage.py — CLASE 2: el prompt de clasificación como artefacto versionado.
import json
import re
from pathlib import Path

from llm import ask, with_retry

# ---------- Paso 2.1: una única fuente de verdad para las categorías ----------
CATEGORIAS = ["equipaje", "cambios", "reembolsos", "servicios_especiales", "otros"]
EMPRESA = "OrbitAir"


# ---------- Paso 2.2: plantilla (se versiona) + variables (cambian por request) ----------
def cargar_prompt(version: str) -> str:
    plantilla = Path(f"prompts/triage_{version}.txt").read_text(encoding="utf-8")
    return plantilla.format(empresa=EMPRESA, categorias=", ".join(CATEGORIAS))


def mensaje_usuario(texto: str, externo: str | None = None) -> str:
    mensaje = f"<consulta>{texto}</consulta>"  # los delimitadores separan instrucción de contenido
    if externo:  # Clase 4: contenido que el pasajero pegó (un mail, una web) va en SU PROPIO canal
        mensaje += f"\n<contenido_externo>{externo}</contenido_externo>"
    return mensaje


# ---------- Paso 2.3: leer la categoría de la respuesta ----------
def parsear(respuesta: str) -> str | None:
    """Busca 'CATEGORIA: x' en la última línea; si no está, busca un nombre válido suelto."""
    lineas = [l.strip() for l in respuesta.strip().splitlines() if l.strip()]
    if lineas:
        m = re.match(r"CATEGOR[IÍ]A\s*:\s*(\w+)", lineas[-1], re.IGNORECASE)
        if m:
            return m.group(1).lower()
    encontradas = [c for c in CATEGORIAS if c in respuesta.lower()]
    return encontradas[0] if len(encontradas) == 1 else None


def clasificar(texto: str, version: str) -> tuple[str | None, object]:
    max_tokens = 200 if version == "v4" else 30  # el razonamiento necesita espacio
    r = with_retry(lambda: ask(mensaje_usuario(texto), cargar_prompt(version), temperature=0, max_tokens=max_tokens))
    return parsear(r.text), r


# ---------- Paso 2.4: medir con datos, no con intuición ----------
def evaluar(version: str, mostrar_errores: bool = True) -> dict:
    consultas = json.load(open("consultas.json", encoding="utf-8"))
    aciertos, costo, tokens_out = 0, 0.0, 0
    for c in consultas:
        categoria, r = clasificar(c["texto"], version)
        aciertos += categoria == c["categoria"]
        costo += r.cost_usd
        tokens_out += r.output_tokens
        if mostrar_errores and categoria != c["categoria"]:
            print(f"   ✘ {c['id']}: esperada={c['categoria']}, obtenida={categoria} · respuesta={r.text[:60]!r}")
    n = len(consultas)
    return {"version": version, "exactitud": aciertos / n, "tokens_out": tokens_out / n, "costo_10k": costo / n * 10_000}
