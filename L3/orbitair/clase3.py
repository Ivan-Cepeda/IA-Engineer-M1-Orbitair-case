# clase3.py — CLASE 3: structured outputs y function calling
# Ejecutar:  python clase3.py
import json
import sys

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import app
from contrato import (TOOL_SCHEMA, ConsultaInvalidaError, ContratoInvalidoError, TriageContrato,
                      TriageContratoDebil, ask_tool, clasificar_validado)
from llm import ask
from triage import CATEGORIAS, cargar_prompt

sys.stdout.reconfigure(encoding="utf-8")

# 3.1 — Modo JSON: garantiza que sea JSON… no que sea el JSON correcto
print("=== 3.1 Modo JSON ===")
r = ask("No me llegaron las millas del vuelo de la semana pasada",
        "Devuelve un objeto JSON con las claves categoria y confianza.",
        temperature=0, response_mime_type="application/json")
dato = json.loads(r.text)
print(f"JSON válido: {dato}")
print(f"¿la categoría es una de las nuestras? {dato.get('categoria') in CATEGORIAS}  ← nadie se lo garantizó\n")

# 3.2 / 3.3 — Contrato débil vs. contrato fuerte (sin llamar a la API)
print("=== 3.2-3.3 Contrato débil vs. fuerte ===")
basura = {"respuesta": "ok", "confianza": 47.0, "categoria": "factura", "acciones": ["llamar_al_gerente"]}
print(f"Débil:  {TriageContratoDebil.model_validate(basura)}  ← pasó sin errores")
try:
    TriageContrato.model_validate(basura)
except ValidationError as e:
    print(f"Fuerte: rechazado con {e.error_count()} errores:")
    for err in e.errors():
        print(f"   {err['loc'][0]}: {err['msg']}")
print()

# 3.4 — Tool calling: el schema sale del contrato
print("=== 3.4 Tool calling ===")
print(f"Schema enviado a Gemini (extracto): categoria ∈ {TOOL_SCHEMA['properties']['categoria']['enum']}")
r = ask_tool("En el aeropuerto me cobraron dos veces el equipaje de bodega.", cargar_prompt("v5"))
print(f"args (ya es un dict): {r.args}")
print(f"validado: {TriageContrato.model_validate(r.args)}\n")

# 3.5 — Reintentos con el error inyectado
print("=== 3.5 Reintento: el primer intento viene roto a propósito ===")
contrato = clasificar_validado({"texto": "¿Puedo llevar a mi perro en cabina?", "simular_error": True})
print(f"   intento 2 válido → {contrato}\n")

# 3.6 — Errores tipados
print("=== 3.6 Errores tipados ===")
try:
    clasificar_validado({"texto": "   "})
except ConsultaInvalidaError as e:
    print(f"ConsultaInvalidaError → {e}  (0 llamadas al modelo)")
try:
    clasificar_validado({"texto": "¿Tienen wifi?", "simular_error": True}, max_intentos=1)
except ContratoInvalidoError as e:
    print(f"ContratoInvalidoError → {str(e)[:90]}...")
print()

# 3.7 — La API: cada error tipado tiene su código HTTP
print("=== 3.7 API /triage ===")
api = TestClient(app)
for cuerpo in [{"texto": "¿Tienen wifi a bordo?"}, {"texto": ""}]:
    resp = api.post("/triage", json=cuerpo)
    print(f"{resp.status_code} ← {cuerpo} → {resp.json()}")
