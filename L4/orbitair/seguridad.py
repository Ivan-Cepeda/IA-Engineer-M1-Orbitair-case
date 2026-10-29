# seguridad.py — CLASE 4: defensas de DISEÑO (antes de que el texto llegue al modelo).
# Detectar frases de control, separar canales y sacar la PII que el modelo no necesita ver.
import os
import re
from hashlib import sha256

# ---------- Paso 4.2: frases de control (inyección directa) ----------
# El usuario intenta que SU texto suene a regla del sistema.
CONTROL = re.compile(
    r"(ignor[aáe]\w* (todas |tus |las )?(\w+ )?instrucciones|olvid[aáe]\w* (tus|las) (reglas|instrucciones|indicaciones)"
    r"|revel[aáe]\w* (el|tu) prompt|a partir de ahora (obedec|solo me)|ignore (all |your |previous )+instructions)",
    re.IGNORECASE,
)

# ---------- Paso 4.3: jailbreaks (persuasión: roleplay, falsa autoridad, "es ficción") ----------
JAILBREAK = re.compile(
    r"(act[uú][aá] como (DAN|.*sin restricciones)|modo (desarrollador|sin filtros?|dios)|sin restricciones"
    r"|soy (el|la) (desarrollador|admin\w*|due[ñn]o)|es solo para (una novela|ficci[oó]n))",
    re.IGNORECASE,
)

# Pedir datos de OTROS clientes no es una consulta de pasajero: es exfiltración.
EXFILTRACION = re.compile(
    r"((todos|lista|listado|base) (de )?(los )?(correos|mails|emails|tel[eé]fonos|datos|pasajeros|clientes))",
    re.IGNORECASE,
)


def neutralizar(texto: str) -> str:
    """Para contenido externo (inyección indirecta): no se bloquea al pasajero, se le saca el 'arma' al texto."""
    return CONTROL.sub("[instrucción-eliminada]", texto)


def detectar(texto: str) -> list[str]:
    """Qué patrones conocidos aparecen. Rápido y gratis… pero solo atrapa lo que ya imaginamos."""
    hallazgos = []
    if CONTROL.search(texto):
        hallazgos.append("inyeccion")
    if JAILBREAK.search(texto):
        hallazgos.append("jailbreak")
    if EXFILTRACION.search(texto):
        hallazgos.append("exfiltracion")
    return hallazgos


# ---------- Paso 4.4: PII — redactar antes de que llegue al modelo (y a los logs) ----------
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
TARJETA = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
TELEFONO = re.compile(r"(?<!\w)\+?\d[\d\s-]{7,}\d\b")
PASAPORTE = re.compile(r"\bpasaporte\s*(n[°ºo.]*\s*)?:?\s*[A-Z0-9]{6,9}\b", re.IGNORECASE)


def luhn_ok(numero: str) -> bool:
    """Las tarjetas reales cumplen el algoritmo de Luhn: así no confundimos un número de vuelo con una tarjeta."""
    digitos = [int(c) for c in re.sub(r"\D", "", numero)][::-1]
    if len(digitos) < 13:
        return False
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2) for i, d in enumerate(digitos))
    return total % 10 == 0


def redactar(texto: str) -> tuple[str, list[str]]:
    """Devuelve el texto sin PII y QUÉ se sacó (para el log: el tipo, nunca el valor)."""
    encontrados = []

    def tarjeta(m):
        if not luhn_ok(m.group()):
            return m.group()  # parece tarjeta pero no lo es: se deja
        encontrados.append("tarjeta")
        return "[tarjeta-•••" + re.sub(r"\D", "", m.group())[-4:] + "]"  # los últimos 4 sirven para atender

    texto = TARJETA.sub(tarjeta, texto)  # primero tarjeta: si no, la regex de teléfono se la come
    for nombre, patron in (("email", EMAIL), ("pasaporte", PASAPORTE), ("telefono", TELEFONO)):
        texto, n = patron.subn(f"[{nombre}-redactado]", texto)
        encontrados += [nombre] * n
    return texto, encontrados


# ---------- Paso 4.6: identificadores anónimos para los logs ----------
def anon(valor: str) -> str:
    """Mismo usuario → mismo hash (se puede correlacionar), pero no se puede volver al valor original."""
    sal = os.getenv("LOG_SALT", "sal-de-desarrollo")
    return sha256((sal + valor).encode("utf-8")).hexdigest()[:16]
