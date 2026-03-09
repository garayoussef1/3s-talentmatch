"""Extraction des expériences professionnelles depuis un texte de CV.

Sprint 2 — US-210

Informations extraites pour chaque expérience :
- Intitulé du poste (Développeur Full Stack, Software Engineer, …)
- Entreprise (spaCy ORG + heuristiques « chez », « at », « @ », « | », « — »)
- Dates de début / fin (ou « en cours »)
- Durée calculée automatiquement (en mois)
- Localisation (ville, pays, remote)
- Missions / responsabilités (bullet points)

Couverture internationale :
- FR : « Développeur chez ACME — janv. 2020 à déc. 2022 »
- EN : « Software Engineer at Google — Jan 2020 - Present »
- DE : « Berufserfahrung »  /  ES : « Experiencia laboral »
- RU : « Опыт работы »
- Formats de date : mois texte, MM/YYYY, YYYY-MM, YYYY seul

Même architecture « par blocs » que formation_extractor.py :
  Section isolée → blocs individuels → extraction sans contamination

Auteur  : Youssef Gara
Projet  : 3S TalentMatch — PFE ESPRIT 2025-2026
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ================================================================
# Mois FR/EN → numéro  (abrégés + complets)
# ================================================================

MONTHS_MAP: Dict[str, int] = {}

for _i, (_full, *_abbrs) in enumerate([
    ("janvier", "janv"),
    ("février", "fevrier", "févr", "fevr"),
    ("mars",),
    ("avril", "avr"),
    ("mai",),
    ("juin",),
    ("juillet", "juil"),
    ("août", "aout"),
    ("septembre", "sept"),
    ("octobre", "oct"),
    ("novembre", "nov"),
    ("décembre", "decembre", "déc", "dec"),
], start=1):
    for _name in (_full, *_abbrs):
        MONTHS_MAP[_name] = _i


def _normalize_date_text(text: str) -> str:
    """Normalise un texte de date pour un matching robuste.

    - minuscules
    - suppression des accents
    - trim des espaces
    """
    text = (text or "").strip().lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    return text


MONTHS_MAP_NORMALIZED: Dict[str, int] = {
    _normalize_date_text(name): num
    for name, num in MONTHS_MAP.items()
}

for _i, (_full, *_abbrs) in enumerate([
    ("january", "jan"), ("february", "feb"),
    ("march", "mar"), ("april", "apr"), ("may",),
    ("june", "jun"), ("july", "jul"), ("august", "aug"),
    ("september", "sep", "sept"), ("october", "oct"),
    ("november", "nov"), ("december", "dec"),
], start=1):
    for _name in (_full, *_abbrs):
        MONTHS_MAP[_name] = _i


# ================================================================
# Patterns de dates
# ================================================================

# Mois texte (FR + EN complet + abrégé)
_MOIS_FR = (
    r"(?:janv(?:ier)?|f[eé]vr(?:ier)?|fevrier|mars|avr(?:il)?|mai"
    r"|juin|juil(?:let)?|ao[uû]t|sept(?:embre)?|oct(?:obre)?"
    r"|nov(?:embre)?|d[eé]c(?:embre)?|decembre)"
)
_MOIS_EN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may"
    r"|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?"
    r"|nov(?:ember)?|dec(?:ember)?)"
)
_MOIS_ALL = rf"(?:{_MOIS_FR}|{_MOIS_EN})"

# Token date individuel : « janvier 2020 », « 01/2020 », « 2020-01 », « 2020 »
_DATE_TOKEN_RE = rf"(?:{_MOIS_ALL}\.?\s+\d{{4}}|\d{{1,2}}[/\-\.]\d{{4}}|\d{{4}}[/\-\.]\d{{1,2}}|\d{{4}})"

# Marqueurs « en cours »
_EN_COURS = re.compile(
    r"\b(?:pr[ée]sent|actuel(?:lement)?|en\s+cours|en\s+poste"
    r"|aujourd[\u2018\u2019''`]?\s*hui|(?:[àa]\s+)?ce\s+jour"
    r"|current(?:ly)?|current|present|presnt|prsent|ongoing|now|to\s+date"
    r"|jusqu[\u2018\u2019''`]?\s*[àa]\s+(?:pr[ée]sent|aujourd)"
    r"|seit|настоящее\s+время"   # DE / RU
    r")\b",
    re.IGNORECASE,
)

# Plage de dates complète
_DATE_RANGE = re.compile(
    rf"({_DATE_TOKEN_RE})"
    rf"\s*(?:[-–—/]{{1,2}}\s*"
    rf"|au\s+(?:mois\s+(?:de\s+|d[\u2018\u2019'']\s*)?)?"   # au mois de / au FR
    rf"|[àa]\s+"
    rf"|to\s+"
    rf"|jusqu[\u2018\u2019''`]?[àa]\s+)"
    rf"({_DATE_TOKEN_RE}|pr[ée]sent|present|presnt|prsent|en\s*cours|en\s+poste|aujourd[\u2018\u2019''`]?\s*hui|(?:[àa]\s+)?ce\s+jour|actuel(?:lement)?|current(?:ly)?|current|now|ongoing|to\s+date)",
    re.IGNORECASE,
)

# « Depuis mars 2023 » / « From March 2023 » / « Since 2020 »
_SINCE_PATTERN = re.compile(
    rf"(?:depuis|since|from|ab|с)\s+({_DATE_TOKEN_RE})",
    re.IGNORECASE,
)

# « Juillet - Août 2023 » : deux noms de mois avec une année partagée en fin
_DATE_RANGE_SHARED_YEAR = re.compile(
    rf"({_MOIS_ALL})\s*[-–—/]{{1,2}}\s*({_MOIS_ALL})\.?\s+(\d{{4}})",
    re.IGNORECASE,
)

# « Juillet 2023 » : un seul mois + année (stage court sans fin explicite)
_DATE_SINGLE_MONTH_YEAR = re.compile(
    rf"({_MOIS_ALL})\.?\s+(\d{{4}})",
    re.IGNORECASE,
)

# Date isolée simple
_DATE_SINGLE = re.compile(rf"({_DATE_TOKEN_RE})", re.IGNORECASE)


def _parse_date_token(token: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse un token de date → (année, mois).

    Supporte :
    - « janvier 2020 »  → (2020, 1)
    - « 01/2020 »       → (2020, 1)
    - « 2020-01 »       → (2020, 1)
    - « 2020 »          → (2020, 1)
    """
    if not token:
        return None, None
    token = token.strip().lower()
    token_norm = _normalize_date_text(token)

    # Token de type « en cours » => pas de date de fin explicite
    if _is_ongoing(token) or _is_ongoing(token_norm):
        return None, None

    _max_year = date.today().year + 2

    # « mois année » : janvier 2020 / Jan 2020
    for month_name, month_num in MONTHS_MAP_NORMALIZED.items():
        pat = re.compile(rf"^{re.escape(month_name)}\s*\.?\s*(\d{{4}})$", re.I)
        m = pat.match(token_norm)
        if m:
            year = int(m.group(1))
            if year < 1950 or year > _max_year:
                return None, None
            return year, month_num

    # « MM/YYYY » ou « MM-YYYY » ou « MM.YYYY »
    m = re.match(r"^(\d{1,2})[/\-\.](\d{4})$", token_norm)
    if m:
        month = int(m.group(1))
        year = int(m.group(2))
        if 1 <= month <= 12 and 1950 <= year <= _max_year:
            return year, month
        return None, None

    # « YYYY-MM » (ISO)
    m = re.match(r"^(\d{4})[/\-\.](\d{1,2})$", token_norm)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        if 1 <= month <= 12 and 1950 <= year <= _max_year:
            return year, month
        return None, None

    # « YYYY » seul
    m = re.match(r"^(\d{4})$", token_norm)
    if m:
        year = int(m.group(1))
        if year < 1950 or year > date.today().year + 2:
            return None, None
        return year, 1

    return None, None


