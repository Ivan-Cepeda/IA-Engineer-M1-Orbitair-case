# contrato.py — CLASE 3: salidas estructuradas, validación y function calling.
# De "lo que el modelo respondió" (texto) a un contrato que el sistema puede verificar.
from dataclasses import dataclass
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from llm import MODELO, THINKING, client, with_retry
from triage import CATEGORIAS, cargar_prompt, mensaje_usuario

# ---------- Paso 3.2: el contrato débil (corre sin errores… y no protege nada) ----------
class TriageContratoDebil(BaseModel):
    respuesta: str
    confianza: float
    categoria: str  # cualquier texto pasa: "factura" también
    acciones: list[str]  # cualquier lista pasa


# ---------- Paso 3.3: el contrato que sí protege (tipo + DOMINIO de valores) ----------
ACCIONES = ["derivar_agente", "pedir_num_reserva", "informar_politica", "iniciar_reembolso", "sin_accion"]

# Única fuente de verdad: los valores válidos salen de las listas, no se tipean dos veces.
CategoriaValida = Literal[tuple(CATEGORIAS)]
AccionValida = Literal[tuple(ACCIONES)]


class TriageContrato(BaseModel):
    respuesta: str = Field(min_length=1, description="Primera respuesta breve para el pasajero")
    confianza: float = Field(ge=0.0, le=1.0, description="Qué tan seguro estás de la categoría, de 0 a 1")
    categoria: CategoriaValida
    acciones: list[AccionValida] = Field(min_length=1)


# ---------- Paso 3.6: errores tipados ----------
class ConsultaInvalidaError(Exception):
    """La consulta no se puede procesar (ej. texto vacío). No se reintenta: es un error de quien llama."""


class ContratoInvalidoError(Exception):
    """Se agotaron los reintentos sin obtener un contrato válido."""


# ---------- Paso 3.4: tool calling — el schema sale del contrato ----------
TOOL_NAME = "clasificar_consulta"
TOOL_SCHEMA = TriageContrato.model_json_schema()


@dataclass
class ToolResponse:
    args: dict | None  # los argumentos de la función, ya como dict (o None si no hubo llamada)
    raw: str  # lo que vino, para poder mostrar el error


def ask_tool(texto: str, system: str) -> ToolResponse:
    herramienta = types.Tool(function_declarations=[types.FunctionDeclaration(
        name=TOOL_NAME,
        description="Registra la clasificación de la consulta del pasajero.",
        parameters_json_schema=TOOL_SCHEMA,
    )])
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        tools=[herramienta],
        # mode="ANY" + un solo nombre permitido = el modelo ESTÁ OBLIGADO a llamar a esta función
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
            mode="ANY", allowed_function_names=[TOOL_NAME])),
        # el SDK no debe ejecutar nada por su cuenta: solo queremos los argumentos
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=THINKING) if THINKING else None,
    )
    r = with_retry(lambda: client.models.generate_content(model=MODELO, contents=mensaje_usuario(texto), config=config))
    llamadas = r.function_calls or []
    if not llamadas:
        partes = r.candidates[0].content.parts if r.candidates and r.candidates[0].content else []
        return ToolResponse(None, " ".join(p.text or "" for p in partes)[:200])
    # Gemini ya entrega los argumentos como dict (OpenAI los entrega como string JSON)
    return ToolResponse(dict(llamadas[0].args), str(llamadas[0].args))


# ---------- Paso 3.5: reintentos que le dicen al modelo QUÉ falló ----------
def clasificar_validado(consulta: dict, max_intentos: int = 3) -> TriageContrato:
    texto = consulta.get("texto", "")
    if not texto.strip():  # se valida ANTES de gastar una sola llamada
        raise ConsultaInvalidaError("La consulta no puede estar vacía.")

    system = cargar_prompt("v5")
    error_previo = None
    for intento in range(1, max_intentos + 1):
        if error_previo:  # la corrección va al system prompt: es una instrucción, no un dato del pasajero
            system += f"\n\n(Tu respuesta anterior fue inválida: {error_previo}. Corrígela.)"

        if consulta.get("simular_error") and intento == 1:  # para la demo: un primer intento roto
            r = ToolResponse({"respuesta": "ok", "confianza": 1.4, "categoria": "factura", "acciones": []}, "simulado")
        else:
            r = ask_tool(texto, system)

        if r.args is None:
            error_previo = f"no llamaste a la función {TOOL_NAME}; respondiste: {r.raw[:80]}"
        else:
            try:
                return TriageContrato.model_validate(r.args)
            except ValidationError as e:
                error_previo = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        print(f"   intento {intento} inválido → {error_previo}")

    raise ContratoInvalidoError(f"Se agotaron los {max_intentos} intentos: {error_previo}")
