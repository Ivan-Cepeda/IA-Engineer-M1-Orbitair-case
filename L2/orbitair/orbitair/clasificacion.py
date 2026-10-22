# clasificacion.py
# Llama al modelo con una versión del prompt de triage y convierte su texto en una categoría.
import json
import re
from dataclasses import dataclass

from orbitair.cliente import LLMResponse, ask
from orbitair.prompts import CATEGORIAS, mensaje_usuario, renderizar_system

# El razonamiento (CoT) necesita espacio; una etiqueta JSON, no.
MAX_TOKENS_POR_VERSION = {"v4": 300}
MAX_TOKENS_DEFAULT = 60


@dataclass
class Clasificacion:
    categoria: str | None  # None si no se pudo extraer
    valida: bool  # está en CATEGORIAS
    metodo: str  # "json" | "linea_final" | "heuristica" | "fallo"
    respuesta: LLMResponse


def parsear(texto: str) -> tuple[str | None, str]:
    """
    Extrae la categoría del texto del modelo, en orden de confiabilidad:
    1. JSON {"categoria": ...}            (v2, v3)
    2. Última línea "CATEGORIA: ..."      (v4, chain-of-thought)
    3. Heurística: buscar un nombre válido en el texto libre (v1). Frágil: solo para comparar.
    """
    limpio = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        dato = json.loads(limpio)
        if isinstance(dato, dict) and "categoria" in dato:
            return str(dato["categoria"]).strip().lower(), "json"
    except json.JSONDecodeError:
        pass

    lineas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    if lineas:
        m = re.match(r"^CATEGOR[IÍ]A\s*:\s*(\S+)", lineas[-1], re.IGNORECASE)
        if m:
            return m.group(1).strip().lower().strip(".\"'`"), "linea_final"

    encontradas = [c for c in CATEGORIAS if re.search(rf"\b{c}\b", texto.lower())]
    if len(encontradas) == 1:
        return encontradas[0], "heuristica"
    return None, "fallo"


def clasificar(provider: str, version: str, texto: str, *, temperature: float = 0.0) -> Clasificacion:
    """Una consulta → una categoría, con la versión de prompt pedida."""
    r = ask(
        provider,
        mensaje_usuario(texto),
        system=renderizar_system(version),
        temperature=temperature,
        max_tokens=MAX_TOKENS_POR_VERSION.get(version, MAX_TOKENS_DEFAULT),
    )
    categoria, metodo = parsear(r.text)
    return Clasificacion(categoria, categoria in CATEGORIAS, metodo, r)
