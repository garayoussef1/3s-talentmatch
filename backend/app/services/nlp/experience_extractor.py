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
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
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
        MONTHS_MAP_NORMALIZED[_normalize_date_text(_name)] = _i


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
    r"ing[ée]nieur\s+commercial",
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
    # Droit & Juridique
    r"avocat(?:e)?(?:\s+(?:associ[ée]e?|collaborateur|junior|senior|stagiaire))?",
    r"juriste(?:\s+(?:d[''']?entreprise|sp[ée]cialis[ée]e?|junior|senior))?",
    r"notaire(?:\s+associ[ée]e?)?",
    r"clerc\s+de\s+notaire",
    r"huissier\s+de\s+justice",
    r"greffier(?:\s+(?:en\s+chef|principal))?",
    r"magistrat",
    r"juge(?:\s+[\w\s]{3,25})?",
    r"conseiller\s+juridique",
    r"responsable\s+juridique",
    r"directeur\s+juridique",
    r"charg[ée]e?\s+d[''']?affaires\s+juridiques?",
    r"paralegal",
    # Architecture & BTP
    r"architecte(?:\s+(?:d\.?p\.?l\.?g\.?|urbaniste|int[ée]rieur|technique|chef\s+de\s+projet))?",
    r"ing[ée]nieu(?:r|re)(?:\s+(?:g[ée]nie\s+civil|structure|b[âa]timent|btp|travaux\s+publics|fluides?))?",
    r"conducteur(?:\s+de)?\s+travaux",
    r"chef\s+de\s+chantier",
    r"ma[îi]tre\s+d[''']?œuvre",
    r"ma[îi]tre\s+d[''']?ouvrage",
    r"responsable\s+(?:b[âa]timent|chantier|travaux)",
    r"technicien(?:\s+(?:b[âa]timent|bureau\s+d[''']?[ée]tudes?|dessinateur))?",
    r"dessinateur(?:\s+(?:projeteur|b[âa]timent|technique))?",
    r"urbaniste",
    r"g[ée]om[èe]tre(?:\s+expert)?",
    r"topographe",
    # Enseignement & Recherche
    r"professeur(?:\s+(?:certifi[ée]|agr[ée]g[ée]|de\s+[\w\s]{3,25}))?",
    r"enseignant(?:e)?(?:\s+(?:chercheur|vacataire|contractuel|titulaire))?",
    r"ma[îi]tre(?:\s+de)?\s+conf[ée]rences",
    r"charg[ée]e?\s+de\s+cours",
    r"formateur(?:\s+(?:professionnel|consultant))?",
    r"formatrice(?:\s+[\w\s]{3,20})?",
    r"tuteur(?:\s+p[ée]dagogique)?",
    r"chercheur(?:\s+(?:senior|associ[ée]|postdoctoral|doctorant))?",
    r"chercheuse(?:\s+[\w\s]{3,20})?",
    r"doctorant(?:e)?",
    r"postdoctorant(?:e)?",
    r"ing[ée]nieu(?:r|re)\s+de\s+recherche",
    r"directeur(?:\s+de)?\s+recherche",
    r"responsable\s+p[ée]dagogique",
    # Logistique & Supply Chain
    r"responsable\s+(?:logistique|supply\s+chain|achats?|approvisionnement|entrepôt|stocks?)",
    r"directeur\s+(?:logistique|supply\s+chain|achats?)",
    r"charg[ée]e?\s+(?:d[''']?approvisionnement|d[''']?achats?|de\s+logistique)",
    r"gestionnaire\s+(?:stocks?|entrepôt|approvisionnement)",
    r"coordinateur\s+logistique",
    r"planificateur(?:\s+de\s+production)?",
    r"acheteur(?:\s+(?:junior|senior|international))?",
    r"supply\s+chain\s+(?:manager|analyst|specialist)",
    r"responsable\s+transport",
    # Agroalimentaire & Qualité
    r"responsable\s+(?:qualit[ée]|qhse|hse|haccp|production\s+agro)",
    r"charg[ée]e?\s+de\s+qualit[ée]",
    r"contr[ôo]leur(?:\s+de)?\s+qualit[ée]",
    r"auditeur(?:\s+(?:qualit[ée]|interne|externe|fournisseur))?",
    r"technicien(?:\s+(?:qualit[ée]|agro|laboratoire|analyse))?",
    r"ing[ée]nieu(?:r|re)\s+(?:qualit[ée]|process|r[\&et]\s*d|agroalimentaire)",
    r"directeur\s+(?:qualit[ée]|production|usine|site)",
    # Médical / Santé étendu
    r"m[ée]decin(?:\s+(?:g[ée]n[ée]raliste|sp[ée]cialiste|r[ée]animateur|urgentiste|r[ée]sident))?",
    r"chirurgien(?:\s+(?:[\w\s]{3,20}))?",
    r"kinesith[ée]rapeute",
    r"kin[ée]sith[ée]rapeute",
    r"radiologue",
    r"anesthesiste",
    r"anesth[ée]siste",
    r"pr[ée]parateur\s+en\s+pharmacie",
    r"laborantin(?:e)?",
    r"technicien(?:\s+de)?\s+laboratoire",
    r"cadre\s+de\s+sant[ée]",
    r"directeur\s+(?:m[ée]dical|de\s+soins|d[''']?[ée]tablissement\s+de\s+sant[ée])",
]

_TITRES_FR = [
    # Informatique & Tech
    r"d[ée]veloppeu(?:r|se)(?:\s+(?:web|mobile|full[\s\-]?stack|front[\s\-]?end|back[\s\-]?end|logiciel|java|python|\.net|php|c\+\+))?",
    r"ing[ée]nieu(?:r|re)(?:\s+(?:logiciel|d[ée]veloppement|syst[eèé]mes?|r[ée]seaux?|devops|cloud|data|ia|s[ée]curit[ée]|test|qualit[ée]|informatique|[ée]tudes?))?",
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
    r"stage(?:\s+[^\n,;]{3,30})?",
    r"stagiaire(?:\s+[^\n,;]{3,30})?",
    r"alternant(?:e)?(?:\s+[\w\s]{3,30})?",
    r"apprenti(?:e)?(?:\s+[\w\s]{3,20})?",
    # Assistant(e) générique
    r"assistant(?:e)?(?:\s+[\w\s]{2,25})?",
    # Business / Gestion
    r"chef\s+d[''']?[ée]quipe",
    r"manager(?:\s+[\w\s]{3,20})?",
    r"coordinateur(?:\s+[\w\s]{3,20})?",
    r"charg[ée](?:\s+d[eé]\s+[\w\s]{3,30})?",
    r"commercial(?:e)?(?:\s+(?:junior|senior|it|b2b|b2c|btob|btoc))?",
    r"technico\s*[-\s]?commercial(?:e)?",
    r"business\s+developer",
    r"account\s+manager",
    r"drh",
]

