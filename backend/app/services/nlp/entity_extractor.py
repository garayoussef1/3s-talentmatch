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


def _normalize_letters(value: str) -> str:
    """Normalise une chaîne en ne gardant que les lettres (pour détecter des mots OCR cassés)."""
    return re.sub(r"[^a-zà-öø-ÿ]+", "", (value or "").lower())


# Mots qui ne sont PAS des noms de personne (filtrage fallback)
_NOT_NAME_WORDS = {
    # Titres de CV
    "curriculum", "vitae", "cv", "resume", "résumé",
    # Titres de section
    "profil", "profile", "about", "summary", "objectif", "objective",
    "compétences", "competences", "skills", "formation", "education",
    "expérience", "experience", "langues", "languages", "contact",
    "références", "references", "projets", "projects", "certifications",
    # Postes courants IT
    "développeur", "developpeur", "développeuse", "developpeuse",
    "ingénieur", "ingenieur", "ingénieure", "ingenieure",
    "engineer",
    "developer", "manager", "consultant", "analyst", "designer",
    "stagiaire", "intern", "junior", "senior", "lead", "chef",
    "data", "scientist", "architect", "devops",
    "fullstack", "full-stack", "full", "stack", "frontend", "backend",
    "recherche", "développement", "intelligence", "artificielle",
    # Postes UX / Design
    "ux", "ui", "ux/ui", "product", "graphic",
    # Métiers non-IT (marketing, santé, compta, manuels)
    "digital", "marketing", "comptable", "expert-comptable",
    "électricien", "electricien", "plombier", "maçon", "macon",
    "menuisier", "mécanicien", "mecanicien", "soudeur",
    "infirmière", "infirmiere", "infirmier",
    "aide-soignant", "aide-soignante",
    "médecin", "medecin", "pharmacien", "pharmacienne",
    "responsable", "directeur", "directrice", "coordinateur",
    "gestionnaire", "technicien", "technicienne",
    "spécialiste", "specialiste", "specialist", "expert",
    "head", "bâtiment", "batiment", "industriel",
    # Architecture / BTP
    "architecte", "urbaniste", "dplg", "d.p.l.g", "d.p.l.g.",
    # Commerce / Vente
    "vendeur", "vendeuse", "commercial", "commerciale",
    "automobile", "terrain",
    # Audit / Finance
    "auditeur", "auditrice", "financier", "financière", "financiere",
    "associé", "associée", "associee",
    # Lieu de travail parasite
    "cabinet", "garage", "clinique", "hôpital", "hopital",
    "agence", "bureau", "studio", "atelier", "laboratoire",
    # Mots de CV/admin
    "etat", "état", "civil", "parcours", "historique",
    "publications", "publication", "divers",
    # Data / ML / AI (souvent collé au nom)
    "machine", "learning", "deep", "science", "scientist",
    "analytics", "analyst", "analysis",
    # Mots génériques / labels
    "monsieur", "madame", "mr", "mrs", "ms", "dr", "prof",
    "email", "mail", "téléphone", "telephone", "phone", "tel",
    "adresse", "address", "linkedin", "github", "portfolio", "site",
    # Mots de langue / niveau parasites
    "bilingue", "anglais", "français", "francais", "arabe", "espagnol",
    "allemand", "natif", "courant", "maternelle", "intermédiaire",
    "fluent", "native", "bilingual", "intermediate", "advanced",
    # Termes de poste anglais/français courants sur les CVs
    "student", "étudiant", "étudiante", "apprenti", "apprentie",
    "computer", "engineering", "development", "management",
    "consulting", "chief", "officer", "associate",
    "assistant", "assistante", "nurse", "accountant", "auditor",
    "sales", "business", "specialization", "spécialisation",
    "professional", "professionnel", "professionnelle",
    "project", "coordinator", "profil", "summary",
    # Domaines d'études / spécialités (souvent collés au nom)
    "génie", "genie", "informatique", "gestion", "communication",
    "technologies", "technologie", "information", "télécommunications",
    "telecommunications", "électronique", "electronique", "mécanique",
    "mecanique", "multimédia", "multimedia", "numérique", "numerique",
    "logiciel", "réseau", "reseaux", "réseaux", "système", "systeme",
    "systèmes", "systemes", "sécurité", "securite", "économie",
    "economie", "comptabilité", "comptabilite", "médecine", "medecine",
    "pharmacie", "biologie", "chimie", "mathématiques", "mathematiques",
    "physique", "droit", "industriel", "industrielle",
    "technology", "systems", "network", "security", "software",
    "hardware", "electronics", "economics", "finance",
    "accounting", "law", "medicine", "pharmacy",
    "spécialité", "specialite", "filière", "filiere", "option",
    # Mois FR/EN (souvent collés au nom dans les PDFs)
    "janvier", "février", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "août", "aout", "septembre", "octobre", "novembre", "décembre", "decembre",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    # Caractères spéciaux / icônes PDF corrompues
    "●", "●●", "●●●", "●●●●", "●●●●●",
    "★", "☆", "◆", "►", "▪",
    # Stopwords / prépositions FR & EN (parasites entre prénom-nom)
    "de", "du", "des", "le", "la", "les", "un", "une",
    "et", "en", "ou", "au", "aux", "par", "pour", "avec",
    "dans", "sur", "sous", "entre", "vers", "chez",
    "the", "and", "for", "with", "from", "into",
    "of", "in", "at", "on", "to", "by", "as", "is", "an", "or",
    "cycle", "année", "préparatoire", "études", "institut", "école", "ecole",
    "supérieur", "superieur", "supérieure", "superieure", "privé", "privée",
    "ingénieurs", "ingenieurs",
    # Mots d'identité / civil (souvent sur la même ligne que le nom)
    "lieu", "naissance", "nationalité", "nationalite", "date",
    "célibataire", "celibataire", "marié", "mariée", "mariee",
    "permis", "conduire", "véhiculé", "vehicule",
    "disponible", "immédiatement", "années", "ans",
    "tunisienne", "tunisien", "français", "française", "marocain", "marocaine",
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
    # Maroc
    "casablanca", "rabat", "fès", "fes", "marrakech", "tanger",
    "agadir", "oujda", "kénitra", "kenitra", "tétouan", "tetouan",
    # International
    "canada", "maroc", "algérie", "algerie", "morocco", "algeria",
    "dubai", "dubaï", "remote", "émirats", "emirats",
    "belgique", "suisse", "allemagne", "espagne", "italie",
    "london", "londres", "bruxelles", "genève", "geneve",
}