def _is_ongoing(token: str) -> bool:
    """Vérifie si le token représente « en cours »."""
    return bool(_EN_COURS.search(token.strip()))


def _compute_duration_months(
    start_year: int, start_month: int,
    end_year: Optional[int], end_month: Optional[int],
) -> int:
    """Calcule la durée en mois entre deux dates."""
    today = date.today()
    if end_year is None or end_year > today.year + 1:
        end_year = today.year
        end_month = today.month
    if end_month is None:
        end_month = 1
    if start_year > today.year + 1:
        return 0
    return max(0, (end_year - start_year) * 12 + (end_month - start_month))


# ================================================================
# Section Expérience (international)
# ================================================================

EXPERIENCE_SECTION_KW = re.compile(
    r"(?:^|\n)\s*"
    r"(?:exp[ée]riences?\s*(?:"
    r"professionnelles?"
    r"|professionnels?"
    r"|professionels?"
    r"|profesionnelles?"
    r"|profesionnels?"
    r"|de\s+travail"
    r")?"
    r"|exp[ée]rience\s+pro"
    r"|exp[ée]rience"
    r"|exp[ée]riences"
    r"|exp[ée]rience\s+professionnelle"
    r"|exp[ée]riences\s+professionnelles"
    r"|professional\s+experience"
    r"|professional\s+experiences"
    r"|prolessional\s+experience"
    r"|prolessional\s+experlence"
    r"|professional\s+experlence"
    r"|work\s+experience"
    r"|work\s+experiences"
    r"|professional\s+background"
    r"|work\s+background"
    r"|employment\s+experience"
    r"|employment\s+summary"
    r"|career"
    r"|employment(?:\s+history)?"
    r"|parcours(?:\s+professionnel)?"
    r"|parcours\s+professionnels"
    r"|parcours\s+de\s+travail"
    r"|parcours"
    r"|historique\s+professionnel"
    r"|exp[ée]riences?\s+de\s+travail"
    r"|emplois?"
    r"|carri[èe]re"
    r"|vie\s+professionnelle"
    r"|career\s+(?:history|summary)"
    r"|berufserfahrung"              # DE
    r"|experiencia\s+(?:laboral|profesional)"   # ES
    r"|опыт\s+работы"               # RU
    r")"
    r"\s*[:\-—]?\s*(?:\n|$)",
    re.IGNORECASE,
)


