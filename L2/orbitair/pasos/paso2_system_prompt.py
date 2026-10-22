"""
PASO 2 — System prompt con los 4 principios (rol, contexto, tarea, formato) + plantilla y variables.

Compara v1 (una línea) contra v2 (4 principios) en el lote dev.
Ejecutar:
    uv run python -m pasos.paso2_system_prompt
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orbitair.clasificacion import clasificar
from orbitair.datos import cargar_consultas, cargar_etiquetas, consulta
from orbitair.evaluacion import categorias_inventadas, evaluar, resumir
from orbitair.prompts import cargar_plantilla, mensaje_usuario, renderizar_system
from pasos.comun import mostrar_errores, proveedor, tabla_resumen, titulo


def main() -> None:
    p = proveedor()

    titulo("2.1 La plantilla v2 (lo que se versiona) — fijate en {empresa}, {categorias} y las llaves dobles")
    print(cargar_plantilla("v2"))

    titulo("2.2 La misma plantilla renderizada con las variables (lo que recibe el modelo)")
    print("[system]")
    print(renderizar_system("v2"))
    print("[user]")
    print(mensaje_usuario(consulta("OA-006")["texto"]))

    titulo("\n2.3 v1 vs v2 en el lote dev")
    dev, etiquetas = cargar_consultas("dev"), cargar_etiquetas()
    resultados = {v: evaluar(v, p, dev, etiquetas) for v in ("v1", "v2")}
    print(tabla_resumen([resumir(f) for f in resultados.values()]))

    for v, filas in resultados.items():
        print(f"\n  Respuestas crudas de {v} (primeras 4):")
        for f in filas[:4]:
            print(f"    {f['id']}: {f['respuesta']!r:<55} → parseo={f['metodo_parseo']}")
        print(f"  Errores de {v}:")
        mostrar_errores(filas)
        inventadas = categorias_inventadas(filas)
        if inventadas:
            print(f"  Fuera de la lista / sin parsear: {dict(inventadas)}")

    titulo("\n2.4 La prueba del cajón: consultas que no encajan en nada")
    for id_ in ("OA-016", "OA-020"):
        texto = consulta(id_)["texto"]
        for v in ("v1", "v2"):
            r = clasificar(p, v, texto)
            print(f"  {id_} con {v}: {r.respuesta.text!r} → categoria={r.categoria} valida={r.valida}")
    print("\n  → Sin 'otro' en la lista, el modelo INVENTA una categoría para no dejar la pregunta sin respuesta.")


if __name__ == "__main__":
    main()
