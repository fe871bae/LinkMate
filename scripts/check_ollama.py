"""Check that Ollama is running and both models are installed."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from linkmate.config import load_config
from linkmate.infra.ollama_client import OllamaClient


def main() -> int:
    config = load_config()
    status = OllamaClient(config.ollama.host, config.llm.model, config.embedding.model).status()
    if not status.running:
        print(f"Ollama is not reachable at {config.ollama.host}. Start it with: ollama serve")
        return 1
    print(f"Ollama is running at {config.ollama.host}.")
    ok = True
    for model, installed in ((status.chat_model, status.chat_model_ok), (status.embed_model, status.embed_model_ok)):
        print(f"  {model}: {'installed' if installed else f'missing, run: ollama pull {model}'}")
        ok = ok and installed
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
