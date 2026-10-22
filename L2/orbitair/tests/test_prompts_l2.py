"""Tests de L2 en modo mock: plantillas, parser y evaluación. Ejecutar: uv run pytest -v"""
import pytest

from orbitair import config
from orbitair.clasificacion import parsear
from orbitair.datos import cargar_consultas, cargar_etiquetas
from orbitair.evaluacion import evaluar, resumir
from orbitair.prompts import CATEGORIAS, renderizar_system, versiones


@pytest.fixture(autouse=True)
def modo_mock(monkeypatch):
    monkeypatch.setattr(config, "MOCK", True)
    monkeypatch.setattr(config, "MOCK_FAIL_RATE", 0.0)


# --- Plantillas y variables ---------------------------------------------------
def test_versiones_disponibles():
    assert versiones() == ["v1", "v2", "v3", "v3_obvio", "v4"]


@pytest.mark.parametrize("version", ["v2", "v3", "v3_obvio", "v4"])
def test_plantillas_renderizan_y_listan_todas_las_categorias(version):
    texto = renderizar_system(version)
    assert "OrbitAir" in texto
    assert all(c in texto for c in CATEGORIAS)  # incluida la categoría cajón "otro"
    assert "{" not in texto.replace('{"categoria"', "")  # sin variables sin reemplazar


def test_variables_cambian_sin_tocar_la_plantilla():
    assert "AeroSur" in renderizar_system("v2", empresa="AeroSur")


# --- Etiquetas ----------------------------------------------------------------
def test_todas_las_consultas_estan_etiquetadas_con_categorias_validas():
    etiquetas = cargar_etiquetas()
    assert {c["id"] for c in cargar_consultas()} == set(etiquetas)
    assert all(e["categoria"] in CATEGORIAS for e in etiquetas.values())


# --- Parser -------------------------------------------------------------------
@pytest.mark.parametrize("salida,esperado", [
    ('{"categoria": "equipaje"}', ("equipaje", "json")),
    ('```json\n{"categoria": "millas"}\n```', ("millas", "json")),
    ("Tema: x\nPide: y\nDecisión: z\nCATEGORIA: otro", ("otro", "linea_final")),
    ("Categoría: reembolsos_cobros", ("reembolsos_cobros", "linea_final")),
    ("Creo que es reembolsos cobros", (None, "fallo")),
])
def test_parsear(salida, esperado):
    assert parsear(salida) == esperado


# --- Evaluación (con el mock guionado) ---------------------------------------
def _exactitud(version, lote):
    return resumir(evaluar(version, "openai", cargar_consultas(lote), cargar_etiquetas(), log=lambda _: None))["exactitud"]


def test_few_shot_obvio_no_mejora_y_el_de_errores_si():
    assert _exactitud("v3_obvio", "dev") == _exactitud("v2", "dev")
    assert _exactitud("v3", "dev") > _exactitud("v2", "dev")


def test_cot_cuesta_mas_tokens_de_salida():
    filas3 = evaluar("v3", "openai", cargar_consultas("dev")[:3], cargar_etiquetas())
    filas4 = evaluar("v4", "openai", cargar_consultas("dev")[:3], cargar_etiquetas())
    assert resumir(filas4)["tokens_out_medio"] > 2 * resumir(filas3)["tokens_out_medio"]


def test_sin_cajon_se_inventan_categorias():
    filas = evaluar("v1", "openai", cargar_consultas("holdout"), cargar_etiquetas())
    assert resumir(filas)["invalidas"] > 0
