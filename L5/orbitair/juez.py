# juez.py — CLASE 5, paso 5.4: LLM-as-judge. Solo para lo que NO tiene forma cerrada:
# el razonamiento de v4 es texto libre, no se puede comparar con ==. Se juzga contra un CRITERIO fijado de antemano.
import json
import re
from collections import Counter
from pathlib import Path

from llm import ask, with_retry

JUEZ_SYSTEM = """Sos un evaluador estricto de razonamientos de un sistema de triage de una aerolínea.
Se te va a dar la consulta, el criterio que ese razonamiento debería cumplir, y el
razonamiento real que escribió el modelo. Juzgá si el razonamiento aplica ese criterio,
más allá de si la categoría final resultó correcta o no. Un razonamiento largo no es mejor por ser largo.

Devolvé exactamente dos líneas:
VEREDICTO: si|no
MOTIVO: <una línea explicando por qué>"""


def extraer_razonamiento(respuesta: str) -> str:
    """v4 escribe el razonamiento y termina con 'CATEGORIA: x'. Al juez le interesa solo lo de antes."""
    lineas = [l for l in respuesta.strip().splitlines() if l.strip()]
    return "\n".join(l for l in lineas if not re.match(r"\s*CATEGOR[IÍ]A\s*:", l, re.IGNORECASE)).strip()


def parsear_veredicto(texto: str) -> dict:
    """Parsear también es parte del eval: si el juez no respeta el formato, eso es un dato, no un crash."""
    v = re.search(r"VEREDICTO\s*:\s*(s[ií]|no)\b", texto, re.IGNORECASE)
    m = re.search(r"MOTIVO\s*:\s*(.+)", texto, re.IGNORECASE)
    veredicto = None if not v else ("si" if v.group(1).lower().startswith("s") else "no")
    return {"veredicto": veredicto, "motivo": m.group(1).strip() if m else texto.strip()[:120]}


def juzgar_razonamiento(consulta: str, criterio: str, razonamiento: str, repeticiones: int = 1) -> dict:
    """temperature=0 (nada de creatividad en quien evalúa) y, si importa mucho, varias corridas + mayoría."""
    prompt = f"CONSULTA: {consulta}\nCRITERIO ESPERADO: {criterio}\nRAZONAMIENTO: {razonamiento}"
    votos, costo = [], 0.0
    for _ in range(repeticiones):
        r = with_retry(lambda: ask(prompt, JUEZ_SYSTEM, temperature=0.0, max_tokens=120))
        votos.append(parsear_veredicto(r.text))
        costo += r.cost_usd
    conteo = Counter(v["veredicto"] for v in votos)
    ganador = conteo.most_common(1)[0][0]
    motivo = next(v["motivo"] for v in votos if v["veredicto"] == ganador)
    return {"veredicto": ganador, "motivo": motivo, "acuerdo": conteo[ganador] / repeticiones, "costo_usd": costo}


# ---------- Paso 5.4b: ¿le creemos al juez? Se valida contra casos puntuados por un humano ----------
def validar_juez(path: str = "data/juez_humano.json") -> dict:
    casos = json.loads(Path(path).read_text(encoding="utf-8"))
    detalle = []
    for c in casos:
        j = juzgar_razonamiento(c["consulta"], c["criterio"], c["razonamiento"])
        detalle.append({"id": c["id"], "humano": c["veredicto_humano"], "juez": j["veredicto"], "motivo": j["motivo"]})
    coinciden = sum(d["humano"] == d["juez"] for d in detalle)
    return {"acuerdo": coinciden / len(detalle), "detalle": detalle}
