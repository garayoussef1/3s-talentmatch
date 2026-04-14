"""Client léger HuggingFace Inference API pour CamemBERT (optionnel).

Objectif: améliorer ponctuellement l'extraction du nom (PERSON) quand les heuristiques
ou spaCy sont insuffisants.

Sécurité / réversibilité:
- Ne bloque jamais le pipeline (fallback silencieux).
- **Désactivé par défaut** : doit être activé explicitement via HF_ENABLE_CAMEMBERT_NAME=1.
- Nécessite HF_TOKEN (sinon ignoré).
- Aucune dépendance lourde (utilise httpx déjà présent).

Vars env:
- HF_ENABLE_CAMEMBERT_NAME=1 pour activer (opt-in)
- HF_ENABLE_CAMEMBERT_NAME=0 pour désactiver (défaut)
- HF_TOKEN=<token HF> (requis si activé)
- HF_CAMEMBERT_NER_MODEL=<repo/model> (optionnel)
- HF_TIMEOUT_SECONDS=5 (optionnel)
"""

from __future__ import annotations

import os
import re
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from huggingface_hub import InferenceClient  # type: ignore

    _HF_HUB_AVAILABLE = True
except Exception:  # pragma: no cover
    InferenceClient = None  # type: ignore
    _HF_HUB_AVAILABLE = False

try:
    # Optionnel: permet d'extraire status_code sans casser si l'API interne change.
    from huggingface_hub.utils import HfHubHTTPError  # type: ignore

    _HF_HUB_HTTP_ERROR_AVAILABLE = True
except Exception:  # pragma: no cover
    HfHubHTTPError = Exception  # type: ignore
    _HF_HUB_HTTP_ERROR_AVAILABLE = False

logger = logging.getLogger(__name__)


_DEFAULT_MODEL = os.getenv("HF_CAMEMBERT_NER_MODEL", "Jean-Baptiste/camembert-ner")
_DEFAULT_TIMEOUT = float(os.getenv("HF_TIMEOUT_SECONDS", "5"))


def camembert_runtime_config() -> Dict[str, Any]:
    """Expose la config runtime CamemBERT (sans révéler le token).

    Retourne un dict stable pour le traçage (metadata/debug).
    """
    return {
        "enabled": _enabled(),
        "model": _model(),
        "timeout_seconds": _timeout(),
        "token_present": bool(_token()),
    }


def _enabled() -> bool:
    """Retourne True si l'extraction CamemBERT doit être tentée.

    Politique:
    - **Opt-in strict** : enabled si et seulement si HF_ENABLE_CAMEMBERT_NAME est défini
      avec une valeur truthy ET que HF_TOKEN est présent.
    - Sinon: disabled.
    """
    raw = os.getenv("HF_ENABLE_CAMEMBERT_NAME")
    if raw is None:
        return False

    v = raw.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return bool(_token())
    return False


def _token() -> Optional[str]:
    t = os.getenv("HF_TOKEN")
    if not t:
        return None
    return t.strip()


def _model() -> str:
    return (os.getenv("HF_CAMEMBERT_NER_MODEL") or _DEFAULT_MODEL).strip()


