# evaluacion.py
# Decidir con datos, no con intuición: cada versión del prompt se mide contra las etiquetas.
import statistics
from collections import Counter

from orbitair.clasificacion import clasificar
from orbitair.costos import proyectar
from orbitair.reintentos import with_retry


def evaluar(
    version: str,
    provider: str,
    consultas: list[dict],
    etiquetas: dict[str, dict],
    *,
    temperature: float = 0.0,
    repeticiones: int = 1,
    log=print,
) -> list[dict]:
    """
    Clasifica cada consulta `repeticiones` veces. La primera corrida define el acierto;
    las demás solo miden si el modelo responde siempre lo mismo (consistencia).
    """
    filas = []
    for c in consultas:
        corridas = [
            with_retry(lambda: clasificar(provider, version, c["texto"], temperature=temperature), log=log)
            for _ in range(repeticiones)
        ]
        primera = corridas[0]
        esperada = etiquetas[c["id"]]["categoria"]
        filas.append({
            "version": version,
            "proveedor": provider,
            "id": c["id"],
            "lote": c["lote"],
            "esperada": esperada,
            "obtenida": primera.categoria or "",
            "acierto": primera.categoria == esperada,
            "valida": primera.valida,
            "metodo_parseo": primera.metodo,
            "regla": etiquetas[c["id"]]["regla"] or "",
            "consistente": len({r.categoria for r in corridas}) == 1,
            "tokens_in": primera.respuesta.input_tokens,
            "tokens_out": primera.respuesta.output_tokens,
            "latencia_s": round(primera.respuesta.latency_s, 3),
            "costo_usd": round(primera.respuesta.cost_usd, 10),
            "respuesta": primera.respuesta.text.replace("\n", " | "),
        })
    return filas


def resumir(filas: list[dict], escala: int = 10_000) -> dict:
    n = len(filas)
    costo_medio = sum(f["costo_usd"] for f in filas) / n
    return {
        "version": filas[0]["version"],
        "proveedor": filas[0]["proveedor"],
        "n": n,
        "exactitud": sum(f["acierto"] for f in filas) / n,
        "invalidas": sum(not f["valida"] for f in filas),
        "parseo_fragil": sum(f["metodo_parseo"] in ("heuristica", "fallo") for f in filas),
        "consistencia": sum(f["consistente"] for f in filas) / n,
        "tokens_in_medio": statistics.mean(f["tokens_in"] for f in filas),
        "tokens_out_medio": statistics.mean(f["tokens_out"] for f in filas),
        "latencia_media_s": statistics.mean(f["latencia_s"] for f in filas),
        "costo_medio_usd": costo_medio,
        "proyeccion_usd": proyectar(costo_medio, escala),
    }


def errores(filas: list[dict]) -> list[dict]:
    return [f for f in filas if not f["acierto"]]


def categorias_inventadas(filas: list[dict]) -> Counter:
    return Counter(f["obtenida"] or "(sin parsear)" for f in filas if not f["valida"])