# ================================================================
# Intitulés de postes (FR + EN composés + international)
# ================================================================

_TITRES_FR_COMPOSES = [
    # RH / Commercial / Management (priorité composés)
    r"drh\s+adjointe?",
    r"directeur(?:\s+des)?\s+ressources\s+humaines",
    r"responsable\s+ressources\s+humaines",
    r"responsable\s+rh",
    r"charg[ée]e?\s+des?\s+ressources\s+humaines",
    r"assistant(?:e)?\s+ressources\s+humaines",
    r"responsable\s+d[ée]veloppement\s+commercial",
    r"responsable\s+commercial(?:e)?",
    r"assistant(?:e)?\s+commercial(?:e)?",
    r"charg[ée]e?\s+de\s+client[èe]le(?:\s+entreprises?)?",
    r"charg[ée]e?\s+d[''']?affaires(?:\s+entreprises?)?",
    r"responsable\s+recrutement",
    r"charg[ée]e?\s+de\s+recrutement",
    r"assistant(?:e)?\s+recrutement",
    r"responsable\s+formation",
    r"charg[ée]e?\s+de\s+formation",
    r"gestionnaire\s+paie",
    r"gestionnaire\s+rh",
    r"responsable\s+marketing",
    r"chef\s+de\s+produit",
    r"responsable\s+produit",
    r"product\s+owner",
    r"scrum\s+master",
    r"chef\s+de\s+projet(?:\s+(?:informatique|technique|digital|web|it))?",
    r"chef\s+de\s+projet\s+fonctionnel",
    r"chef\s+de\s+projet\s+digital",
    r"project\s+manager",
    r"program\s+manager",
    r"delivery\s+manager",
    r"account\s+manager",
    r"key\s+account\s+manager",
    r"sales\s+manager",
    r"business\s+analyst",
    r"data\s+analyst",
    r"business\s+developer",
    r"customer\s+success\s+manager",
    r"talent\s+acquisition\s+specialist",
    r"technical\s+recruiter",
    r"responsable\s+acquisition\s+talents",
    r"responsable\s+relations\s+clients",
    r"consultant\s+fonctionnel",
    r"consultant\s+erp",
    r"consultant\s+sap",
    r"analyste\s+fonctionnel",
    r"analyste\s+m[ée]tier",
    r"responsable\s+administratif\s+et\s+financier",
    r"assistant(?:e)?\s+de\s+direction",
    r"office\s+manager",
    r"responsable\s+service\s+client",
    r"responsable\s+support",
    r"charg[ée]e?\s+de\s+support",
    r"ing[ée]nieur\s+d[''']?affaires",
    r"responsable\s+partenariats?",
    r"directeur\s+commercial",
    r"directeur\s+marketing",
    r"directeur\s+de\s+projet",
    # Marketing / Communication
    r"head\s+of\s+digital\s+marketing",
    r"digital\s+marketing\s+(?:manager|specialist|expert)",
    r"social\s+media\s+(?:manager|specialist)",
    r"responsable\s+marketing\s+digital",
    r"charg[ée]e?\s+de\s+communication\s+digitale?",
    r"growth\s+hacker",
    r"content\s+(?:manager|strategist)",
    r"community\s+manager",
    r"traffic\s+manager",
    r"seo\s+(?:manager|specialist|expert)",
    # Comptabilité / Finance
    r"expert(?:e)?\s*[\-\s]?comptable",
    r"expert(?:e)?\s+comptable\s+associ[ée]e?",
    r"chef\s+comptable",
    r"responsable\s+comptable",
    r"auditeur(?:\s+junior)?",
    r"auditrice(?:\s+junior(?:e)?)?",
    r"commissaire\s+aux\s+comptes",
    r"contr[ôo]leur\s+de\s+gestion",
    r"analyste\s+financier",
    # Santé / Médical
    r"infirmi[èe]re?(?:\s+en\s+r[ée]animation)?",
    r"infirmi[èe]re?(?:\s+service\s+urgences)?",
    r"infirmi[èe]re?(?:\s+polyvalente?)?",
    r"aide[\-\s]soignant(?:e)?",
    r"m[ée]decin(?:\s+g[ée]n[ée]raliste)?",
    r"pharmacien(?:ne)?",
    r"sage[\-\s]femme",
    # Métiers manuels
    r"[ée]lectricien(?:\s+b[âa]timent)?",
    r"[ée]lectricien(?:\s+industriel)?",
    r"plombier(?:\s+chauffagiste)?",
    r"ma[çc]on",
    r"menuisier",
    r"m[ée]canicien(?:\s+auto)?",
    r"soudeur",
    r"peintre\s+en\s+b[âa]timent",
    r"charpentier",
]