def _timeout() -> float:
    try:
        return float(os.getenv("HF_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT)))
    except Exception:
        return _DEFAULT_TIMEOUT


def _clip_text(text: str, max_chars: int = 2000) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars]


_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ'\-]{2,}")


def _normalize_spaces(s: str) -> str:
    return " ".join((s or "").split()).strip()


@dataclass
class PersonCandidate:
    text: str
    score: float
    start: int


class HFCamembertNameExtractor:
    """Extraction PERSON via un modèle NER hébergé sur HuggingFace."""

    @staticmethod
    def _parse_token_classification_response(payload: Any) -> List[PersonCandidate]:
        """Parse les sorties HF Inference API (token classification).

        On supporte:
        - Liste de dicts: [{"entity_group":"PER", "word":"Jean", "score":...}, ...]
        - Ou "entity" au lieu de entity_group selon modèles.

        Retourne une liste de candidats PERSON avec texte agrégé.
        """
        if not isinstance(payload, list):
            return []

        # Normaliser les champs
        def to_dict(x: Any) -> Optional[Dict[str, Any]]:
            if isinstance(x, dict):
                return x
            # Supporte les sorties huggingface_hub (TokenClassificationOutputElement)
            d: Dict[str, Any] = {}
            for k in ("entity_group", "entity", "score", "word", "start", "end", "text"):
                if hasattr(x, k):
                    d[k] = getattr(x, k)
            return d or None

        items: List[Dict[str, Any]] = []
        for x in payload:
            d = to_dict(x)
            if d is not None:
                items.append(d)
        if not items:
            return []

        def is_person(it: Dict[str, Any]) -> bool:
            label = (it.get("entity_group") or it.get("entity") or "").upper()
            # Selon modèles/tokenizers: PER, PERSON, B-PER, I-PER, B-PERSON, I-PERSON
            if label in {"PER", "PERSON", "I-PER", "B-PER", "I-PERSON", "B-PERSON"}:
                return True
            # Heuristique permissive: accepter les tags BIO autour de PER/PERSON
            return label.endswith("-PER") or label.endswith("-PERSON")

        persons = [it for it in items if is_person(it)]
        if not persons:
            return []

        # Agréger les tokens consécutifs en spans
        candidates: List[PersonCandidate] = []
        current_words: List[str] = []
        current_scores: List[float] = []
        current_start: Optional[int] = None
        last_end: Optional[int] = None

        for it in persons:
            word = str(it.get("word") or it.get("text") or "").strip()
            if not word:
                continue
            # HF renvoie parfois "▁Jean" ou "##dupont" selon tokenizer
            word = word.replace("▁", " ")
            word = word.replace("##", "")
            word = _normalize_spaces(word)
            score = float(it.get("score") or 0.0)
            start = int(it.get("start") or 0)
            end = int(it.get("end") or (start + len(word)))

            if current_start is None:
                current_start = start
                last_end = end
                current_words = [word]
                current_scores = [score]
                continue

            # Heuristique de continuité: tokens proches
            gap = start - (last_end or start)
            if gap <= 2:
                current_words.append(word)
                current_scores.append(score)
                last_end = end
            else:
                text_span = _normalize_spaces(" ".join(current_words))
                if len(_WORD.findall(text_span)) >= 2:
                    candidates.append(PersonCandidate(text=text_span, score=sum(current_scores) / max(len(current_scores), 1), start=current_start))
                current_start = start
                last_end = end
                current_words = [word]
                current_scores = [score]

        # flush
        if current_words and current_start is not None:
            text_span = _normalize_spaces(" ".join(current_words))
            if len(_WORD.findall(text_span)) >= 2:
                candidates.append(PersonCandidate(text=text_span, score=sum(current_scores) / max(len(current_scores), 1), start=current_start))

        # Trier: priorité au début du texte, puis score, puis longueur
        candidates.sort(key=lambda c: (c.start, -c.score, -len(c.text)))
        return candidates

    def extract_person_name(self, text: str) -> Optional[str]:
        if not _enabled():
            logger.debug(
                "CamemBERT désactivé (HF_ENABLE_CAMEMBERT_NAME=0). "
                "Extraction nom assurée par spaCy seul."
            )
            return None
        token = _token()
        if not token:
            logger.debug("CamemBERT ignoré : HF_TOKEN absent. spaCy utilisé.")
            return None
        logger.info("CamemBERT activé — appel API HuggingFace (%s)", _model())

        clipped = _clip_text(text, max_chars=2000)
        if len(clipped) < 50:
            return None

        # Nouvelle API HF (2024+): utiliser le router via Inference Providers.
        # On passe par huggingface_hub.InferenceClient, qui gère le routage vers
        # https://router.huggingface.co et les formats de requêtes/réponses.
        if _HF_HUB_AVAILABLE and InferenceClient is not None:
            try:
                client = InferenceClient(provider="hf-inference", token=token, timeout=_timeout())
                result = client.token_classification(
                    clipped,
                    model=_model(),
                    aggregation_strategy="simple",
                )
                candidates = self._parse_token_classification_response(list(result) if result is not None else [])
                if not candidates:
                    return None
                best = _normalize_spaces(candidates[0].text)
                if len(best) < 3:
                    return None
                if best.isupper():
                    best = best.title()
                return best
            except Exception as e:
                # Ne jamais bloquer le pipeline.
                # Si possible, logguer le status HTTP (utile pour 401/403/429).
                if _HF_HUB_HTTP_ERROR_AVAILABLE and isinstance(e, HfHubHTTPError):
                    try:
                        status = getattr(getattr(e, "response", None), "status_code", None)
                        msg = getattr(getattr(e, "response", None), "text", None) or str(e)
                        logger.info("HF hub inference failed (status=%s): %s", status, msg)
                    except Exception:
                        logger.info("HF hub inference failed: %s", str(e))
                else:
                    logger.info("HF hub inference failed: %s", str(e))
                return None

        # Fallback: ancien mode httpx direct (peut être obsolète côté HF).
        url = f"https://api-inference.huggingface.co/models/{_model()}"
        headers = {"Authorization": f"Bearer {token}"}

        # Certains appels Inference API répondent d'abord "model is loading" (503)
        # avec un champ estimated_time. On tente un retry léger.
        payload: Any = None
        attempts = 2
        for attempt in range(attempts):
            t0 = time.time()
            try:
                with httpx.Client(timeout=_timeout()) as client:
                    resp = client.post(
                        url,
                        headers=headers,
                        json={
                            "inputs": clipped,
                            "parameters": {"aggregation_strategy": "simple"},
                            "options": {"wait_for_model": True},
                        },
                    )

                # Erreurs HTTP
                if resp.status_code >= 400:
                    # Cas courant: token invalide / absent de droits
                    if resp.status_code in (401, 403):
                        logger.info("HF NER unauthorized (status=%s). Check HF_TOKEN permissions.", resp.status_code)
                        return None

                    # 503: modèle en cours de chargement
                    try:
                        maybe = resp.json()
                    except Exception:
                        maybe = None

                    est = None
                    if isinstance(maybe, dict):
                        est = maybe.get("estimated_time")
                        err = str(maybe.get("error") or "")
                        if est or ("loading" in err.lower()):
                            payload = maybe
                    if resp.status_code == 503 and attempt < (attempts - 1) and payload:
                        wait_s = float(est) if isinstance(est, (int, float)) else 2.0
                        wait_s = max(0.5, min(wait_s, 8.0))
                        logger.info("HF NER model loading (503). Retrying in %.1fs", wait_s)
                        time.sleep(wait_s)
                        continue

                    logger.info("HF NER error status=%s", resp.status_code)
                    return None

                payload = resp.json()

                # Payload de type {"error": "...loading...", "estimated_time": ...}
                if isinstance(payload, dict):
                    err = str(payload.get("error") or "")
                    est = payload.get("estimated_time")
                    if attempt < (attempts - 1) and (est or ("loading" in err.lower())):
                        wait_s = float(est) if isinstance(est, (int, float)) else 2.0
                        wait_s = max(0.5, min(wait_s, 8.0))
                        logger.info("HF NER returned loading payload. Retrying in %.1fs", wait_s)
                        time.sleep(wait_s)
                        continue

                break
            except Exception as e:
                logger.info("HF NER call failed: %s", str(e))
                return None
            finally:
                dt = round((time.time() - t0) * 1000)
                logger.debug("HF NER call duration_ms=%s", dt)

        candidates = self._parse_token_classification_response(payload)
        if not candidates:
            return None

        # Prendre le meilleur candidat (déjà trié)
        best = candidates[0].text
        best = _normalize_spaces(best)
        if len(best) < 3:
            return None
        # Capitaliser de façon simple
        if best.isupper():
            best = best.title()
        return best
