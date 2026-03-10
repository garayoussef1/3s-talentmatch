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
        r"\b(?:doctorat|phd|ph\.d|th[èeé]se(?:\s+de\s+doctorat)?)\b", re.I),
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
        r"\b(?:dipl[ôo]me\s*d[\u0027\u2018\u2019`]?\s*ing[ée]nieur"
        r"|cycle\s+(?:d[\u0027\u2018\u2019`]\s*)?ing[ée]nieur"
        r"|ing[ée]nieur\s*d[\u0027\u2018\u2019`]?[ée]tat)\b", re.I),
     "level": 5, "diploma": "Diplôme d'Ingénieur"},
    {"pattern": re.compile(r"\bingenieur\b", re.I),
     "level": 5, "diploma": "Diplôme d'Ingénieur"},
    # EN : "Engineering in [specialty]" (Tunisian 5-yr programme)
    {"pattern": re.compile(r"\bengineering\s+in\s+[\w\s]{3,40}", re.I),
     "level": 5, "diploma": "Diplôme d'Ingénieur"},
    {"pattern": re.compile(r"\bmba\b", re.I),
     "level": 5, "diploma": "MBA"},
    {"pattern": re.compile(r"\bbac\s*\+\s*5\b", re.I),
     "level": 5, "diploma": "Bac+5"},

    # ══════════════ Bac+3 ══════════════
    {"pattern": re.compile(r"\b(?:licence\s*pro(?:fessionnelle)?)\b", re.I),
     "level": 3, "diploma": "Licence Professionnelle"},
    {"pattern": re.compile(r"\blicence(?:\s+(?:fondamentale|appliqu[ée]e))?\b", re.I),
     "level": 3, "diploma": "Licence"},
    {"pattern": re.compile(r"\b(?:bachelor|bsc|b\.sc|b\.eng)\b", re.I),
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
        r"|dipl[oô]me\s+(?:universitaire|professionnel))"
        r"\b", re.I),
     "level": 2, "diploma": "Diploma"},

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
    r"|academic\s+background"
    r"|education"
    r"|qualifications?"
    r"|background\s+acad[ée]mique"
    r"|formation"
    r")\s*[:\-\u2013\u2014]?\s*(?:\n|$)",
    re.IGNORECASE,
)

# Année réaliste (1980-2035)
YEAR_PATTERN = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
YEAR_RANGE_PATTERN = re.compile(
    r"\b(19[89]\d|20[0-3]\d)\s*(?:[-–—]|[àa]|to)\s*(19[89]\d|20[0-3]\d)\b",
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

# Détection « en cours » / « présent »
EN_COURS_PATTERN = re.compile(
    r"\b(?:en\s*cours|pr[ée]sent|actuel(?:lement)?|current|ongoing|aujourd[''']?hui)\b",
    re.IGNORECASE,
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
        }

        def _add(name: str) -> None:
            name = " ".join(name.split()).strip(" ,-;:")
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

    def _pick_best_establishment(self, candidates: List[str]) -> Optional[str]:
        """Choisit l'établissement le plus plausible parmi les candidats."""
        if not candidates:
            return None

        good_indicators = [
            'université', 'university', 'école', 'ecole', 'institut',
            'institute', 'faculté', 'faculty', 'college', 'school',
            'polytechnique', 'centrale', 'ens', 'sup', 'esprit', 'insat',
            'enit', 'ensi', 'ihec', 'isg', 'fst', 'eniso', 'supcom',
        ]
        bad_indicators = [
            'master', 'licence', 'doctorat', 'phd', 'bachelor', 'ingénieur',
            'informatique', 'mathématiques', 'physique', 'chimie', 'biologie',
            'gestion', 'management', 'commerce', 'marketing', 'finance',
        ]

        def score(name: str) -> int:
            name_lower = name.lower()
            s = 0
            for indicator in good_indicators:
                if indicator in name_lower:
                    s += 3
            for indicator in bad_indicators:
                if indicator in name_lower and len(name) < 40:
                    s -= 2
            if name[0].isupper():
                s += 1
            if re.search(r'\d', name):
                s -= 1
            return s

        valid_candidates = [c for c in candidates if len(c) >= 4]
        if not valid_candidates:
            return None
        return max(valid_candidates, key=score)

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

    def _is_en_cours(self, text: str) -> bool:
        """Vérifie si le contexte mentionne que la formation est en cours."""
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
        return [b for b in blocks if len(b.strip()) > 10]

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

            # En cours ?
            en_cours = self._is_en_cours(block)

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

            # Établissement
            establishments = self._extract_establishments(block)
            establishment = self._pick_best_establishment(establishments)

            return {
                "diplome": diploma,
                "specialite": specialty,
                "etablissement": establishment,
                "annee": annee,
                "en_cours": en_cours,
                "mention": mention,
                "niveau_bac_plus": level,
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
