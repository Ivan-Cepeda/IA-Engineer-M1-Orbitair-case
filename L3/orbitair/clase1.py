# clase1.py — CLASE 1: cómo funciona un LLM (tokens, sampling, streaming, costo)
# Ejecutar:  python clase1.py
import json
import sys

from llm import MODELO, ask, ask_stream, contar_tokens, with_retry

sys.stdout.reconfigure(encoding="utf-8")  # para que la consola de Windows muestre emojis

SYSTEM = "Eres el asistente de OrbitAir, una aerolínea. Responde en máximo 3 frases, en el idioma del pasajero."
consultas = json.load(open("consultas.json", encoding="utf-8"))

print(f"Modelo: {MODELO}\n")

# 1.3 — Primera llamada
print("=== 1.3 Primera llamada ===")
r = ask("¿Puedo llevar a mi perro en cabina?", SYSTEM)
print(r.text)
print(f"tokens {r.input_tokens} in / {r.output_tokens} out · {r.latency_s:.2f}s · USD {r.cost_usd:.7f}\n")

# 1.4 — Tokens: idioma y emojis
print("=== 1.4 Tokens ===")
for texto in ["The payment failed at checkout.", "El pago falló en el checkout.",
              "Perdieron mi maleta", "Perdieron mi maleta 😡😡🧳❌"]:
    print(f"{contar_tokens(texto):>3} tokens · {texto}")
print()

# 1.5 — Sampling: temperature baja = respuestas consistentes
print("=== 1.5 temperature 0 vs 1 ===")
for temp in (0.0, 1.0):
    for i in range(2):
        print(f"temp={temp} #{i + 1}: {ask('Dame un saludo de bienvenida para un pasajero', SYSTEM, temperature=temp).text[:80]}")
print()

# 1.5 — max_tokens: un techo, no una instrucción de brevedad
print("=== 1.5 max_tokens=20 ===")
r = ask(consultas[6]["texto"], SYSTEM, max_tokens=20)
print(f"finish_reason={r.finish_reason} → {r.text!r}\n")

# 1.6 — Streaming: el TTFT es lo que percibe el pasajero
print("=== 1.6 Streaming ===")
r = ask_stream(consultas[6]["texto"], SYSTEM, on_token=lambda t: print(t, end="", flush=True))
print(f"\nTTFT {r.ttft_s:.2f}s · total {r.latency_s:.2f}s · USD {r.cost_usd:.7f}\n")

# 1.7 — Costo a escala: las 10 consultas, con reintentos
print("=== 1.7 Costo de las 10 consultas ===")
total = 0.0
for c in consultas:
    r = with_retry(lambda: ask(c["texto"], SYSTEM))
    total += r.cost_usd
    print(f"{c['id']}  {r.input_tokens:>4} in / {r.output_tokens:>4} out  {r.latency_s:.2f}s  USD {r.cost_usd:.7f}")
print(f"\nPromedio por consulta: USD {total / len(consultas):.7f}")
print(f"× 10.000 consultas:    USD {total / len(consultas) * 10_000:.2f}")
