"""Module d'extraction de texte depuis des PDFs.

Stratégie:
- Essayer une extraction "layout-aware" via PyMuPDF (fitz) si disponible
    (meilleure reconstruction des lignes/colonnes sur CVs).
- Fallback sur pypdf pour compatibilité.
"""

from pypdf import PdfReader
from pathlib import Path
from typing import Dict
import logging
import re

try:
        import fitz  # PyMuPDF

        _HAVE_PYMUPDF = True
except Exception:  # pragma: no cover
        fitz = None
        _HAVE_PYMUPDF = False

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extracteur de texte pour PDFs textuels"""
    
    def __init__(self, min_text_length: int = 100):
        self.min_text_length = min_text_length
        logger.info("PDFExtractor initialisé")

    @staticmethod
    def _reconstruct_text_from_pymupdf_page(page_dict: dict, page_width: float) -> str:
        """Reconstruit un texte lisible à partir d'une page PyMuPDF (dict).

        Objectif: préserver l'ordre de lecture (colonnes) et les retours à la ligne.
        """
        lines = []
        for block in page_dict.get("blocks", []) or []:
            # 0 = texte (PyMuPDF)
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []) or []:
                spans = line.get("spans", []) or []
                text = "".join((sp.get("text") or "") for sp in spans).strip()
                if not text:
                    continue
                x0, y0, x1, y1 = line.get("bbox", [0, 0, 0, 0])
                lines.append({
                    "x0": float(x0 or 0),
                    "y0": float(y0 or 0),
                    "x1": float(x1 or 0),
                    "y1": float(y1 or 0),
                    "text": text,
                })

        if not lines:
            return ""

        # Détection de colonnes: chercher un "gap" significatif dans les x0.
        # Important: ignorer les lignes "pleine largeur" (titres/phrases centrées)
        # qui peuvent masquer la séparation de colonnes.
        narrow_lines = lines
        if page_width:
            narrow_lines = [
                l for l in lines
                if 0 < (l["x1"] - l["x0"]) < float(page_width) * 0.65
            ] or lines

        xs = sorted(l["x0"] for l in narrow_lines)
        col_split = None
        if len(xs) >= 4 and page_width:
            # Gap significatif ~15% de la largeur page
            min_gap = max(60.0, float(page_width) * 0.15)
            best_gap = 0.0
            best_at = None
            for a, b in zip(xs, xs[1:]):
                gap = b - a
                if gap > best_gap:
                    best_gap = gap
                    best_at = (a + b) / 2
            if best_at is not None and best_gap >= min_gap:
                col_split = best_at

        # ── Détection colonne "dates uniquement" (timeline) ─────────────
        # Certains CVs ont une colonne droite narrow contenant exclusivement
        # des dates (Jul–Sep 2025, 2021–2026). Dans ce cas, traiter toutes
        # les lignes par ordre Y global (interleave) donne un meilleur résultat
        # que colonne-par-colonne (qui met toutes les dates à la fin).
        _date_re = re.compile(
            r'\b(?:19|20)\d{2}\b|'
            r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|'
            r'june?|july?|aug(?:ust)?|sep(?:t)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b|'
            r'\b(?:janv|f[ée]vr|mars|avr|juin|juil|ao[uû]t|sept|nov|d[eé]c)\b',
            re.IGNORECASE,
        )

        def _is_date_timeline_col(col_lines: list) -> bool:
            """Retourne True si la colonne ne contient que des dates/info courtes."""
            if not col_lines:
                return False
            avg_len = sum(len(l["text"]) for l in col_lines) / len(col_lines)
            date_hits = sum(1 for l in col_lines if _date_re.search(l["text"]))
            return avg_len < 30 and date_hits / len(col_lines) >= 0.55

        if col_split is None:
            columns = [lines]
            _interleave = False
        else:
            left = [l for l in lines if l["x0"] < col_split]
            right = [l for l in lines if l["x0"] >= col_split]
            # Si une "colonne" est trop petite, annuler la séparation
            if len(left) < 2 or len(right) < 2:
                columns = [lines]
                _interleave = False
            elif _is_date_timeline_col(right):
                # Colonne droite = uniquement dates → interleave toutes les lignes par Y
                columns = [lines]
                _interleave = True
            else:
                columns = [left, right]
                _interleave = False

        out_lines = []
        for col in columns:
            # Tri principal: haut vers bas, puis gauche vers droite
            col_sorted = sorted(col, key=lambda d: (d["y0"], d["x0"]))
            last_y = None
            for item in col_sorted:
                y = item["y0"]
                t = item["text"]
                if last_y is not None and (y - last_y) > 18:
                    # Marquer un saut de paragraphe si gros gap vertical
                    if out_lines and out_lines[-1] != "":
                        out_lines.append("")
                out_lines.append(t)
                last_y = y
            # Séparer les colonnes par une ligne vide (pas en mode interleave)
            if not _interleave and out_lines and out_lines[-1] != "":
                out_lines.append("")

        # Nettoyage minimal: enlever vides en fin
        while out_lines and out_lines[-1] == "":
            out_lines.pop()
        return "\n".join(out_lines).strip()

    def _extract_with_pymupdf(self, path: Path) -> tuple[str, int, int]:
        """Extraction via PyMuPDF (layout-aware)."""
        if not _HAVE_PYMUPDF:
            return "", 0, 0
        doc = fitz.open(str(path))
        num_pages = doc.page_count
        text_parts = []
        pages_with_text = 0
        for i in range(num_pages):
            page = doc.load_page(i)
            page_dict = page.get_text("dict")
            page_text = self._reconstruct_text_from_pymupdf_page(page_dict, page.rect.width)
            if page_text.strip():
                text_parts.append(page_text)
                pages_with_text += 1
            logger.debug("PyMuPDF page %d: %d caractères", i + 1, len(page_text))
        doc.close()
        return "\n\n".join(text_parts), num_pages, pages_with_text
    
    def extract(self, file_path: str) -> Dict:
        """
        Extrait le texte d'un fichier PDF
        
        Returns:
            dict avec success, text, pages, method, needs_ocr, error
        """
        logger.info(f"Début extraction: {file_path}")
        
        try:
            # Vérifier existence
            path = Path(file_path)
            if not path.exists():
                error_msg = f"Fichier non trouvé: {file_path}"
                logger.error(error_msg)
                return self._error_response(error_msg)
            
            # Vérifier extension
            if path.suffix.lower() != '.pdf':
                error_msg = f"Extension invalide: {path.suffix}"
                logger.error(error_msg)
                return self._error_response(error_msg)
            
            # 1) Essayer PyMuPDF (layout-aware)
            cleaned_text = ""
            num_pages = 0
            pages_with_text = 0
            method = "pypdf"

            if _HAVE_PYMUPDF:
                try:
                    full_text, num_pages, pages_with_text = self._extract_with_pymupdf(path)
                    cleaned_text = self._clean_text(full_text)
                    method = "pymupdf"
                    logger.info("Extraction PyMuPDF: %d caractères", len(cleaned_text))
                except Exception as e:
                    logger.warning("PyMuPDF a échoué (%s) → fallback pypdf", str(e))
                    cleaned_text = ""
                    num_pages = 0
                    pages_with_text = 0
                    method = "pypdf"

            # 2) Fallback pypdf
            if not cleaned_text.strip():
                reader = PdfReader(str(path))
                num_pages = len(reader.pages)
                logger.info(f"PDF chargé: {num_pages} page(s)")

                text_parts = []
                pages_with_text = 0
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(page_text)
                        pages_with_text += 1
                    logger.debug("Page %d: %d caractères", i + 1, len(page_text))

                full_text = "\n\n".join(text_parts)
                cleaned_text = self._clean_text(full_text)
                method = "pypdf"

            needs_ocr, reason = self._should_use_ocr(
                cleaned_text=cleaned_text,
                num_pages=num_pages,
                pages_with_text=pages_with_text,
            )

            if needs_ocr:
                logger.warning("PDF probablement scanné (%s)", reason)
                return {
                    'success': False,
                    'text': cleaned_text,
                    'pages': num_pages,
                    'method': method,
                    'needs_ocr': True,
                    'error': reason
                }
            
            # Succès
            logger.info(f"Extraction réussie: {len(cleaned_text)} caractères")
            
            return {
                'success': True,
                'text': cleaned_text,
                'pages': num_pages,
                'method': method,
                'needs_ocr': False,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Erreur extraction PDF: {str(e)}"
            logger.exception(error_msg)
            return self._error_response(error_msg)
    
    def _clean_text(self, text: str) -> str:
        """Nettoie le texte extrait"""
        if not text:
            return ""

        # Normaliser retours ligne + enlever caractères nuls
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")

        # Normalisations typographiques courantes (ligatures)
        text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")

        # Nettoyer ligne par ligne (préserver les \n, compacter les espaces)
        cleaned_lines = []
        prev_empty = False
        for raw_line in text.split("\n"):
            line = re.sub(r"\s+", " ", (raw_line or "").strip())
            if not line:
                if not prev_empty:
                    cleaned_lines.append("")
                prev_empty = True
                continue

            # Recoller les mots coupés (césure): "inter-\nnational" -> "international"
            if (
                cleaned_lines
                and cleaned_lines[-1]
                and cleaned_lines[-1].endswith("-")
                and re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]-$", cleaned_lines[-1])
                and re.match(r"^[a-zà-öø-ÿ]", line)
            ):
                cleaned_lines[-1] = cleaned_lines[-1][:-1] + line
            else:
                cleaned_lines.append(line)
            prev_empty = False

        cleaned = "\n".join(cleaned_lines).strip()
        logger.debug("Nettoyage PDF: %s -> %s caractères", len(text), len(cleaned))
        return cleaned

    def _should_use_ocr(self, cleaned_text: str, num_pages: int, pages_with_text: int) -> tuple[bool, str]:
        """Heuristique pour déterminer si un PDF nécessite un fallback OCR."""
        if num_pages <= 0:
            return True, "PDF invalide (0 page) - OCR nécessaire"

        if not cleaned_text.strip():
            return True, "Aucun texte extractible (pypdf) - OCR nécessaire"

        # 1) Seuil brut (compat historique)
        if len(cleaned_text) < self.min_text_length:
            return True, f"Texte trop court (<{self.min_text_length}) - OCR nécessaire"

        # 2) Signal fort : aucune page avec du texte extractible
        if pages_with_text == 0:
            return True, "Aucune page avec texte extractible - OCR nécessaire"

        # 2b) Signal fort : beaucoup de pages sans texte (scans multi-pages)
        if num_pages >= 2:
            ratio_pages_with_text = pages_with_text / max(1, num_pages)
            if ratio_pages_with_text < 0.30:
                return True, "Très peu de pages avec texte extractible - OCR recommandé"

        # 3) Texte présent mais très pauvre en lettres (artefacts, chiffres, ponctuation)
        non_ws = re.sub(r"\s+", "", cleaned_text)
        if not non_ws:
            return True, "Texte vide après nettoyage - OCR nécessaire"

        alpha = sum(ch.isalpha() for ch in non_ws)
        alpha_ratio = alpha / max(1, len(non_ws))

        if len(non_ws) < 600 and alpha_ratio < 0.30:
            return True, "Texte peu alphabétique (artefacts) - OCR recommandé"

        return False, ""
    
    def _error_response(self, error_msg: str) -> Dict:
        """Réponse d'erreur standardisée"""
        return {
            'success': False,
            'text': '',
            'pages': 0,
            'method': 'pypdf',
            'needs_ocr': False,
            'error': error_msg
        }


def extract_text_from_pdf(file_path: str) -> str:
    """Fonction simple pour extraction rapide"""
    extractor = PDFExtractor()
    result = extractor.extract(file_path)
    
    if result['success']:
        return result['text']
    else:
        raise Exception(result['error'])