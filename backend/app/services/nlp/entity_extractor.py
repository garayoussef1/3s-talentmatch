"""
Extraction d'entités de base depuis un texte de CV.
Sprint 2 - US-034

Stratégie multi-passes pour le nom :
1. Ligne préfixée "Nom :" / "Name :"
2. spaCy NER (entité PERSON/PER)
3. Fallback : 1ère ligne du CV qui ressemble à un nom humain
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# Mots qui ne sont PAS des noms de personne (filtrage fallback)
_NOT_NAME_WORDS = {
    # Titres de CV
    "curriculum", "vitae", "cv", "resume", "résumé",
    # Titres de section
    "profil", "profile", "about", "summary", "objectif", "objective",
    "compétences", "competences", "skills", "formation", "education",
    "expérience", "experience", "langues", "languages", "contact",
    "références", "references", "projets", "projects", "certifications",
    # Postes courants (pas un nom)
    "développeur", "developpeur", "ingénieur", "ingenieur", "engineer",
    "developer", "manager", "consultant", "analyst", "designer",
    "stagiaire", "intern", "junior", "senior", "lead", "chef",
    "data", "scientist", "architect", "devops", "fullstack", "full-stack",
    "recherche", "développement", "intelligence", "artificielle",
    # Mots génériques / labels
    "monsieur", "madame", "mr", "mrs", "ms", "dr", "prof",
    "email", "mail", "téléphone", "telephone", "phone", "tel",
    "adresse", "address", "linkedin", "github", "portfolio", "site",
    # Mots de langue / niveau parasites
    "bilingue", "anglais", "français", "francais", "arabe", "espagnol",
    "allemand", "natif", "courant", "maternelle", "intermédiaire",
    "fluent", "native", "bilingual", "intermediate", "advanced",
    # Caractères spéciaux / icônes PDF corrompues
    "●", "●●", "●●●", "●●●●", "●●●●●",
    "★", "☆", "◆", "►", "▪",
}

# Villes / pays / lieux souvent captés par NER comme PERSON
_LOCATION_WORDS = {
    # Tunisie
    "tunis", "tunisie", "tunisia", "sfax", "sousse", "monastir", "nabeul",
    "bizerte", "gabès", "gabes", "kairouan", "ariana", "manouba",
    "ben arous", "zaghouan", "jendouba", "kasserine", "sidi bouzid",
    "tozeur", "gafsa", "médenine", "medenine", "tataouine", "kébili",
    # France
    "paris", "lyon", "marseille", "toulouse", "nantes", "bordeaux",
    "lille", "nice", "strasbourg", "montpellier", "france",
    # Autres
    "canada", "maroc", "algérie", "algerie", "morocco", "algeria",
}

# Pattern pour vérifier qu'un mot ressemble à un prénom/nom
# Supporte: Jean, JEAN, Jean-Pierre, Ben
_NAME_WORD = re.compile(r"^[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:-[A-ZÀ-ÖØ-Þa-zà-öø-ÿ]+)?$|^[A-ZÀ-ÖØ-Þ]{2,}$")


# Caractères décoratifs à nettoyer dans les lignes de CV (box-drawing, etc.)
_DECORATIVE_CHARS = re.compile(r"[║╔╗╚╝═╠╣╬─│┌┐└┘├┤┬┴┼▒░▓█▌▐▄▀■□▪▫●○◆◇►▶◄◀★☆✓✗✔✘→←↑↓•‣⁃‐‑‒–—]")  # noqa: E501


class EntityExtractor:
    """Extracteur d'entités centré sur le nom complet du candidat."""

    # Pass 1 : "Nom :" / "Name :" / "Prénom et Nom :"
    NAME_PREFIX_PATTERN = re.compile(
        r"(?:^|\n)\s*(?:nom\s*(?:complet|et\s*prénom)?|name|prénom\s*(?:et)?\s*nom|full\s*name)"
        r"\s*[:\-\u2013\u2014]\s*"
        r"([A-Za-zÀ-ÖØ-öø-ÿ'\-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'\-]+){0,3})"
        r"(?=\s+\w+\s*[:\-]|$|\n)",
        flags=re.IGNORECASE,
    )

    # Pass 1b : Titre honorifique suivi d'un nom (Dr. AMIRA JEBALI, M. Dupont, Mme Ben Ali)
    HONORIFIC_PATTERN = re.compile(
        r"(?:^|\n)\s*(?:Dr\.?|Pr\.?|Prof\.?|M\.?|Mme\.?|Mlle\.?)\s+"
        r"([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'\-]+(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'\-]+){1,3})",
    )

    # Pass 1c : CamelCase collé sans espace (FirstLast → First Last) - typique PyPDF
    CAMELCASE_NAME_PATTERN = re.compile(
        r"^([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,15})([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,15})"
    )

    def __init__(self, nlp_model):
        self._nlp = nlp_model

    @staticmethod
    def _clean_name(value: str) -> str:
        """Nettoie un nom extrait : supprime les mots parasites, emails, symboles."""
        cleaned = " ".join((value or "").split()).strip("-: ")
        # Supprimer tout ce qui contient @ (email collé au nom)
        words = [w for w in cleaned.split(" ") if w and "@" not in w]
        # Supprimer les mots parasites connus
        filtered = []
        for w in words:
            wl = w.lower().rstrip(".,;:")
            # Supprimer caractères spéciaux / icônes (●, ★, etc.)
            if all(c in "●★☆◆►▪•○■□▶" for c in w):
                continue
            if wl in _NOT_NAME_WORDS or wl in _LOCATION_WORDS:
                continue
            # Supprimer les mots qui contiennent des URLs
            if "http" in wl or "www." in wl or ".com" in wl:
                continue
            filtered.append(w)
        if len(filtered) > 4:
            filtered = filtered[:4]
        return " ".join(filtered)

    @staticmethod
    def _strip_location_words(name: str) -> str:
        """Supprime les mots de lieu en fin de nom (ex: 'Youssef Gara Tunis' → 'Youssef Gara')."""
        words = name.strip().split()
        while words and words[-1].lower().rstrip(".,;:") in _LOCATION_WORDS:
            words.pop()
        return " ".join(words)

    @staticmethod
    def _is_plausible_name(text: str) -> bool:
        """Vérifie si un texte ressemble à un nom de personne."""
        words = text.strip().split()
        if len(words) < 2 or len(words) > 5:
            return False
        # Aucun mot ne doit être un mot interdit
        for w in words:
            wl = w.lower().rstrip(".,;:")
            if wl in _NOT_NAME_WORDS or wl in _LOCATION_WORDS:
                return False
        # Au moins 2 mots doivent ressembler à des noms propres
        name_words = sum(1 for w in words if _NAME_WORD.match(w.rstrip(".,;:")))
        if name_words < 2:
            # Cas spécial : tout en majuscules (YOUSSEF GARA)
            upper_words = sum(1 for w in words if w == w.upper() and len(w) >= 2 and w.isalpha())
            if upper_words < 2:
                return False
        # Pas trop long
        if len(text.strip()) > 60:
            return False
        # Pas de chiffres
        if any(c.isdigit() for c in text):
            return False
        # Pas de @ ou : (c'est un email ou un label)
        if "@" in text or ":" in text or "www." in text.lower():
            return False
        return True

    def _extract_name_from_prefix(self, text: str) -> Optional[str]:
        match = self.NAME_PREFIX_PATTERN.search(text or "")
        if not match:
            return None
        candidate = self._clean_name(match.group(1))
        if len(candidate) < 3:
            return None
        return candidate

    def _extract_name_from_person_entities(self, text: str) -> Optional[str]:
        # Limiter spaCy aux 2000 premiers caractères (le nom est toujours en haut du CV)
        header_text = (text or "")[:2000]
        doc = self._nlp(header_text)
        person_labels = {"PER", "PERSON"}
        candidates = []

        for ent in doc.ents:
            if ent.label_ not in person_labels:
                continue
            name = self._clean_name(ent.text)
            words = [w for w in name.split(" ") if len(w) > 1]
            if len(words) < 2:
                continue
            # Vérifier la plausibilité après nettoyage
            if not self._is_plausible_name(name):
                continue
            # Score : priorité aux entités en début de texte + nombre de mots
            position_score = max(0, 10 - ent.start)  # Plus tôt = meilleur
            word_score = len(words)
            candidates.append((name, position_score + word_score))

        if not candidates:
            return None
        # Retourner le meilleur candidat
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    @staticmethod
    def _normalize_case(name: str) -> str:
        """Convertit ALL-CAPS en Title Case."""
        if name and name == name.upper():
            return name.title()
        return name

    @staticmethod
    def _strip_decorations(line: str) -> str:
        """Supprime les caractères décoratifs (box-drawing) d'une ligne."""
        cleaned = _DECORATIVE_CHARS.sub(" ", line)
        return " ".join(cleaned.split()).strip()

    def _extract_name_from_honorific(self, text: str) -> Optional[str]:
        """Pass 1b : Détecte Dr. / M. / Mme suivi d'un nom propre."""
        m = self.HONORIFIC_PATTERN.search((text or "")[:500])
        if m:
            candidate = self._clean_name(m.group(1))
            if candidate and len(candidate.split()) >= 2:
                return candidate
        return None

    def _extract_name_from_camelcase(self, text: str) -> Optional[str]:
        """Pass 1c : Détecte FirstLast (CamelCase sans espace) en début de CV."""
        first_line = (text or "").split("\n")[0].strip() if text else ""
        # Aussi vérifier le 1er "mot" du texte complet (si pas de newline)
        first_chunk = (text or "").split()[0] if text and text.split() else ""
        for chunk in [first_line, first_chunk]:
            m = self.CAMELCASE_NAME_PATTERN.match(chunk)
            if m:
                first = m.group(1)
                last = m.group(2)
                # Vérifier que ce ne sont pas des mots interdits
                if first.lower() not in _NOT_NAME_WORDS and last.lower() not in _NOT_NAME_WORDS:
                    if first.lower() not in _LOCATION_WORDS and last.lower() not in _LOCATION_WORDS:
                        return f"{first} {last}"
        return None

    def _extract_name_from_first_lines(self, text: str) -> Optional[str]:
        lines = (text or "").split('\n')[:10]
        for line in lines:
            line = line.strip()
            if not line or len(line) > 60:
                continue
            line = re.sub(r'[|¦•●►║═]', '', line).strip()
            words = line.split()
            if len(words) < 2 or len(words) > 4:
                continue
            if re.search(r'\d', line):
                continue
            if ':' in line:
                continue
            section_keywords = ['curriculum', 'vitae', 'cv', 'resume', 'profil',
                               'profile', 'contact', 'information', 'expérience',
                               'compétences', 'competences', 'skills', 'formation',
                               'langues', 'langue']
            if any(kw in line.lower() for kw in section_keywords):
                continue
            valid = True
            for w in words:
                w_clean = w.strip('.,;:')
                if len(w_clean) < 2:
                    valid = False
                    break
                if not (w_clean[0].isupper() or w_clean.isupper()):
                    valid = False
                    break
            if valid:
                return ' '.join(words)
        return None

    def extract_full_name(self, text: str) -> Optional[str]:
        """
        Extrait le nom complet du candidat.
        
        Priorité (5 passes) :
        1a. Ligne préfixée "Nom :" / "Name :"
        1b. Titre honorifique "Dr. NOM" / "M. NOM" / "Mme NOM"
        1c. CamelCase PyPDF ("SarahJohnson" → "Sarah Johnson")
        2.  Entité NER PERSON/PER (spaCy)
        3.  Fallback : 1ère ligne qui ressemble à un nom
        
        Returns:
            Nom complet en Title Case, ou None.
        """
        logger.info("Extraction nom commencée (%d chars)", len(text or ""))

        try:
            # Pass 1a : Préfixe explicite ("Nom :", "Name :", etc.)
            from_prefix = self._extract_name_from_prefix(text)
            if from_prefix:
                result = self._normalize_case(from_prefix)
                logger.info("Nom trouvé par préfixe : %s", result)
                return result

            # Pass 1b : Titre honorifique (Dr. AMIRA JEBALI, M. Dupont)
            from_honorific = self._extract_name_from_honorific(text)
            if from_honorific:
                result = self._normalize_case(from_honorific)
                logger.info("Nom trouvé par honorifique : %s", result)
                return result

            # Pass 1c : CamelCase (SarahJohnson → Sarah Johnson)
            from_camel = self._extract_name_from_camelcase(text)
            if from_camel:
                logger.info("Nom trouvé par CamelCase : %s", from_camel)
                return from_camel

            # Pass 2 : spaCy NER
            from_ner = self._extract_name_from_person_entities(text)
            if from_ner:
                from_ner = self._strip_location_words(from_ner)
                if len(from_ner.split()) >= 2:
                    result = self._normalize_case(from_ner)
                    logger.info("Nom trouvé par spaCy NER : %s", result)
                    return result
                logger.debug("NER a retourné '%s' mais insuffisant après nettoyage", from_ner)

            # Pass 3 : Première ligne du CV (avec nettoyage décorations)
            from_first_line = self._extract_name_from_first_lines(text)
            if from_first_line:
                result = self._normalize_case(from_first_line)
                logger.info("Nom trouvé par première ligne : %s", result)
                return result

            logger.warning("Aucun nom détecté par les 5 passes")
            return None

        except Exception as e:
            logger.error("Erreur extraction nom : %s", str(e), exc_info=True)
            return None

        return None
