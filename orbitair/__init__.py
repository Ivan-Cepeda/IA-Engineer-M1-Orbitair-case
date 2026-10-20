"""OrbitAir — cliente multi-proveedor para la primera respuesta del centro de atención (M1/L1)."""
import sys

# La consola de Windows usa cp1252 por defecto y explota con emojis (OA-004).
# Forzamos UTF-8 para que todos los Pasos impriman igual en cualquier sistema.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")
