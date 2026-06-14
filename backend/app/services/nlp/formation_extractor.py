"""Extraction des formations et diplômes depuis un texte de CV.

Sprint 2 — US-209

Informations extraites pour chaque formation :
- Diplôme (Master, Licence, Ingénieur, DUT, BTS, Doctorat, Bachelor, …)
- Spécialité (Informatique, IA, Génie Logiciel, …)
- Établissement (Université, École, Institut, University — spaCy ORG + heuristiques)
- Année d'obtention (ou "en cours")
- Niveau calculé (Bac+X)
- Mention éventuelle (Très Bien, Bien, Assez Bien, Cum Laude, Honors, GPA)

Couverture internationale :
- Tunisie  : ESPRIT, INSAT, ENIT, FST, IHEC, ISET, …
- France   : Grandes écoles, Universités, CPGE, IUT, …
- USA/UK   : University of…, … State University, MIT, Stanford, Oxford, …
- Allemagne: TU, Universität, Hochschule, …
- Russie   : МГУ, СПбГУ, lomonosov, ITMO, …
- Monde    : spaCy NER (ORG) comme filet de sécurité pour tout pays

Gestion des abréviations courantes (M2, L3, CPI, BAC+5, BS, BA, AS, …)
Robuste face aux textes OCR (accents manquants, casse variable)

Auteur  : Youssef Gara
Projet  : 3S TalentMatch — PFE ESPRIT 2025-2026
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ================================================================
# Patterns de diplômes → niveau Bac+X
# ================================================================

DIPLOMA_PATTERNS: List[Dict] = [
    # ══════════════ Bac+8 ══════════════
    {"pattern": re.compile(
        r"\b(?:doctorat|phd|ph\.d\.?|d\.?phil\.?|doctorate|doctoral\s+degree"
        r"|th[èeé]se(?:\s+de\s+doctorat)?)\b", re.I),
     "level": 8, "diploma": "Doctorat"},

    # ══════════════ Bac+6 ══════════════
    {"pattern": re.compile(
        r"\b(?:mast[èeé]re\s*(?:sp[ée]cialis[ée]|recherche|professionnel))\b", re.I),
     "level": 6, "diploma": "Mastère Spécialisé"},

    # ══════════════ Bac+5 ══════════════
    {"pattern": re.compile(r"\b(?:master\s*2|m2)\b", re.I),
     "level": 5, "diploma": "Master 2"},
    {"pattern": re.compile(r"\b(?:master\s*1|m1)\b", re.I),
     "level": 4, "diploma": "Master 1"},
    {"pattern": re.compile(r"\b(?:master|m\.?sc\.?)\b", re.I),
     "level": 5, "diploma": "Master"},
    {"pattern": re.compile(r"\b(?:ma[iî]trise)\b", re.I),
     "level": 4, "diploma": "Maîtrise"},
    {"pattern": re.compile(
        r"\b(?:dipl.?me\s*d[\u0027\u2018\u2019`]?\s*ing[ée]nieur"
        r"|cycle\s+(?:d[\u0027\u2018\u2019`]\s*)?ing[ée]nieur"
        r"|ing[ée]nieur\s*d[\u0027\u2018\u2019`]?[ée]tat)\b", re.I),
     "level": 5, "diploma": "Diplôme d'Ingénieur"},
    {"pattern": re.compile(
        r"\bdipl[oô]me\s+national\s+d[\u0027\u2018\u2019`]?architecture\b", re.I),
     "level": 5, "diploma": "Diplôme National d'Architecture"},
    {"pattern": re.compile(r"\bingenieur\b", re.I),
     "level": 5, "diploma": "Diplôme d'Ingénieur"},
    # EN : "Engineering in [specialty]" (Tunisian 5-yr programme)
    {"pattern": re.compile(r"\bengineering\s+in\s+[\w\s]{3,40}", re.I),
     "level": 5, "diploma": "Diplôme d'Ingénieur"},
    # EN : "Engineering degree" / "Degree in engineering"
    {"pattern": re.compile(r"\b(?:engineering\s+degree|degree\s+in\s+engineering)\b", re.I),
     "level": 5, "diploma": "Diplôme d'Ingénieur"},
    {"pattern": re.compile(r"\bmba\b", re.I),
     "level": 5, "diploma": "MBA"},
    # EN Bac+5 : MEng, MPhil, MRes, MArch, LLM
    {"pattern": re.compile(
        r"\b(?:m\.?eng\.?|m\.?phil\.?|m\.?res\.?|m\.?arch\.?|llm)\b", re.I),
     "level": 5, "diploma": "Master"},
    # EN : Master of Science / Arts / Engineering / Business / Computer Science ...
    {"pattern": re.compile(
        r"\bmaster(?:'s)?\s+(?:of\s+)?(?:science|arts|engineering|technology|business"
        r"|computer\s+science|information|administration|management|education|law)\b", re.I),
     "level": 5, "diploma": "Master"},
    # EN : Postgraduate Diploma / Postgrad
    {"pattern": re.compile(
        r"\b(?:postgraduate\s+(?:diploma|certificate|degree)|pgdip|pgcert)\b", re.I),
     "level": 5, "diploma": "Master"},
    {"pattern": re.compile(r"\bbac\s*\+\s*5\b", re.I),
     "level": 5, "diploma": "Bac+5"},

    # ══════════════ Bac+3 ══════════════
    {"pattern": re.compile(r"\b(?:licence\s*pro(?:fessionnelle)?)\b", re.I),
     "level": 3, "diploma": "Licence Professionnelle"},
    {"pattern": re.compile(r"\blicence(?:\s+(?:fondamentale|appliqu[ée]e))?\b", re.I),
     "level": 3, "diploma": "Licence"},
    {"pattern": re.compile(r"\b(?:bachelor|bsc|b\.sc|b\.eng|bba|b\.b\.a)\b", re.I),
     "level": 3, "diploma": "Bachelor"},
    {"pattern": re.compile(r"\b(?:l3|l2|l1)\b", re.I),
     "level": 3, "diploma": "Licence"},
    {"pattern": re.compile(r"\bbac\s*\+\s*3\b", re.I),
     "level": 3, "diploma": "Bac+3"},

    # ══════════════ Bac+2 ══════════════
    {"pattern": re.compile(r"\b(?:dut|deust|deug)\b", re.I),
     "level": 2, "diploma": "DUT"},
    {"pattern": re.compile(r"\bbts\b", re.I),
     "level": 2, "diploma": "BTS"},
    {"pattern": re.compile(r"\bbac\s*\+\s*2\b", re.I),
     "level": 2, "diploma": "Bac+2"},
    # Prépas françaises ET tunisiennes (CPI = Cycle Préparatoire Intégré)
    {"pattern": re.compile(
        r"\b(?:pr[ée]pa|cpge"
        r"|classe[s]?\s*pr[ée]paratoire[s]?"
        r"|cpi"
        r"|cycle\s+pr[ée]paratoire(?:\s+int[ée]gr[ée])?"
        r")\b", re.I),
     "level": 2, "diploma": "Cycle Préparatoire"},

    # ══════════════ Bac+3 (international) ══════════════
    # Espagnol : Licenciatura
    {"pattern": re.compile(
        r"\b(?:licenciatura)\b", re.I),
     "level": 3, "diploma": "Licenciatura"},
    # USA/UK : Bachelor of Science / Arts
    {"pattern": re.compile(
        r"\b(?:bachelor(?:'s)?\s+(?:of\s+)?(?:science|arts|engineering|technology|business)"
        r"|b\.?s\.?c?\.?|b\.?a\.?|b\.?eng\.?)"
        r"\b", re.I),
     "level": 3, "diploma": "Bachelor"},

    # ══════════════ Bac+2 (international) ══════════════
    # USA : Associate Degree
    {"pattern": re.compile(
        r"\b(?:associate(?:'s)?\s+(?:degree|of\s+(?:science|arts))"
        r"|a\.?a\.?s?\.?\s+degree)"
        r"\b", re.I),
     "level": 2, "diploma": "Associate Degree"},
    # Diploma / Certificat professionnel
    {"pattern": re.compile(
        r"\b(?:diploma\s+(?:in|of)\s+[\w\s]{3,30}"
        r"|dipl.?me\s+(?:universitaire|professionnel))"
        r"\b", re.I),
     "level": 2, "diploma": "Diploma"},

    # Certifications (si un titre est présent)
    {"pattern": re.compile(
        r"\bcertification(?:s)?\s+[A-Za-zÀ-ÖØ-öø-ÿ0-9'\-]{2,}", re.I),
     "level": 0, "diploma": "Certification"},

    # Formation professionnelle / qualifiante (CVs métiers)
    {"pattern": re.compile(
        r"\b(?:formation\s+professionnelle(?:s)?"
        r"|formation\s+qualifiante(?:s)?"
        r"|certificat(?:ion)?\s+professionnel(?:le)?(?:s)?)\b",
        re.I,
    ),
     "level": 0, "diploma": "Formation Professionnelle"},

    # ══════════════ Bac+4 ══════════════
    # DEA (ancien système français, avant LMD)
    {"pattern": re.compile(r"\b(?:dea|diplôme\s+d[\u0027\u2018\u2019`]?\s*[ée]tudes\s+approfondies)\b", re.I),
     "level": 4, "diploma": "DEA"},
    # DESS (Diplôme d'Études Supérieures Spécialisées)
    {"pattern": re.compile(r"\b(?:dess|diplôme\s+d[\u0027\u2018\u2019`]?\s*[ée]tudes\s+sup[ée]rieures\s+sp[ée]cialis[ée]es?)\b", re.I),
     "level": 4, "diploma": "DESS"},

    # ══════════════ Bac+3 (médical/paramédical) ══════════════
    # Diplôme d'État infirmier, kiné, sage-femme, etc.
    {"pattern": re.compile(
        r"\b(?:dipl[ôo]me\s+d[\u0027\u2018\u2019`]?\s*[ée]tat"
        r"(?:\s+d[\u0027\u2018\u2019`]?\s*(?:infirmier(?:e)?|sage[\-\s]femme"
        r"|kin[ée]sith[ée]rapeute|ergoth[ée]rapeute|orthophoniste"
        r"|podologue|psychomotricien(?:ne)?|manipulateur"
        r"|technicien\s+de\s+laboratoire))?"
        r"|de\s+infirmier(?:e)?|d[\u0027\u2018\u2019`]?\s*infirmier(?:e)?"
        r")\b", re.I),
     "level": 3, "diploma": "Diplôme d'État"},
    # DES (Diplôme d'Études Spécialisées — médecine)
    # Pas de re.I : on veut matcher "DES" en majuscules uniquement, pas le mot français "des"
    {"pattern": re.compile(r"\bDES\b|dipl[oô]me\s+d[''\u2018\u2019`]?\s*[eé]tudes\s+sp[eé]cialis[eé]es?"),
     "level": 6, "diploma": "DES (Spécialité médicale)"},

    # ══════════════ Bac+2 (vocational) ══════════════
    # BEP (Brevet d'Études Professionnelles)
    {"pattern": re.compile(r"\b(?:bep|brevet\s+d[\u0027\u2018\u2019`]?\s*[ée]tudes?\s+professionnelles?)\b", re.I),
     "level": 1, "diploma": "BEP"},

    # ══════════════ Bac+0 (vocational) ══════════════
    # CAP (Certificat d'Aptitude Professionnelle)
    {"pattern": re.compile(r"\b(?:cap|certificat\s+d[\u0027\u2018\u2019`]?\s*aptitude\s+professionnelle)\b", re.I),
     "level": 0, "diploma": "CAP"},
    # MC (Mention Complémentaire)
    {"pattern": re.compile(r"\b(?:mention\s+compl[ée]mentaire|MC\b)", re.I),
     "level": 0, "diploma": "Mention Complémentaire"},

    # ══════════════ Bac+0 ══════════════
    {"pattern": re.compile(r"\bbaccalaur[ée]at[e]?\b", re.I),
     "level": 0, "diploma": "Baccalauréat"},
    {"pattern": re.compile(r"\bbac\b(?!\s*\+)", re.I),
     "level": 0, "diploma": "Baccalauréat"},
    # UK A-Levels / USA High School Diploma
    {"pattern": re.compile(
        r"\b(?:a[\-\s]?levels?"
        r"|high\s+school\s+diploma"
        r"|abitur"
        r"|аттестат)\b", re.I),
     "level": 0, "diploma": "High School Diploma"},
]

# Mots-clés déclencheurs de la section « Formation »
FORMATION_SECTION_KEYWORDS = re.compile(
    r"(?:^|\n)\s*(?:"
    r"formation[s]?\s*(?:acad[ée]mique[s]?|universitaire[s]?|professionnelle[s]?)?"
    r"|[ée]ducation"
    r"|[ée]tudes?"
    r"|dipl[ôo]mes?"
    r"|cursus"
    r"|parcours\s*(?:acad[ée]mique|universitaire|scolaire)?"
    r"|academic\s+(?:background|history|profile)"
    r"|education(?:al)?\s*(?:background|history)?"
    r"|qualifications?"
    r"|background\s+acad[ée]mique"
    r"|formation"
    r"|degrees?\s+(?:and|&)\s+certifications?"
    r"|academic\s+credentials?"
    r"|scholastic\s+record"
    r"|university\s+education"
    r")\s*[:\-\u2013\u2014]?\s*(?:\n|$)",
    re.IGNORECASE,
)

# Année réaliste (1980-2035)
YEAR_PATTERN = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
YEAR_RANGE_PATTERN = re.compile(
    r"\b(19[89]\d|20[0-3]\d)\s*(?:[\-\u2010\u2011\u2012\u2013\u2014]|[àa]|to)\s*(19[89]\d|20[0-3]\d)\b",
    re.IGNORECASE,
)

# Pattern explicite diplôme + spécialité (groupe 1 = diplôme, groupe 2 = spécialité)
DIPLOMA_SPECIALTY_PATTERN = re.compile(
    r"\b("
    r"master(?:\s*[12])?"
    r"|licence(?:\s+pro(?:fessionnelle)?)?"
    r"|doctorat"
    r"|dipl[ôo]me\s+national\s+d[''`’]?\s*ing[ée]nieur"
    r"|dipl[ôo]me\s+d[''`’]?\s*ing[ée]nieur"
    r"|ing[ée]nieur"
    r")\b"
    r"(?:\s+(?:en|de|option|sp[ée]cialit[ée]\s*:? )\s+|\s+)"
    r"([^\n|;]{2,140})",
    re.IGNORECASE,
)

# Détection « en cours » — signaux textuels uniquement (pas de comparaison de dates)
EN_COURS_PATTERN = re.compile(
    r"\b(?:en\s*cours|pr[ée]sent|actuel(?:lement)?|current|ongoing|aujourd[''']?hui)\b"
    # Plage ouverte : "2022 - présent", "2022 → ..."
    r"|(?:20\d{2})\s*[-–—/]\s*(?:pr[ée]sent|actuel|en\s*cours|now|current|\.\.\.|…)"
    # Plage sans fin : "2022 -" suivi de rien (fin de ligne)
    r"|(?:20\d{2})\s*[-–—]\s*$"
    # Prévu / attendu : "prévu en 2027", "expected 2027"
    r"|\b(?:pr[ée]vu(?:e)?|attendu(?:e)?|expected|anticipated)\s+(?:en\s+)?20\d{2}"
    # Promo : "Promo 2027", "Promotion 2027"
    r"|\b(?:promo(?:tion)?)\s*:?\s*20\d{2}",
    re.IGNORECASE | re.MULTILINE,
)

# Mentions académiques (FR + EN + Latin)
MENTION_PATTERN = re.compile(
    r"\b(?:mention\s+)?"
    r"(tr[èeé]s\s+bien|bien|assez\s+bien|passable"
    r"|excellent|honors?|with\s+(?:highest\s+)?honors?"
    r"|cum\s+laude|magna\s+cum\s+laude|summa\s+cum\s+laude"
    r"|distinction|first\s+class|second\s+class"
    r"|dean[''\u2019]?s\s+list"
    r"|gpa\s*[:\-]?\s*[34]\.[0-9]+"
    r"|\u043a\u0440\u0430\u0441\u043d\u044b\u0439\s+\u0434\u0438\u043f\u043b\u043e\u043c" # русский: красный диплом
    r")\b",
    re.IGNORECASE,
)

# Spécialités courantes — INTERNATIONAL (FR + EN + DE + ES + RU + AR)
SPECIALTIES = [
    # ── Informatique & Tech (FR) ──
    "Informatique", "Génie Logiciel", "Intelligence Artificielle",
    "IA", "Data Science", "Science des Données", "Cybersécurité",
    "Sécurité Informatique", "Réseaux", "Télécommunications",
    "Réseaux et Télécommunications",
    # ── Ingénierie (FR) ──
    "Électronique", "Électrique", "Mécanique", "Mécatronique",
    "Génie Civil", "Génie Industriel", "Génie Électrique",
    "Automatique", "Robotique", "Systèmes Embarqués",
    "Systèmes d'Information",
    # ── Sciences (FR) ──
    "Mathématiques", "Physique", "Chimie", "Biologie",
    "Mathématiques Appliquées", "Sciences de la Vie",
    # ── Business & Gestion (FR) ──
    "Gestion", "Management", "Commerce", "Marketing", "Finance",
    "Comptabilité", "Droit", "Économie", "Ressources Humaines",
    "Communication", "Design", "Architecture",
    # ── TIC modernes (FR) ──
    "Big Data", "Cloud Computing", "DevOps", "IoT",
    "Multimédia", "Web", "Mobile", "Blockchain",
    "ERP", "Business Intelligence",
    # ── English (USA / UK / International) ──
    "Computer Science", "Software Engineering",
    "Information Technology", "IT", "Information Systems",
    "Electrical Engineering", "Mechanical Engineering",
    "Chemical Engineering", "Biomedical Engineering",
    "Aerospace Engineering", "Industrial Engineering",
    "Civil Engineering", "Environmental Engineering",
    "Materials Science", "Nuclear Engineering",
    "Business Administration", "Data Engineering",
    "Artificial Intelligence", "Machine Learning",
    "Cyber Security", "Network Engineering",
    "Statistics", "Applied Mathematics", "Physics",
    "Chemistry", "Biology", "Biochemistry",
    "Economics", "Political Science", "Psychology",
    "Sociology", "Philosophy", "History",
    "Accounting", "Human Resources", "Supply Chain",
    "Operations Research", "Biostatistics",
    "Public Health", "Nursing", "Medicine",
    "Pharmacy", "Dentistry", "Veterinary",
    "Law", "International Relations", "Journalism",
    # ── Deutsch (Allemagne) ──
    "Informatik", "Maschinenbau", "Elektrotechnik",
    "Wirtschaftsinformatik", "Betriebswirtschaftslehre",
    # ── Español ──
    "Ingeniería en Sistemas", "Ciencias de la Computación",
    "Administración de Empresas",
    # ── Русский (Russie) ──
    "Информатика", "Программная инженерия",
    "Экономика", "Менеджмент", "Юриспруденция",
    # ── العربية (Arabe) ──
    "هندسة البرمجيات", "علوم الحاسوب", "إدارة الأعمال",
]

_SPECIALTY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in SPECIALTIES) + r")\b",
    re.IGNORECASE,
)


# ================================================================
# A3 — Domaine d'études (informatique, finance, rh, medecine…)
# Aligné avec _EDU_DOMAINS dans bert_scorer.py
# ================================================================
_DOMAINE_KEYWORDS: dict = {
    "informatique": [
        "informatique", "genie logiciel", "software", "computer science",
        "developpement", "programmation", "systemes", "reseaux",
        "cybersecurite", "data", "intelligence artificielle", "ia",
        "numerique", "digital", "web", "mobile", "cloud", "devops",
        "python", "java", "algorithme", "base de donnees", "si",
        "information technology", "telecommunications",
    ],
    "finance": [
        "finance", "comptabilite", "accounting", "economie",
        "audit", "fiscalite", "banque", "bourse", "tresorerie",
        "controle de gestion", "sciences economiques", "gestion financiere",
        "analyse financiere", "microeconomie", "gestion",
    ],
    "marketing": [
        "marketing", "communication", "commerce", "vente", "publicite",
        "media", "strategie commerciale", "digital marketing",
        "community", "relations publiques",
    ],
    "rh": [
        "ressources humaines", "rh", "management des ressources",
        "psychologie du travail", "relations sociales", "droit social",
        "talent", "recrutement", "formation professionnelle",
    ],
    "droit": [
        "droit", "juridique", "law", "sciences juridiques", "notariat",
        "droit des affaires", "droit public", "droit prive", "avocat",
    ],
    "medecine": [
        "medecine", "sante", "soins", "pharmacie", "paramedical",
        "infirmier", "dentaire", "biomedical", "sciences medicales",
        "chirurgie", "pathologie", "biologie medicale", "kine",
        "nursing", "pharmacy",
    ],
    "btp": [
        "genie civil", "architecture", "construction", "btp",
        "topographie", "batiment", "travaux publics", "structures",
        "geotechnique", "hydraulique",
    ],
    "logistique": [
        "logistique", "supply chain", "transport", "achats",
        "genie industriel", "gestion de production", "qualite",
        "lean", "management industriel",
    ],
    "sciences": [
        "chimie", "physique", "biologie", "mathematiques",
        "physique-chimie", "biochimie",
    ],
    "lettres": [
        "lettres", "langues", "litterature", "traduction",
        "francais", "anglais", "linguistique",
    ],
}


def _detect_formation_domaine(specialty: str, block_text: str = "") -> Optional[str]:
    """Détecte le domaine d'études (informatique, finance…) depuis la spécialité."""
    import re as _re
    import unicodedata as _ud

    def _n(t: str) -> str:
        t = t.lower()
        t = _ud.normalize("NFKD", t)
        return "".join(c for c in t if not _ud.combining(c))

    # Priorité à la spécialité seule, puis au bloc complet en fallback
    spec_norm  = _n(specialty or "")
    block_norm = _n(block_text or "")

    def _count_hits(text: str, keywords: list) -> int:
        hits = 0
        for kw in keywords:
            # word-boundary pour éviter "ia" dans "IAE"
            if _re.search(r"(?<!\w)" + _re.escape(kw) + r"(?!\w)", text):
                hits += 1
        return hits

    best, best_score = None, 0
    for domain, keywords in _DOMAINE_KEYWORDS.items():
        # Spécialité d'abord (score × 2), puis bloc entier (score × 1)
        hits = _count_hits(spec_norm, keywords) * 2 + _count_hits(block_norm, keywords)
        if hits > best_score:
            best_score = hits
            best = domain
    return best if best_score >= 1 else None


