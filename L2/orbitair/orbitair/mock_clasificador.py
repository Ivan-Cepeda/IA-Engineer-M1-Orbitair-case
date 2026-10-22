# mock_clasificador.py
# Clasificador SIMULADO para seguir L2 sin API keys. Imita patrones reales de los LLM:
#   - sin formato pedido → texto libre con redacción variable
#   - sin categoría cajón → inventa una categoría nueva
#   - en los casos ambiguos se equivoca hasta que un ejemplo (few-shot) o el razonamiento (CoT)
#     cubre esa ambigüedad; un ejemplo obvio no cambia nada
# Es una simulación con guion: sirve para practicar el flujo. Las conclusiones reales salen con API.
import random
import re

# clave (texto que aparece en la consulta) → (correcta, respuesta "ingenua", regla, tema, pide)
_CASOS = [
    ("perro en cabina", "servicios_especiales", "servicios_especiales", None, "viajar con un perro en cabina", "saber si puede llevar a su mascota"),
    ("fue cancelado", "cambios_cancelaciones", "cambios_cancelaciones", "R2", "vuelo cancelado por la aerolínea", "opciones para reprogramar"),
    ("charged twice", "reembolsos_cobros", "reembolsos_cobros", "R1", "cobro duplicado de un upgrade", "que le devuelvan el cobro extra"),
    ("perdieron mi maleta", "equipaje", "equipaje", None, "maleta perdida", "recuperar su maleta"),
    ("equipaje de mano en la tarifa", "equipaje", "equipaje", None, "equipaje de mano", "medidas y peso permitidos"),
    ("error en mi apellido", "cambios_cancelaciones", "otro", "R2", "error en el apellido del boleto", "corregir un dato de la reserva"),
    ("tengo tres dudas", "cambios_cancelaciones", "servicios_especiales", "R3", "conexión perdida, hotel y silla de ruedas", "primero, que lo reubiquen si pierde la conexión"),
    ("cambiar la fecha", "cambios_cancelaciones", "cambios_cancelaciones", "R2", "cambio de fecha por enfermedad", "cambiar la fecha sin multa"),
    ("millas orbitplus", "millas", "millas", None, "canje de millas", "cuántas millas necesita"),
    ("viaja sola", "servicios_especiales", "servicios_especiales", None, "menor que viaja sola", "documentos y costo del servicio"),
    ("rueda rota", "equipaje", "equipaje", None, "valija dañada", "saber dónde reclamar"),
    ("devuelven el dinero", "reembolsos_cobros", "cambios_cancelaciones", "R1", "cancelación hecha por el pasajero", "que le devuelvan el dinero"),
    ("embarazada", "servicios_especiales", "servicios_especiales", None, "viaje durante el embarazo", "requisitos para viajar"),
    ("pasarle el pasaje", "cambios_cancelaciones", "otro", "R2", "pasaporte vencido", "cambiar el titular de la reserva"),
    ("puntos orbitplus", "millas", "millas", None, "acumulación de puntos", "cuántos puntos suma"),
    ("wifi a bordo", "otro", "otro", None, "servicio de wifi", "información sobre el servicio a bordo"),
    ("cobraron dos veces el equipaje", "reembolsos_cobros", "equipaje", "R1", "equipaje cobrado dos veces", "que le devuelvan un cobro"),
    ("perdí la conexión a roma", "cambios_cancelaciones", "otro", "R3", "atraso y conexión perdida", "que lo reubiquen"),
    ("la guitarra", "equipaje", "servicios_especiales", "R4", "gato en cabina y guitarra", "saber si la guitarra cuenta como equipaje de mano"),
    ("horario de atención", "otro", "otro", None, "horario del call center", "información general"),
]

_INVENTADAS = {"otro": ["informacion_general", "consultas_generales"]}
_FRASES_LIBRES = ["Categoría: {c}", "Esta consulta corresponde a {t}.", "{T}", "La categoría es {t}."]


def _buscar(texto: str):
    t = texto.lower()
    for clave, *datos in _CASOS:
        if clave in t:
            return datos
    return None


def _cubre(system: str, regla: str | None) -> bool:
    """¿El prompt trae un ejemplo o un razonamiento que resuelva esta ambigüedad?"""
    s = system.lower()
    ejemplos = s.split("ejemplos", 1)[1] if "ejemplos" in s else ""
    return {
        "R1": "cobraron dos veces" in ejemplos,
        "R2": "nombre" in ejemplos and "cambios_cancelaciones" in ejemplos,
        "R3": "perdí la conexión" in ejemplos,
        "R4": "pide:" in s and "no lo que menciona" in s,  # solo con chain-of-thought
    }.get(regla, True)


def responder(system: str, prompt: str, temperature: float) -> str:
    texto = re.sub(r"</?consulta>", "", prompt)
    caso = _buscar(texto)
    if caso is None:  # consulta nueva que no está en el dataset: respuesta genérica
        caso = ("otro", "otro", None, "una consulta general", "información")
    correcta, ingenua, regla, tema, pide = caso

    acierta = _cubre(system, regla)
    if temperature >= 0.7 and regla:  # con temperature alta, los casos ambiguos "bailan"
        acierta = random.random() < (0.85 if acierta else 0.4)
    categoria = correcta if acierta else ingenua

    tiene_lista = "servicios_especiales" in system
    if not tiene_lista or (categoria == "otro" and "otro" not in system):
        # Sin la opción cajón, el modelo inventa un nombre para no dejar la pregunta sin respuesta
        categoria = random.Random(texto).choice(_INVENTADAS.get(categoria, [categoria]))

    if "CATEGORIA:" in system:  # chain-of-thought con última línea parseable
        decision = f"gana {categoria}" + (" porque se clasifica lo que pide" if regla else "")
        return f"Tema: {tema}.\nPide: {pide}.\nDecisión: {decision}.\nCATEGORIA: {categoria}"
    if '"categoria"' in system:  # JSON pedido
        return f'{{"categoria": "{categoria}"}}'
    # Sin formato definido: redacción libre (y distinta según la consulta)
    frase = random.Random(texto).choice(_FRASES_LIBRES)
    return frase.format(c=categoria, t=categoria.replace("_", " "), T=categoria.replace("_", " ").capitalize())