_TITRES_FR = [
    # Informatique & Tech
    r"d[ée]veloppeur(?:\s+(?:web|mobile|full[\s\-]?stack|front[\s\-]?end|back[\s\-]?end|logiciel|java|python|\.net|php|c\+\+))?",
    r"ing[ée]nieur(?:\s+(?:logiciel|d[ée]veloppement|syst[eèé]mes?|r[ée]seaux?|devops|cloud|data|ia|s[ée]curit[ée]|test|qualit[ée]|informatique|[ée]tudes?))?",
    r"architecte(?:\s+(?:logiciel|solutions?|technique|cloud|syst[eèé]me|s[ée]curit[ée]))?",
    r"chef\s+de\s+projet(?:\s+(?:informatique|technique|digital|web|it))?",
    r"responsable(?:\s+(?:technique|informatique|it|d[ée]veloppement|infrastructure|s[ée]curit[ée]|data|digital))?",
    r"directeur(?:\s+(?:technique|informatique|it|des\s+syst[eèé]mes\s+d[''']?information|digital))?",
    r"consultant(?:\s+(?:technique|it|sap|erp|s[ée]curit[ée]|data|fonctionnel|bi))?",
    r"analyste(?:\s+(?:d[ée]veloppeur|programmeur|fonctionnel|technique|donn[ée]es?|data|business|s[ée]curit[ée]))?",
    r"administrateur(?:\s+(?:syst[eèé]mes?|r[ée]seaux?|bases?\s+de\s+donn[ée]es?|linux|windows))?",
    r"technicien(?:\s+(?:informatique|r[ée]seaux?|syst[eèé]me|support|maintenance))?",
    r"data\s+(?:scientist|engineer|analyst|architect)",
    r"scrum\s+master",
    r"product\s+owner",
    r"devops(?:\s+engineer)?",
    r"lead\s+(?:d[ée]veloppeur|technique|developer|tech)",
    # Stages & alternance
    r"stagiaire(?:\s+[\w\s]{3,30})?",
    r"alternant(?:e)?(?:\s+[\w\s]{3,30})?",
    r"apprenti(?:e)?(?:\s+[\w\s]{3,20})?",
    # Business / Gestion
    r"chef\s+d[''']?[ée]quipe",
    r"manager(?:\s+[\w\s]{3,20})?",
    r"coordinateur(?:\s+[\w\s]{3,20})?",
    r"charg[ée](?:\s+d[eé]\s+[\w\s]{3,30})?",
    r"drh",
]

_TITRES_EN = [
    r"(?:senior|junior|lead|principal|staff)\s+(?:software\s+)?(?:engineer|developer)",
    r"software\s+(?:engineer|developer|architect)",
    r"(?:front[\s\-]?end|back[\s\-]?end|full[\s\-]?stack)\s+(?:developer|engineer)",
    r"(?:web|mobile|ios|android|cloud|platform|site\s+reliability)\s+(?:developer|engineer)",
    r"(?:machine\s+learning|ml|ai|data)\s+(?:engineer|scientist|analyst)",
    r"(?:qa|test|quality)\s+(?:engineer|analyst|lead|manager|automation)",
    r"(?:devops|devsecops|sre|infrastructure|systems?)\s+engineer",
    r"(?:project|program|product|engineering|delivery)\s+manager",
    r"(?:technical|tech)\s+lead",
    r"(?:cto|cio|coo|ceo|vp\s+of\s+engineering)",
    r"(?:business|data|systems?|security|network)\s+(?:analyst|engineer|architect|administrator)",
    r"(?:ux|ui|ux[/\s]ui)\s+(?:designer|researcher|engineer)",
    r"(?:solutions?|enterprise|cloud)\s+architect",
    r"(?:release|build)\s+(?:manager|engineer)",
    r"agile\s+coach",
    r"scrum\s+master",
    r"product\s+owner",
    r"(?:intern|trainee|apprentice)(?:\s+[\w\s]{3,20})?",
    r"(?:research|teaching)\s+(?:assistant|associate)",
    r"professor(?:\s+[\w\s]{3,20})?",
    r"freelanc(?:e|er)",
]

_TITRE_PATTERN = re.compile(
    r"\b(" + "|".join(_TITRES_FR_COMPOSES + _TITRES_FR + _TITRES_EN) + r")\b",
    re.IGNORECASE,
)


# ================================================================
# Séparateurs entreprise
# ================================================================

_COMPANY_SEP = re.compile(
    r"\s+(?:chez|at|@|auprès\s+de|au\s+sein\s+de|pour|bei)\s+",
    re.IGNORECASE,
)

# Mots à exclure des noms d'entreprise
_COMPANY_STOP = {
    "stage", "alternance", "cdi", "cdd", "freelance", "intérim",
    "interim", "mission", "contrat", "temps", "plein", "partiel",
    "remote", "télétravail", "teletravail", "hybrid", "hybride",
    "à", "en", "de", "du", "le", "la", "les", "des",
}


# ================================================================
# Localisation (villes + pays courants)
# ================================================================

