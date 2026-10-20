"""
PASO 2 — Tokenización: idiomas, emojis y presupuesto de contexto (parte B de la consigna).

La tokenización con tiktoken es REAL también en modo mock.
Ejecutar:
    uv run python -m pasos.paso2_tokens
"""
import tiktoken

from orbitair import config
from orbitair.costos import calcular_costo
from orbitair.datos import SYSTEM_PROMPT, cargar_consultas, consulta
from orbitair.tokenizadores import contar_gemini, tokenizador_gemini

O200K = tiktoken.get_encoding("o200k_base")  # gpt-4o / gpt-4o-mini / gpt-4.1
CL100K = tiktoken.get_encoding("cl100k_base")  # gpt-4 / gpt-3.5 (tokenizador anterior)
GEMINI = config.MODELOS["gemini"]


def gemini_local_disponible() -> bool:
    try:
        tokenizador_gemini(GEMINI)
        return True
    except Exception as e:
        print(f"  (tokenizador local de Gemini no disponible para {GEMINI}: {e})")
        return False


def piezas_bytes(lista_bytes: list[bytes]) -> str:
    """Mismo formato que piezas(), para tokens que vienen como bytes (Gemini)."""
    salida = []
    for b in lista_bytes:
        try:
            salida.append(f"[{b.decode('utf-8')}]")
        except UnicodeDecodeError:
            salida.append("<" + " ".join(f"{x:02X}" for x in b) + ">")
    return "".join(salida)


def piezas(texto: str, enc=O200K) -> str:
    """Muestra cómo se parte un texto: [El][ pago][ fall]... Los bytes sueltos se ven como <F0 9F>."""
    salida = []
    for t in enc.encode(texto):
        b = enc.decode_single_token_bytes(t)
        try:
            salida.append(f"[{b.decode('utf-8')}]")
        except UnicodeDecodeError:  # un trozo de emoji: no es un carácter válido por sí solo
            salida.append("<" + " ".join(f"{x:02X}" for x in b) + ">")
    return "".join(salida)


