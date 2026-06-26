"""
Client LLM unifié pour le module d'entretien IA.

Bascule automatiquement entre deux fournisseurs, sans changer le code appelant :
  1. Groq (Llama 3.3 70B) — si GROQ_API_KEY est défini (meilleure qualité)
  2. Ollama local (Mistral/Llama) — sinon (zéro cloud, conforme RGPD)

Le client expose la MÊME interface que le SDK Groq/OpenAI :
    client.chat.completions.create(model=..., messages=[...],
        temperature=..., max_tokens=..., response_format={"type": "json_object"})
    -> objet avec .choices[0].message.content (texte JSON)

Ainsi, le moteur d'entretien existant fonctionne avec l'un ou l'autre sans
modification de sa logique.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Optional


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_INTERVIEW_MODEL", os.getenv("OLLAMA_MODEL", "mistral"))
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL      = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


# ─────────────────────────────────────────────────────────────────────────────
# Objets de réponse compatibles SDK (pour que le code appelant ne change pas)
# ─────────────────────────────────────────────────────────────────────────────
class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


# ─────────────────────────────────────────────────────────────────────────────
# Backend Ollama (local)
# ─────────────────────────────────────────────────────────────────────────────
def _ollama_available() -> bool:
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
    # Timeout large : Mistral 7B en local (CPU) peut être lent sur de longues
    # générations JSON. Groq (LPU) répond en quelques secondes.
    _timeout = int(os.getenv("OLLAMA_TIMEOUT", "600"))
    with urllib.request.urlopen(req, timeout=_timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp.get("message", {}).get("content", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Interface compatible : client.chat.completions.create(...)
# ─────────────────────────────────────────────────────────────────────────────
class _Completions:
    def __init__(self, parent: "LLMClient"):
        self._parent = parent

    def create(self, *, model: str = "", messages: list[dict],
               temperature: float = 0.4, max_tokens: int = 2000,
               response_format: Optional[dict] = None, **_ignored) -> _Response:
        force_json = bool(response_format and response_format.get("type") == "json_object")

        # ── Provider Groq ───────────────────────────────────────────────────
        if self._parent.provider == "groq":
            kwargs: dict[str, Any] = {
                "model": model or GROQ_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format
            resp = self._parent._groq.chat.completions.create(**kwargs)
            return _Response(resp.choices[0].message.content)

        # ── Provider Ollama (local) ─────────────────────────────────────────
        content = _ollama_chat(messages, temperature, max_tokens, force_json)
        return _Response(content)


class _Chat:
    def __init__(self, parent: "LLMClient"):
        self.completions = _Completions(parent)


class LLMClient:
    """Client unifié Groq ↔ Ollama, interface compatible SDK OpenAI/Groq."""

    def __init__(self, prefer: Optional[str] = None):
        self._groq = None
        self.provider = self._select_provider(prefer)
        self.chat = _Chat(self)

    def _select_provider(self, prefer: Optional[str]) -> str:
        # Priorité explicite
        if prefer == "ollama":
            return "ollama"
        if prefer == "groq" and GROQ_API_KEY:
            self._init_groq()
            return "groq"

        # Auto : Groq si clé + SDK dispo, sinon Ollama
        if GROQ_API_KEY:
            try:
                self._init_groq()
                return "groq"
            except Exception:
                pass
        return "ollama"

    def _init_groq(self):
        from groq import Groq  # import paresseux : pas requis si on utilise Ollama
        self._groq = Groq(api_key=GROQ_API_KEY)

    @property
    def model_name(self) -> str:
        return GROQ_MODEL if self.provider == "groq" else OLLAMA_MODEL

    def info(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "ollama_available": _ollama_available() if self.provider == "ollama" else None,
        }


# Fabrique pratique
def get_llm_client(prefer: Optional[str] = None) -> LLMClient:
    return LLMClient(prefer=prefer)