# Mots-clés métier utilisés par Pass 0 pour rejeter les lignes
# contenant des titres de poste (même capitalisés)
_PASS0_JOB_KEYWORDS = {
    "engineer", "engineering", "developer", "development",
    "manager", "management", "director", "chief",
    "student", "stagiaire", "intern", "apprenti",
    "consultant", "consulting", "specialist", "expert",
    "marketing", "commercial", "sales", "business",
    "comptable", "accountant", "auditeur", "auditor",
    "infirmier", "infirmière", "nurse",
    "électricien", "plombier", "maçon", "menuisier",
    "responsable", "chargé", "chef", "lead",
    "senior", "junior", "assistant", "associate",
    "computer", "science", "intelligence", "specialization",
    "spécialisation", "digital", "architect", "architecte",
    "designer", "analyst", "data", "web", "fullstack",
    "full-stack", "frontend", "backend", "devops", "dev", "ops",
    "technicien", "technician", "coordinateur", "coordinator",
    "gestionnaire", "officer", "professionnel", "professional",
    "étudiant", "étudiante", "ingénieur", "développeur",
    "développeuse", "developpeuse", "ingénieure",
    "stack", "full",
    # Mois courants (souvent collés dans les PDFs)
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
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

    def __init__(self, nlp_model=None):
        self._nlp = nlp_model

    # Titres métiers/postes à supprimer APRES extraction du nom
    _JOB_TITLE_PATTERN = re.compile(
        r"\b(?:"
        r"Digital\s+Marketing|Marketing\s+Digital|Marketing|Manager|Engineer"
        r"|Developer|D[ée]veloppeu(?:r|se)|Ing[ée]nieu(?:r|re)"
        r"|Full[\-\s]?Stack(?:e)?"
        r"|Électricien|Electricien|Plombier|Ma[\u00e7c]on|Menuisier"
        r"|M[ée]canicien|Soudeur"
        r"|Infirmi[\u00e8e]re?|Aide[\-\s]Soignante?"
        r"|M[ée]decin|Pharmacien(?:ne)?"
        r"|Comptable|Expert(?:e)?[\-\s]?Comptable"
        r"|Chef\s+de|Responsable|Charg[ée]e?(?:\s+de?)?"
        r"|Directeur(?:rice)?|Consultant(?:e)?"
        r"|Technicien(?:ne)?|Sp[ée]cialiste|Specialist"
        r"|Coordinat(?:eur|rice)|Gestionnaire"
        r"|Head\s+of|Senior|Junior|Lead|Expert"
        r"|B[\u00e2a]timent|Industriel(?:le)?"
        # Architecture / BTP
        r"|Architecte(?:\s+D\.?P\.?L\.?G\.?)?|Urbaniste|D\.?P\.?L\.?G\.?"
        # UX / Design
        r"|UX/?UI|UX|UI|Product\s+Designer|Graphic\s+Designer"
        # Data / ML / AI
        r"|Data\s+Scientist|Machine\s+Learning(?:\s+Engineer)?"
        r"|Deep\s+Learning|Data\s+Analyst|Data\s+Engineer"
        r"|Business\s+Analyst|Business\s+Intelligence"
        # Commerce / Vente
        r"|Vendeur(?:se)?(?:\s+automobile)?|Commercial(?:e)?(?:\s+terrain)?"
        # Audit / Finance
        r"|Audit(?:eur|rice)(?:\s+Financi[eè]re?)?"
        r")\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _clean_name(value: str) -> str:
        """Nettoie un nom extrait : supprime les mots parasites, emails, symboles."""
        # 0. Séparer les mots collés CamelCase (ex: "Full-StackJuin" → "Full-Stack Juin")
        cleaned = re.sub(r'([a-zà-öø-ÿ])([A-ZÀ-ÖØ-Þ])', r'\1 \2', value or '')
        # 1. Supprimer décorations
        cleaned = re.sub(r'[\u2551\u25ba\u25aa\u25cf\u25c6\u2192\u2022\u2550\u2554\u2557\u255a\u255d\u2560\u2563\u256c]', '', cleaned)
        cleaned = " ".join(cleaned.split()).strip("-: ")
        # 2. Supprimer tout ce qui contient @ (email collé au nom)
        words = [w for w in cleaned.split(" ") if w and "@" not in w]
        # 3. Supprimer les mots parasites connus
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

        # Détecter les faux positifs fréquents quand l'OCR/PDF "casse" un mot
        # (ex: "Form ation" → "formation", "Dev Ops" → "devops").
        joined = "".join(_normalize_letters(w) for w in words)
        blocked_joined = {
            "formation",
            "competences",
            "compétences",
            "experience",
            "expérience",
            "experiences",
            "expériences",
            "experienceprofessionnelle",
            "experienceprofessionnelles",
            "experiencesprofessionnelle",
            "experiencesprofessionnelles",
            "profil",
            "contact",
            "langues",
            "languages",
            "skills",
            "education",
            "projects",
            "projets",
            "certifications",
            "references",
            "références",
            "objectif",
            "objective",
            "resume",
            "résumé",
            "curriculumvitae",
            "devops",
            "fullstack",
        }
        blocked_norm = {_normalize_letters(x) for x in blocked_joined}
        joined_norm = _normalize_letters(joined)
        if joined_norm in blocked_norm:
            return False

        # Aucun mot ne doit être un mot interdit
        for w in words:
            wl = w.lower().rstrip(".,;:")
            if wl in _NOT_NAME_WORDS or wl in _LOCATION_WORDS:
                return False
            if _normalize_letters(w) in blocked_norm:
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
        if not self._nlp:
            return None
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

    def _extract_name_pass0(self, text: str) -> Optional[str]:
        """Pass 0 : Extraction simple depuis les 3 premières lignes non-vides.

        Vérifie si une ligne contient exactement 2-4 mots commençant par
        une majuscule, sans aucun mot-clé métier. Taux de confiance très élevé.
        """
        lines = (text or "").split('\n')
        count = 0
        for line in lines:
            if count >= 3:
                break
            # Nettoyer décorations (box-drawing, puces, etc.)
            cleaned = _DECORATIVE_CHARS.sub(' ', line)
            cleaned = " ".join(cleaned.split()).strip()
            if not cleaned:
                continue
            count += 1

            words = cleaned.split()
            if len(words) < 2 or len(words) > 4:
                continue

            # Chaque mot doit commencer par une majuscule
            if not all(w[0].isupper() for w in words if w):
                continue

            # Aucun mot ne doit être un keyword métier
            if any(w.lower().rstrip('.,;:') in _PASS0_JOB_KEYWORDS for w in words):
                continue

            # Aucun mot interdit ou lieu
            if any(
                w.lower().rstrip('.,;:') in _NOT_NAME_WORDS
                or w.lower().rstrip('.,;:') in _LOCATION_WORDS
                for w in words
            ):
                continue

            # Pas de chiffres
            if any(c.isdigit() for c in cleaned):
                continue

            # Pas de @ : www
            if '@' in cleaned or ':' in cleaned or 'www.' in cleaned.lower():
                continue

            return cleaned

        return None

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
        """Pass 3: Extraction intelligente depuis les premières lignes.

        Stratégie :
        1. Prend les 10 premières lignes
        2. Pour chaque ligne, découpe aux séparateurs (|, –, —, email, tél)
           et teste le premier fragment
        3. Nettoie les mots parasites puis vérifie la plausibilité
        """
        lines = (text or "").split('\n')[:10]
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Découper la ligne aux séparateurs courants dans les CVs
            # |, –, —, email, phone, urls  →  prendre le premier fragment
            fragment = re.split(
                r'\s*[|¦║]\s*'               # pipe / box-drawing
                r'|\s+[-–—]\s+'              # tiret entouré d'espaces
                r'|\s+\d{2,4}[\s./\-]'       # début numéro de téléphone
                r'|\s+\+\d'                   # +216, +33, +212...
                r'|\s+\S+@\S+'               # email
                r'|\s+https?://'              # url
                r'|\s+linkedin'              # linkedin
                r'|\s+www\.',                # website
                line, maxsplit=1
            )[0].strip()

            # Si le fragment contient ':', découper aussi sur ':'
            # Ex: "Othmen ZID Lieu de naissance: Ghazala" → "Othmen ZID Lieu de naissance"
            if ':' in fragment:
                fragment = fragment.split(':')[0].strip()

            # Supprimer décorations résiduelles
            fragment = re.sub(r'[•●►▪◆★☆/⌢⌣]', ' ', fragment)
            # Séparer les mots collés CamelCase (ex: "StackJuin" → "Stack Juin")
            fragment = re.sub(r'([a-zà-öø-ÿ])([A-ZÀ-ÖØ-Þ])', r'\1 \2', fragment)
            fragment = " ".join(fragment.split()).strip()

            if not fragment or len(fragment) > 80:
                continue

            # Nettoyer les titres de métier du fragment
            cleaned = self._JOB_TITLE_PATTERN.sub("", fragment)
            cleaned = " ".join(cleaned.split()).strip("- ,;:")

            # Nettoyer les mots parasites
            words = cleaned.split()
            filtered = []
            for w in words:
                wl = w.lower().rstrip(".,;:-()")
                if wl in _NOT_NAME_WORDS or wl in _LOCATION_WORDS:
                    continue
                # Gérer préfixes d'/l'/s'/n'/qu' (ex: "D'Ingénieurs" → check "ingénieurs")
                apo_m = re.match(r"^(?:d|l|s|n|qu|j)['''](.+)$", wl, re.I)
                if apo_m:
                    suffix = apo_m.group(1)
                    if suffix in _NOT_NAME_WORDS or suffix in _LOCATION_WORDS:
                        continue
                    # Aussi vérifier le singulier (ingénieurs → ingénieur)
                    if suffix.endswith('s') and suffix[:-1] in _NOT_NAME_WORDS:
                        continue
                if len(wl) < 2:
                    continue
                # Ignorer les abréviations type D.P.L.G
                if re.match(r'^[A-Z]\.([A-Z]\.)+$', w):
                    continue
                # Ignorer les acronymes >= 4 lettres tout en majuscules (noms d'écoles, etc.)
                w_clean = w.strip(".,;:-()")
                if len(w_clean) >= 4 and w_clean.isupper() and w_clean.isalpha():
                    continue
                filtered.append(w)

            if len(filtered) < 2 or len(filtered) > 4:
                continue

            # Rejeter explicitement les titres de poste/keywords métier
            # (ex: "Dev Ops", "Data Engineer", "Full Stack")
            filtered_job_tokens = set()
            for w in filtered:
                wl = w.lower().rstrip(".,;:-()")
                parts = [p for p in re.split(r"[^a-zà-öø-ÿ]+", wl) if p]
                filtered_job_tokens.update(parts or [wl])
            if any(tok in _PASS0_JOB_KEYWORDS for tok in filtered_job_tokens):
                continue

            candidate = " ".join(filtered)

            # Vérifier : pas de chiffres, pas de :, pas de @, pas de virgule
            if re.search(r'\d', candidate) or ':' in candidate or '@' in candidate:
                continue
            if ',' in candidate:
                continue

            # Rejeter si ça contient des mots techniques / langages / termes non-nom
            _TECH_WORDS = {"python", "java", "javascript", "react", "angular",
                           "vue", "django", "flask", "node", "docker", "sql",
                           "html", "css", "excel", "word", "powerpoint",
                           "spring", "laravel", "php", "ruby", "swift", "kotlin"}
            if any(w.lower().rstrip(".,;:") in _TECH_WORDS for w in filtered):
                continue

            # Chaque mot doit commencer par une majuscule (ou tout en majuscule)
            valid = True
            for w in filtered:
                w_clean = w.strip('.,;:')
                if not (w_clean[0].isupper() or w_clean.isupper()):
                    valid = False
                    break
            if not valid:
                continue

            # Validation finale (inclut la détection de mots OCR cassés type "Form ation")
            if not self._is_plausible_name(candidate):
                continue

            return candidate
        return None

    def _strip_job_title(self, name: str) -> str:
        """Supprime les titres de métier/poste collés au nom."""
        cleaned = self._JOB_TITLE_PATTERN.sub("", name)
        # Supprimer connecteurs orphelins (& et -)
        cleaned = re.sub(r'\s*[&]\s*', ' ', cleaned)
        cleaned = re.sub(r'(?:^|\s)-+(?:\s|$)', ' ', cleaned)
        cleaned = " ".join(cleaned.split()).strip("- ,;:.")
        # Si tout a été supprimé, garder l'original
        if len(cleaned.split()) < 2:
            return name
        return cleaned

    def _extract_name_from_linkedin(self, text: str) -> Optional[str]:
        """Pass 4 : Extraire le nom depuis une URL LinkedIn.

        Exemples :
          linkedin.com/in/ines-bensaad     → Ines Ben Saad
          linkedin.com/in/marie-martin     → Marie Martin
          www.linkedin.com/ines-bensaad    → Ines Ben Saad  (sans /in/)
        """
        # Chercher une URL LinkedIn dans les 500 premiers caractères
        header = (text or "")[:500]
        linkedin_re = re.compile(
            r"linkedin\.com(?:/in)?/([A-Za-z][A-Za-z0-9\-]{2,})",
            re.IGNORECASE,
        )
        match = linkedin_re.search(header)
        if not match:
            return None

        slug = match.group(1)  # ex: "ines-bensaad" ou "ines-bensaad-123abc"
        # Supprimer suffixe numérique LinkedIn (ex: -123abc à la fin)
        slug = re.sub(r"-[a-z0-9]{4,}$", "", slug)
        parts = [p for p in slug.split("-") if p and not p.isdigit()]

        # Doit avoir au moins prénom + nom (2 parties)
        if len(parts) < 2:
            return None

        # Chaque partie doit ressembler à un mot de nom (lettres seulement)
        if not all(re.match(r"^[a-zA-Zà-öø-ÿÀ-Þ]+$", p) for p in parts):
            return None

        candidate = " ".join(p.capitalize() for p in parts)

        # Validation : pas un titre de métier, pas un mot de section
        if not self._is_plausible_name(candidate):
            return None

        return candidate

    def _extract_name_from_email(self, text: str) -> Optional[str]:
        """Pass 5 : Extraire un nom depuis la partie locale d'un email.

        Exemples :
          inesbensaad95@gmail.com  → tente de décomposer "inesbensaad" en prénom+nom
          jean.dupont@example.com  → Jean Dupont
        """
        header = (text or "")[:500]
        email_re = re.compile(r"\b([A-Za-z][A-Za-z0-9._+-]{2,})@[A-Za-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)
        match = email_re.search(header)
        if not match:
            return None

        local = match.group(1)
        # Cas 1 : séparé par point ou underscore (jean.dupont / jean_dupont)
        if "." in local or "_" in local:
            parts = re.split(r"[._]", local)
            parts = [re.sub(r"[0-9]+$", "", p) for p in parts]  # retirer chiffres finaux
            parts = [p for p in parts if len(p) >= 2 and p.isalpha()]
            if len(parts) >= 2:
                candidate = " ".join(p.capitalize() for p in parts)
                if self._is_plausible_name(candidate):
                    return candidate

        # Cas 2 : tout collé (inesbensaad95) → retirer chiffres, puis CamelCase split
        clean = re.sub(r"[0-9]+", "", local)
        if len(clean) < 4:
            return None

        # Chercher si on peut deviner deux segments (prénom 3-8 lettres + nom restant)
        # Heuristique : essayer toutes les coupures prénom de 3 à 7 caractères
        for cut in range(3, min(8, len(clean) - 2)):
            first = clean[:cut].capitalize()
            last = clean[cut:].capitalize()
            candidate = f"{first} {last}"
            if self._is_plausible_name(candidate):
                return candidate

        return None

    def _extract_name_allcaps_anywhere(self, text: str) -> Optional[str]:
        """Pass 3b : cherche un nom en MAJUSCULES n'importe où dans le texte.

        Utile pour les CVs 2 colonnes où le nom apparaît dans la colonne droite
        (ex: Ines ben Saad → "INES BEN SAAD" en milieu de texte extrait).
        """
        # Pattern : 2-4 mots tous en MAJUSCULES, sur une ligne seule ou après \n
        # On exclut les sections connues (EDUCATION, SKILLS, etc.)
        _SECTION_CAPS = re.compile(
            r"^(?:EDUCATION|SKILLS|EXPERIENCE|FORMATION|COMPETENCES|LANGUES|LANGUAGES"
            r"|CERTIFICATIONS|PROJECTS|SUMMARY|OBJECTIVE|CONTACT|PROFIL|WORK"
            r"|TECHNICAL|PROFESSIONAL|ACADEMIC|ACTIVITIES|EXTRA)\b",
            re.IGNORECASE,
        )
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            words = line.split()
            if len(words) < 2 or len(words) > 4:
                continue
            # Tous les mots en majuscules, ≥2 lettres chacun
            if not all(w.isupper() and len(w) >= 2 and w.isalpha() for w in words):
                continue
            if _SECTION_CAPS.match(line):
                continue
            # Pas de mots interdits
            if any(w.lower() in _NOT_NAME_WORDS for w in words):
                continue
            # Plausibilité du nom
            candidate = " ".join(w.capitalize() for w in words)
            if self._is_plausible_name(candidate):
                return candidate
        return None

    def extract_full_name(self, text: str) -> Optional[str]:
        """
        Extrait le nom complet du candidat.

        Priorité (7 passes) :
        0.  Ligne simple : 2-4 mots capitalisés sans mot-clé métier
        1a. Ligne préfixée "Nom :" / "Name :"
        1b. Titre honorifique "Dr. NOM" / "M. NOM" / "Mme NOM"
        1c. CamelCase PyPDF ("SarahJohnson" → "Sarah Johnson")
        2.  Fallback : 1ère ligne qui ressemble à un nom (découpage intelligent)
        3.  Entité NER PERSON/PER (spaCy)
        4.  URL LinkedIn (linkedin.com/in/prenom-nom → Prenom Nom)
        5.  Email local part (prenom.nom@ ou prenomnom@)

        0.  Ligne simple : 2-4 mots capitalisés sans mot-clé métier
        1a. Ligne préfixée "Nom :" / "Name :"
        1b. Titre honorifique "Dr. NOM" / "M. NOM" / "Mme NOM"
        1c. CamelCase PyPDF ("SarahJohnson" → "Sarah Johnson")
        2.  Fallback : 1ère ligne qui ressemble à un nom (découpage intelligent)
        3.  Entité NER PERSON/PER (spaCy)
        
        Returns:
            Nom complet en Title Case, ou None.
        """
        logger.info("Extraction nom commencée (%d chars)", len(text or ""))

        try:
            # Pass 0 : Première ligne simple (2-4 mots capitalisés, aucun mot-clé métier)
            from_pass0 = self._extract_name_pass0(text)
            if from_pass0:
                result = self._normalize_case(from_pass0)
                logger.info("Nom trouvé par Pass 0 (ligne simple) : %s", result)
                return result

            # Pass 1a : Préfixe explicite ("Nom :", "Name :", etc.)
            from_prefix = self._extract_name_from_prefix(text)
            if from_prefix:
                result = self._strip_job_title(self._normalize_case(from_prefix))
                logger.info("Nom trouvé par préfixe : %s", result)
                return result

            # Pass 1b : Titre honorifique (Dr. AMIRA JEBALI, M. Dupont)
            from_honorific = self._extract_name_from_honorific(text)
            if from_honorific:
                result = self._strip_job_title(self._normalize_case(from_honorific))
                logger.info("Nom trouvé par honorifique : %s", result)
                return result

            # Pass 1c : CamelCase (SarahJohnson → Sarah Johnson)
            from_camel = self._extract_name_from_camelcase(text)
            if from_camel:
                result = self._strip_job_title(from_camel)
                logger.info("Nom trouvé par CamelCase : %s", result)
                return result

            # Pass 2 : Première ligne du CV (avec découpage intelligent)
            from_first_line = self._extract_name_from_first_lines(text)
            if from_first_line:
                result = self._strip_job_title(self._normalize_case(from_first_line))
                logger.info("Nom trouvé par première ligne : %s", result)
                return result

            # Pass 3 : spaCy NER
            from_ner = self._extract_name_from_person_entities(text)
            if from_ner:
                from_ner = self._strip_location_words(from_ner)
                if len(from_ner.split()) >= 2:
                    result = self._strip_job_title(self._normalize_case(from_ner))
                    logger.info("Nom trouvé par spaCy NER : %s", result)
                    return result
                logger.debug("NER a retourné '%s' mais insuffisant après nettoyage", from_ner)

            # Pass 3b : ALL_CAPS name anywhere in text (2-column PDFs where name is in right col)
            # Ex: "INES BEN SAAD" appears mid-text after all left-column content
            from_allcaps = self._extract_name_allcaps_anywhere(text)
            if from_allcaps:
                result = self._strip_job_title(self._normalize_case(from_allcaps))
                logger.info("Nom trouvé par ALL_CAPS anywhere : %s", result)
                return result

            # Pass 4 : LinkedIn URL (ex: linkedin.com/in/ines-bensaad → Ines Ben Saad)
            from_linkedin = self._extract_name_from_linkedin(text)
            if from_linkedin:
                logger.info("Nom trouvé par LinkedIn URL : %s", from_linkedin)
                return from_linkedin

            # Pass 5 : Email local part (ex: inesbensaad95@gmail.com → Ines Ben Saad)
            from_email = self._extract_name_from_email(text)
            if from_email:
                logger.info("Nom trouvé par email : %s", from_email)
                return from_email

            logger.warning("Aucun nom détecté par les 7 passes")
            return None

        except Exception as e:
            logger.error("Erreur extraction nom : %s", str(e), exc_info=True)
            return None

        return None