def main() -> None:
    # 2.1 — Tabla de las 10 consultas
    print("=" * 78)
    print("2.1 Las 10 consultas con o200k_base (tokenizador de gpt-4.1-mini)")
    print("=" * 78)
    con_gemini = gemini_local_disponible()
    print(f"{'id':<8}{'chars':>6}{'palabras':>9}{'tokens':>8}{'chars/tok':>10}{'cl100k':>8}{'gemini':>8}")
    for c in cargar_consultas():
        t = c["texto"]
        n = len(O200K.encode(t))
        g = contar_gemini(GEMINI, t) if con_gemini else "-"
        print(f"{c['id']:<8}{len(t):>6}{len(t.split()):>9}{n:>8}{len(t) / n:>10.2f}{len(CL100K.encode(t)):>8}{g:>8}")
    print("\n  → Mayor chars/token = el tokenizador 'conoce' mejor ese texto = más barato por carácter.")
    print(f"  → Columna gemini: tokenizador LOCAL de {GEMINI} (real, también en modo mock).")

    # 2.2 — Desarmar las consultas clave
    print("\n" + "=" * 78)
    print("2.2 ¿Cómo se parte cada consulta?")
    print("=" * 78)
    for id_ in ("OA-001", "OA-003", "OA-004"):
        t = consulta(id_)["texto"]
        print(f"\n{id_} ({len(O200K.encode(t))} tokens): {t}")
        print(f"  {piezas(t)}")

    # 2.3 — Mismo significado, distinto idioma
    print("\n" + "=" * 78)
    print("2.3 Mismo significado, distinto idioma")
    print("=" * 78)
    pares = [
        ("The payment failed at checkout.", "El pago falló en el checkout."),
        (consulta("OA-003")["texto"],
         "Hola, me cobraron dos veces la mejora de asiento en el vuelo OA455. "
         "¿Cómo puedo obtener el reembolso del cargo duplicado?"),
    ]
    for en, es in pares:
        n_en, n_es = len(O200K.encode(en)), len(O200K.encode(es))
        print(f"  EN {n_en:>3} tokens | {en}")
        print(f"  ES {n_es:>3} tokens | {es}")
        print(f"  → el español usa {n_es / n_en:.2f}x los tokens del inglés\n")

    # 2.4 — Emojis: cada uno cuesta varios tokens
    print("=" * 78)
    print("2.4 Emojis de OA-004, uno por uno")
    print("=" * 78)
    for emoji in ["😡", "🧳", "❌", "✈️", "🙏", "a", "ñ"]:
        print(f"  {emoji!s:<4} bytes UTF-8={len(emoji.encode('utf-8')):>2}  tokens={len(O200K.encode(emoji)):>2}  {piezas(emoji)}")
    sin_emojis = "Perdieron mi maleta llevo 3 días esperando!!! vuelo OA778 necesito mi ropa YA"
    print(f"\n  OA-004 con emojis: {len(O200K.encode(consulta('OA-004')['texto']))} tokens · "
          f"sin emojis: {len(O200K.encode(sin_emojis))} tokens")

    # 2.5 — Estimar ANTES de llamar (solo válido para OpenAI) y presupuesto de contexto
    print("\n" + "=" * 78)
    print("2.5 Estimación previa con tiktoken (solo OpenAI) y presupuesto de contexto")
    print("=" * 78)
    modelo = config.MODELOS["openai"]
    ventana = 128_000  # ventana de referencia de la lección (GPT-4o); revisar la del modelo que uses
    for id_ in ("OA-001", "OA-007"):
        t = consulta(id_)["texto"]
        entrada = len(O200K.encode(SYSTEM_PROMPT)) + len(O200K.encode(t))
        peor_caso = entrada + config.MAX_TOKENS
        print(f"  {id_}: system+consulta ≈ {entrada} tokens + max_tokens {config.MAX_TOKENS} = {peor_caso} "
              f"({peor_caso / ventana:.3%} de una ventana de {ventana:,})")
        print(f"         costo máximo estimado en {modelo}: USD {calcular_costo(modelo, entrada, config.MAX_TOKENS):.7f}")
    print("\n  → Es una COTA, no el costo. El costo real sale del usage (Paso 4): ahí vas a ver que")
    print("    el input real es algo mayor por los tokens de formato de los mensajes (roles, separadores).")

    # 2.6 — Gemini: dos formas de contar ANTES de llamar
    print("\n" + "=" * 78)
    print(f"2.6 Gemini ({GEMINI}): tokenizador local y count_tokens vía API")
    print("=" * 78)
    if con_gemini:
        print("  a) LOCAL (google.genai.local_tokenizer.LocalTokenizer) — sin key, sin costo:")
        for id_ in ("OA-001", "OA-004"):
            t = consulta(id_)["texto"]
            info = tokenizador_gemini(GEMINI).compute_tokens(t).tokens_info[0]
            print(f"\n  {id_} · Gemini {len(info.tokens)} tokens vs o200k {len(O200K.encode(t))}")
            print(f"    gemini: {piezas_bytes(info.tokens)}")
            print(f"    o200k : {piezas(t)}")
        sistema = contar_gemini(GEMINI, SYSTEM_PROMPT)
        print(f"\n  System prompt: Gemini {sistema} tokens vs o200k {len(O200K.encode(SYSTEM_PROMPT))}")
    if not config.MOCK and "gemini" in config.proveedores_disponibles():
        from google import genai

        cliente = genai.Client(api_key=config.GEMINI_API_KEY)
        print("\n  b) API (client.models.count_tokens) — exacto, gratis, pero es una llamada de red:")
        for id_ in ("OA-001", "OA-003", "OA-004"):
            t = consulta(id_)["texto"]
            r = cliente.models.count_tokens(model=GEMINI, contents=t)
            local = contar_gemini(GEMINI, t) if con_gemini else "-"
            print(f"  {id_}: API={r.total_tokens:>3} · local={local:>3} · tiktoken o200k={len(O200K.encode(t)):>3}")
    else:
        print("\n  b) count_tokens vía API: se omite (modo mock o sin GEMINI_API_KEY).")

    # 2.7 — Anthropic: no hay tokenizador local; se cuenta vía API
    print("\n" + "=" * 78)
    print("2.7 Anthropic: los tokens se consultan a la API, no se calculan localmente")
    print("=" * 78)
    if config.MOCK or "anthropic" not in config.proveedores_disponibles():
        print("  (modo mock o sin ANTHROPIC_API_KEY: se omite. En el Paso 4 verás el usage simulado de Claude.)")
        return
    import anthropic

    cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    for id_ in ("OA-001", "OA-003", "OA-004"):
        t = consulta(id_)["texto"]
        r = cliente.messages.count_tokens(model=config.MODELOS["anthropic"], messages=[{"role": "user", "content": t}])
        print(f"  {id_}: Claude={r.input_tokens:>3} tokens (incluye formato) · tiktoken o200k={len(O200K.encode(t)):>3}")


if __name__ == "__main__":
    main()
