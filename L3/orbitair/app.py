# app.py — CLASE 3, paso 3.7: el triage como API. Cada error tipado → su código HTTP.
# Ejecutar:  uvicorn app:app --reload    y abrir http://127.0.0.1:8000/docs
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from contrato import ConsultaInvalidaError, ContratoInvalidoError, clasificar_validado

app = FastAPI(title="OrbitAir Triage")


class ConsultaIn(BaseModel):
    texto: str
    simular_error: bool = False  # solo para la demo de reintentos


@app.post("/triage")
def triage(consulta: ConsultaIn):
    try:
        return clasificar_validado(consulta.model_dump()).model_dump()
    except ConsultaInvalidaError as e:
        raise HTTPException(400, detail=str(e))  # error de quien llama: no tiene sentido reintentar
    except ContratoInvalidoError as e:
        raise HTTPException(502, detail=str(e))  # la consulta era válida, pero el modelo no cumplió