class FormationExtractor:
    """
    Extracteur de formations académiques.

    - Détecte les diplômes (Master, Licence, Ingénieur, BTS, etc.)
    - Extrait les établissements via spaCy NER (ORG)
    - Détecte la spécialité
    - Extrait l'année d'obtention
    - Calcule le niveau Bac+X
    """

    def __init__(self, nlp_model=None):
        """Initialise l'extracteur de formations.

        Args:
            nlp_model: Modèle spaCy chargé (optionnel).
                       Si fourni, les entités ORG servent à détecter
                       les établissements. Sinon, seules les
                       heuristiques regex sont utilisées.
        """
        self._nlp = nlp_model

    def _find_formation_section(self, text: str) -> str:
        """
        Isole la section 'Formation' du CV si elle existe.
        Sinon retourne le texte complet.
        """
        match = FORMATION_SECTION_KEYWORDS.search(text)
        if not match:
            # Fallback : en-tête inline (ex: "DIPLÔMES & ÉTUDES Master ...")
            inline = re.search(
                r"\b(?:formation[s]?|dipl[ôo]mes?(?:\s*&\s*[ée]tudes)?|[ée]tudes|etudes|"
                r"scolarit[éee]|parcours\s+acad[ée]mique|[ée]ducation|education)\b",
                text,
                re.IGNORECASE,
            )
            if not inline:
                return text
            # Si le mot-clé est inline ET suivi d'une année proche,
            # il fait souvent partie de la 1ère entrée (ex: "Formation Professionnelle 2015-2017 ...")
            # → ne pas tronquer le libellé.
            window = text[inline.start(): inline.start() + 140]
            if re.search(r"\b(19[89]\d|20[0-3]\d)\b", window):
                start = inline.start()
            else:
                start = inline.end()
        else:
            start = match.end()

        # Chercher la prochaine section (mot-clé en début de ligne)
        next_section = re.search(
            r"\n\s*(?:exp[ée]rience|exp[ée]riences|exp[ée]riences?\s+professionnelles?"
            r"|parcours|emplois?|carri[èe]re|work\s+experience|professional\s+experience"
            r"|comp[ée]tences?|skills?|savoir[\s\-]faire|connaissances?|technologies?|stack\s+technique|outils?"
            r"|langues?|projets?|certifications?|loisirs?|divers|r[ée]f[ée]rences?)\s*[:\-]?\s*\n",
            text[start:],
            re.IGNORECASE,
        )
        if next_section:
            return text[start:start + next_section.start()]
        return text[start:]

    def _extract_establishments(self, text: str) -> List[str]:
        """Extrait les noms d'établissements via heuristiques + spaCy NER.

        Stratégie deux-passes :
        1. Heuristiques regex — couvre les cas fréquents (Université de…,
           École Supérieure…, ESPRIT, INSAT, etc.).
        2. spaCy NER (ORG) — complète avec les entités non captées
           par les regex.

        Returns:
            Liste de noms d'établissements dédupliqués.
        """
        establishments: List[str] = []
        seen_lower: set = set()

        # Mots de champs/diplômes à ne PAS inclure en début de nom
        _FIELD_PREFIXES = {
            "engineering", "science", "sciences", "technology",
            "arts", "business", "computing", "management",
            "applied", "education", "medicine", "nursing",
            "of", "in", "and", "the", "de", "du", "des", "en",
            # Mots de diplômes (EN) qui précèdent parfois le nom d'établissement
            "degree", "bachelor", "master", "diploma", "certificate",
            "graduate", "undergraduate", "postgraduate", "doctorate",
            "honours", "honors", "advanced",
        }

        def _add(name: str) -> None:
            name = " ".join(name.split()).strip(" ,-;:")
            # Supprimer les années (ex: "FST Sousse 2021" → "FST Sousse")
            name = re.sub(r"\b(19[5-9]\d|20[0-4]\d)\b", "", name).strip(" ,-;:")
            name = " ".join(name.split())  # normaliser les espaces multiples
            # Nettoyer les mots de champs en début de nom
            # Ex: "Engineering Massachusetts Institute" → "Massachusetts Institute"
            words = name.split()
            while words and words[0].lower() in _FIELD_PREFIXES:
                words.pop(0)
            name = " ".join(words).strip()
            if len(name) < 3:
                return
            low = name.lower()
            if low not in seen_lower:
                seen_lower.add(low)
                establishments.append(name)

        # ── Passe 0 : heuristique par segments (capture noms complets) ──
        org_hint = re.compile(
            r"\b(?:universit[ée]|[ée]cole|ecole|institut|facult[ée]|school|college|"
            r"ihec|esprit|insi?t|ensi|enit|iset|fst|isg|essect|supcom)\b",
            re.IGNORECASE,
        )
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            # Couper sur séparateurs forts (|, --, en-dash, em-dash) y compris simples
            parts = re.split(r"\s*(?:\|+|[\u2013\u2014]|[-]{2,})\s*", stripped)
            for part in parts:
                candidate = part.strip(" ,-;:•")
                if not candidate:
                    continue
                # Couper sur virgule si après le org_hint (ex: "ESPRIT, Tunis")
                hint_match = org_hint.search(candidate)
                if not hint_match:
                    continue
                # Extraire : depuis le début jusqu'à la première virgule après le hint
                before_comma = candidate.split(',')[0].strip(" ,-;:")
                before_paren = re.sub(r'\s*\(.*$', '', before_comma).strip()
                # Supprimer les années
                cleaned = re.sub(r"\b(19[89]\d|20[0-3]\d)\b", "", before_paren).strip(" ,-;:")
                if cleaned and len(cleaned) >= 3:
                    _add(cleaned)

        # ── Passe 1 : heuristiques regex (INTERNATIONAL) ──────
        org_patterns = [
            # ---- FRANCOPHONE ----
            re.compile(r"\b(?:universit[ée]\s+(?:de\s+|du\s+|des\s+)?[\w\s\-'']{3,80})", re.I),
            re.compile(
                r"\b(?:[ée]cole\s+"
                r"(?:nationale\s+|sup[ée]rieure\s+|polytechnique\s+|centrale\s+|priv[ée]e\s+)?"
                r"[\w\s\-'']{3,80})", re.I,
            ),
            re.compile(
                r"\b(?:institut\s+(?:national\s+|sup[ée]rieur\s+|priv[ée]\s+)?"
                r"[\w\s\-'']{3,100})", re.I,
            ),
            re.compile(r"\b(?:facult[ée]\s+(?:de[s]?\s+)?[\w\s\-'']{3,80})", re.I),

            # ---- TUNISIE (sigles) ----
            re.compile(
                r"\b(?:ESPRIT|INSAT|ENIT|ENSI|ISI|ISET|FST|FSB|ISTIC"
                r"|IHEC|ISG|ESSECT|SUP'?COM|ENSIT|ENISO|ENSA|ISIMS"
                r"|ISSAT|ISSIG|POLYTECHNIQUE)"
                r"(?:\s+(?:de\s+)?[A-ZÀ-Ö][\w\s\-'']{2,20})?"
                r"\b", re.I,
            ),

            # ---- FRANCE (grandes écoles) ----
            re.compile(
                r"\b(?:Centrale|HEC|ESSEC|EDHEC"
                r"|INSA|UTC|UTBM|UTT|ENSIMAG|ENSEEIHT|Télécom|Mines)"
                r"(?:\s+(?:de\s+|Paris|Lyon|Lille|Toulouse|Nantes)?[\w\s\-'']{0,20})?"
                r"\b", re.I,
            ),

            # ---- ANGLOPHONE (USA / UK / Canada / Australie / Inde) ----
            # "University of <Name>" ou "<Name> University"
            re.compile(
                r"\b(?:University\s+of\s+[A-ZÀ-Ö][\w\s\-'']{2,40})"
                r"\b", re.I,
            ),
            re.compile(
                r"\b(?:[A-Z][\w\-'']+(?:\s+[A-Z][\w\-'']+)?\s+University)"
                r"\b",
            ),
            # "<Name> State University" or "<Name> Institute of Technology"
            re.compile(
                r"\b(?:[A-Z][\w\-'']+(?:\s+[A-Z][\w\-'']+)?\s+"
                r"(?:State\s+University|Institute\s+of\s+Technology|College|Polytechnic))"
                r"\b",
            ),
            # Top universités mondiales (sigles et noms)
            re.compile(
                r"\b(?:MIT|Stanford|Harvard|Yale|Princeton|Columbia"
                r"|Oxford|Cambridge|Imperial\s+College|UCL|LSE|ETH\s+Z[uü]rich"
                r"|Caltech|Berkeley|UCLA|NYU|Georgetown|Duke|Cornell"
                r"|Carnegie\s+Mellon|Georgia\s+Tech"
                r"|University\s+of\s+Toronto|McGill|UBC"
                r"|IIT|IISc|NUS|NTU"
                r"|Tsinghua|Peking\s+University|Fudan"
                r"|TU\s+(?:Munich|Berlin|Dresden|Darmstadt)"
                r"|Sorbonne|Sciences\s+Po)"
                r"\b", re.I,
            ),

            # ---- GERMANOPHONE ----
            # "Universität <Name>" ou "Technische Universität"
            re.compile(
                r"\b(?:Universit[äa]t\s+[\w\s\-'']{3,30}"
                r"|Technische\s+Universit[äa]t\s+[\w\s\-'']{3,30}"
                r"|Hochschule\s+[\w\s\-'']{3,30}"
                r"|Fachhochschule\s+[\w\s\-'']{3,30})"
                r"\b", re.I,
            ),

            # ---- HISPANOPHONE ----
            re.compile(
                r"\b(?:Universidad\s+(?:de\s+|del\s+|Nacional\s+)?[\w\s\-'']{3,40}"
                r"|Polit[ée]cnica\s+(?:de\s+)?[\w\s\-'']{3,30})"
                r"\b", re.I,
            ),

            # ---- RUSSOPHONE ----
            # МГУ/СПбГУ/ITMO/Бауманка + formes translittérées
            re.compile(
                r"\b(?:МГУ|СПбГУ|ITMO|Бауманка|МИФИ|МГИМО"
                r"|Moscow\s+State\s+University"
                r"|Lomonosov"
                r"|Saint[\-\s]Petersburg\s+(?:State\s+)?University"
                r"|университет\s+[\w\s\-]{3,30}"
                r"|институт\s+[\w\s\-]{3,30})"
                r"\b", re.I,
            ),

            # ---- ARABE ----
            re.compile(
                r"(?:جامعة\s+[\w\s\-]{3,30}"
                r"|كلية\s+[\w\s\-]{3,30}"
                r"|معهد\s+[\w\s\-]{3,30})",
            ),

            # ---- CATCH-ALL : "<Name> Academy / School of <X>" ----
            re.compile(
                r"\b(?:[A-Z][\w\-'']+(?:\s+[A-Z][\w\-'']+)?\s+"
                r"(?:Academy|School\s+of\s+[\w\s]{3,20}|Conservatory))"
                r"\b",
            ),
        ]

        for pat in org_patterns:
            for m in pat.finditer(text):
                _add(m.group(0))

        # ── Passe 2 : spaCy NER (ORG) ──────────────────────────
        if self._nlp:
            doc = self._nlp(text)
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    _add(ent.text)

        return establishments

    def _extract_years(self, text: str) -> List[int]:
        """Extrait toutes les années du texte."""
        return [int(y) for y in YEAR_PATTERN.findall(text)]

    def _extract_end_year_from_range(self, text: str) -> Optional[int]:
        """Extrait l'année de FIN d'une plage (ex: 2010 à 2012 -> 2012)."""
        matches = YEAR_RANGE_PATTERN.findall(text)
        if not matches:
            return None
        return max(int(end) for _, end in matches)

    @staticmethod
    def _normalize_diploma_label(raw: str) -> Optional[Dict]:
        """Normalise un libellé de diplôme vers le format canonique interne."""
        if not raw:
            return None
        low = raw.lower().strip()
        if "master 2" in low:
            return {"diploma": "Master 2", "level": 5}
        if "master 1" in low:
            return {"diploma": "Master 1", "level": 4}
        if "master" in low:
            return {"diploma": "Master", "level": 5}
        if "licence pro" in low:
            return {"diploma": "Licence Professionnelle", "level": 3}
        if "licence" in low:
            return {"diploma": "Licence", "level": 3}
        if "doctorat" in low:
            return {"diploma": "Doctorat", "level": 8}
        if "ing" in low:
            return {"diploma": "Diplôme d'Ingénieur", "level": 5}
        return None

    def _extract_diploma_specialty_pair(self, text: str) -> Optional[Dict]:
        """Extrait diplôme et spécialité avec regex explicite à 2 groupes."""
        m = DIPLOMA_SPECIALTY_PATTERN.search(text)
        if not m:
            return None

        diploma_info = self._normalize_diploma_label(m.group(1))
        if not diploma_info:
            return None

        specialty = m.group(2).strip(" ,-;:")
        specialty = re.split(r"\s*(?:\|+|[-–—]{2,})\s*", specialty, maxsplit=1)[0].strip()
        specialty = re.sub(r"\b(19[89]\d|20[0-3]\d)\b", "", specialty).strip(" ,-;:")
        if len(specialty) < 2:
            specialty = None

        return {
            "diplome": diploma_info["diploma"],
            "niveau_bac_plus": diploma_info["level"],
            "specialite": specialty,
        }

    def _extract_specialties(self, text: str) -> List[str]:
        """Extrait les spécialités détectées dans le texte."""
        found = []
        seen = set()
        for m in _SPECIALTY_PATTERN.finditer(text):
            val = m.group(0)
            low = val.lower()
            if low not in seen:
                seen.add(low)
                found.append(val)
        return found

    # Établissements tunisiens/français connus — boost fort
    _ETAB_CONNUS = frozenset({
        "esprit", "insat", "enit", "ensi", "isi", "iset", "fst", "fsb",
        "istic", "ihec", "isg", "essect", "supcom", "ensit", "eniso",
        "ensa", "isims", "issat", "issig", "polytechnique",
        "centrale", "hec", "essec", "edhec", "insa", "utc", "utbm",
        "utt", "ensimag", "mit", "stanford", "oxford", "cambridge",
    })

    def _score_establishment(self, name: str) -> int:
        """Calcule un score de plausibilité pour un nom d'établissement."""
        name_lower = name.lower()
        s = 0

        has_institution_kw = any(
            kw in name_lower
            for kw in (
                'université', 'university', 'école', 'ecole', 'institut',
                'institute', 'faculté', 'faculty', 'college', 'school'
            )
        )

        # Signal fort : mot institution explicite
        for kw in ('université', 'university', 'école', 'ecole', 'institut',
                   'institute', 'faculté', 'faculty', 'college', 'school'):
            if kw in name_lower:
                s += 4
                break

        # Signal fort : établissement connu
        for tok in re.split(r'\W+', name_lower):
            if tok in self._ETAB_CONNUS:
                s += 5
                break

        # Signal moyen : sigle capitalisé court (ESPRIT, INSAT, FST…)
        if re.match(r'^[A-Z]{2,8}$', name.split()[0] if name.split() else ''):
            s += 2

        # Longueur cohérente
        if 4 <= len(name) <= 60:
            s += 1

        # Pénalités
        bad = ('master', 'licence', 'doctorat', 'phd', 'bachelor',
               'ingénieur', 'informatique', 'mathématiques', 'gestion',
               'management', 'commerce', 'marketing', 'finance', 'data science')
        for b in bad:
            if b in name_lower and len(name) < 40:
                # Éviter de pénaliser les vrais établissements contenant une spécialité
                # (ex: "Institut Supérieur d'Informatique", "Data Science Institute").
                if has_institution_kw:
                    continue
                s -= 3

        # Cas fréquent : spécialité prise pour établissement ("Data Science")
        # On pénalise fortement si ce n'est pas accompagné d'un signal institutionnel.
        if "data science" in name_lower:
            if not has_institution_kw and len(name_lower.split()) <= 3:
                s -= 6

        if re.search(r'\d', name):
            s -= 1
        if name and not name[0].isupper():
            s -= 1

        return s

    def _pick_best_establishment(
        self, candidates: List[str]
    ) -> Optional[str]:
        """Choisit l'établissement le plus plausible parmi les candidats."""
        if not candidates:
            return None
        valid = [c for c in candidates if len(c) >= 4]
        if not valid:
            return None
        best = max(valid, key=self._score_establishment)
        # Rejeter si le meilleur score est négatif (spécialité prise pour établissement)
        if self._score_establishment(best) < 0:
            return None
        return best

    def _rank_establishments(
        self, candidates: List[str]
    ) -> List[Dict]:
        """Retourne tous les candidats triés par score décroissant (pour ia_candidats)."""
        scored = [
            {"valeur": c, "score": self._score_establishment(c)}
            for c in candidates if len(c) >= 4
        ]
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def _extract_mention(self, text: str) -> Optional[str]:
        """Détecte une mention académique dans le contexte."""
        m = MENTION_PATTERN.search(text)
        if not m:
            return None
        raw = m.group(0).strip()
        # Normaliser
        low = raw.lower()
        if "très bien" in low or "tres bien" in low:
            return "Très Bien"
        if "assez bien" in low:
            return "Assez Bien"
        if "bien" in low:
            return "Bien"
        if "passable" in low:
            return "Passable"
        if "summa" in low:
            return "Summa Cum Laude"
        if "magna" in low:
            return "Magna Cum Laude"
        if "cum laude" in low:
            return "Cum Laude"
        if "excellent" in low or "honor" in low:
            return "Honors"
        if "distinction" in low:
            return "Distinction"
        if "first class" in low:
            return "First Class Honours"
        if "second class" in low:
            return "Second Class Honours"
        if "dean" in low:
            return "Dean's List"
        if "gpa" in low:
            return raw.upper()  # Ex: "GPA: 3.85"
        if "красный" in low:
            return "Красный Диплом"
        return raw.title()

    def _is_en_cours(self, text: str, annee: int = None) -> bool:
        """Vérifie si la formation est en cours.

        Deux signaux complémentaires :
        1. Mot-clé textuels : "en cours", "présent", "actuel", "Promo 2027"…
        2. Année future : si annee > année courante du serveur → formation non encore obtenue.
           datetime.now().year est dynamique : en 2027 il retourne 2027, en 2030 il retourne 2030.
           Aucun changement de code nécessaire d'une année à l'autre.
        """
        from datetime import datetime
        if annee is not None and annee > datetime.now().year:
            return True
        return bool(EN_COURS_PATTERN.search(text))

    @staticmethod
    def _split_into_blocks(section: str) -> List[str]:
        """Découpe la section Formation en blocs individuels."""
        if not section:
            return []
        # Séparateurs visuels → saut de ligne
        section = re.sub(r'[|¦•●►]', '\n', section)
        # Normalisation texte compact : injecter \n avant mots-clés de diplôme
        section = re.sub(
            r'(?<!\n)\s+(?=(?:master(?:\s*[12])?|ma[iî]trise|licence|baccalaur[ée]at[e]?'
            r'|doctorat|dipl[ôo]me|ing[ée]nieur'
            r'|engineering\s+in|bachelor|high\s+school|diploma\s+in'
            r')\b)',
            '\n',
            section,
            flags=re.IGNORECASE,
        )
        section = re.sub(r'\n\s*\n+', '\n\n', section)
        blocks = []
        current_block: List[str] = []
        lines = section.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                if current_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                continue
            is_bullet = line.startswith(('-', '–', '*'))
            content = re.sub(r'^[-–*]+\s*', '', line).strip() if is_bullet else line
            if not content:
                continue
            has_year = bool(re.search(r'\b(19[89]\d|20[0-3]\d)\b', content))
            has_diploma = any(dp["pattern"].search(content) for dp in DIPLOMA_PATTERNS)
            if current_block and (has_year or has_diploma):
                if is_bullet or len(content) < 80:
                    blocks.append('\n'.join(current_block))
                    current_block = [content]
                    continue
            current_block.append(content)
        if current_block:
            blocks.append('\n'.join(current_block))

        # ── Post-traitement : fusionner "diplôme" puis "années" sur ligne suivante ──
        # Certains PDFs donnent:
        #   "Formation Professionnelle Bizerte"\n"2015-2017 ..."
        # On veut un bloc unique pour que l'année soit extraite.
        _org_hint_re = re.compile(
            r"\b(?:universit[ée]|[ée]cole|ecole|institut|school|college|"
            r"ihec|esprit|insi?t|ensi|enit|iset|fst|isg|essect|supcom|"
            r"private\s+higher|higher\s+school)\b",
            re.IGNORECASE,
        )
        merged: List[str] = []
        i = 0
        while i < len(blocks):
            b = blocks[i]
            if i + 1 < len(blocks):
                n = blocks[i + 1]
                b_has_year = bool(re.search(r"\b(19[89]\d|20[0-3]\d)\b", b))
                n_has_year = bool(re.search(r"\b(19[89]\d|20[0-3]\d)\b", n))
                b_has_diploma = any(dp["pattern"].search(b) for dp in DIPLOMA_PATTERNS)
                n_has_diploma = any(dp["pattern"].search(n) for dp in DIPLOMA_PATTERNS)
                next_starts_with_year = bool(re.match(r"^\s*(?:19[89]\d|20[0-3]\d)\b", n))
                # Cas : établissement seul (pas diplôme, pas année) suivi d'une ligne diplôme
                # Ex: "ESPRIT – Private Higher School..." + "Engineering Degree in CS..."
                if (not b_has_diploma) and (not b_has_year) and n_has_diploma and "\n" not in b:
                    if _org_hint_re.search(b):
                        merged.append(b + "\n" + n)
                        i += 2
                        continue
                if b_has_diploma and (not b_has_year) and n_has_year and (not n_has_diploma) and next_starts_with_year:
                    merged.append(b + "\n" + n)
                    i += 2
                    continue
                # Variante: la ligne suivante est une continuation (minuscule, parenthèse, ou année)
                # Ex: "Diplôme ... École Nationale" + "d'Architecture de Tunis (2010-2015)"
                if b_has_diploma and (not b_has_year) and (not n_has_diploma):
                    n_strip = n.strip()
                    if n_has_year or n_strip.startswith("(") or (n_strip and n_strip[0].islower()):
                        merged.append(b + "\n" + n)
                        i += 2
                        continue
            merged.append(b)
            i += 1

        return [b for b in merged if len(b.strip()) > 10]

    # Villes connues pour extraction du lieu (Tunisie, France, Maghreb, International)
    _VILLES_CONNUES = re.compile(
        r"\b(?:"
        # Tunisie
        r"Tunis|Sousse|Sfax|Monastir|Bizerte|Kairouan|Gab[eè]s|Nabeul|Hammamet"
        r"|Manouba|Ariana|Ben\s+Arous|La\s+Marsa|Carthage|Djerba|M[eé]denine"
        r"|Zaghouan|Siliana|Kasserine|Sidi\s+Bouzid|Jendouba|Beja|Le\s+Kef"
        r"|Gafsa|Tozeur|Tataouine|K[eé]libia"
        # France
        r"|Paris|Lyon|Marseille|Toulouse|Nice|Nantes|Strasbourg|Bordeaux|Lille"
        r"|Montpellier|Rennes|Reims|Saint[\s\-]Etienne|Toulon|Grenoble|Dijon"
        r"|Angers|Le\s+Mans|Nimes|Clermont[\s\-]Ferrand|Aix[\s\-]en[\s\-]Provence"
        # Maghreb
        r"|Alger|Oran|Constantine|Casablanca|Rabat|Marrakech|Fes|Tanger|Agadir"
        # International fréquent
        r"|Londres?|London|Berlin|Madrid|Rome|Geneve|Zurich|Montreal|Quebec"
        r"|New\s+York|San\s+Francisco|Toronto|Dubai|Riyad|Doha|Beyrouth"
        r")\b",
        re.IGNORECASE,
    )

    def _extract_lieu(self, block: str, etablissement: Optional[str]) -> Optional[str]:
        """Extrait la ville/lieu depuis le bloc ou depuis le nom de l'établissement.

        Stratégie :
        1. Ville après virgule, pipe ou parenthèse dans le bloc
        2. Ville connue dans le nom de l'établissement (ex: FST Sousse → Sousse)
        3. spaCy LOC/GPE sur le bloc
        """
        # Passe 1 : ville après séparateur explicite (ex: "ESPRIT, Tunis" ou "ESPRIT | Tunis")
        sep_pattern = re.compile(
            r"(?:[,|/]\s*|[\(\[]\s*)"
            r"(" + self._VILLES_CONNUES.pattern + r")"
            r"(?:\s*[\)\]])?",
            re.IGNORECASE,
        )
        m = sep_pattern.search(block)
        if m:
            return m.group(1).strip()

        # Passe 2 : ville dans le nom de l'établissement (ex: "FST Sousse")
        if etablissement:
            mv = self._VILLES_CONNUES.search(etablissement)
            if mv:
                return mv.group(0).strip()

        # Passe 3 : ville connue n'importe où dans le bloc
        mv = self._VILLES_CONNUES.search(block)
        if mv:
            return mv.group(0).strip()

        # Passe 4 : spaCy LOC/GPE
        if self._nlp:
            doc = self._nlp(block[:300])
            for ent in doc.ents:
                if ent.label_ in ("LOC", "GPE"):
                    return ent.text.strip()

        return None

    def _extract_formation_from_block(self, block: str) -> Optional[Dict]:
        """Analyse un bloc de texte individuel pour en extraire UNE formation.

        Parcourt les patterns de diplôme du plus spécifique (Bac+8) au
        moins spécifique (Bac+0). Dès qu'un match est trouvé, on
        extrait les métadonnées et on retourne.

        Args:
            block: Texte d'un bloc de formation (1-3 lignes).

        Returns:
            Dict formation ou None si aucun diplôme détecté.
        """
        for dp in DIPLOMA_PATTERNS:
            match = dp["pattern"].search(block)
            if not match:
                continue

            # Année d'obtention : priorité à la fin de plage (2010 à 2012 -> 2012)
            annee = self._extract_end_year_from_range(block)
            if annee is None:
                years = self._extract_years(block)
                annee = years[-1] if years else None

            # En cours ? (mot-clé OU année future automatique)
            en_cours = self._is_en_cours(block, annee=annee)

            # Mention
            mention = self._extract_mention(block)

            # Diplôme + spécialité (regex explicite) puis fallback par listes
            diploma = dp["diploma"]
            level = dp["level"]
            specialty = None

            pair = self._extract_diploma_specialty_pair(block)
            if pair:
                diploma = pair["diplome"]
                level = pair["niveau_bac_plus"]
                specialty = pair.get("specialite")

            if not specialty:
                specialties = self._extract_specialties(block)
                specialty = specialties[0] if specialties else None

            # Établissement + lieu
            establishments = self._extract_establishments(block)
            establishment = self._pick_best_establishment(establishments)
            lieu = self._extract_lieu(block, establishment)
            ia_candidats_etab = self._rank_establishments(establishments)

            return {
                "diplome": diploma,
                "specialite": specialty,
                "domaine": _detect_formation_domaine(specialty, block),
                "etablissement": establishment,
                "lieu": lieu,
                "annee": annee,
                "en_cours": en_cours,
                "mention": mention,
                "niveau_bac_plus": level,
                "ia_candidats_etablissement": ia_candidats_etab,
            }

        return None

    def extract(self, text: str) -> Dict:
        """Extrait les formations depuis le texte du CV.

        Stratégie par blocs (qualité PFE) :
        1. Isoler la section « Formation » du CV.
        2. Découper la section en **blocs individuels** (1 par formation).
        3. Pour chaque bloc, détecter le diplôme et extraire les
           métadonnées (spécialité, établissement, année, mention)
           sans contamination entre formations.
        4. Dédupliquer : si « Master 2 » trouvé, ne pas ajouter « Master ».

        Returns:
            {
                "formations": [
                    {
                        "diplome":          "Diplôme d'Ingénieur",
                        "specialite":       "Informatique",
                        "etablissement":    "ESPRIT",
                        "annee":            2025,
                        "en_cours":         False,
                        "mention":          "Bien",
                        "niveau_bac_plus":  5
                    },
                    ...
                ],
                "niveau_max":        5,
                "total_formations":  2
            }
        """
        if not text:
            return {"formations": [], "niveau_max": 0, "total_formations": 0}

        section = self._find_formation_section(text)
        blocks = self._split_into_blocks(section)

        formations: List[Dict] = []
        seen_formations: set = set()

        for block in blocks:
            formation = self._extract_formation_from_block(block)
            if formation is None:
                continue

            # Déduplication : éviter seulement les doublons stricts
            diploma_key = formation["diplome"].lower()
            dedup_key = (
                diploma_key,
                (formation.get("etablissement") or "").lower(),
                formation.get("annee") or 0,
                (formation.get("specialite") or "").lower(),
            )

            if dedup_key in seen_formations:
                continue

            # Si un "Master" générique est déjà présent et qu'on trouve
            # ensuite un "Master 1/2" sur la même ligne académique, remplacer.
            if diploma_key in {"master 1", "master 2"}:
                formations = [
                    f for f in formations
                    if not (
                        f["diplome"].lower() == "master"
                        and (f.get("etablissement") or "").lower() == (formation.get("etablissement") or "").lower()
                        and (f.get("annee") or 0) == (formation.get("annee") or 0)
                    )
                ]
            elif diploma_key == "master":
                has_specific_master = any(
                    f["diplome"].lower() in {"master 1", "master 2"}
                    and (f.get("etablissement") or "").lower() == (formation.get("etablissement") or "").lower()
                    and (f.get("annee") or 0) == (formation.get("annee") or 0)
                    for f in formations
                )
                if has_specific_master:
                    continue

            seen_formations.add(dedup_key)
            formations.append(formation)

        # Tri : plus récent en premier, puis par niveau décroissant
        formations.sort(
            key=lambda f: (f["annee"] or 0, f["niveau_bac_plus"]),
            reverse=True,
        )

        niveau_max = max(
            (f["niveau_bac_plus"] for f in formations), default=0
        )

        return {
            "formations": formations,
            "niveau_max": niveau_max,
            "total_formations": len(formations),
        }