_LOCATION_PATTERN = re.compile(
    r"\b("
    # FR
    r"Paris|Lyon|Marseille|Toulouse|Nice|Nantes|Strasbourg|Montpellier"
    r"|Bordeaux|Lille|Rennes|Grenoble|Rouen|Toulon|Clermont[\-\s]Ferrand"
    # TN (28 villes)
    r"|Tunis|Sfax|Sousse|Ariana|Ben\s+Arous|La\s+Marsa|Monastir|Bizerte|Nabeul"
    r"|Gab[eè]s|Kairouan|M[eé]denine|Tozeur|Gafsa|B[eé]ja|Jendouba"
    r"|Siliana|Le\s+Kef|La\s+Manouba|Manouba|K[eé]libia|Hammamet"
    r"|Mahdia|Djerba|Kasserine|Zaghouan|Sidi\s+Bouzid|Tataouine"
    # International
    r"|London|New\s+York|San\s+Francisco|Los\s+Angeles|Seattle|Boston|Chicago"
    r"|Berlin|Munich|Frankfurt|Hamburg|Zurich|Geneva|Brussels|Amsterdam"
    r"|Dublin|Madrid|Barcelona|Lisbon|Milan|Rome|Vienna"
    r"|Tokyo|Singapore|Dubai|Toronto|Montreal|Vancouver|Sydney|Melbourne"
    r"|Shanghai|Beijing|Seoul|Bangalore|Mumbai"
    r"|Casablanca|Rabat|Alger|Le\s+Caire|Doha|Riyad"
    r"|Москва|Санкт[\-\s]Петербург"
    # Pays
    r"|France|Tunisie|Tunisia|USA|UK|United\s+Kingdom|Germany|Deutschland"
    r"|Switzerland|Suisse|Canada|Australia|India|Japan|China|Россия"
    r"|Maroc|Morocco|Alg[eé]rie|Algeria|[EÉ]gypte|Egypt|Qatar|Arabie\s+Saoudite"
    # Remote
    r"|Remote|T[éeè]l[éeè]travail|Hybrid[e]?"
    r")\b",
    re.IGNORECASE,
)


# ================================================================
# Extracteur principal
# ================================================================

