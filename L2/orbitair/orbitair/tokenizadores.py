# tokenizadores.py
# Cómo contar tokens ANTES de llamar, según el proveedor:
#   OpenAI    → tiktoken (local, oficial)
#   Gemini    → LocalTokenizer del SDK google-genai (local, experimental) o models.count_tokens (API)
#   Anthropic → solo vía API: client.messages.count_tokens
import warnings
from functools import lru_cache

import tiktoken

O200K = tiktoken.get_encoding("o200k_base")


@lru_cache
def tokenizador_gemini(modelo: str):
    """
    Tokenizador LOCAL de Gemini (no gasta API ni necesita key). La primera vez descarga
    el vocabulario. Solo texto, y solo los modelos que el SDK conoce: si no está, lanza ValueError.
    """
    warnings.filterwarnings("ignore", message=".*local tokenizer.*")  # avisa que es experimental
    from google.genai.local_tokenizer import LocalTokenizer

    return LocalTokenizer(model_name=modelo)


def contar_gemini(modelo: str, texto: str) -> int:
    return tokenizador_gemini(modelo).count_tokens(texto).total_tokens
