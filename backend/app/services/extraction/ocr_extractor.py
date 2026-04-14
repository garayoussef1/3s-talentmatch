"""
Module d'extraction OCR pour PDFs scannés et images.

Stratégie moteur OCR (système hybride) :
1) Tesseract  — rapide (2-4 sec/page), moteur principal
2) EasyOCR    — fallback si qualité Tesseract < seuil
3) Cache SHA256 — résultat instantané si fichier déjà traité

Auteur  : Youssef Gara
Projet  : 3S TalentMatch — PFE ESPRIT 2025-2026
"""

from pathlib import Path
from typing import Dict, List, Optional
import hashlib
import importlib.util
import json
import logging
import re
import time

logger = logging.getLogger(__name__)

# ── Chemin Tesseract (Windows) ───────────────────────────────────────────────
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ── Cache global EasyOCR (chargé une seule fois) ─────────────────────────────
_EASYOCR_READER_CACHE: Dict = {}


def _get_easyocr_reader_cached(languages: tuple):
    if languages not in _EASYOCR_READER_CACHE:
        import easyocr
        logger.info("Chargement EasyOCR (une seule fois) — langues=%s", list(languages))
        _EASYOCR_READER_CACHE[languages] = easyocr.Reader(list(languages), gpu=False)
        logger.info("EasyOCR chargé et mis en cache")
    return _EASYOCR_READER_CACHE[languages]


# ── Répertoire de cache OCR ───────────────────────────────────────────────────
def _cache_dir() -> Path:
    base = Path(__file__).resolve().parents[4] / "data" / "ocr_cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cache_load(sha: str) -> Optional[str]:
    p = _cache_dir() / f"{sha}.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data.get("text", "")
        except Exception:
            return None
    return None


def _cache_save(sha: str, text: str) -> None:
    p = _cache_dir() / f"{sha}.json"
    try:
        p.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ── Évaluation qualité OCR ────────────────────────────────────────────────────
_COMMON_WORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "à",
    "the", "and", "of", "in", "for", "with", "at", "by",
    "je", "mon", "ma", "mes", "par", "sur", "est", "pas",
}


def _quality_score(text: str) -> float:
    """Retourne un score 0-100 estimant la qualité OCR.

    Critères :
    - Ratio de caractères alphabétiques
    - Présence de mots communs FR/EN
    - Longueur du texte
    """
    if not text or not text.strip():
        return 0.0

    clean = text.strip()
    total = len(clean)
    if total == 0:
        return 0.0

    # Ratio alphanumérique
    alpha = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", clean))
    alpha_ratio = alpha / total

    # Présence de mots courants
    words = re.findall(r"\b[a-zA-Zà-ÿ]{2,}\b", clean.lower())
    common_count = sum(1 for w in words if w in _COMMON_WORDS)
    word_score = min(common_count / max(len(words), 1) * 2, 1.0)

    # Score longueur (plafonné à 500 chars)
    length_score = min(total / 500, 1.0)

    score = (alpha_ratio * 50) + (word_score * 30) + (length_score * 20)
    return round(score, 1)


def _is_good_enough(text: str, threshold: float = 55.0) -> bool:
    return _quality_score(text) >= threshold


