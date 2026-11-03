# test_metricas.py — tests SIN llamar a la API: las métricas son código determinista.
# Ejecutar:  python test_metricas.py
import json
import sys
from collections import Counter
from pathlib import Path

from juez import extraer_razonamiento, parsear_veredicto
from metricas import chequear_regresion, costo_por_acierto, evaluar_exact_match, exact_match
from registro import RegistroEval

sys.stdout.reconfigure(encoding="utf-8")


def fila(esperada, obtenida, costo=0.001):
    return RegistroEval("X", "v", "t", esperada, obtenida, 10, 5, costo, 0.1, "", 0.0)


def test_exact_match_normaliza_y_none_es_error():
    assert exact_match(" Equipaje ", "equipaje")
    assert not exact_match(None, "equipaje")
    assert not exact_match("cambios", "equipaje")


def test_promedio_esconde_la_categoria_floja():
    regs = [fila("equipaje", "equipaje")] * 9 + [fila("cambios", "otros")]
    r = evaluar_exact_match(regs)
    assert r["accuracy_global"] == 0.9
    assert r["accuracy_por_categoria"]["cambios"] == 0.0
    assert chequear_regresion(r["accuracy_por_categoria"]) == ["cambios"]


def test_costo_por_acierto():
    assert costo_por_acierto(0.03, 3) == 0.01
    assert costo_por_acierto(0.03, 0) == float("inf")


def test_parsea_veredicto_del_juez():
    assert parsear_veredicto("VEREDICTO: sí\nMOTIVO: aplica el criterio") == {"veredicto": "si", "motivo": "aplica el criterio"}
    assert parsear_veredicto("no sé")["veredicto"] is None


def test_extrae_razonamiento_sin_la_categoria():
    assert extraer_razonamiento("Pide X.\nClasifico lo que pide.\nCATEGORIA: cambios") == "Pide X.\nClasifico lo que pide."


def test_dataset_curado():
    d = json.loads(Path("data/eval_dataset.json").read_text(encoding="utf-8"))
    assert len({c["id"] for c in d}) == len(d) >= 30
    assert len(set(Counter(c["categoria_esperada"] for c in d).values())) == 1  # categorías parejas
    assert sum(c["dificultad"] != "facil" for c in d) / len(d) >= 0.4  # más difíciles que producción
    assert all(c["criterio"] and c["nota"] for c in d)  # la referencia se documenta


if __name__ == "__main__":
    tests = [f for n, f in dict(globals()).items() if n.startswith("test_")]
    for t in tests:
        t()
        print(f"✔ {t.__name__}")
    print(f"{len(tests)} tests OK")
