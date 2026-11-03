# metricas.py — CLASE 5, pasos 5.3 y 5.5: métricas deterministas. Ninguna llama a la API.
from registro import RegistroEval

UMBRAL_MINIMO = 0.70  # por categoría — fijado ANTES de correr nada, nunca después de ver los números


# ---------- Paso 5.3: exact match (la salida tiene forma cerrada: es "equipaje" o no lo es) ----------
def exact_match(categoria_modelo: str | None, categoria_referencia: str) -> bool:
    if categoria_modelo is None:  # el parser no encontró categoría: cuenta como error, no se descarta
        return False
    return categoria_modelo.strip().lower() == categoria_referencia.strip().lower()


def evaluar_exact_match(registros: list[RegistroEval]) -> dict:
    """Accuracy global Y por categoría: el promedio esconde la categoría floja."""
    por_categoria: dict[str, list[bool]] = {}
    for r in registros:
        por_categoria.setdefault(r.categoria_esperada, []).append(exact_match(r.categoria_obtenida, r.categoria_esperada))
    detalle = {cat: sum(a) / len(a) for cat, a in por_categoria.items()}
    todos = [a for aciertos in por_categoria.values() for a in aciertos]
    return {"accuracy_global": sum(todos) / len(todos), "accuracy_por_categoria": detalle,
            "aciertos": sum(todos), "n": len(todos)}


# ---------- Paso 5.5: umbral y regresión ----------
def chequear_regresion(scores_por_categoria: dict, umbral: float = UMBRAL_MINIMO) -> list[str]:
    """Regresión, en su forma más directa: una categoría que no llega al piso."""
    return [c for c, score in scores_por_categoria.items() if score < umbral]


# ---------- Paso 5.6: el cruce que importa ----------
def costo_por_acierto(costo_total_usd: float, aciertos: int) -> float:
    return costo_total_usd / aciertos if aciertos else float("inf")


def resumir(registros: list[RegistroEval]) -> dict:
    """Todo lo que el reporte necesita de una versión, calculado desde el .jsonl."""
    em = evaluar_exact_match(registros)
    costo = sum(r.costo_usd for r in registros)
    return {
        "score_total": em["accuracy_global"],
        "scores_por_categoria": em["accuracy_por_categoria"],
        "aciertos": em["aciertos"],
        "n": em["n"],
        "costo_total": costo,
        "costo_por_acierto": costo_por_acierto(costo, em["aciertos"]),
        "tokens_out_prom": sum(r.output_tokens for r in registros) / len(registros),
        "latencia_prom": sum(r.latencia_s for r in registros) / len(registros),
    }