class OCRExtractor:
    """
    Extracteur OCR hybride : Tesseract (rapide) + EasyOCR (fallback).

    Pipeline pour chaque image :
    1. Vérifier le cache SHA256 → résultat instantané si déjà traité
    2. Prétraitement image (niveaux de gris, débruitage, contraste)
    3. Tesseract FR+EN → évaluation qualité
    4. Si qualité >= 55 → retourner résultat Tesseract
    5. Sinon → EasyOCR multi-passes → retourner meilleur résultat
    6. Sauvegarder dans le cache
    """

    QUALITY_THRESHOLD = 55.0  # Score minimum pour accepter Tesseract sans fallback

    def __init__(
        self,
        languages: List[str] = None,
        preferred_engine: str = "tesseract",
        enable_preprocessing: bool = True,
        enable_cache: bool = True,
    ):
        self.languages = languages or ["fr", "en"]
        self.preferred_engine = preferred_engine
        self.enable_preprocessing = enable_preprocessing
        self.enable_cache = enable_cache
        self._easyocr_reader = None
        logger.info(
            "OCRExtractor initialisé — moteur=%s, langues=%s, cache=%s",
            preferred_engine, self.languages, enable_cache,
        )

    # ── Tesseract ─────────────────────────────────────────────────────────────

    def _is_tesseract_available(self) -> bool:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def _is_easyocr_available(self) -> bool:
        return importlib.util.find_spec("easyocr") is not None

    def _extract_tesseract(self, img) -> str:
        """Extraction Tesseract sur une image OpenCV (BGR ou gris)."""
        import pytesseract
        from PIL import Image
        import numpy as np
        import cv2

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

        # Convertir BGR → RGB pour Pillow
        if len(img.shape) == 3:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img

        pil_img = Image.fromarray(img_rgb)

        # Config Tesseract : mode page = 6 (bloc de texte uniforme)
        # Langues disponibles : fra+eng
        langs = "+".join(
            {"fr": "fra", "en": "eng"}.get(l, l) for l in self.languages
        )
        config = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(pil_img, lang=langs, config=config)
        return text.strip()

    # ── EasyOCR ───────────────────────────────────────────────────────────────

    def _get_easyocr_reader(self):
        return _get_easyocr_reader_cached(tuple(self.languages))

    def _extract_easyocr(self, img) -> str:
        """Extraction EasyOCR sur une image OpenCV."""
        reader = self._get_easyocr_reader()
        results = reader.readtext(img)
        lines = [text for (_, text, conf) in results if conf > 0.3]
        return "\n".join(lines)

    # ── Prétraitement image ───────────────────────────────────────────────────

    def _load_image(self, image_path: str):
        """Charge une image (gère les chemins Unicode Windows)."""
        import numpy as np
        import cv2

        data = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Impossible de décoder l'image : {image_path}")
        return img

    def _preprocess(self, img, mode: str = "enhanced"):
        """Prétraitement pour améliorer la qualité OCR.

        Modes :
          basic    : niveaux de gris uniquement
          enhanced : gris + upscale + contraste CLAHE + débruitage
          binary   : enhanced + binarisation adaptative
        """
        import cv2
        import numpy as np

        if img is None:
            return img
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)

        # Niveaux de gris
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        if mode == "basic":
            return gray

        # Upscale agressif : viser 2500px de large minimum (≈300 DPI sur A4)
        # Les images de CV sont souvent 800-1200px → trop petit pour OCR précis
        h, w = gray.shape[:2]
        target_w = 2500
        if w < target_w:
            scale = target_w / w
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # Amélioration contraste (CLAHE) — clipLimit plus élevé pour CVs à faible contraste
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Sharpening (unsharp mask) — rend les contours de lettres plus nets
        blur = cv2.GaussianBlur(gray, (0, 0), 3)
        gray = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)

        # Débruitage léger (après sharpening)
        gray = cv2.fastNlMeansDenoising(gray, h=8)

        if mode == "binary":
            # Binarisation adaptative (meilleure pour scans)
            gray = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 31, 10,
            )

        return gray

    # ── Pipeline principal ────────────────────────────────────────────────────

    def _run_pipeline(self, image_path: str) -> str:
        """Pipeline complet : Tesseract → évaluation → fallback EasyOCR."""
        t0 = time.time()

        img = self._load_image(image_path)

        # ── Étape 1 : Tesseract (rapide) ──────────────────────────────────
        tess_text = ""
        tess_score = 0.0
        use_tesseract = self.preferred_engine in ("tesseract", "auto") and self._is_tesseract_available()

        if use_tesseract:
            try:
                if self.enable_preprocessing:
                    proc = self._preprocess(img, mode="enhanced")
                else:
                    proc = img
                tess_text = self._extract_tesseract(proc)
                tess_score = _quality_score(tess_text)
                logger.info(
                    "Tesseract terminé en %.1fs — score=%.1f — %d chars",
                    time.time() - t0, tess_score, len(tess_text),
                )
            except Exception as e:
                logger.warning("Tesseract échoué : %s", e)

            # Résultat Tesseract suffisant → retourner immédiatement
            if tess_score >= self.QUALITY_THRESHOLD:
                logger.info("Tesseract OK (score=%.1f) — pas de fallback EasyOCR", tess_score)
                return tess_text

            # Essai avec binarisation si score faible
            if self.enable_preprocessing and tess_score < self.QUALITY_THRESHOLD:
                try:
                    proc_bin = self._preprocess(img, mode="binary")
                    tess_bin = self._extract_tesseract(proc_bin)
                    bin_score = _quality_score(tess_bin)
                    if bin_score > tess_score:
                        tess_text = tess_bin
                        tess_score = bin_score
                    logger.info("Tesseract binary — score=%.1f", tess_score)
                except Exception:
                    pass

            if tess_score >= self.QUALITY_THRESHOLD:
                return tess_text

        # ── Étape 2 : Fallback EasyOCR ────────────────────────────────────
        if not self._is_easyocr_available():
            logger.warning("EasyOCR indisponible — retour texte Tesseract (score=%.1f)", tess_score)
            return tess_text

        logger.info("Tesseract score=%.1f < %.1f — fallback EasyOCR", tess_score, self.QUALITY_THRESHOLD)

        candidates = []

        # Pass EasyOCR brut
        try:
            easy_raw = self._extract_easyocr(img)
            candidates.append((easy_raw, _quality_score(easy_raw)))
        except Exception as e:
            logger.warning("EasyOCR brut échoué : %s", e)

        # Pass EasyOCR enhanced (si preprocessing activé)
        if self.enable_preprocessing:
            try:
                proc = self._preprocess(img, mode="enhanced")
                easy_enh = self._extract_easyocr(proc)
                candidates.append((easy_enh, _quality_score(easy_enh)))
            except Exception:
                pass

        # Ajouter le résultat Tesseract comme candidat aussi
        if tess_text:
            candidates.append((tess_text, tess_score))

        if not candidates:
            return ""

        # Retourner le meilleur candidat
        best_text, best_score = max(candidates, key=lambda x: x[1])
        logger.info(
            "Meilleur résultat OCR — score=%.1f — %d chars — %.1fs total",
            best_score, len(best_text), time.time() - t0,
        )
        return best_text

    # ── Point d'entrée public ─────────────────────────────────────────────────

    def extract_from_image(self, image_path: str) -> Dict:
        """Extrait le texte d'une image avec cache + pipeline hybride.

        Returns:
            {
                "success": bool,
                "text": str,
                "method": str,  # "tesseract" | "easyocr" | "cache"
                "quality_score": float,
                "cached": bool,
            }
        """
        # ── Cache ──────────────────────────────────────────────────────────
        sha = None
        if self.enable_cache:
            try:
                sha = _file_sha256(image_path)
                cached = _cache_load(sha)
                if cached is not None:
                    logger.info("Cache hit pour %s", Path(image_path).name)
                    return {
                        "success": True,
                        "text": cached,
                        "method": "cache",
                        "quality_score": _quality_score(cached),
                        "cached": True,
                    }
            except Exception:
                pass

        # ── Pipeline OCR ───────────────────────────────────────────────────
        try:
            text = self._run_pipeline(image_path)
            score = _quality_score(text)

            # Sauvegarder dans le cache
            if self.enable_cache and sha:
                _cache_save(sha, text)

            # Détecter le moteur utilisé
            method = "tesseract+easyocr" if score < self.QUALITY_THRESHOLD else "tesseract"
            if not self._is_tesseract_available():
                method = "easyocr"

            return {
                "success": True,
                "text": text,
                "method": method,
                "quality_score": score,
                "cached": False,
            }
        except Exception as e:
            logger.error("Erreur OCR pipeline : %s", e, exc_info=True)
            return {
                "success": False,
                "text": "",
                "method": "error",
                "quality_score": 0.0,
                "cached": False,
            }

    def extract_from_pdf_page(self, page_image) -> str:
        """Extrait le texte d'une page PDF déjà convertie en image numpy."""
        import numpy as np

        if not isinstance(page_image, np.ndarray):
            raise TypeError("page_image doit être un numpy array (OpenCV)")

        use_tesseract = self.preferred_engine in ("tesseract", "auto") and self._is_tesseract_available()

        if use_tesseract:
            try:
                proc = self._preprocess(page_image, mode="enhanced") if self.enable_preprocessing else page_image
                text = self._extract_tesseract(proc)
                score = _quality_score(text)
                if score >= self.QUALITY_THRESHOLD:
                    return text
                # Fallback binary
                proc_bin = self._preprocess(page_image, mode="binary")
                text_bin = self._extract_tesseract(proc_bin)
                if _quality_score(text_bin) > score:
                    text = text_bin
                    score = _quality_score(text_bin)
                if score >= self.QUALITY_THRESHOLD:
                    return text
            except Exception as e:
                logger.warning("Tesseract page échoué : %s", e)

        # Fallback EasyOCR
        try:
            return self._extract_easyocr(page_image)
        except Exception as e:
            logger.error("EasyOCR page échoué : %s", e)
            return ""

    # ── Compatibilité avec l'ancien code (CVExtractor l'appelle) ─────────────

    def extract(self, image_path: str) -> Dict:
        """Alias de extract_from_image pour compatibilité."""
        result = self.extract_from_image(image_path)
        # Format attendu par CVExtractor
        return {
            "success": result["success"],
            "text": result["text"],
            "pages": 1,
            "method": result["method"],
            "format": Path(image_path).suffix.lower(),
            "needs_ocr": True,
            "error": None if result["success"] else "OCR échoué",
        }
