# app.py — CLASE 4, paso 4.8: el middleware como API.
# Ejecutar:  uvicorn app:app --reload    y abrir http://127.0.0.1:8000/docs
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from contrato import ConsultaInvalidaError, ContratoInvalidoError
from moderacion import Decision, moderar
from pipeline import atender

app = FastAPI(title="OrbitAir Triage seguro")


class ModerarIn(BaseModel):
    user_id: str
    input_text: str
    modo: str = "reglas+llm"


class ConsultaIn(BaseModel):
    user_id: str = "anonimo"
    texto: str
    externo: str | None = None  # un mail o una web que el pasajero pegó


@app.post("/moderate", response_model=Decision)
def moderate(body: ModerarIn):
    """Solo la compuerta: cualquier otro servicio puede preguntar 'permitir / marcar / bloquear'."""
    return moderar(body.input_text, body.user_id, body.modo)


@app.post("/triage")
def triage(consulta: ConsultaIn):
    try:
        return atender(consulta.texto, consulta.user_id, consulta.externo)
    except ConsultaInvalidaError as e:
        raise HTTPException(400, detail=str(e))
    except ContratoInvalidoError as e:
        raise HTTPException(502, detail=str(e))
