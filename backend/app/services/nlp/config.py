"""
Configuration centrale du pipeline NLP — 3S TalentMatch.

Centralise les patterns, listes de référence et constantes
utilisés par les différents extracteurs (formation, expérience,
compétences, contact, entité).


"""

from __future__ import annotations


# ================================================================
# Patterns de sections CV
# ================================================================

SECTION_PATTERNS: dict[str, list[str]] = {
    "formations": [
        r"Formation[s]?", r"[ÉE]ducation", r"Education",
        r"Dipl[ôo]mes?", r"Dipl[ôo]mes?\s*&\s*[ÉE]tudes", r"[ÉE]tudes",
        r"Scolarit[ée]", r"Parcours\s+acad[ée]mique",
        r"Academic\s+Background", r"Ausbildung", r"Estudios",
        r"Образование",
    ],
    "experiences": [
        r"Exp[ée]riences?\s*(?:professionnelles?)?",
        r"Work\s+Experience", r"Professional\s+Experience",
        r"Parcours", r"Parcours\s+professionnel", r"Carri[èe]re", r"Emplois?",
        r"Career\s+(?:History|Summary)",
        r"Employment(?:\s+History)?",
        r"Berufserfahrung", r"Experiencia\s+(?:laboral|profesional)",
        r"Опыт\s+работы",
    ],
    "competences": [
        r"Comp[ée]tences?\s*(?:techniques?|professionnelles?|cl[ée]s?)?",
        r"Skills?\s*(?:&\s*)?(?:competenc(?:ies|es))?",
        r"Technologies?\s*(?:utilis[ée]es?)?",
        r"Stack\s+technique", r"Outils?\s*(?:et\s+technologies?)?",
        r"Connaissances?\s*(?:techniques?)?",
        r"Savoir[\s\-]faire", r"Technical\s+Skills?",
        r"Hard\s+Skills?", r"Core\s+(?:competenc(?:ies|es)|skills?)",
    ],
    "langues": [
        r"Langues?", r"Languages?", r"Sprachen", r"Idiomas",
        r"Ma[îi]trise\s+des\s+langues", r"Langues?\s+parl[ée]es", r"Langues?\s+ma[îi]tris[ée]es",
    ],
    "projets": [
        r"Projets?\s*(?:personnels?|acad[ée]miques?)?",
        r"Projects?", r"Projekte",
    ],
    "certifications": [
        r"Certifications?", r"Certificats?", r"Certificates?",
    ],
}


# ================================================================
# Mois avec ET sans accents (FR + EN)
# ================================================================

MONTHS_FR: dict[str, str] = {
    "janvier": "01", "janv": "01",
    "février": "02", "fevrier": "02", "févr": "02", "fevr": "02",
    "mars": "03",
    "avril": "04", "avr": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07", "juil": "07",
    "août": "08", "aout": "08",
    "septembre": "09", "sept": "09",
    "octobre": "10", "oct": "10",
    "novembre": "11", "nov": "11",
    "décembre": "12", "decembre": "12", "déc": "12", "dec": "12",
}

MONTHS_EN: dict[str, str] = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}

# Tous les mois combinés
ALL_MONTHS: dict[str, str] = {**MONTHS_FR, **MONTHS_EN}


# ================================================================
# Marqueurs "en cours"
# ================================================================

ONGOING_KEYWORDS: list[str] = [
    "présent", "present", "aujourd'hui", "actuel", "actuellement",
    "en cours", "current", "currently", "now", "ongoing",
    "to date", "jusqu'à présent", "à ce jour",
]


# ================================================================
# Villes par pays
# ================================================================

CITIES_BY_COUNTRY: dict[str, list[str]] = {
    "Tunisia": [
        "Tunis", "Sfax", "Sousse", "Monastir", "Nabeul", "Bizerte",
        "Gabès", "Kairouan", "Médenine", "Tozeur", "Gafsa", "Béja",
        "Jendouba", "Siliana", "Le Kef", "La Manouba", "Ben Arous",
        "Ariana", "Manouba", "Kélibia", "Hammamet", "Mahdia",
        "Djerba", "Kasserine", "Zaghouan", "Sidi Bouzid", "Tataouine",
        "La Marsa",
    ],
    "France": [
        "Paris", "Lyon", "Marseille", "Toulouse", "Nice", "Nantes",
        "Strasbourg", "Montpellier", "Bordeaux", "Lille", "Rennes",
        "Grenoble", "Rouen", "Toulon", "Clermont-Ferrand",
    ],
    "Germany": [
        "Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne",
    ],
    "UK": [
        "London", "Manchester", "Birmingham", "Edinburgh",
    ],
    "USA": [
        "New York", "San Francisco", "Los Angeles", "Seattle",
        "Boston", "Chicago",
    ],
    "Canada": [
        "Toronto", "Montreal", "Vancouver",
    ],
    "North_Africa": [
        "Casablanca", "Rabat", "Alger", "Le Caire",
    ],
    "Gulf": [
        "Dubai", "Doha", "Riyad",
    ],
}

# Liste plate de toutes les villes (pour matching rapide)
ALL_CITIES: set[str] = set()
for _cities in CITIES_BY_COUNTRY.values():
    for _city in _cities:
        ALL_CITIES.add(_city.lower())


# ================================================================
# Patterns de postes les plus courants (pour détection rapide)
# ================================================================

COMMON_JOB_TITLES: list[str] = [
    # FR
    "Développeur", "Ingénieur", "Architecte", "Consultant",
    "Chef de projet", "Responsable", "Directeur", "Analyste",
    "Administrateur", "Technicien", "Stagiaire", "Alternant",
    "Data Scientist", "Data Engineer", "Scrum Master", "Product Owner",
    "DevOps", "Lead Technique", "UX Designer", "UI Designer",
    "Testeur", "QA Engineer",
    # EN
    "Software Engineer", "Developer", "Architect", "Manager",
    "Tech Lead", "Data Analyst", "Intern", "Freelance",
]


# ================================================================
# Titres honorifiques à supprimer des noms
# ================================================================

HONORIFIC_TITLES: set[str] = {
    "m", "m.", "mr", "mr.", "mme", "mme.", "mrs", "mrs.",
    "ms", "ms.", "dr", "dr.", "prof", "prof.",
    "ing", "ing.", "maître", "maitre",
}