_TITRES_EN = [
    r"(?:senior|junior|lead|principal|staff)\s+(?:software\s+|data\s+)?(?:engineer|developer|analyst|scientist)",
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
    r"(?:intern|trainee|apprentice|internship|fellowship)(?:\s+(?!(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|f[ée]v|mars|avr|mai|juin|juil|ao[ûu]|sept|d[ée]c)\b)[\w\s]{3,20})?",
    r"(?:research|teaching)\s+(?:assistant|associate)",
    r"professor(?:\s+[\w\s]{3,20})?",
    r"freelanc(?:e|er)",
    r"engineering\s+manager",
    r"staff\s+(?:engineer|developer|software\s+engineer)",
    r"principal\s+(?:engineer|developer|architect|software\s+engineer)",
    r"distinguished\s+engineer",
    r"(?:vp|vice\s+president)\s+(?:of\s+)?(?:engineering|technology|product)",
    r"head\s+of\s+(?:engineering|technology|product|data|platform)",
    r"director\s+of\s+(?:engineering|technology|product|data)",
    r"(?:co[\-\s]?)?founder",
    r"(?:technical|tech)\s+co[\-\s]?founder",
    r"cto|ceo|coo|cpo|cdo",
    r"software\s+architect",
    r"cloud\s+architect",
    r"solutions?\s+architect",
    r"platform\s+engineer",
    r"site\s+reliability\s+engineer",
    r"sre",
    r"contract(?:or)?(?:\s+(?:developer|engineer|consultant))?",
    r"consultant(?:\s+[\w\s]{3,20})?",
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

# Tokens techniques fréquents qui ne doivent jamais être considérés comme une entreprise
# (souvent présents dans la section compétences, ou juste sous un titre de poste).
_COMPANY_TECH_BLACKLIST = {
    "java", "python", "javascript", "typescript", "php", "html", "css",
    "react", "angular", "node", "node.js", "nodejs", "spring", "spring boot",
    "docker", "kubernetes", "aws", ".net", "dotnet",
    "mysql", "mongodb", "sqlite", "postgresql", "redis", "oracle",
    "symfony", "laravel", "django", "flask", "fastapi",
    "jenkins", "gitlab", "github", "jira", "confluence", "sonarqube",
    "ansible", "terraform", "grafana", "kibana",
    "c", "c++", "git", "linux", "ubuntu",
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

    # Fichier persistant pour postes et entreprises découverts
    _DISCOVERED_FILE = (
        Path(__file__).resolve().parents[4] / "data" / "experiences_discovered.json"
    )

    def __init__(self, nlp_model=None):
        """Initialise l'extracteur.

        Args:
            nlp_model: Modèle spaCy chargé (optionnel).
        """
        self._nlp = nlp_model
        self._discovered = self._load_discovered()

    def _load_discovered(self) -> Dict:
        """Charge le dictionnaire persistant postes/entreprises."""
        try:
            if self._DISCOVERED_FILE.exists():
                data = json.loads(self._DISCOVERED_FILE.read_text(encoding="utf-8"))
                # Structure : {"postes": {"dev full stack": 3}, "entreprises": {"techcorp": 2}}
                if isinstance(data, dict):
                    data.setdefault("postes", {})
                    data.setdefault("entreprises", {})
                    return data
        except Exception as e:
            logger.warning("[ExpDict] Chargement échoué : %s", e)
        return {"postes": {}, "entreprises": {}}

    def _save_discovered(self, experiences: List[Dict]) -> None:
        """Sauvegarde les postes et entreprises extraits dans le dict persistant."""
        if not experiences:
            return
        try:
            for exp in experiences:
                poste = (exp.get("poste") or "").strip().lower()
                entreprise = (exp.get("entreprise") or "").strip().lower()
                if poste and len(poste) >= 4:
                    self._discovered["postes"][poste] = (
                        self._discovered["postes"].get(poste, 0) + 1
                    )
                if (entreprise and len(entreprise) >= 3
                        and entreprise not in _COMPANY_STOP
                        and entreprise not in _COMPANY_TECH_BLACKLIST):
                    self._discovered["entreprises"][entreprise] = (
                        self._discovered["entreprises"].get(entreprise, 0) + 1
                    )
            self._DISCOVERED_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._DISCOVERED_FILE.write_text(
                json.dumps(self._discovered, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug(
                "[ExpDict] Dict mis à jour : %d postes, %d entreprises",
                len(self._discovered["postes"]),
                len(self._discovered["entreprises"]),
            )
        except Exception as e:
            logger.warning("[ExpDict] Sauvegarde échouée : %s", e)

    def is_known_poste(self, text: str) -> bool:
        """Retourne True si ce texte est un titre de poste connu."""
        return text.strip().lower() in self._discovered["postes"]

    def is_known_entreprise(self, text: str) -> bool:
        """Retourne True si cette entreprise a déjà été vue."""
        return text.strip().lower() in self._discovered["entreprises"]

    # ────────────────────────────────────────────────────────────
    # Section isolation
    # ────────────────────────────────────────────────────────────

    def _find_experience_section_and_flag(self, text: str) -> Tuple[str, bool]:
        """Isole la section Expérience du CV et indique si elle a été détectée.

        Returns:
            (section_text, section_detected)

        Notes:
            - Si aucune section Expérience n'est trouvée, retourne le texte complet
              et section_detected=False (important pour éviter les faux positifs).
        """
        header_re = re.compile(
            r"^(?:contact|profil|exp[ée]riences?\s+professionnelles?|exp[ée]riences?"
            r"|langues?|languages?|comp[ée]tences?|skills?|certifications?"
            r"|formations?|[ée]ducation|education|projets?|projects?)\b",
            re.IGNORECASE,
        )

        def _next_nonempty_lines(start_idx: int, *, max_chars: int = 350, max_lines: int = 3) -> List[str]:
            snippet = text[start_idx:start_idx + max_chars]
            lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
            return lines[:max_lines]

        def _looks_like_header_chain(start_idx: int) -> bool:
            """Détecte le cas TOC : après un header, on voit immédiatement un autre header."""
            lines = _next_nonempty_lines(start_idx)
            return bool(lines and header_re.match(lines[0]))

        def _looks_like_toc(snippet: str) -> bool:
            """Détecte un "sommaire" en haut de CV (liste de sections uniquement).

            Ex: CONTACT / PROFIL / EXPÉRIENCES / LANGUES / COMPÉTENCES / ...
            """
            if not snippet:
                return False
            lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
            lines = lines[:12]
            if len(lines) < 4:
                return False
            headers = sum(1 for ln in lines if header_re.match(ln))
            non_headers = len(lines) - headers
            return headers >= 3 and non_headers <= 1

        def _slice_section(start_idx: int) -> str:
            next_section_re = re.compile(
                r"\n\s*(?:dipl[ôo]mes?\s*(?:&\s*[ée]tudes)?"
                r"|formation[s]?\s*(?:acad[ée]mique[s]?)?"
                r"|[ée]ducation|education"
                r"|academic\s+(?:background|projects?)"
                r"|comp[ée]tences?\s*(?:techniques?|professionnelles?|cl[ée]s?)?"
                r"|skills?\b(?!\s*:)"
                r"|langues?\s*(?:parl[ée]es?)?|languages?\b(?!\s*:)"
                r"|ma[îi]trise\s+des\s+langues"
                r"|savoir[\s\-]faire|connaissances?|technologies?\b(?!\s*:)|stack\s+technique|outils?"
                r"|projets?\s*(?:personnels?|acad[ée]miques?)?"
                r"|certifications?\s*(?:professionnelles?)?"
                r"|publications?|loisirs?|passions?|hobbies?"
                r"|engagements?|activit[ée]s?"
                r"|divers|r[ée]f[ée]rences?"
                r"|profil|summary|objective|qualifications?"
                r"|ausbildung|formaci[oó]n"
                r"|образование"
                r")[^\n]*\n",
                re.IGNORECASE,
            )

            tail = text[start_idx:]
            if not tail:
                return ""

            # Sur PDFs en colonnes, des headers d'autres sections (LANGUE MATERNELLE, COMPÉTENCES...)
            # peuvent s'intercaler après "EXPÉRIENCES". On coupe seulement quand:
            # - on a vu au moins un indice clair d'expérience (titre/date) dans le contenu,
            # - et il n'y a pas de titre de poste plus loin (sinon on risque de perdre des expériences
            #   qui continuent dans une autre colonne).
            for m2 in next_section_re.finditer(tail):
                candidate = tail[:m2.start()]
                has_anchor = (
                    bool(_TITRE_PATTERN.search(candidate))
                    or bool(_DATE_RANGE.search(candidate))
                    or bool(_SINCE_PATTERN.search(candidate))
                    or bool(re.search(r"\b(?:19|20)\d{2}\b", candidate))
                )
                if not has_anchor:
                    continue
                # Éviter les coupes trop agressives si le contenu est encore très court
                if len(candidate.strip()) < 80:
                    continue

                boundary_line = (m2.group(0) or "").lower()
                boundary_is_side_column = any(
                    kw in boundary_line
                    for kw in ["langue", "langues", "languages", "compétence", "competence", "skills"]
                )
                if boundary_is_side_column:
                    lookahead = tail[m2.end(): m2.end() + 1200]
                    if _TITRE_PATTERN.search(lookahead):
                        # Il y a encore un poste plus loin → ne pas couper ici
                        continue
                return candidate

            return tail

        # 1) Chercher toutes les occurrences et ignorer celles qui ressemblent à un sommaire
        for m in EXPERIENCE_SECTION_KW.finditer(text):
            start = m.end()
            section = _slice_section(start)
            # Cas TOC classique : "EXPÉRIENCES" suivi immédiatement de "LANGUES/COMPÉTENCES/..."
            # → la section isolée est quasi vide.
            if len(section.strip()) < 200 and _looks_like_header_chain(start):
                continue
            # Si l'occurrence est dans un sommaire, la "section" est souvent quasi vide
            if _looks_like_toc(text[m.start(): m.start() + 500]) and len(section.strip()) < 200:
                continue
            return section, True

        # 2) Fallback : en-tête inline (ex: "PARCOURS DRH Adjointe...")
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
                return text, False
            start = inline.end()
            section_detected = True
        else:
            start = match.end()
            section_detected = True

        section = _slice_section(start)
        if section_detected and len(section.strip()) < 200 and _looks_like_header_chain(start):
            # Header d'expérience pris depuis un sommaire → analyser sur texte complet
            return text, False
        if section_detected and _looks_like_toc(text[max(0, start - 120): start + 500]) and len(section.strip()) < 200:
            # Sommaire détecté : ne pas isoler de section vide → analyser sur texte complet
            return text, False
        return section, section_detected

    def _find_experience_section(self, text: str) -> str:
        """Isole la section Expérience du CV."""
        section, _detected = self._find_experience_section_and_flag(text)
        return section

    # ────────────────────────────────────────────────────────────
    # Block splitting
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _split_into_blocks(section: str) -> List[str]:
        if not section:
            return []
        # Em dash (U+2014) → séparateur de blocs pour CV compacts inline
        section = re.sub(r'\s+\u2014\s+', '\n', section)
        # Marqueurs visuels → newline (absorber whitespace autour pour éviter \n\n)
        section = re.sub(r'\s*[¦•●►]\s*', '\n', section)
        # Cercles et puces spéciales → newline (○ utilisé par certains PDFs)
        section = re.sub(r'\s*[○◯◦▸▹‣⁃∙]\s*', '\n', section)
        # Recoller saison + année séparés par un saut de ligne
        # "Summer\n2016" → "Summer 2016", "Été\n2022" → "Été 2022"
        section = re.sub(
            r'\b(Summer|Winter|Spring|Fall|Autumn|[ÉE]t[ée]|Printemps|Automne|Hiver)\s*\n\s*(\d{4})\b',
            r'\1 \2',
            section,
            flags=re.IGNORECASE,
        )

        lines = section.split('\n')
        blocks: List[str] = []
        current: List[str] = []
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                if current:
                    blocks.append('\n'.join(current))
                    current = []
                continue
            has_date_range = bool(re.search(r'(?<!\()\b(19|20)\d{2}\s*[-\u2013\u2014]\s*(?:19|20)?\d{2}\b(?!\))', line))
            has_ongoing_range = bool(re.search(
                r'\b(19|20)\d{2}\s*[-\u2013\u2014]\s*(?:present|pr[\u00e9e]sent|actuel|en\s+cours)\b',
                line, re.I))
            has_year = bool(re.search(r'\b(19|20)\d{2}\b', line))
            has_title = bool(re.search(
                r'\b(?:Stage|Stagiaire|DRH|Responsable|Charg[éè]e?|Assistant(?:e)?|Ing[ée]nieur'
                r'|D[ée]veloppeu(?:r|se)|Consultant|Manager|Directeur|Chef|Analyste'
                r'|Coordinateur|Gestionnaire|Électricien|Electricien|Plombier|Ma[çc]on'
                r'|Menuisier|Mécanicien|Mecanicien|Soudeur|Infirmi[èe]re?|Aide[\-\s]Soignant'
                r'|Expert[\-\s]?Comptable|Comptable|Auditeur|Pharmacien|Médecin|Medecin'
                r'|Community\s+Manager|Digital\s+Marketing|Social\s+Media'
                # EN titles for block splitting
                r'|(?:Senior|Junior|Lead|Staff)\s+(?:Software\s+|Data\s+)?(?:Engineer|Developer|Analyst|Scientist)'
                r'|Software\s+(?:Engineer|Developer|Architect)'
                r'|(?:Front[\s\-]?end|Back[\s\-]?end|Full[\s\-]?Stack)\s+(?:Developer|Engineer)'
                r'|Data\s+(?:Scientist|Analyst|Engineer)'
                r'|Project\s+Manager|Product\s+Manager|Program\s+Manager'
                r'|(?:QA|Test)\s+(?:Engineer|Analyst)'
                r'|(?:DevOps|SRE)\s+Engineer'
                r'|Intern(?:\s+[\-\u2013])?|Trainee|Apprentice|Freelanc(?:e|er))\b',
                line, re.I))
            has_company_sep = bool(_COMPANY_SEP.search(line))
            has_season = bool(re.search(
                r'\b(?:Summer|Winter|Spring|Fall|Autumn|[\u00c9E]t[\u00e9e])\s+\d{4}\b',
                line, re.I))
            # Look-ahead : ligne titre suivie d'une ligne avec date → nouveau poste
            next_has_date = False
            next_has_title = False
            next_looks_like_company = False
            if idx + 1 < len(lines):
                nxt = lines[idx + 1].strip()
                next_has_date = bool(re.search(r'\b(?:19|20)\d{2}\b', nxt))
                next_has_title = bool(re.search(
                    r'\b(?:Stage|Stagiaire|DRH|Responsable|Charg[éè]e?|Assistant(?:e)?|Ing[ée]nieur'
                    r'|D[ée]veloppeu(?:r|se)|Consultant|Manager|Directeur|Chef|Analyste'
                    r'|Coordinateur|Gestionnaire|Électricien|Electricien|Plombier|Ma[çc]on'
                    r'|Menuisier|Mécanicien|Mecanicien|Soudeur|Infirmi[èe]re?|Aide[\-\s]Soignant'
                    r'|Expert[\-\s]?Comptable|Comptable|Auditeur|Pharmacien|Médecin|Medecin'
                    r'|Community\s+Manager|Digital\s+Marketing|Social\s+Media'
                    r'|(?:Senior|Junior|Lead|Staff)\s+(?:Software\s+|Data\s+)?(?:Engineer|Developer|Analyst|Scientist)'
                    r'|Software\s+(?:Engineer|Developer|Architect)'
                    r'|(?:Front[\s\-]?end|Back[\s\-]?end|Full[\s\-]?Stack)\s+(?:Developer|Engineer)'
                    r'|Data\s+(?:Scientist|Analyst|Engineer)'
                    r'|Project\s+Manager|Product\s+Manager|Program\s+Manager'
                    r'|(?:QA|Test)\s+(?:Engineer|Analyst)'
                    r'|(?:DevOps|SRE)\s+Engineer'
                    r'|Intern(?:\s+[\-\u2013])?|Trainee|Apprentice|Freelanc(?:e|er))\b',
                    nxt, re.I))
                # Lignes "Entreprise" fréquentes : puce/tiret + Nom, ou "Nom, Ville"
                next_looks_like_company = bool(re.match(
                    r'^(?:[\-•\u2013\u2014→▪►●◆○◯◦▸▹‣⁃∙]\s*)+[A-ZÀ-Ö][^\n]{1,80}$',
                    nxt,
                )) or (
                    bool(re.match(r'^[A-ZÀ-Ö][^\n]{1,60}(?:\s*[\(,])', nxt))
                    and not next_has_date
                    and not next_has_title
                )

            # On démarre un nouveau bloc principalement sur des lignes "header" (titre ou date
            # qui annonce un nouveau poste). Une simple ligne de date qui suit un titre doit
            # rester dans le même bloc.
            is_title_header = (
                has_title and (
                    has_company_sep
                    or next_has_date
                    or next_looks_like_company
                    or (has_year and len(line) < 80)
                    or has_season
                )
            )
            is_date_header = (has_date_range or has_ongoing_range or has_season) and next_has_title
            is_new_experience = is_title_header or is_date_header
            if current and is_new_experience:
                blocks.append('\n'.join(current))
                current = [line]
                continue
            current.append(line)
        if current:
            blocks.append('\n'.join(current))

        # ── Post-traitement : fusionner les blocs « date seule » avec le suivant ──
        merged: List[str] = []
        i = 0
        while i < len(blocks):
            block = blocks[i]
            # Bloc très court sans titre → probablement juste une date
            if (i + 1 < len(blocks)
                    and len(block.strip()) < 60
                    and not _TITRE_PATTERN.search(block)
                    and re.search(r'\b(19|20)\d{2}\b', block)):
                merged.append(block + '\n' + blocks[i + 1])
                i += 2
                continue
            merged.append(block)
            i += 1

        return [b for b in merged if len(b.strip()) > 10]

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

            # 1 quater. « Summer 2016 » / « Été 2023 » (saison + année)
            _SEASON_MAP = {
                'summer': 6, 'été': 6, 'ete': 6,
                'spring': 3, 'printemps': 3,
                'fall': 9, 'autumn': 9, 'automne': 9,
                'winter': 12, 'hiver': 12,
            }
            season_m = re.search(
                r'\b(Summer|Winter|Spring|Fall|Autumn|[\u00c9E]t[ée]|Printemps|Automne|Hiver)\s+(\d{4})\b',
                text, re.I,
            )
            if season_m:
                s_word = season_m.group(1).lower()
                s_word = _normalize_date_text(s_word)
                s_month = _SEASON_MAP.get(s_word, 6)
                s_year = int(season_m.group(2))
                if 1950 <= s_year <= date.today().year + 2:
                    result["date_debut"] = f"{s_year}-{str(s_month).zfill(2)}"
                    e_month = min(s_month + 2, 12)
                    result["date_fin"] = f"{s_year}-{str(e_month).zfill(2)}"
                    result["en_cours"] = False
                    result["duree_mois"] = 3
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

        # Si on n'a pas réussi à parser une date de fin et que ce n'est pas "en cours",
        # la durée est inconnue (ne pas extrapoler jusqu'à aujourd'hui).
        if not ongoing and ey is None:
            result["duree_mois"] = None
            return result

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

        # Mots de description technique (jamais un nom d'entreprise)
        _desc_words = re.compile(
            r'\b(?:development|engineering|backend|frontend|full.?stack|web|mobile|'
            r'design|support|research|analysis|management|operations|testing|'
            r'd[eé]veloppement|d[eé]ploiement|conception|gestion|maintenance|'
            r'infrastructure|architecture|integration|migration|analytics)\b',
            re.IGNORECASE,
        )

        # Lignes qui décrivent une mission/résultat, pas une entreprise
        _action_line_start = re.compile(
            r'^(?:'
            r'contributed\s+to|worked\s+on|participated\s+in|involved\s+in|'
            r'assisted\s+in|helped\s+to|collaborated\s+with|'
            r'developed\b|implemented\b|designed\b|built\b|created\b|'
            r'led\b|managed\b|'
            r'contribution\s+[àa]|participation\s+[àa]|r[ée]alis[ée]e?\s+(?:un|une|des|le|la)?|mise\s+en\s+place'
            r')\b',
            re.IGNORECASE,
        )

        # Passe 0 : entreprise déjà connue dans le dict auto-appris
        for line in block.split("\n")[:4]:
            for token in re.split(r"[|,;]", line):
                candidate = self._clean_company(token.strip())
                if candidate and self.is_known_entreprise(candidate):
                    return candidate

        # Passe 1 : séparateur explicite (chez/at/@)
        sep_m = _COMPANY_SEP.search(first_line)
        if sep_m:
            after = first_line[sep_m.end():].strip()
            company = re.split(r"\s*[\-–—|│┃¦,;]\s*", after)[0].strip()
            company = self._clean_company(company)
            if company and len(company) >= 2:
                return company

        # Passe 1-dash : "Title — Something" où Something pourrait être description
        # Ex: "Software Engineer Intern — Backend Development"
        # On vérifie si ce qui suit le dash est un nom d'entreprise réel ou une description.
        # Si c'est une description (contient des mots génériques tech/métier), on l'ignore
        # et on cherche la company sur la ligne suivante.
        _DASH_SEP = re.compile(r"\s+[\u2013\u2014\u2212\-]\s+", re.UNICODE)
        dash_m = _DASH_SEP.search(first_line)
        if dash_m:
            after_dash = first_line[dash_m.end():].strip()
            # Nettoyage de la partie titre (avant le dash) — pour voir si c'est un poste connu
            # Si "after_dash" ressemble à une description (mots en minuscule, termes métier...)
            _desc_indicators = _desc_words
            # C'est une description si : contient un mot-clé description ET pas de virgule/parenthèse
            # caractéristique d'une vraie entreprise
            is_desc = (
                bool(_desc_indicators.search(after_dash))
                and "," not in after_dash
                and "(" not in after_dash
                and len(after_dash.split()) <= 4
            )
            if not is_desc:
                # Ressemble à un vrai nom d'entreprise
                company = self._clean_company(re.split(r"\s*[|│┃¦,;]\s*", after_dash)[0].strip())
                if (company and len(company) >= 2
                        and company.lower() not in _COMPANY_TECH_BLACKLIST
                        and not _TITRE_PATTERN.search(company)):
                    return company
            # Si c'est une description, on continue vers les passes suivantes

        # On garde plus de lignes car les CV en colonnes peuvent intercaler du bruit
        # (langues/compétences) avant la ligne d'entreprise.
        header_lines = block.split("\n")[:12]

        _SECTION_NOISE = re.compile(
            r"^(?:contact|profil|formations?|[ée]ducation|education|langues?|languages?|comp[ée]tences?|skills?|projets?|projects?|certifications?)\b",
            re.IGNORECASE,
        )

        # Passe 1 bis-c : lignes 2-5 après un titre (format EN sans séparateur)
        # Ex: "Software Engineer Intern — Backend Development\nJul–Sep 2025\nSociété (S.I.C.)\n•"
        # Ex: "Intern – Mobile App Development\nAbrarOne\n•bullets"
        block_lines_all = block.split("\n")
        # Pattern pour toutes formes de dates (mois-année, année-année, etc.)
        _date_any = re.compile(
            r'\b(?:19|20)\d{2}\b',  # contient une année
            re.IGNORECASE,
        )
        for _candidate_line in block_lines_all[1:7]:
            line2 = _candidate_line.strip()
            if not line2:
                continue
            if _action_line_start.match(line2):
                continue
            if line2[0] in '-•–—*→▪►●◆○':
                continue  # bullet → description
            if re.match(r'^[\d\s\-\u2013\u2014/,\.]+$', line2):
                continue  # ligne de chiffres/dates pures
            if _date_any.search(line2):
                continue  # contient une année → date range
            if not line2[0].isupper():
                continue  # commence en minuscule → description
            if len(line2) > 60:
                continue  # trop long pour un nom d'entreprise
            if re.match(r'^(?:contact|profil|formations?|[ée]ducation|comp[ée]tences?|skills?|langues?)\b', line2, re.I):
                continue  # section header
            # Rejeter si c'est une description technique (Backend Development, Mobile App Design...)
            if _desc_words.search(line2) and len(line2.split()) <= 5:
                continue
            if _TITRE_PATTERN.search(line2) and len(line2.split()) <= 5:
                continue  # titre de poste
            # Candidat valide
            cand = self._clean_company(re.split(r"\s*[\(,]\s*", line2)[0].strip())
            if (cand and len(cand) >= 2
                    and cand.lower() not in _COMPANY_TECH_BLACKLIST
                    and not _TITRE_PATTERN.search(cand)
                    and not _desc_words.search(cand)):
                return cand

        # Passe 1 bis : format « YYYY Entreprise, Ville » (EN CVs)
        # Ex: "June – August 2025 Feki Développement Startup, Tunisia"
        # Priorité haute car sans ambiguïté (année + nom capitalisé + délimiteur)
        for hdr_line in header_lines:
            m = re.search(
                r'\b(?:19|20)\d{2}\s+([A-ZÀ-Ö][\w\s\-&\u00e0-\u00ff]{2,40})(?:\s*[\(,]|\s*$)',
                hdr_line,
            )
            if m:
                candidate = self._clean_company(m.group(1).strip())
                if (candidate and len(candidate) >= 2
                        and not _TITRE_PATTERN.search(candidate)
                        and not _EN_COURS.search(candidate)):
                    return candidate
        # Variante cross-line : année en fin de ligne, entreprise sur la suivante
        header_text = "\n".join(header_lines)
        m_cross = re.search(
            r'\b(?:19|20)\d{2}[ \t]*\n[ \t]*([A-ZÀ-Ö][\w \t\-&\u00e0-\u00ff]{2,40})(?:[ \t]*[\(,]|[ \t]*$)',
            header_text,
        )
        if m_cross:
            candidate = self._clean_company(m_cross.group(1).strip())
            if (candidate and len(candidate) >= 2
                    and not _TITRE_PATTERN.search(candidate)
                    and not _EN_COURS.search(candidate)):
                return candidate

        _LANG_NOISE = re.compile(
            r"^(?:arabe|fran[çc]ais|anglais|allemand|espagnol|italien|courant|interm[ée]diaire|d[eé]butant|langue\s+maternelle)\b",
            re.IGNORECASE,
        )

        # Passe 1 bis-b : ligne dédiée « Entreprise, Ville » / « Entreprise (Info) » (lignes 2–N)
        for hdr_line in header_lines[1:]:
            hdr_line = hdr_line.strip()
            # Les lignes commençant par un bullet/tiret sont des missions → ignorer
            if hdr_line and hdr_line[0] in '-•–—*→▪►●◆○◯◦':
                continue
            if not hdr_line or len(hdr_line) < 3:
                continue
            if _SECTION_NOISE.match(hdr_line):
                continue
            # Ignorer les lignes de langue / niveau (artefacts de colonnes)
            if _LANG_NOISE.match(hdr_line):
                continue
            # Ignorer les lignes qui ressemblent à un intitulé (ex: "Stage Développement Web")
            # sans séparateur entreprise (évite entreprise="Développement Web").
            if re.match(r"^(?:stage|stagiaire|alternant|apprenti)\b", hdr_line, re.I) and not _COMPANY_SEP.search(hdr_line):
                if ',' not in hdr_line and '(' not in hdr_line:
                    continue
            # Ignorer ligne de date pure
            if re.match(r'^[\d\s\-\u2013\u2014/,\.]+(?:present|pr[\u00e9e]sent|actuel|en\s+cours)?$', hdr_line, re.I):
                continue
            # Ignorer ligne commençant en minuscule (description)
            if hdr_line[0].islower():
                continue
            # Ignorer ligne de date avec mois ("Juin – Août 2025", "February – May 2024")
            if re.match(r'^[A-ZÀ-Öa-zà-ö]+\s*[\-–—]\s*[A-ZÀ-Öa-zà-ö]*\s*\d{4}', hdr_line):
                continue
            # 1) Avec virgule/parenthèse
            m_cl = re.match(r'([A-ZÀ-Ö][\w\s\-&\u00e0-\u00ff\']{1,40})(?:\s*[\(,])', hdr_line)
            if m_cl:
                candidate = self._clean_company(m_cl.group(1).strip())
                if candidate and candidate.lower() in _COMPANY_TECH_BLACKLIST:
                    continue
                if (candidate and len(candidate) >= 2
                        and not _TITRE_PATTERN.search(candidate)
                        and not _EN_COURS.search(candidate)
                        and not re.match(r'\d', candidate)):
                    return candidate
            # 2a) Mot unique capitalisé ou CamelCase (ex: AbrarOne, SilkDev, CGI)
            words_cl = [w for w in hdr_line.split() if w]
            if (len(words_cl) == 1
                    and len(hdr_line) >= 3
                    and len(hdr_line) <= 40
                    and hdr_line[0].isupper()):
                candidate = self._clean_company(hdr_line)
                if (candidate
                        and candidate.lower() not in _COMPANY_TECH_BLACKLIST
                        and not _TITRE_PATTERN.search(candidate)
                        and not re.match(r'^\d', candidate)):
                    return candidate

            # 2b) Sans virgule : ligne courte de type nom propre (Company Name)
            #    Toutes les lettres initiales majuscules, ≥2 mots, ≤4 mots, pas de titre
            if (2 <= len(words_cl) <= 4
                    and len(hdr_line) <= 50
                    and all(w[0].isupper() for w in words_cl)):
                candidate = self._clean_company(hdr_line)
                if candidate and candidate.lower() in _COMPANY_TECH_BLACKLIST:
                    continue
                if (candidate and len(candidate) >= 2
                        and len(candidate.split()) >= 2
                        and not _TITRE_PATTERN.search(candidate)
                        and not _EN_COURS.search(candidate)
                        and not re.match(r'[\d\-\u2013\u2014]', candidate)):
                    return candidate

        # Passe 1 ter : séparateurs forts de type en-dash (–), em-dash (—)
        en_dash_parts = re.split(r"\s*[\u2013\u2014]\s*", first_line)  # – ou —
        if len(en_dash_parts) >= 2:
            for part in en_dash_parts[1:]:
                part = part.strip()
                if _action_line_start.match(part):
                    continue
                if _desc_words.search(part) and len(part.split()) <= 5:
                    continue
                # Couper sur virgule (ex: "Desinget, Agence de Voyage (...)")
                if ',' in part:
                    part = part.split(',')[0].strip()
                # Couper avant parenthèse de date
                part = re.sub(r'\s*\(.*$', '', part).strip()
                if len(part) > 40 or len(part.split()) > 5:
                    continue
                company = self._clean_company(part)
                if (company and len(company) >= 2
                        and not _TITRE_PATTERN.search(company)
                        and not _EN_COURS.search(company)):
                    return company

        # Passe 1 quater : séparateurs forts de type "--" ou "|"
        strong_parts = re.split(r"\s*(?:\|+|[-]{2,})\s*", first_line)
        if len(strong_parts) >= 2:
            for part in strong_parts[1:]:
                part = part.strip()
                if _action_line_start.match(part):
                    continue
                if _desc_words.search(part) and len(part.split()) <= 5:
                    continue
                if len(part) > 40 or len(part.split()) > 5 or ',' in part:
                    continue
                company = self._clean_company(part)
                if (company and len(company) >= 2
                        and not _TITRE_PATTERN.search(company)
                        and company.lower() not in _COMPANY_TECH_BLACKLIST
                        and not _desc_words.search(company)):
                    return company

        # Passe 1 quinquies : format virgule « Titre,Entreprise,Ville » (EN CVs)
        # ou « Titre (info),Entreprise,Ville »
        for hdr_line in block.split("\n")[:12]:
            title_m = _TITRE_PATTERN.search(hdr_line)
            if title_m:
                after_title = hdr_line[title_m.end():]
                # Supprimer les parenthèses entre le titre et la virgule
                # "Développeur (Stage),Startup" → ",Startup"
                after_title = re.sub(r'^\s*\([^)]*\)\s*', '', after_title)
                comma_m = re.match(r'\s*,\s*([^,\n]{2,40})(?:\s*,|\s*$)', after_title)
                if comma_m:
                    candidate = self._clean_company(comma_m.group(1).strip())
                    if candidate and candidate.lower() in _COMPANY_TECH_BLACKLIST:
                        continue
                    if (candidate and len(candidate) >= 2
                            and not _TITRE_PATTERN.search(candidate)
                            and not _EN_COURS.search(candidate)):
                        return candidate

        # Passe 2 : spaCy NER (ORG)
        if self._nlp:
            # Limiter aux 3 premières lignes pour capturer le header
            header = "\n".join(block.split("\n")[:3])
            doc = self._nlp(header)
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    name = self._clean_company(ent.text)
                    if not name or len(name) < 2:
                        continue
                    # Rejeter si commence par un article/préposition français
                    if re.match(r'^(?:une?|des?|le|la|les|du|pour|avec|de|au|en)\b', name, re.I):
                        continue
                    # Rejeter si c'est un titre de poste détecté comme ORG
                    if _TITRE_PATTERN.search(name):
                        continue
                    return name

        # Passe 3 : segment après tiret/pipe (unique en-dash ou regular dash)
        parts = re.split(r"\s*[\-–—|]\s*", first_line)
        if len(parts) >= 2:
            for part in parts[1:]:
                part = part.strip()
                if _action_line_start.match(part):
                    continue
                if _desc_words.search(part) and len(part.split()) <= 5:
                    continue
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
                       not _TITRE_PATTERN.search(candidate) and \
                       candidate.lower() not in _COMPANY_TECH_BLACKLIST and \
                       not _desc_words.search(candidate):
                        return candidate

        return None

    def _score_company(self, name: str, source: str = "") -> int:
        """Calcule un score de plausibilité pour un nom d'entreprise.

        Plus le score est élevé, plus le candidat est fiable.
        """
        if not name:
            return -99
        s = 0
        name_lower = name.lower()

        # Connu dans le dict auto-appris → très fiable
        if self.is_known_entreprise(name):
            freq = self._discovered["entreprises"].get(name_lower, 0)
            s += 4 + min(freq, 3)  # +4 de base, +1 par occurrence (max +3)

        # Détecté par NER spaCy → fiable
        if source == "ner":
            s += 3

        # Longueur cohérente (3–40 chars)
        if 3 <= len(name) <= 40:
            s += 2

        # Commence par une majuscule
        if name[0].isupper():
            s += 1

        # Contient un indicateur juridique (SA, SARL, SAS, Ltd, Inc, Corp, GmbH…)
        if re.search(r'\b(?:sa(?:rl)?|sas|llc|ltd|inc|corp|gmbh|bv|spa|plc|s\.a\.)\b', name_lower):
            s += 2

        # Pénalités
        if _TITRE_PATTERN.search(name):
            s -= 5  # ressemble à un titre de poste
        if re.match(r'^(?:le|la|les|un|une|des|du|de|the|a|an)\b', name_lower):
            s -= 3  # commence par article
        if re.search(r'\d{4}', name):
            s -= 2  # contient une année
        if name_lower in _COMPANY_STOP:
            s -= 5  # mot stop
        if name_lower in _COMPANY_TECH_BLACKLIST:
            s -= 6  # outil/framework tech

        return s

    def _get_all_company_candidates(self, block: str) -> List[Dict]:
        """Collecte tous les candidats entreprise avec leur source."""
        candidates: List[Dict] = []
        first_line = block.split("\n")[0]
        first_line_clean = re.sub(r'\)\s+[A-ZÀ-Ö].*$', ')', first_line).strip()
        header_lines = block.split("\n")[:12]

        def _add(name: str, source: str) -> None:
            c = self._clean_company(name)
            if c and len(c) >= 2:
                candidates.append({"valeur": c, "source": source})

        # Passe 0 : dict auto-appris
        for line in header_lines[:4]:
            for token in re.split(r"[|,;]", line):
                c = self._clean_company(token.strip())
                if c and self.is_known_entreprise(c):
                    _add(c, "dict_connu")

        # Passe 1 : séparateur explicite
        sep_m = _COMPANY_SEP.search(first_line_clean)
        if sep_m:
            after = first_line_clean[sep_m.end():].strip()
            company = re.split(r"\s*[\-–—|│┃¦,;]\s*", after)[0].strip()
            _add(company, "separateur")

        # Passe 2 : spaCy NER
        if self._nlp:
            header = "\n".join(header_lines[:3])
            doc = self._nlp(header)
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    _add(ent.text, "ner")

        # Passe 3 : segment après tiret/pipe (premiere ligne ET ligne suivante)
        for scan_line in [first_line_clean] + [l.strip() for l in header_lines[1:3]]:
            # Ignorer les lignes de missions (bullet points)
            if scan_line and scan_line[0] in '-•–—*→▪►●◆○◯◦':
                continue
            parts = re.split(r"\s*[\-–—|]\s*", scan_line)
            if len(parts) < 2:
                continue
            for part in parts[1:]:
                if ',' in part:
                    part = part.split(',')[0]
                part = re.sub(r'\([^)]*$', '', part).strip()
                _add(part, "separateur_fort")

        # Dédupliquer par valeur
        seen: set = set()
        deduped = []
        for c in candidates:
            key = c["valeur"].lower()
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        return deduped

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

    # Pattern pour supprimer les plages de dates en fin de ligne
    # Ex: "Feb 2025 – Jun 2025", "Jul 2024 – Aug 2024", "2022 - Present"
    _DATE_TAIL = re.compile(
        r'\s+(?:(?:jan(?:v)?|feb|f[eé]v|mar(?:s)?|apr|avr|may|mai|jun|juin|jul|juil'
        r'|aug|ao[uû]t?|sep(?:t)?|oct|nov|dec|d[eé]c)[a-z]*\.?\s+)?\d{4}\b.*$',
        re.IGNORECASE,
    )

    def _extract_job_title(self, block: str) -> Optional[str]:
        """Extrait l'intitulé du poste (FR + EN).

        Stratégie multi-lignes :
        1. Chercher _TITRE_PATTERN dans les 3 premières lignes (date supprimée en queue)
        2. Fallback : texte avant séparateur (chez/at/@)
        """
        lines = block.split('\n')

        # Passe 0 : poste déjà connu dans le dict auto-appris
        for line in lines[:3]:
            clean = re.split(
                r'\s*(?:--|@|\||\bchez\b|\bat\b|\bau\s+sein\s+de\b)',
                line, maxsplit=1, flags=re.I,
            )[0]
            clean_no_date = self._DATE_TAIL.sub('', clean).strip()
            if clean_no_date and self.is_known_poste(clean_no_date):
                return self._capitalize_title(clean_no_date)

        # Passe 1 : chercher un titre connu dans les 3 premières lignes
        for line in lines[:3]:
            # Étape 1 : retirer le séparateur entreprise (chez/at/@/|)
            # Note : | est très fréquent dans les CV FR "Titre | Entreprise | Dates"
            clean = re.split(
                r'\s*(?:--|@|\||\bchez\b|\bat\b|\bau\s+sein\s+de\b)',
                line, maxsplit=1, flags=re.I,
            )[0]
            # Étape 2 : retirer la plage de dates en fin de ligne (avant de splitter)
            clean_no_date = self._DATE_TAIL.sub('', clean).strip()
            # Couper au premier ',' (souvent société après virgule)
            if ',' in clean_no_date:
                clean_no_date = clean_no_date.split(',')[0].strip()
            m = _TITRE_PATTERN.search(clean_no_date)
            if m:
                # Retourner le texte complet nettoyé si court (<= 60 chars),
                # sinon juste la sous-chaîne matchée
                candidate = clean_no_date if len(clean_no_date) <= 60 else m.group(0)
                # Retirer tout séparateur fort en début/fin (–, —, |)
                candidate = re.sub(r'^[\s\u2013\u2014\-|]+|[\s\u2013\u2014\-|]+$', '', candidate).strip()
                if len(candidate) >= 3:
                    return self._capitalize_title(candidate)

        # Passe 2 : texte avant séparateur (chez / at / @)
        first_line = lines[0] if lines else ""
        for sep_pat in [r'\bchez\b', r'\bat\b', '@', r'\bau\s+sein\s+de\b', r'\bpour\b']:
            m = re.search(sep_pat, first_line, re.I)
            if m:
                before = first_line[:m.start()].strip()
                before = re.sub(r'[-\u2013\u2014|].*$', '', before).strip()
                if before and len(before) >= 3:
                    return self._capitalize_title(before)
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
            if stripped and stripped[0] in "-•–*→▪►●◆○◯◦":
                mission = stripped.lstrip("-•–*→▪►●◆○◯◦ ").strip()
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

    def _parse_block(self, block: str, *, allow_no_dates: bool = False) -> Optional[Dict]:
        """Analyse un bloc pour en extraire UNE expérience.

        Condition de validité : au moins un titre OU une date.
        """
        job_title = self._extract_job_title(block)
        date_info = self._parse_date_range(block)
        location = self._extract_location(block)
        missions = self._extract_missions(block)

        # ── IA : scoring multi-candidats pour l'entreprise ───────────────────
        all_company_candidates = self._get_all_company_candidates(block)
        ia_candidats_entreprise: List[Dict] = []
        company: Optional[str] = None

        if all_company_candidates:
            # Scorer chaque candidat
            scored = [
                {
                    "valeur": c["valeur"],
                    "source": c["source"],
                    "score": self._score_company(c["valeur"], source=c["source"]),
                }
                for c in all_company_candidates
            ]
            scored.sort(key=lambda x: x["score"], reverse=True)
            ia_candidats_entreprise = scored
            # Meilleur candidat avec score positif
            best = scored[0]
            if best["score"] >= 0:
                company = best["valeur"]
        else:
            # Fallback : méthode originale si aucun candidat collecté
            company = self._extract_company(block)

        has_title = job_title is not None
        has_dates = date_info["date_debut"] is not None

        # Validation : par défaut on exige des dates (meilleur précision).
        # Mais pour améliorer le rappel, on accepte certains blocs sans dates
        # uniquement si une vraie section « Expérience » a été détectée.
        if not has_dates:
            if not allow_no_dates:
                return None
            if not has_title:
                return None
            has_strong_context = bool(company) or bool(location) or len(missions) >= 1
            if not has_strong_context:
                # Dernier filet : présence d'un séparateur explicite « chez/at/@ »
                header = "\n".join(block.split("\n")[:2])
                if not _COMPANY_SEP.search(header):
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
            "ia_candidats_entreprise": ia_candidats_entreprise,
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

        section, section_detected = self._find_experience_section_and_flag(text)
        blocks = self._split_into_blocks(section)

        # On autorise certains blocs sans dates si on a des signaux forts
        # (titre de poste + séparateur entreprise + éventuellement une date ailleurs).
        allow_no_dates = section_detected
        if not allow_no_dates:
            signals = 0
            title_matches = len(_TITRE_PATTERN.findall(text))
            company_sep_matches = len(_COMPANY_SEP.findall(text))
            has_dates = bool(
                _DATE_RANGE.search(text)
                or _SINCE_PATTERN.search(text)
                or re.search(r"\b(?:19|20)\d{2}\b", text)
            )
            if title_matches >= 1:
                signals += 1
            if company_sep_matches >= 1:
                signals += 1
            if has_dates:
                signals += 1
            # Autorisé si :
            #   - 3 signaux (titre + séparateur + date), ou
            #   - 2 signaux (titre + séparateur) mais ≥2 postes distincts
            #     → probable CV sans en-tête de section mais avec vrai historique
            allow_no_dates = signals >= 3 or (signals == 2 and title_matches >= 2 and company_sep_matches >= 2)

        experiences: List[Dict] = []
        for block in blocks:
            parsed = self._parse_block(block, allow_no_dates=allow_no_dates)
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

        # Sauvegarder les postes et entreprises découverts
        self._save_discovered(experiences)

        return {
            "experiences": experiences,
            "annees_experience_totales": round(total_months / 12, 1) if total_months else 0,
            "total_experiences": len(experiences),
            "postes_connus": len(self._discovered["postes"]),
            "entreprises_connues": len(self._discovered["entreprises"]),
        }
