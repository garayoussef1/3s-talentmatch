"""
Extraction des informations de contact depuis un texte de CV.
Sprint 2 - US-035

Détecte : emails, téléphones, LinkedIn, GitHub, site web, adresse postale.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContactExtractor:
    """Extracteur de contacts : email, téléphone, LinkedIn, GitHub, site web, adresse."""

    # ── Email ────────────────────────────────────────────────────
    # Utilise un lookbehind pour exiger que l'email ne soit PAS précédé d'une lettre
    # (corrige le bug des icônes PDF : /envel⌢pesarah@... → capturait "pesarah@...")
    EMAIL_PATTERN = re.compile(
        r"(?<![a-zA-Z])[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    )

    # Variante OCR: espaces autour de @ et des points (ex: "prenom.nom @ gmail . com")
    EMAIL_OCR_SPACED_PATTERN = re.compile(
        r"(?<![a-zA-Z])"
        r"[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+(?:\s*\.\s*[a-zA-Z]{2,})+\b"
    )

    # Pattern email avec label (Email: ..., E-mail: ..., Mail: ...)
    EMAIL_LABEL_PATTERN = re.compile(
        r"(?:e[\-\s]?mail|courriel)\s*[:\-–—|.]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        re.IGNORECASE,
    )

    # Artefacts PDF courants avant un email (icônes Font Awesome : envelope, etc.)
    _PDF_EMAIL_ARTIFACTS = re.compile(
        r"^(?:pe|ope|lope|elope|velope|nvelope|envelope)"
        r"(?=[a-z])",
        re.IGNORECASE,
    )

    # ── Téléphone (international : FR, TN, US, UK, DE, etc.) ────
    PHONE_PATTERN = re.compile(
        r"(?:"
        r"(?:\+|00)\d{1,3}[\s\-.]?"                       # indicatif international
        r"(?:\(?\d{1,4}\)?[\s\-.]?){1,4}\d{2,4}"
        r"|"
        r"\(?\d{2,4}\)?[\s\-.]?\d{2,4}[\s\-.]?\d{2,4}[\s\-.]?\d{2,4}"  # local 4 groupes
        r"|"
        r"\d{2}[\s\-.]?\d{3}[\s\-.]?\d{3}"               # tunisien : XX XXX XXX
        r")"
    )

    # Pattern avec label pour les numéros ambigus
    PHONE_LABEL_PATTERN = re.compile(
        r"(?:t[eé]l(?:[eé]phone)?|phone|mobile|gsm|fax)\s*[:\-–—|.]?\s*"
        r"([\d\s\-.\(\)+]{7,20})",
        re.IGNORECASE,
    )

    # ── LinkedIn ─────────────────────────────────────────────────
    # Détecte : URL complète, ou "linkedin.com/in/xxx", ou "LinkedIn : xxx"
    # Note: certains CV contiennent des URLs de profil au format
    #   linkedin.com/<slug> (sans /in/). On gère les deux formes.
    LINKEDIN_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-_.%]+)/?",
        re.IGNORECASE,
    )
    LINKEDIN_ANY_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?linkedin\.com/(?P<path>[^\s,;\)\]]+)",
        re.IGNORECASE,
    )
    LINKEDIN_LABEL_PATTERN = re.compile(
        r"(?:linkedin|linked\s*in)\s*[:\-–—|/]\s*"
        r"(?:(?:https?://)?(?:www\.)?linkedin\.com/)?"
        r"(?:(?:in|pub)/)?"
        r"([a-zA-Z0-9\-_./%]+)",
        re.IGNORECASE,
    )

    # ── GitHub ───────────────────────────────────────────────────
    GITHUB_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9\-_.]+)/?",
        re.IGNORECASE,
    )
    GITHUB_LABEL_PATTERN = re.compile(
        r"(?:github|git\s*hub)\s*[:\-–—|/]\s*"
        r"(?:(?:https?://)?(?:www\.)?github\.com/)?"
        r"([a-zA-Z0-9\-_./%]+)",
        re.IGNORECASE,
    )

    # ── Site web / Portfolio ─────────────────────────────────────
    WEBSITE_PATTERN = re.compile(
        r"(?:(?:site\s*(?:web)?|portfolio|website|blog)\s*[:\-–—|]\s*)?"
        r"(https?://[a-zA-Z0-9\-_.]+\.[a-zA-Z]{2,}(?:/[^\s,;]*)?)",
        re.IGNORECASE,
    )

    # ── Adresse postale (simple) ─────────────────────────────────
    ADDRESS_PATTERN = re.compile(
        r"(?:adresse|address|domicile)\s*[:\-–—|]\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )
    # Pattern ville/pays courant dans les en-têtes de CV
    CITY_LINE_PATTERN = re.compile(
        r"(?:^|\n)\s*(?:\d{4,5}\s+)?"
        r"((?:Tunis|Paris|Lyon|Marseille|Toulouse|Bordeaux|Lille|Nantes|Strasbourg|Montpellier"
        r"|Sousse|Sfax|Monastir|Nabeul|Bizerte|Gabès|Kairouan|Ariana|Ben Arous|La Manouba"
        r"|London|Berlin|Munich|New York|San Francisco|Dubai|Remote)"
        r"(?:\s*,\s*(?:Tunisie|Tunisia|France|Allemagne|Germany|UK|USA|Émirats|Remote))?)",
        re.IGNORECASE,
    )

    # Patterns de dates qu'on NE veut PAS capturer comme téléphones
    DATE_PATTERN = re.compile(
        r"^\d{4}[\s\-–—/]\d{4}$"          # 2019-2022, 2024 2026
        r"|^\d{4}[\s\-–—/]\d{2}[\s\-–—/]\d{4}$"  # 1000 2004-2007
        r"|^\d{2}/\d{4}$"                   # 01/2020
        r"|^\d{4}$"                          # 2024
    )
    # Patterns à exclure des téléphones (ORCID, identifiants numériques)
    ORCID_PATTERN = re.compile(r"0000[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}")
    @staticmethod
    def _normalize_phone(value: str) -> str:
        phone = " ".join(value.split())
        return phone.strip("- .")

    @staticmethod
    def _normalize_email_candidate(value: str) -> Optional[str]:
        """Normalise un candidat email issu d'OCR et valide le format final."""
        if not value:
            return None
        email = value.strip()
        # Remplacer les formes masquées courantes (sans être trop agressif)
        email = re.sub(r"\s*(\(|\[|\{)\s*at\s*(\)|\]|\})\s*", "@", email, flags=re.IGNORECASE)
        email = re.sub(r"\s*(\(|\[|\{)\s*dot\s*(\)|\]|\})\s*", ".", email, flags=re.IGNORECASE)
        # Supprimer les espaces autour des séparateurs
        email = re.sub(r"\s*@\s*", "@", email)
        email = re.sub(r"\s*\.\s*", ".", email)

        # Heuristiques OCR : parfois le domaine/TLD est séparé par des espaces ("hotmail fr")
        # ou carrément collé ("hotmailfr"). On corrige AVANT de retirer tous les espaces.
        if "@" in email:
            local_part, domain_part = email.split("@", 1)
            local_part = re.sub(r"\s+", "", local_part)

            domain_part = domain_part.strip()
            if " " in domain_part:
                if "." in domain_part:
                    domain_part = domain_part.replace(" ", "")
                else:
                    domain_part = re.sub(r"\s+", ".", domain_part)
            else:
                # Exemple OCR: hotmailfr, gmailcom, outlooktn
                m = re.fullmatch(
                    r"([a-zA-Z0-9\-]{2,})(fr|tn|com|net|org|io|edu|gov|info|me)",
                    domain_part,
                    flags=re.IGNORECASE,
                )
                if m:
                    domain_part = f"{m.group(1)}.{m.group(2)}"

            email = f"{local_part}@{domain_part}"

        # Un email ne contient pas d'espaces
        email = re.sub(r"\s+", "", email)

        if ContactExtractor.EMAIL_PATTERN.fullmatch(email):
            return email
        return None

    @staticmethod
    def _email_candidates_from_at_context(text: str, window: int = 80) -> List[str]:
        """Extrait des candidats email en prenant un contexte autour de chaque '@'.

        Utile pour les sorties OCR tokenisées du style:
          "alexandre rozand@hotmail fr"
        """
        if not text or "@" not in text:
            return []

        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%+-@ ")
        candidates: List[str] = []

        for m in re.finditer(r"@", text):
            i = m.start()
            left = max(0, i - window)
            right = min(len(text), i + window)
            chunk = text[left:right]

            # Étendre dans le chunk pour ne garder que les caractères "email-ish" contigus
            at_in_chunk = i - left
            start = at_in_chunk
            while start > 0 and chunk[start - 1] in allowed:
                start -= 1
            end = at_in_chunk
            while end < len(chunk) and chunk[end] in allowed:
                end += 1

            cand = chunk[start:end].strip()
            if cand and "@" in cand:
                candidates.append(cand)

        # Dédupliquer grossièrement (insensible à la casse)
        seen = set()
        uniq: List[str] = []
        for c in candidates:
            k = c.lower()
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        return uniq

    def _strip_pdf_email_artifacts(self, email: str) -> str:
        """Supprime les artefacts PDF en début de local-part (pe/velope/...)."""
        if not email or "@" not in email:
            return email
        local_part, domain_part = email.split("@", 1)
        cleaned_local = self._PDF_EMAIL_ARTIFACTS.sub("", local_part)
        if cleaned_local != local_part:
            return f"{cleaned_local}@{domain_part}"
        return email

    def extract_emails(self, text: str) -> List[str]:
        unique = []
        seen = set()

        # Priorité 1 : emails avec label (Email: xxx@yyy.com) → toujours fiables
        for m in self.EMAIL_LABEL_PATTERN.finditer(text or ""):
            email = m.group(1).strip()
            normalized = self._normalize_email_candidate(email) or email
            email = self._strip_pdf_email_artifacts(normalized)
            low = email.lower()
            if low not in seen:
                seen.add(low)
                unique.append(email)

        # Priorité 1.5 : OCR avec espaces autour de @ et .
        for m in self.EMAIL_OCR_SPACED_PATTERN.finditer(text or ""):
            raw = m.group(0)
            email = self._normalize_email_candidate(raw)
            if not email:
                continue
            email = self._strip_pdf_email_artifacts(email)
            low = email.lower()
            if low not in seen:
                seen.add(low)
                unique.append(email)

        # Priorité 1.75 : candidats OCR autour de '@' (ex: "prenom nom@domaine tld")
        for raw in self._email_candidates_from_at_context(text or ""):
            email = self._normalize_email_candidate(raw)
            if not email:
                continue
            email = self._strip_pdf_email_artifacts(email)
            low = email.lower()
            if low not in seen:
                seen.add(low)
                unique.append(email)

        # Priorité 2 : regex générale avec nettoyage artefacts PDF
        for m in self.EMAIL_PATTERN.finditer(text or ""):
            email = m.group(0).strip()
            # Nettoyer les artefacts PDF (ex: "pesarah@..." → "sarah@...")
            local_part = email.split("@")[0]
            domain_part = email.split("@")[1] if "@" in email else ""
            cleaned_local = self._PDF_EMAIL_ARTIFACTS.sub("", local_part)
            if cleaned_local != local_part:
                email = f"{cleaned_local}@{domain_part}"
            normalized = self._normalize_email_candidate(email) or email
            email = self._strip_pdf_email_artifacts(normalized)
            low = email.lower()
            if low not in seen:
                seen.add(low)
                unique.append(email)

        return unique

    def extract_phones(self, text: str) -> List[str]:
        # Regex générale
        matches = self.PHONE_PATTERN.findall(text or "")
        # Regex avec label (Téléphone: ..., Tel: ...)
        for m in self.PHONE_LABEL_PATTERN.finditer(text or ""):
            matches.append(m.group(1))
        cleaned = []
        seen = set()
        for raw_phone in matches:
            phone = self._normalize_phone(raw_phone)
            digits_only = re.sub(r"\D", "", phone)
            # Minimum 8 chiffres pour un vrai numéro de téléphone
            if len(digits_only) < 8:
                continue
            # Exclure les dates (2019-2022, 2024 2026, etc.)
            if self.DATE_PATTERN.match(phone.strip()):
                continue
            # Exclure les patterns qui ressemblent clairement à des dates
            # Ex: "2019 2022" → 4 chiffres espace 4 chiffres
            if re.match(r"^(19|20)\d{2}[\s\-–—](19|20)\d{2}$", phone.strip()):
                continue
            # Exclure les dates OCR collées (20242026, etc.)
            if re.match(r"^(19|20)\d{6}$", digits_only):
                continue
            # Exclure ORCID (0000-xxxx-xxxx-xxxx)
            if self.ORCID_PATTERN.match(phone.strip()):
                continue
            # Exclure les numéros commençant par 0000 ou fragments d'ORCID (0002-1234-5678)
            if digits_only.startswith("0000") or re.match(r"^000\d[\s\-]\d{4}[\s\-]\d{4}$", phone.strip()):
                continue
            # Exclure les patterns "NNNN NNNN-NNNN" (ex: 1000 2004-2007)
            if re.match(r"^\d{4}\s+\d{4}[\s\-]\d{4}$", phone.strip()):
                continue
            # Exclure les numéros trop courts si pas d'indicatif
            if not phone.strip().startswith("+") and not phone.strip().startswith("00"):
                if len(digits_only) < 8:
                    continue
            key = digits_only
            if key not in seen:
                seen.add(key)
                cleaned.append(phone)
        return cleaned

    def extract_linkedin(self, text: str) -> Optional[str]:
        """Extrait le profil LinkedIn (retourne l'URL complète)."""
        # Chercher d'abord une URL complète (forme canonique /in/)
        m = self.LINKEDIN_URL_PATTERN.search(text or "")
        if m:
            username = m.group(1).strip("/").rstrip(".")
            return f"https://linkedin.com/in/{username}"

        # Fallback : URL de profil sans /in/ (ex: linkedin.com/ines-bensaad)
        # On évite les segments non-profil (company, jobs, feed, ...).
        reserved = {
            "company",
            "jobs",
            "feed",
            "learning",
            "school",
            "posts",
            "groups",
            "events",
            "help",
            "pulse",
            "mwlite",
        }
        for m in self.LINKEDIN_ANY_URL_PATTERN.finditer(text or ""):
            raw = (m.group("path") or "").strip().rstrip(".,;)]\"")
            raw = raw.split("?", 1)[0].split("#", 1)[0]
            path = raw.strip("/")
            if not path:
                continue

            segments = [s for s in path.split("/") if s]
            if not segments:
                continue

            head = segments[0].lower()
            if head in reserved:
                continue

            username = None
            if head in {"in", "pub"}:
                if len(segments) >= 2:
                    username = segments[1]
            else:
                username = segments[0]

            if not username:
                continue
            username = username.strip("/").rstrip(".")
            if len(username) < 2:
                continue
            if username.lower() in reserved:
                continue

            return f"https://linkedin.com/in/{username}"

        # Sinon chercher un label "LinkedIn : ..."
        m = self.LINKEDIN_LABEL_PATTERN.search(text or "")
        if m:
            username = m.group(1).strip("/").rstrip(".")
            if len(username) >= 2 and not username.startswith("http"):
                return f"https://linkedin.com/in/{username}"

        return None

    def extract_github(self, text: str) -> Optional[str]:
        """Extrait le profil GitHub (retourne l'URL complète)."""
        m = self.GITHUB_URL_PATTERN.search(text or "")
        if m:
            username = m.group(1).strip("/").rstrip(".")
            return f"https://github.com/{username}"

        m = self.GITHUB_LABEL_PATTERN.search(text or "")
        if m:
            username = m.group(1).strip("/").rstrip(".")
            if len(username) >= 2 and not username.startswith("http"):
                return f"https://github.com/{username}"

        return None

    def extract_website(self, text: str) -> Optional[str]:
        """Extrait le site web / portfolio."""
        for m in self.WEBSITE_PATTERN.finditer(text or ""):
            url = m.group(1).rstrip(".,;)")
            # Exclure LinkedIn et GitHub (déjà gérés)
            if "linkedin.com" in url.lower() or "github.com" in url.lower():
                continue
            return url
        return None

    def extract_address(self, text: str) -> Optional[str]:
        """Extrait l'adresse postale ou la ville."""
        m = self.ADDRESS_PATTERN.search(text or "")
        if m:
            return m.group(1).strip()

        # Fallback : chercher une ville connue dans les 10 premières lignes
        lines = (text or "").split("\n")[:10]
        header = "\n".join(lines)
        m = self.CITY_LINE_PATTERN.search(header)
        if m:
            return m.group(1).strip()

        return None

    def extract(self, text: str) -> Dict:
        """
        Extraction complète de tous les contacts.

        Returns:
            {
                "emails": [...],
                "phones": [...],
                "primary_email": str | None,
                "primary_phone": str | None,
                "linkedin": str | None,
                "github": str | None,
                "website": str | None,
                "address": str | None,
            }
        """
        emails = self.extract_emails(text)
        phones = self.extract_phones(text)
        linkedin = self.extract_linkedin(text)
        github = self.extract_github(text)
        website = self.extract_website(text)
        address = self.extract_address(text)

        return {
            "emails": emails,
            "phones": phones,
            "primary_email": emails[0] if emails else None,
            "primary_phone": phones[0] if phones else None,
            "linkedin": linkedin,
            "github": github,
            "website": website,
            "address": address,
        }
