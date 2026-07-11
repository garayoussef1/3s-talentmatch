"""
Client LLM 100% LOCAL (Ollama) pour le module d'évaluation.

Conformité entreprise : AUCUNE API externe — le modèle (Mistral) tourne sur la
machine via Ollama (http://localhost:11434). Aucune donnée ne quitte le poste.

Interface standard (`client.chat.completions.create(...)`) pour que le code
appelant reste simple et testable.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Optional

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral")


# ── Objets réponse (imitent l'interface OpenAI) ──────────────────────────────
class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


# ── Appel Ollama ──────────────────────────────────────────────────────────────
def ollama_available() -> bool:
    """True si le serveur Ollama local répond."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _ollama_chat(messages: list[dict], temperature: float, max_tokens: int,
                 force_json: bool) -> str:
    """Appel Ollama /api/chat. Retourne le contenu texte (JSON si force_json)."""
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if force_json:
        payload["format"] = "json"   # Ollama garantit une sortie JSON valide

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Timeout large : un modèle 7B en local (CPU) peut être lent sur de longues
    # générations JSON.
    _timeout = int(os.getenv("OLLAMA_TIMEOUT", "600"))
    with urllib.request.urlopen(req, timeout=_timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp.get("message", {}).get("content", "").strip()


# ── Interface compatible : client.chat.completions.create(...) ────────────────
class _Completions:
    def create(self, *, model: str = "", messages: list[dict],
               temperature: float = 0.4, max_tokens: int = 2000,
               response_format: Optional[dict] = None, **_ignored) -> _Response:
        force_json = bool(response_format and response_format.get("type") == "json_object")
        return _Response(_ollama_chat(messages, temperature, max_tokens, force_json))


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class LLMClient:
    """Client LLM local (Ollama uniquement)."""

    provider = "ollama"

    def __init__(self):
        self.chat = _Chat()

    @property
    def model_name(self) -> str:
        return OLLAMA_MODEL

    def info(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "ollama_available": ollama_available(),
        }


def get_llm_client(prefer: Optional[str] = None) -> LLMClient:
    """Retourne le client LLM local (le paramètre `prefer` est ignoré :
    seul Ollama est autorisé — conformité entreprise)."""
    return LLMClient()