class ExperienceExtractor:
    """Extracteur d'expériences professionnelles.

    Stratégie par blocs (cohérente avec FormationExtractor) :
    1. Isoler la section « Expérience » du CV.
    2. Découper en blocs individuels (1 par poste).
    3. Pour chaque bloc : poste, entreprise, dates, durée,
       localisation, missions.
    4. spaCy NER (ORG) en renfort pour la détection d'entreprises.
    """

    def __init__(self, nlp_model=None):
        """Initialise l'extracteur.

        Args:
            nlp_model: Modèle spaCy chargé (optionnel).
        """
        self._nlp = nlp_model

    # ────────────────────────────────────────────────────────────
    # Section isolation
    # ────────────────────────────────────────────────────────────

    def _find_experience_section(self, text: str) -> str:
        """Isole la section Expérience du CV."""
        match = EXPERIENCE_SECTION_KW.search(text)
        if not match:
            # Fallback : en-tête inline (ex: "PARCOURS DRH Adjointe...")
            inline = re.search(
                r"\b(?:exp[ée]riences?\s*(?:professionnelles?|de\s+travail)?"
                r"|work\s+experience|professional\s+experience"
                r"|parcours(?:\s+professionnel)?|emplois?|carri[èe]re)\b",
                text,
                re.IGNORECASE,
            )
            if not inline:
                return text
            start = inline.end()
        else:
            start = match.end()

        next_section = re.search(
            r"\n\s*(?:dipl[ôo]mes?\s*(?:&\s*[ée]tudes)?"
            r"|formation[s]?\s*(?:acad[ée]mique[s]?)?"
            r"|[ée]ducation|education"
            r"|academic\s+background"
            r"|comp[ée]tences?\s*(?:techniques?|professionnelles?|cl[ée]s?)?"
            r"|skills?"
            r"|langues?\s*(?:parl[ée]es?)?|languages?"
            r"|ma[îi]trise\s+des\s+langues"
            r"|savoir[\s\-]faire|connaissances?|technologies?|stack\s+technique|outils?"
            r"|projets?\s*(?:personnels?|acad[ée]miques?)?"
            r"|certifications?\s*(?:professionnelles?)?"
            r"|publications?|loisirs?|passions?|hobbies?"
            r"|engagements?|activit[ée]s?"
            r"|divers|r[ée]f[ée]rences?"
            r"|profil|summary|objective"
            r"|ausbildung|formaci[oó]n"
            r"|образование"
            r")[^\n]*\n",
            text[start:],
            re.IGNORECASE,
        )
        if next_section:
            return text[start:start + next_section.start()]
        return text[start:]

    # ────────────────────────────────────────────────────────────
    # Block splitting
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _split_into_blocks(section: str) -> List[str]:
        if not section:
            return []
        # Em dash (U+2014) → séparateur de blocs pour CV compacts inline
        section = re.sub(r'\s+\u2014\s+', '\n', section)
        # Marqueurs visuels → newline ; | gardé (format "titre | société | dates")
        section = re.sub(r'[¦•●►]', '\n', section)
        lines = section.split('\n')
        blocks: List[str] = []
        current: List[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                if current:
                    blocks.append('\n'.join(current))
                    current = []
                continue
            has_date_range = bool(re.search(r'(?<!\()\b(19|20)\d{2}\s*[-\u2013\u2014]\s*(?:19|20)?\d{2}\b(?!\))', line))
            has_year = bool(re.search(r'\b(19|20)\d{2}\b', line))
            has_title = bool(re.search(r'\b(?:Stage|Stagiaire|DRH|Responsable|Charg[ée]e?|Assistant(?:e)?|Ing[ée]nieur|D[ée]veloppeur|Consultant|Manager|Directeur|Chef|Analyste|Coordinateur|Gestionnaire|Électricien|Electricien|Plombier|Ma[çc]on|Menuisier|Mécanicien|Mecanicien|Soudeur|Infirmi[èe]re?|Aide[\-\s]Soignant|Expert[\-\s]?Comptable|Comptable|Auditeur|Pharmacien|Médecin|Medecin|Community\s+Manager|Digital\s+Marketing|Social\s+Media)\b', line, re.I))
            is_new_experience = has_date_range or (has_year and has_title)
            if current and is_new_experience:
                blocks.append('\n'.join(current))
                current = [line]
                continue
            current.append(line)
        if current:
            blocks.append('\n'.join(current))
        return [b for b in blocks if len(b.strip()) > 10]

    # ────────────────────────────────────────────────────────────
    # Date parsing
    # ────────────────────────────────────────────────────────────

    def _parse_date_range(self, text: str) -> Dict:
        """Extrait dates début/fin d'un bloc.

        Returns:
            {
                "date_debut": "2020-01" | None,
                "date_fin":   "2022-12" | None,
                "en_cours":   bool,
                "duree_mois": int | None,
            }
        """
        result: Dict = {
            "date_debut": None, "date_fin": None,
            "en_cours": False, "duree_mois": None,
        }

        # 1. Plage explicite
        range_m = _DATE_RANGE.search(text)
        since_m = _SINCE_PATTERN.search(text)

        if range_m:
            sy, sm = _parse_date_token(range_m.group(1))
            end_tok = range_m.group(2)
            ongoing = _is_ongoing(end_tok)
            ey, em = (None, None) if ongoing else _parse_date_token(end_tok)
        elif since_m:
            sy, sm = _parse_date_token(since_m.group(1))
            ongoing = True
            ey, em = None, None
        else:
            # 1 bis. « Juillet - Août 2023 » (année partagée entre deux mois)
            shared_m = _DATE_RANGE_SHARED_YEAR.search(text)
            if shared_m:
                year = int(shared_m.group(3))
                m1 = MONTHS_MAP_NORMALIZED.get(_normalize_date_text(shared_m.group(1)), 1)
                m2 = MONTHS_MAP_NORMALIZED.get(_normalize_date_text(shared_m.group(2)), 1)
                result["date_debut"] = f"{year}-{str(m1).zfill(2)}"
                result["date_fin"] = f"{year}-{str(m2).zfill(2)}"
                result["en_cours"] = False
                result["duree_mois"] = _compute_duration_months(year, m1, year, m2)
                return result

            # 1 ter. « Juillet 2023 » (mois seul → stage d'un mois)
            single_m = _DATE_SINGLE_MONTH_YEAR.search(text)
            if single_m:
                year = int(single_m.group(2))
                m1 = MONTHS_MAP_NORMALIZED.get(_normalize_date_text(single_m.group(1)), 1)
                result["date_debut"] = f"{year}-{str(m1).zfill(2)}"
                result["date_fin"] = f"{year}-{str(m1).zfill(2)}"
                result["en_cours"] = False
                result["duree_mois"] = 1
                return result

            # Aucune date → pas une vraie expérience
            return result

        if sy is None:
            return result

        result["date_debut"] = f"{sy}-{str(sm or 1).zfill(2)}"
        result["en_cours"] = ongoing

        if ongoing:
            result["date_fin"] = None
        elif ey:
            result["date_fin"] = f"{ey}-{str(em or 1).zfill(2)}"

        result["duree_mois"] = _compute_duration_months(
            sy, sm or 1,
            ey if not ongoing else None,
            em if not ongoing else None,
        )

        return result

    # ────────────────────────────────────────────────────────────
    # Entreprise extraction (multi-passes)
    # ────────────────────────────────────────────────────────────

    def _extract_company(self, block: str) -> Optional[str]:
        """Extrait le nom de l'entreprise.

        Stratégie 3 passes :
        1. Séparateur explicite (« chez X », « at X », « @ X »)
        2. spaCy NER (ORG) sur les 2 premières lignes
        3. Heuristique : segment après tiret/pipe dans la 1ère ligne
        """
        first_line = block.split("\n")[0]
        # Tronquer la première ligne avant le début d'une phrase de mission
        # (mots capitalisés après une parenthèse fermante ou une ponctuation forte)
        first_line = re.sub(r'\)\s+[A-ZÀ-Ö].*$', ')', first_line).strip()

        # Passe 1 : séparateur explicite
        sep_m = _COMPANY_SEP.search(first_line)
        if sep_m:
            after = first_line[sep_m.end():].strip()
            company = re.split(r"\s*[\-–—|,;]\s*", after)[0].strip()
            company = self._clean_company(company)
            if company and len(company) >= 2:
                return company

        # Passe 1 bis : séparateurs forts de type "--", "|", en-dash (–), em-dash (—)
        # Priorité : si en-dash ou em-dash unique → nom de société très probable
        en_dash_parts = re.split(r"\s*[\u2013\u2014]\s*", first_line)  # – ou —
        if len(en_dash_parts) >= 2:
            for part in en_dash_parts[1:]:
                part = part.strip()
                # Couper sur virgule (ex: "Desinget, Agence de Voyage (...)")
                if ',' in part:
                    part = part.split(',')[0].strip()
                # Couper avant parenthèse de date
                part = re.sub(r'\s*\(.*$', '', part).strip()
                if len(part) > 40 or len(part.split()) > 5:
                    continue
                company = self._clean_company(part)
                if company and len(company) >= 2 and not _TITRE_PATTERN.search(company):
                    return company

        # Passe 1 ter : séparateurs forts de type "--" ou "|"
        strong_parts = re.split(r"\s*(?:\|+|[-]{2,})\s*", first_line)
        if len(strong_parts) >= 2:
            for part in strong_parts[1:]:
                part = part.strip()
                if len(part) > 40 or len(part.split()) > 5 or ',' in part:
                    continue
                company = self._clean_company(part)
                if company and len(company) >= 2:
                    if not _TITRE_PATTERN.search(company):
                        return company

        # Passe 2 : spaCy NER (ORG)
        if self._nlp:
            # Limiter à la première ligne uniquement pour éviter de capturer des missions
            header = block.split("\n")[0]
            doc = self._nlp(header)
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    name = self._clean_company(ent.text)
                    if not name or len(name) < 2:
                        continue
                    # Rejeter si commence par un article/préposition français
                    if re.match(r'^(?:une?|des?|le|la|les|du|pour|avec|de|au|en)\b', name, re.I):
                        continue
                    return name

        # Passe 3 : segment après tiret/pipe (unique en-dash ou regular dash)
        parts = re.split(r"\s*[\-–—|]\s*", first_line)
        if len(parts) >= 2:
            for part in parts[1:]:
                part = part.strip()
                # Si la partie contient une virgule → prendre avant la virgule (ex: "BeeCoders, Tunis")
                if ',' in part:
                    part = part.split(',')[0].strip()
                # Ignorer les parties avec parenthèse non fermée ou trop longues
                if '(' in part and ')' not in part:
                    part = re.sub(r'\([^)]*$', '', part).strip()
                candidate = self._clean_company(part)
                if candidate and len(candidate) >= 2:
                    # Exclure les dates et marqueurs « en cours »
                    if not re.fullmatch(r"\d{4}", candidate) and \
                       not _EN_COURS.search(candidate) and \
                       not _TITRE_PATTERN.search(candidate):
                        return candidate

        return None

    @staticmethod
    def _clean_company(name: str) -> str:
        """Nettoie un nom d'entreprise."""
        if not name:
            return ""
        # Retirer parenthèses secondaires
        name = re.sub(r"\([^)]*\)", "", name).strip()
        # Retirer dates (YYYY, MM/YYYY, YYYY-MM)
        name = re.sub(r"\b\d{4}\b", "", name).strip()
        name = re.sub(r"\b\d{1,2}[/\-\.]\d{4}\b", "", name).strip()
        name = re.sub(r"\b\d{4}[/\-\.]\d{1,2}\b", "", name).strip()
        # Retirer noms de mois isolés (souvent des résidus de dates)
        month_names = set(MONTHS_MAP.keys())
        words = name.split()
        cleaned = [
            w for w in words
            if w.lower() not in _COMPANY_STOP
            and w.lower().rstrip(".") not in month_names
        ]
        name = " ".join(cleaned).strip(" ,-;:")
        # Rejeter les résidus numériques purs
        if name and re.fullmatch(r"[\d\s/\-\.]+", name):
            return ""
        return name

    # ────────────────────────────────────────────────────────────
    # Poste
    # ────────────────────────────────────────────────────────────

    def _extract_job_title(self, block: str) -> Optional[str]:
        lines = block.split('\n')
        first_line = lines[0] if lines else ""
        # Isoler la partie titre avant séparateur d'entreprise ou année
        clean = re.split(r'\s*(?:--|@|\bchez\b|\bau\s+sein\s+de\b)', first_line, maxsplit=1, flags=re.I)[0]
        # Séparer sur | , double tiret, en-dash (–) ou em-dash (—) — séparateurs titre/société
        clean = re.split(r'\s*(?:\|+|[\u2013\u2014]|\-{2,})\s*', clean, maxsplit=1)[0]
        clean = re.sub(r'\s+\d{4}.*$', '', clean).strip()
        for pattern in re.finditer(
            r'\b(?:Stage|Stagiaire|DRH|Responsable|Charg[\u00e9e]e?|Assistant(?:e)?|Ing[\u00e9e]nieur|D[\u00e9e]veloppeur'
            r'|Consultant|Manager|Directeur|Chef|Analyste|Coordinateur|Gestionnaire)[^\n]{3,80}',
            clean, re.I,
        ):
            title = pattern.group(0).strip()
            if len(title) >= 3:
                return title.title()
        for sep_pat in [r'\bchez\b', r'\bat\b', '@', r'\bau\s+sein\s+de\b', r'\bpour\b']:
            m = re.search(sep_pat, first_line, re.I)
            if m:
                before = first_line[:m.start()].strip()
                before = re.sub(r'[-\u2013\u2014|].*$', '', before).strip()
                if before and len(before) >= 3:
                    return before.title()
        return None

    @staticmethod
    def _capitalize_title(title: str) -> str:
        """Capitalise intelligemment un titre de poste."""
        small = {"de", "du", "des", "d", "l", "le", "la", "les",
                 "en", "et", "à", "au", "aux",
                 "of", "in", "at", "and", "the", "for", "a", "an"}
        words = title.split()
        return " ".join(
            w.capitalize() if i == 0 or w.lower() not in small else w.lower()
            for i, w in enumerate(words)
        )

    # ────────────────────────────────────────────────────────────
    # Missions (bullet points)
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_missions(block: str) -> List[str]:
        """Extrait les missions / responsabilités (lignes à puces)."""
        missions: List[str] = []
        for line in block.split("\n"):
            stripped = line.strip()
            if stripped and stripped[0] in "-•–*→▪►●◆":
                mission = stripped.lstrip("-•–*→▪►●◆ ").strip()
                if mission and len(mission) >= 10:
                    missions.append(mission)
        return missions

    # ────────────────────────────────────────────────────────────
    # Localisation
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_location(block: str) -> Optional[str]:
        """Extrait la localisation (ville/pays/remote)."""
        header = "\n".join(block.split("\n")[:2])
        m = _LOCATION_PATTERN.search(header)
        return m.group(0).strip() if m else None

    # ────────────────────────────────────────────────────────────
    # Extraction d'un bloc complet
    # ────────────────────────────────────────────────────────────

    def _parse_block(self, block: str) -> Optional[Dict]:
        """Analyse un bloc pour en extraire UNE expérience.

        Condition de validité : au moins un titre OU une date.
        """
        job_title = self._extract_job_title(block)
        date_info = self._parse_date_range(block)
        company = self._extract_company(block)
        location = self._extract_location(block)
        missions = self._extract_missions(block)

        has_title = job_title is not None
        has_dates = date_info["date_debut"] is not None

        # Validation : exiger au minimum des dates pour une vraie expérience
        # (un titre seul sans dates est trop risqué — faux positifs)
        if not has_dates:
            return None

        return {
            "poste": job_title,
            "entreprise": company,
            "date_debut": date_info["date_debut"],
            "date_fin": date_info["date_fin"],
            "en_cours": date_info["en_cours"],
            "duree_mois": date_info["duree_mois"],
            "localisation": location,
            "missions": missions,
        }

    # ────────────────────────────────────────────────────────────
    # Point d'entrée public
    # ────────────────────────────────────────────────────────────

    def extract(self, text: str) -> Dict:
        """Extrait les expériences professionnelles depuis le texte du CV.

        Stratégie par blocs (qualité PFE) :
        1. Isoler la section « Expérience ».
        2. Découper en blocs individuels (1 par poste).
        3. Pour chaque bloc, extraire poste, entreprise, dates,
           durée, localisation, missions.

        Returns:
            {
                "experiences": [
                    {
                        "poste":        "Développeur Full Stack",
                        "entreprise":   "TechCorp",
                        "date_debut":   "2020-01",
                        "date_fin":     "2022-12",
                        "en_cours":     False,
                        "duree_mois":   36,
                        "localisation": "Paris",
                        "missions":     ["Développement API REST", ...]
                    },
                    ...
                ],
                "annees_experience_totales":  5.0,
                "total_experiences":          2
            }
        """
        if not text:
            return {
                "experiences": [],
                "annees_experience_totales": 0,
                "total_experiences": 0,
            }

        section = self._find_experience_section(text)
        blocks = self._split_into_blocks(section)

        experiences: List[Dict] = []
        for block in blocks:
            parsed = self._parse_block(block)
            if parsed:
                experiences.append(parsed)

        # Tri : plus récent en premier (en cours → max)
        def _sort_key(e: Dict) -> Tuple[int, int]:
            if e.get("en_cours"):
                return (9999, 12)
            raw = e.get("date_fin") or e.get("date_debut") or ""
            y, m = _parse_date_token(raw)
            return (y or 0, m or 0)

        experiences.sort(key=_sort_key, reverse=True)

        # Durée totale
        total_months = sum(
            e["duree_mois"] for e in experiences if e["duree_mois"]
        )

        return {
            "experiences": experiences,
            "annees_experience_totales": round(total_months / 12, 1) if total_months else 0,
            "total_experiences": len(experiences),
        }
