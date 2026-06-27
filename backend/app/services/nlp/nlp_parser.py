"""
Module NLP pour parsing et structuration de CVs - Sprint 2
Point d'entrée principal du pipeline NLP

Pipeline complet :
1. Contact (email, téléphone, LinkedIn, GitHub)
2. Entités nommées (NER) : PERSON, ORG, DATE
3. Compétences techniques (300+ skills, catégories, niveaux)
4. Formations académiques (international, 7 pays)
5. Expériences professionnelles (postes, entreprises, missions)
"""

from datetime import datetime, timezone
from typing import Dict, Optional
import logging
import re
try:
    import spacy  # type: ignore
except ImportError:  # pragma: no cover
    spacy = None
from app.services.nlp.contact_extractor import ContactExtractor
from app.services.nlp.entity_extractor import EntityExtractor
from app.services.nlp.hf_camembert import HFCamembertNameExtractor, camembert_runtime_config
from app.services.nlp.skills_extractor import SkillsExtractor
from app.services.nlp.formation_extractor import FormationExtractor
from app.services.nlp.experience_extractor import ExperienceExtractor
from app.services.nlp.sector_classifier import SectorClassifier
from app.services.nlp.language_detector import detect_language

logger = logging.getLogger(__name__)


# ── Extraction simple de langues ─────────────────────────────────
# Negative lookbehind : exclure "Programming Languages", "Scripting Languages", etc.
_LANGUES_KW = re.compile(
    r"(?<!programming\s)(?<!scripting\s)(?<!markup\s)(?<!coding\s)"
    r"(?:ma[îi]trise\s+des\s+langues"
    r"|langues?\s+parl[ée]es"
    r"|langues?\s+ma[îi]tris[ée]es"
    r"|langues?|languages?|sprachen|idiomas)\s*[:\-–]?\s*\n?",
    re.IGNORECASE,
)

# Liste consolidée des noms de langues parlées (FR + EN + variantes)
_LANGUE_NAMES = (
    r"Fran[çc]ais|French|Anglais|English|Arabe|Arabic"
    r"|Espagnol|Spanish|Allemand|German|Italien|Italian"
    r"|Portugais|Portuguese|Chinois|Chinese|Japonais|Japanese"
    r"|Russe|Russian|Turc|Turkish|Cor[ée]en|Korean"
    r"|Hindi|N[ée]erlandais|Dutch|Polonais|Polish"
    r"|H[ée]breu|Hebrew|Persan|Persian|Farsi"
    r"|Su[ée]dois|Swedish|Norv[ée]gien|Norwegian|Danois|Danish"
    r"|Finnois|Finnish|Grec|Greek|Roumain|Romanian"
    r"|Tch[èe]que|Czech|Hongrois|Hungarian|Tha[ïi]|Thai"
    r"|Vi[êe]tnamien|Vietnamese|Indon[ée]sien|Indonesian"
    r"|Malais|Malay|Swahili|Ourdou|Urdu|Bengali"
    r"|Tamoul|Tamil|T[ée]lougou|Telugu|Ukrainien|Ukrainian"
)

_NIVEAU_PATTERN = (
    r"Natif|Maternelle?|Langue\s+maternelle|Courant|Bilingue"
    r"|Professionnel(?:le)?|Interm[ée]diaire|Avanc[ée]|D[ée]butant|Scolaire"
    r"|Notions?\s*(?:de\s+)?base"
    r"|Tr[èe]s\s+bon|Bon|Moyen|Faible"
    r"|Very\s+good|Good|Average|Poor"
    r"|Native|Fluent|Bilingual|Professional|Intermediate|Advanced|Beginner|Basic"
    r"|Op[ée]rationnel(?:le)?|Technique"
    r"|C2|C1|B2\+?|B1|A2|A1"
    r"|TOEIC\s*\d+|TOEFL\s*\d+|IELTS\s*[\d.]+"
    r"|(?:[\u2605\u2606\u2B50]{1,5}|\*{1,5})"
    r"|(?:[1-5]\s*/\s*5|[1-9]\s*/\s*10)"
)

_LANGUE_LINE = re.compile(
    r"^\s*[-•▪►●◆]?\s*"
    r"(" + _LANGUE_NAMES + r")"
    r"\s*(?:[:\-–—/|]\s*|\s*\(\s*)?"
    r"(" + _NIVEAU_PATTERN + r")?"
    r"\)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_LANGUE_INLINE = re.compile(
    r"\b"
    r"(" + _LANGUE_NAMES + r")"
    r"\s*(?:[:\-–—/|]\s*|\s*\(\s*)?"
    r"(" + _NIVEAU_PATTERN + r")?"
    r"\)?\s*",
    re.IGNORECASE,
)

# Fallback global : cherche des langues n'importe où dans le texte,
# SEULEMENT quand accompagnées d'un niveau explicite (pour éviter les faux positifs)
_LANGUE_GLOBAL = re.compile(
    r"\b(" + _LANGUE_NAMES + r")"
    r"\s*(?:[:\-–—/|,]\s*|\s*\(\s*)"
    r"(" + _NIVEAU_PATTERN + r")"
    r"\)?\s*",
    re.IGNORECASE,
)

# Variante : séparateur = simple espace (ex: "French Fluent", "Arabic native")
# On garde l'exigence d'un niveau explicite pour limiter les faux positifs.
_LANGUE_GLOBAL_WS = re.compile(
    r"\b(" + _LANGUE_NAMES + r")\b"
    r"\s+"
    r"(" + _NIVEAU_PATTERN + r")\b",
    re.IGNORECASE,
)


class NLPParser:
    """
    Parser NLP principal pour extraction structurée de CVs.

    Pipeline complet :
    - spaCy fr_core_news_md (NER)
    - ContactExtractor (email, tél, LinkedIn, GitHub)
    - SkillsExtractor (300+ skills, catégories, niveaux)
    - FormationExtractor (diplômes, établissements, international)
    - ExperienceExtractor (postes, entreprises, dates, missions)
    """

    @staticmethod
    def _normalize_pdf_text(text: str) -> str:
        """Injecte les sauts de ligne nécessaires dans les PDF compacts (0 newlines)."""
        if not text:
            return text

        # ── 0. NFC : compose les accents combinants (´e → é, etc.) ──────────
        import unicodedata
        text = unicodedata.normalize("NFC", text)
        # Artefacts PDF : accent_char + ESPACE + lettre → lettre accentuée
        # ex: "´ e" → "é",  "` e" → "è",  "ˆ a" → "â"
        def _fix_pdf_accent(m):
            acc, letter = m.group(1), m.group(2)
            table = {
                "\u00b4": {"e":"é","E":"É","a":"á","A":"Á","o":"ó","O":"Ó","u":"ú","U":"Ú","i":"í","I":"Í"},
                "`":      {"e":"è","E":"È","a":"à","A":"À","o":"ò","O":"Ò","u":"ù","U":"Ù"},
                "\u02c6": {"e":"ê","E":"Ê","a":"â","A":"Â","o":"ô","O":"Ô","u":"û","U":"Û"},
                "\u02c7": {"e":"ě","c":"č","s":"š","z":"ž"},
                "\u00b8": {"c":"ç","C":"Ç"},
            }
            return table.get(acc, {}).get(letter, acc + letter)
        text = re.sub(r"([\u00b4`\u02c6\u02c7\u00b8])\s*([a-zA-Z])", _fix_pdf_accent, text)

        # ── 0c. Séparateurs OCR corrompus : "�" avant une Majuscule ──────
        # Exemple: "associ�e�Atelier" → "associée - Atelier"
        text = re.sub(r"\uFFFD(?=[A-ZÀ-Ö])", " - ", text)

        # ── 0b. Recoller les mots cassés par le PDF ─────────────────────────
        # Certains PDF insèrent un espace parasite au milieu des mots :
        # "Djang o" → "Django", "Inter nship" → "Internship", etc.
        # On utilise un dictionnaire de corrections connues puis une heuristique.
        _BROKEN_WORDS = {
            # Frameworks / Libs
            "Djang o": "Django", "Djang o-based": "Django-based",
            "TensorFlo w": "TensorFlow", "Pytorc h": "PyTorch",
            "FlutterFlo w": "FlutterFlow", "Scikit-lear n": "Scikit-learn",
            "NodeJS": "NodeJS", "Angular JS": "AngularJS",
            # Mots métier / académiques
            "Inter nship": "Internship", "inter nship": "internship",
            "Inter n ": "Intern ", "Inter n\n": "Intern\n",
            "Depar tment": "Department", "depar tment": "department",
            "Uni versity": "University", "uni versity": "university",
            "Technolo gy": "Technology", "technolo gy": "technology",
            "Intellig ence": "Intelligence", "intellig ence": "intelligence",
            "Ar tificial": "Artificial", "ar tificial": "artificial",
            "Dev elopment": "Development", "dev elopment": "development",
            "Pr ogramming": "Programming", "pr ogramming": "programming",
            "Framew orks": "Frameworks", "framew orks": "frameworks",
            "Platf orms": "Platforms", "platf orms": "platforms",
            "Mana gement": "Management", "mana gement": "management",
            "Langua ges": "Languages", "langua ges": "languages",
            "Cer tifications": "Certifications", "cer tifications": "certifications",
            "Cer tificates": "Certificates", "cer tificates": "certificates",
            "Generati ve": "Generative", "generati ve": "generative",
            "Representati ve": "Representative",
            "administrati ve": "administrative",
            "interacti ve": "interactive",
            "predicti ve": "predictive",
            "Integ rated": "Integrated", "integ rated": "integrated",
            "Baccalaur eate": "Baccalaureate",
            "Anal ytics": "Analytics", "anal ytics": "analytics",
            "transfor mation": "transformation",
            "AI-po wered": "AI-powered", "AI-P owered": "AI-Powered",
            "Pr edicti ve": "Predictive",
            "suppor t": "support",
            "Manag ed": "Managed", "manag ed": "managed",
            "anniversar y": "anniversary",
            "feedbac k": "feedback",
            "concer ns": "concerns",
            "displa yed": "displayed",
            "Pri vate": "Private", "pri vate": "private",
            "Tuni visions": "Tunivisions",
            "PhotoF olio": "PhotoFolio",
            "Galler y": "Gallery",
            "Ar t": "Art", "ar t": "art",
            "Pr oject": "Project", "pr oject": "project",
            "cer tificates": "certificates",
            "Applica tions": "Applications", "applica tions": "applications",
            "Inspecto r": "Inspector",
            "recogni tion": "recognition",
            "classifica tion": "classification",
            "regressi on": "regression",
            "clusteri ng": "clustering",
            "senti ment": "sentiment",
            "outco mes": "outcomes",
            "insi ghts": "insights",
            # Mots collés PDF (espace manquant)
            "Manag edand": "Managed and",
            "Assist edthe": "Assisted the",
            "Organiz edand": "Organized and",
            "Manag edthe": "Managed the",
            "Design edand": "Designed and",
            "Solutionfor": "Solution for",
            "Djangoweb": "Django web",
            "Modelsfrom": "Models from",
            "Learningfrom": "Learning from",
            # Espaces après virgule manquantes ou mots collés
            ",CSS": ", CSS", ",Javascript": ", Javascript",
            ",Cisco": ", Cisco", ",NodeJS": ", NodeJS",
            ",Pytorc h": ", PyTorch", ",Generati ve": ", Generative",
        }
        for broken, fixed in _BROKEN_WORDS.items():
            text = text.replace(broken, fixed)

        # 0b-bis. Mots collés : "Managedand" → "Managed and", "Djangoweb" → "Django web"
        # Pattern: mot>=5 lettres suivi directement de (and|the|for|with|from|web|app)
        _GLUED_SUFFIXES = r'(?:and|the|for|with|from|web|app|via|into|that|this|based)'
        def _split_glued(m):
            return m.group(1) + ' ' + m.group(2)
        text = re.sub(
            rf'\b([A-Za-zÀ-ö]{{3,}})({_GLUED_SUFFIXES})\b',
            _split_glued,
            text,
        )

        # Heuristique : recoller les fragments "Xxx xx" où le 2e fragment
        # est 1-3 lettres minuscules suivies d'une lettre minuscule
        # (mais pas les mots courts réels : in, de, du, le, la, en, et, or, of, at, to)
        _SHORT_REAL_WORDS = {"in", "de", "du", "le", "la", "en", "et", "ou",
                             "or", "of", "at", "to", "by", "an", "on", "it",
                             "is", "un", "se", "sa", "ce", "a", "y", "n",
                             # Prépositions FR courtes souvent collées par accident
                             "vers", "pour", "avec", "sans", "sous", "sur",
                             "dans", "dont", "mais", "donc", "tout", "très",
                             "plus", "bien", "puis", "leur", "leurs", "nous",
                             "vous", "ils", "elles", "aussi"}
        def _rejoin_broken(m):
            w1, space, w2 = m.group(1), m.group(2), m.group(3)
            if w2.lower() in _SHORT_REAL_WORDS:
                return m.group(0)  # garder tel quel
            return w1 + w2
        # "Djang o" → "Django" : mot capitalisé + espace + 1-3 lettres minuscules + lettre min
        text = re.sub(
            r'\b([A-ZÀ-Ö][a-zà-ö]{1,8})(\s)([a-zà-ö]{1,3}[a-zà-ö])\b',
            _rejoin_broken,
            text,
        )

        # ── 1. Inject \n\n AVANT les titres de section ──────────────────────
        # (?<!\n)\s+ : uniquement si précédé d'un espace (pas déjà en début de ligne)
        # IMPORTANT : les mots simples (formation, expérience…) ne sont
        # matchés qu'en MAJUSCULES via (?-i:…) pour ne pas casser les
        # phrases contenant ces mots en minuscule.
        section_pattern = re.compile(
            r"(?<!\n)\s+"
            r"("
            # ── Multi-word patterns – case-insensitive (safe) ──
            r"EXP[ÉE]RIENCES?\s+PROFESSIONNELLES?"
            r"|PARCOURS\s+PROFESSIONNEL?"
            r"|FORMATIONS?\s+AC?AD[ÉE]MIQUES?"
            r"|DIPL[ÔO]MES?\s*&\s*[ÉE]TUDES"
            r"|COMP[ÉE]TENCES?\s+(?:TECHNIQUES?|CL[ÉE]S?|PROFESSIONNELLES?)"
            r"|MA[ÎI]TRISE\s+DES\s+LANGUES"
            r"|LANGUES?\s+PARL[ÉE]ES?"
            r"|PROFIL\s+PROFESSIONNEL?"
            r"|PROJETS?\s+(?:PERSONNELS?|AC?AD[ÉE]MIQUES?)"
            r"|SAVOIR[\s\-]FAIRE"
            r"|ENGAGEMENTS?\s*&\s*ACTIVIT[ÉE]S?"
            r"|[ÀA]\s+PROPOS(?:\s+DE\s+MOI)?"
            r"|CERTIFICATIONS?\s+PROFESSIONNELLES?"
            # ── Multi-word patterns EN – case-insensitive (safe) ──
            r"|Work\s+Experiences?"
            r"|Professional\s+Experiences?"
            r"|Employment\s+(?:History|Summary)"
            r"|Career\s+(?:History|Summary)"
            r"|Academic\s+(?:Background|Projects?)"
            r"|Professional\s+Background"
            r"|Work\s+Background"
            # ── Single words – ALL CAPS only (prevent false positives) ──
            r"|(?-i:EXP[ÉE]RIENCES?)"
            r"|(?-i:FORMATIONS?)"
            r"|(?-i:DIPL[ÔO]MES?)"
            r"|(?-i:[ÉE]TUDES?)"
            r"|(?-i:COMP[ÉE]TENCES?)"
            r"|(?-i:SKILLS)"
            r"|(?-i:LANGUES?)"
            r"|(?-i:CERTIFICATIONS?)"
            r"|(?-i:PROJETS?)"
            r"|(?-i:PARCOURS)"
            r"|(?-i:PROFIL)"
            r"|(?-i:[ÉE]DUCATION)"
            r"|(?-i:SCOLARIT[ÉE])"
            r"|(?-i:CONTACT)"
            r"|(?-i:R[ÉE]F[ÉE]RENCES?)"
            r"|(?-i:PUBLICATIONS?)"
            # ── EN single words (title-case safe, unlikely false positives) ──
            r"|Education"
            r"|Skills"
            r"|Languages"
            r"|Certifications?"
            r"|Qualifications?"
            r"|Publications?"
            r"|Profile"
            r"|Summary"
            r"|Objective"
            r")"
            r"(?!\w)",
            re.IGNORECASE,
        )

        # ── 1b. Séparer les en-têtes collés à une année (ex: "2018PARCOURS") ──
        text = re.sub(
            r"(\d{4})(?=(?:EXP[ÉE]RIENCES?|PARCOURS|FORMATIONS?|DIPL[ÔO]MES?"
            r"|COMP[ÉE]TENCES?|LANGUES?|PROFIL|PROJETS?|REALISATIONS?|CERTIFICATIONS?))",
            r"\1\n",
            text,
            flags=re.IGNORECASE,
        )
        text = section_pattern.sub(r"\n\n\1\n", text)

        # ── 1a. Séparer les mots collés CamelCase après une date ──────────────
        # "2015–2017Master of Science" → "2015–2017\nMaster of Science"
        # "2020–PresentSenior" → "2020–Present\nSenior"
        text = re.sub(
            r'(\d{4}|[Pp]resent|[Aa]ctuel(?:lement)?)([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ])',
            r'\1\n\2',
            text,
        )

        # ── 1a-bis. Séparer mot_minuscule + année collée ─────────────────────
        # "Intelligence2024" → "Intelligence\n2024"
        text = re.sub(r'([a-zà-öø-ÿ])(\d{4})\b', r'\1\n\2', text)

        # ── 1a-ter. Séparer Present/Actuel + mot MAJUSCULE (avec espace) ─────
        # "Present ESPRIT" → "Present\nESPRIT", "présent ESPRIT" → "présent\nESPRIT"
        text = re.sub(
            r'\b(Pr[ée]sent|Present|Actuel(?:lement)?)\s+(?=[A-ZÀ-ÖØ-Þ])',
            r'\1\n',
            text,
            flags=re.IGNORECASE,
        )

        # ── 1a-quater. Séparer mot_minuscule + Mois (CamelCase) ──────────────
        # "WebsiteApril" → "Website\nApril", "ScientistJune" → "Scientist\nJune"
        text = re.sub(
            r'([a-zà-öø-ÿ])'
            r'((?:Jan(?:uary|vier)?|Feb(?:ruary)?|F[eé]vr(?:ier)?|'
            r'Mar(?:ch|s)?|Apr(?:il)?|Avr(?:il)?|Ma[iy]|June?|Juin|'
            r'July?|Juil(?:let)?|Aug(?:ust)?|Ao[uû]t|'
            r'Sep(?:t(?:ember|embre)?)?|Oct(?:o(?:ber|bre)?)?|'
            r'Nov(?:ember|embre)?|Dec(?:ember)?|D[éeè]c(?:embre)?)\b)',
            r'\1\n\2',
            text,
        )

        # ── 1a-quinquies. Séparer Season+Year du texte précédent ─────────────
        # "...optimization Summer 2016" → "...optimization\nSummer 2016"
        text = re.sub(
            r'(?<=[a-zà-öø-ÿ])\s+'
            r'((?:Summer|Winter|Spring|Fall|Autumn|[ÉE]t[ée]|Printemps|Automne|Hiver)'
            r'\s+\d{4})\b',
            r'\n\1',
            text,
            flags=re.IGNORECASE,
        )

        # ── 1b. Nettoyer décorations et symboles (box-drawing, bullets déco) ──
        text = re.sub(r'[║╔╗╚╝═╠╣╬►▪◆→]', '', text)
        text = re.sub(r'[^\S\n]{2,}', ' ', text)  # collapse espaces horizontaux seulement

        # ── 2. Inject \n AVANT les titres de postes (pour CV compacts inline) ──
        # Permet de séparer "...WebAgency 2023 - Présent Développeur Junior..."
        text = re.sub(
            r"(?<!\n)\s+(?="
            r"(?:DRH|Responsable|Charg[ée]e?|Assistant(?:e)?|Ing[ée]nieur"
            r"|D[ée]veloppeu(?:r|se)|Consultant|Manager|Directeur|Chef\s+de"
            r"|Analyste|Coordinateur|Gestionnaire|Technicien"
            r"|Électricien|Electricien|Plombier|Ma[çc]on|Menuisier"
            r"|M[ée]canicien|Soudeur|Peintre"
            r"|Infirmi[èe]re?|Aide[\-\s]Soignant"
            r"|Expert[\-\s]?Comptable|Comptable|Auditeur|Auditrice"
            r"|Stagiaire|Alternant(?:e)?|Apprenti(?:e)?"
            r"|Pharmacien|M[ée]decin|Sage[\-\s]Femme"
            r"|Community\s+Manager|Digital\s+Marketing|Social\s+Media|Growth\s+Hacker"
            # EN job titles
            r"|(?:Senior|Junior|Lead|Principal|Staff)\s+(?:Software\s+|Data\s+)?(?:Engineer|Developer|Analyst|Scientist)"
            r"|Software\s+(?:Engineer|Developer|Architect)"
            r"|(?:Front[\s\-]?end|Back[\s\-]?end|Full[\s\-]?Stack)\s+(?:Developer|Engineer)"
            r"|Data\s+(?:Scientist|Analyst|Engineer)"
            r"|Project\s+Manager|Product\s+Manager|Program\s+Manager"
            r"|(?:QA|Test|Quality)\s+(?:Engineer|Analyst)"
            r"|(?:DevOps|SRE|Infrastructure)\s+Engineer"
            r"|(?:UX|UI|UX[/\s]UI)\s+(?:Designer|Researcher)"
            r"|(?:Business|Systems?)\s+(?:Analyst|Architect)"
            r"|(?:Solutions?|Cloud|Enterprise)\s+Architect"
            r"|Intern(?:\s+[\-\u2013])?|Trainee|Apprentice"
            r"|Freelanc(?:e|er))\b"
            r")",
            r"\n",
            text,
            flags=re.IGNORECASE,
        )

        # ── 2b. Recoller les titres composés accidentellement séparés ────
        # "Senior\nData Scientist" → "Senior Data Scientist"
        text = re.sub(
            r'\n((?:Senior|Junior|Lead|Principal|Staff|Chief))\n'
            r'((?:Software|Data|Front|Back|Full|DevOps|QA|Test|Quality|Project|'
            r'Product|Program|Network|Systems?|Business|Cloud|Solutions?|'
            r'Enterprise|Site|Machine|Platform|Web|Mobile))',
            r'\n\1 \2',
            text,
            flags=re.IGNORECASE,
        )

        # ── 2c. Recoller Title + Intern/Trainee séparés ──────────────────────
        # "Developer\nIntern" → "Developer Intern"
        text = re.sub(
            r'((?:Developer|Engineer|Analyst|Scientist|Designer|Manager|Architect|Consultant))\n'
            r'((?:Intern|Trainee|Apprentice)\b)',
            r'\1 \2',
            text,
            flags=re.IGNORECASE,
        )

        # ── 3. Bullets (•, ●, ►, ▪, ✓, \x7f byte-127) → nouvelle ligne ────
        text = re.sub(r"\s*([•●►▪✓\x7f])\s*", r"\n• ", text)

        # ── 4. Em dash (—) comme séparateur de blocs compacts ────────────────
        text = re.sub(r"\s+—\s+", "\n— ", text)

        # ── 5. Nettoyer les lignes vides en excès ────────────────────────────
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    @staticmethod
    def _derive_name_from_email(email: Optional[str]) -> Optional[str]:
        """Tente de dériver un nom lisible depuis un email (prenom.nom@...).

        Retourne None si le format est trop ambigu (initiales, chiffres, etc.).
        """
        if not email or "@" not in email:
            return None
        local = email.split("@", 1)[0].strip().lower()
        if not local:
            return None

        # Enlever des tags type "+recrut" et les chiffres parasites
        local = local.split("+", 1)[0]
        local = re.sub(r"\d+$", "", local)
        if not local:
            return None

        # Segments séparés par ., _, -
        parts = [p for p in re.split(r"[._\-]+", local) if p]

        # Fallback: local-part concaténé (pas de séparateurs).
        # On reste conservateur et on ne gère que des particules très discriminantes
        # (ex: "inesbensaad" → "Ines Ben Saad").
        if len(parts) < 2:
            compact = re.sub(r"[^a-zà-öø-ÿ]+", "", local)
            if not compact:
                return None

            # Éviter les emails trop "tech" (support, contact, hr...)
            banned = {"contact", "support", "hr", "recrutement", "recruitment", "jobs", "career", "admin"}
            if compact in banned:
                return None

            m = re.fullmatch(r"([a-zà-öø-ÿ]{3,})(ben|ibn|bint)([a-zà-öø-ÿ]{3,})", compact)
            if not m:
                return None

            first, particle, last = m.group(1), m.group(2), m.group(3)
            parts = [first, particle, last]

        first, last = parts[0], parts[1]
        # Éviter les emails basés sur initiales (a.b@...)
        if len(first) < 2 or len(last) < 2:
            return None
        # Éviter les emails trop "tech" (support, contact, hr...)
        banned = {"contact", "support", "hr", "recrutement", "recruitment", "jobs", "career", "admin"}
        if first in banned or last in banned:
            return None

        def _title(s: str) -> str:
            s = re.sub(r"[^a-zà-öø-ÿ']+", "", s)
            if not s:
                return ""
            return s[0].upper() + s[1:]

        first_t = _title(first)
        last_t = _title(last)
        if not first_t or not last_t:
            return None

        # Cas "ben/ibn/bint" : on retourne 3 mots (Prénom Particule Nom)
        if len(parts) >= 3 and parts[1] in {"ben", "ibn", "bint"}:
            particle_t = _title(parts[1])
            last2_t = _title(parts[2])
            if not particle_t or not last2_t:
                return None
            return f"{first_t} {particle_t} {last2_t}"

        return f"{first_t} {last_t}"

    @staticmethod
    def _is_name_suspicious(name: Optional[str]) -> bool:
        if not name:
            return True
        candidate = " ".join(str(name).split()).strip()
        if len(candidate) < 3 or len(candidate) > 80:
            return True
        if any(ch.isdigit() for ch in candidate):
            return True
        if "@" in candidate or ":" in candidate:
            return True

        words = candidate.split()
        if len(words) < 2 or len(words) > 5:
            return True

        def norm_letters(s: str) -> str:
            return re.sub(r"[^a-zà-öø-ÿ]+", "", s.lower())

        joined = norm_letters("".join(words))
        banned_joined = {
            "formation", "competences", "compétences", "experience", "expérience",
            "experiences", "expériences",
            "experienceprofessionnelle", "experienceprofessionnelles",
            "experiencesprofessionnelle", "experiencesprofessionnelles",
            "experiencesprofessionnel", "experiencesprofessionnels",
            "profil", "contact", "langues", "languages", "skills", "education",
            "projets", "projects", "certifications", "references", "références",
            "objective", "objectif", "resume", "résumé", "curriculumvitae",
            "devops", "fullstack",
        }
        banned_norm = {norm_letters(x) for x in banned_joined}
        if joined in banned_norm:
            return True

        jobish = {
            "dev", "ops", "devops", "engineer", "developer", "architect", "manager",
            "analyst", "consultant", "designer", "fullstack", "frontend", "backend",
            "data", "scientist", "lead", "senior", "junior",
        }
        # Services/départements + établissements (souvent pris à tort comme nom)
        section_org = {
            "ressources", "humaines", "humaine", "ressource", "achats", "ventes",
            "vente", "production", "qualite", "logistique", "juridique",
            "administratif", "direction", "service", "services", "departement",
            "pole", "unite", "secteur", "division",
            "centre", "universite", "lycee", "societe", "entreprise", "groupe",
            "hopital", "clinique", "cabinet", "institut", "ecole", "faculte",
            "fondation", "association", "sarl", "sas", "suarl",
        }
        for w in words:
            wl = norm_letters(w)
            if wl in banned_norm:
                return True
            # Titres de sections fréquents dans les CV (souvent pris à tort comme nom)
            if wl in {"professionnel", "professionnelle", "professionnels", "professionnelles"}:
                return True
            if wl in jobish:
                return True
            if wl in section_org:
                return True
        return False

    @staticmethod
    def _normalize_name_for_match(name: Optional[str]) -> str:
        """Normalise un nom pour comparaison (insensible aux accents / casse / ponctuation)."""
        if not name:
            return ""
        import unicodedata

        s = " ".join(str(name).split()).strip().lower()
        # Retirer les accents (NFKD + suppression combining marks)
        s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
        # Garder uniquement lettres et espaces
        s = re.sub(r"[^a-zà-öø-ÿ ]+", " ", s)
        return " ".join(s.split()).strip()

    @classmethod
    def _names_overlap(cls, a: Optional[str], b: Optional[str]) -> bool:
        """True si deux noms partagent au moins un token significatif (≥ 3 lettres).

        Sert à détecter quand un nom extrait (header/NER) CONTREDIT totalement le
        nom dérivé de l'email du candidat (aucun token commun → faux positif probable).
        """
        ta = {w for w in cls._normalize_name_for_match(a).split() if len(w) >= 3}
        tb = {w for w in cls._normalize_name_for_match(b).split() if len(w) >= 3}
        if not ta or not tb:
            return True  # info insuffisante → ne pas trancher contre l'extracteur
        return bool(ta & tb)


    def __init__(self, model_name: str = "fr_core_news_md"):
        self.model_name = model_name
        self._nlp = None        # Lazy loading — modèle FR
        self._nlp_en = None     # Lazy loading — modèle EN (optionnel)
        self._multilingual = False  # True si en_core_web_md disponible
        self._contact_extractor = ContactExtractor()
        self._skills_extractor = SkillsExtractor()
        self._sector_classifier = SectorClassifier()
        self._formation_extractor = None   # Needs spaCy model
        self._experience_extractor = None  # Needs spaCy model

        # Infos runtime sur spaCy (exposées dans metadata)
        self._spacy_loaded_model: Optional[str] = None
        self._spacy_fallback: Optional[bool] = None
        self._spacy_has_ner: Optional[bool] = None
        self._spacy_pipes: list[str] = []
        self._spacy_version: Optional[str] = None
        logger.info(f"NLPParser initialisé (modèle: {model_name})")

    def _load_model(self):
        """Charge les modèles spaCy FR + EN (lazy loading) et initialise les extracteurs."""
        if self._nlp is None:
            if spacy is None:
                raise RuntimeError(
                    "spaCy n'est pas installé. Installez les dépendances backend (requirements.txt) "
                    "et exécutez ensuite: python -m spacy download fr_core_news_md"
                )
            logger.info(f"Chargement modèle spaCy : {self.model_name}...")
            try:
                self._nlp = spacy.load(self.model_name)
                self._spacy_loaded_model = self.model_name
                self._spacy_fallback = False
            except Exception as e:
                logger.warning(
                    "Impossible de charger le modèle spaCy '%s' (%s). Fallback vers spacy.blank('fr').",
                    self.model_name,
                    e,
                )
                self._nlp = spacy.blank("fr")
                self._spacy_loaded_model = "blank:fr"
                self._spacy_fallback = True

            # Charger modèle anglais si disponible (optionnel)
            try:
                self._nlp_en = spacy.load("en_core_web_md")
                self._multilingual = True
                logger.info("Modèle EN chargé : en_core_web_md — mode multilingue actif")
            except Exception:
                self._nlp_en = None
                self._multilingual = False
                logger.info("en_core_web_md non disponible — mode FR uniquement")

            # Capturer infos pipeline
            try:
                self._spacy_pipes = list(getattr(self._nlp, "pipe_names", []) or [])
                self._spacy_has_ner = bool(getattr(self._nlp, "has_pipe", lambda _: False)("ner"))
            except Exception:
                self._spacy_pipes = []
                self._spacy_has_ner = None
            self._spacy_version = getattr(spacy, "__version__", None)

            self._formation_extractor = FormationExtractor(nlp_model=self._nlp)
            self._experience_extractor = ExperienceExtractor(nlp_model=self._nlp)
            self._skills_extractor = SkillsExtractor(nlp_model=self._nlp)
            logger.info("Modèles spaCy + extracteurs chargés")
        return self._nlp

    @staticmethod
    def _extract_langues(text: str):
        """
        Extraction des langues parlées depuis le texte du CV.

        Stratégie en 2 passes :
        1. Chercher une section explicite (Langues:, Languages:, etc.)
           et en extraire les langues ligne par ligne ou inline
        2. Fallback global : scanner tout le texte pour des mentions
           « Langue + niveau » (ex: "Français (Courant)", "English: Fluent")
        """
        langues = []
        seen = set()

        # ── Pass 1 : Section explicite ───────────────────────────────
        for m in _LANGUES_KW.finditer(text):
            # Vérifier que ce n'est pas "Programming Languages" etc.
            prefix_start = max(0, m.start() - 30)
            prefix = text[prefix_start: m.start()].lower()
            if re.search(r"\b(?:programming|scripting|markup|coding|query)\s*$", prefix):
                continue  # faux positif → ignorer

            section = text[m.end(): m.end() + 1200]

            # Couper à la prochaine section
            end = re.search(
                r"\b(?:comp[ée]tences?|savoir[\s\-]faire|formation|dipl[ôo]mes?|"
                r"exp[ée]rience|parcours|projets?|engagements?|publications?|"
                r"passions?|loisirs?|r[ée]f[ée]rences?|skills?|education"
                r"|hobbies?|interests?|certifications?)\b",
                section,
                re.IGNORECASE,
            )
            if end and end.start() > 40:
                section = section[: end.start()]

            for lm in _LANGUE_LINE.finditer(section):
                langue = lm.group(1).strip()
                niveau = (lm.group(2) or "").strip() or None
                if langue:
                    key = (langue.lower(), (niveau or "").lower())
                    if key not in seen:
                        seen.add(key)
                        langues.append({"langue": langue, "niveau": niveau})

            for lm in _LANGUE_INLINE.finditer(section):
                langue = lm.group(1).strip()
                niveau = (lm.group(2) or "").strip() or None
                if langue:
                    key = (langue.lower(), (niveau or "").lower())
                    if key not in seen:
                        seen.add(key)
                        langues.append({"langue": langue, "niveau": niveau})

            if langues:
                break  # trouvé dans une section, pas besoin de continuer

        # ── Pass 2 : Fallback global (langue + niveau n'importe où) ──
        if not langues:
            for lm in _LANGUE_GLOBAL.finditer(text):
                langue = lm.group(1).strip()
                niveau = (lm.group(2) or "").strip() or None
                if langue:
                    key = (langue.lower(), (niveau or "").lower())
                    if key not in seen:
                        seen.add(key)
                        langues.append({"langue": langue, "niveau": niveau})

            for lm in _LANGUE_GLOBAL_WS.finditer(text):
                langue = lm.group(1).strip()
                niveau = (lm.group(2) or "").strip() or None
                if langue:
                    key = (langue.lower(), (niveau or "").lower())
                    if key not in seen:
                        seen.add(key)
                        langues.append({"langue": langue, "niveau": niveau})

        # ── Normalisation des niveaux ─────────────────────────────────────────
        _NIVEAU_NORM = {
            # Natif
            "natif": "Natif", "native": "Natif", "maternelle": "Langue maternelle",
            "langue maternelle": "Langue maternelle", "mother tongue": "Langue maternelle",
            # Bilingue
            "bilingue": "Bilingue", "bilingual": "Bilingue",
            # Courant / Fluent
            "courant": "Courant", "fluent": "Courant", "professionnel": "Professionnel",
            "professionelle": "Professionnel", "professional": "Professionnel",
            "très bon": "Courant", "very good": "Courant",
            # Avancé
            "avancé": "Avancé", "advanced": "Avancé", "bon": "Avancé",
            "good": "Avancé", "c1": "Avancé (C1)", "c2": "Courant (C2)",
            # Intermédiaire
            "intermédiaire": "Intermédiaire", "intermediate": "Intermédiaire",
            "moyen": "Intermédiaire", "average": "Intermédiaire",
            "b1": "Intermédiaire (B1)", "b2": "Intermédiaire (B2)",
            # Débutant / Scolaire
            "débutant": "Débutant", "beginner": "Débutant", "scolaire": "Scolaire",
            "notions": "Notions", "notions de base": "Notions", "basic": "Notions",
            "faible": "Débutant", "poor": "Débutant",
            "a1": "Débutant (A1)", "a2": "Débutant (A2)",
            # Opérationnel
            "opérationnel": "Opérationnel", "opérationelle": "Opérationnel",
            "technique": "Opérationnel",
        }
        for lang in langues:
            raw_niv = (lang.get("niveau") or "").strip()
            if not raw_niv:
                lang["niveau"] = "Non spécifié"
            else:
                normalized = _NIVEAU_NORM.get(raw_niv.lower())
                if normalized:
                    lang["niveau"] = normalized
                # sinon garder la valeur originale (TOEIC 850, ★★★, etc.)

        return langues

    def parse(self, text: str, cv_id: Optional[str] = None) -> Dict:
        """
        Parse un CV et extrait toutes les informations structurées.

        Returns:
            Dict CVDataStructured-compatible :
            {
                "success": bool,
                "cv_id": str,
                "parsed_data": {
                    "identite": {...},
                    "contacts": {...},
                    "competences": [...],
                    "formations": [...],
                    "experiences": [...],
                    "langues": [...],
                    "competences_par_categorie": {...},
                    "metadata": {...}
                },
                "error": str or None
            }
        """
        logger.info(f"Début parsing NLP complet (cv_id: {cv_id})")

        # Trace CamemBERT (HF)
        hf_cfg = {}
        try:
            hf_cfg = camembert_runtime_config() or {}
        except Exception:
            hf_cfg = {}
        hf_enabled = bool(hf_cfg.get("enabled"))
        hf_model = hf_cfg.get("model")
        hf_timeout = hf_cfg.get("timeout_seconds")
        hf_attempted = False
        hf_used = False

        result = {
            "success": False,
            "cv_id": cv_id,
            "parsed_data": {},
            "error": None,
        }

        # Validation entrée
        if not text or len(text.strip()) < 50:
            result["error"] = "Texte trop court pour parsing (minimum 50 caractères)"
            logger.error(result["error"])
            return result

        # Pré-normalisation : certains PDF compact exportent tout sur 1 ligne
        original_lines = text.count("\n")
        text = self._normalize_pdf_text(text)
        added_lines = text.count("\n") - original_lines
        if added_lines > 0:
            logger.info("_normalize_pdf_text : +%d sauts de ligne ajoutés", added_lines)

        try:
            # ── 0. Charger spaCy + extracteurs ───────────────────────
            nlp = self._load_model()

            # ── 0b. Détecter la langue du CV ─────────────────────────
            lang_info = detect_language(text)
            cv_langue = lang_info["langue"]   # "fr" ou "en"
            lang_confiance = lang_info["confiance"]
            lang_bilingue = lang_info.get("bilingue", False)
            lang_methode = lang_info.get("methode", "unknown")

            # Choisir le modèle spaCy selon la langue détectée
            if cv_langue == "en" and self._multilingual and self._nlp_en is not None:
                nlp_active = self._nlp_en
                nlp_active_name = "en_core_web_md"
                logger.info("CV anglais détecté (%.0f%%) — modèle EN actif", lang_confiance * 100)
            else:
                nlp_active = nlp
                nlp_active_name = self._spacy_loaded_model or self.model_name
                logger.info("CV %s détecté (%.0f%%) — modèle FR actif", cv_langue.upper(), lang_confiance * 100)

            entity_extractor = EntityExtractor(nlp_active)

            # Liste des erreurs partielles (pipeline continue malgré tout)
            errors: list = []

            # ── 1. CONTACT ───────────────────────────────────────────
            contact_data = {}
            full_name = None
            name_source = None
            name_candidates = {
                "entity_extractor": None,
                "hf_camembert": None,
                "email": None,
            }
            name_conflict = False
            try:
                contact_data = self._contact_extractor.extract(text)
                logger.info("ContactExtractor OK — email=%s, phone=%s, linkedin=%s",
                            contact_data.get("primary_email"), contact_data.get("primary_phone"),
                            contact_data.get("linkedin"))
            except Exception as e:
                logger.error("Erreur ContactExtractor : %s", e, exc_info=True)
                errors.append({"module": "contact_extractor", "error": str(e)})

            # ── 1b. Nom (IA + heuristiques) ──────────────────────────
            # Politique: on tente CamemBERT *systématiquement* (si configuré),
            # et on garde un fallback heuristique + email pour garantir robustesse.
            try:
                candidate = entity_extractor.extract_full_name(text)
                if candidate and not self._is_name_suspicious(candidate):
                    name_candidates["entity_extractor"] = candidate
            except Exception as e:
                logger.error("Erreur EntityExtractor : %s", e, exc_info=True)
                errors.append({"module": "entity_extractor", "error": str(e)})

            try:
                # On marque "attempted" uniquement si CamemBERT est activé.
                hf_attempted = hf_enabled
                hf_name = HFCamembertNameExtractor().extract_person_name(text)
                if hf_name and not self._is_name_suspicious(hf_name):
                    name_candidates["hf_camembert"] = hf_name
            except Exception as e:
                # Ne doit jamais bloquer le pipeline
                logger.info("CamemBERT/HF ignoré: %s", str(e))

            derived = self._derive_name_from_email(contact_data.get("primary_email"))
            if derived and not self._is_name_suspicious(derived):
                name_candidates["email"] = derived

            # Décision finale
            # Priorité : entity_extractor (5 passes, optimisé CVs) > CamemBERT (complément) > email
            # CamemBERT ne remplace entity_extractor QUE s'il est absent — pas de confiance aveugle.
            if name_candidates["entity_extractor"]:
                # Validation croisée email : l'email est l'adresse réelle du candidat.
                # Si le nom extrait ne partage AUCUN token avec le nom dérivé de
                # l'email, l'extracteur a probablement capté un lieu/service/établissement
                # (ex: "Charles Nicolle" = hôpital) → on fait confiance à l'email.
                if name_candidates["email"] and not self._names_overlap(
                    name_candidates["entity_extractor"], name_candidates["email"]
                ):
                    full_name = name_candidates["email"]
                    name_source = "email_override"
                    name_conflict = True
                    logger.info(
                        "Nom: email prioritaire (aucun token commun) — entity=%r email=%r",
                        name_candidates["entity_extractor"], name_candidates["email"],
                    )
                elif name_candidates["hf_camembert"]:
                    norm_entity = self._normalize_name_for_match(name_candidates["entity_extractor"])
                    norm_hf = self._normalize_name_for_match(name_candidates["hf_camembert"])
                    if norm_entity == norm_hf:
                        full_name = name_candidates["entity_extractor"]
                        name_source = "entity_extractor+hf_camembert"
                    else:
                        # En cas de désaccord, entity_extractor gagne (spécialisé CVs)
                        full_name = name_candidates["entity_extractor"]
                        name_source = "entity_extractor"
                        name_conflict = True
                else:
                    full_name = name_candidates["entity_extractor"]
                    name_source = "entity_extractor"
            elif name_candidates["hf_camembert"]:
                # CamemBERT utilisé uniquement si entity_extractor n'a rien trouvé
                full_name = name_candidates["hf_camembert"]
                name_source = "hf_camembert"
            elif name_candidates["email"]:
                full_name = name_candidates["email"]
                name_source = "email"

            if name_conflict:
                logger.info(
                    "Nom conflict entity vs hf (cv_id=%s) — entity_extractor retenu: entity=%r hf=%r",
                    cv_id,
                    name_candidates["entity_extractor"],
                    name_candidates["hf_camembert"],
                )
            elif full_name and name_source == "hf_camembert":
                logger.info("Nom via CamemBERT/HF (entity vide) (cv_id=%s): %s", cv_id, full_name)
            elif full_name and name_source == "email":
                logger.info("Nom dérivé depuis email (cv_id=%s): %s", cv_id, full_name)

            hf_used = bool(name_source in {"hf_camembert", "hf_camembert_override"})

            # ── 2. COMPÉTENCES ───────────────────────────────────────
            skills_data = {"skills": [], "by_category": {}, "total_skills": 0}
            try:
                skills_data = self._skills_extractor.extract(text)
                logger.info("SkillsExtractor OK — %d compétences", skills_data.get("total_skills", 0))
            except Exception as e:
                logger.error("Erreur SkillsExtractor : %s", e, exc_info=True)
                errors.append({"module": "skills_extractor", "error": str(e)})

            # ── 2b. CLASSIFICATION SECTORIELLE ───────────────────────
            sector_data = {"secteur": "inconnu", "label": "Non déterminé", "confiance": 0.0,
                           "secteurs_secondaires": [], "methode": "skills_distribution+text_signals"}
            try:
                sector_data = self._sector_classifier.classify(
                    by_category=skills_data.get("by_category", {}),
                    raw_text=text,
                )
                logger.info(
                    "SectorClassifier OK — secteur: %s (confiance: %.0f%%)",
                    sector_data.get("secteur"),
                    sector_data.get("confiance", 0) * 100,
                )
            except Exception as e:
                logger.error("Erreur SectorClassifier : %s", e, exc_info=True)
                errors.append({"module": "sector_classifier", "error": str(e)})

            # ── 3. FORMATIONS ────────────────────────────────────────
            # Pour les CVs EN, on utilise un extracteur avec le modèle EN
            formation_data = {"formations": [], "niveau_max": 0}
            try:
                if cv_langue == "en" and self._multilingual and self._nlp_en is not None:
                    _form_ext = FormationExtractor(nlp_model=self._nlp_en)
                else:
                    _form_ext = self._formation_extractor
                formation_data = _form_ext.extract(text)
                logger.info("FormationExtractor OK — %d formations", len(formation_data.get("formations", [])))
            except Exception as e:
                logger.error("Erreur FormationExtractor : %s", e, exc_info=True)
                errors.append({"module": "formation_extractor", "error": str(e)})

            # ── 4. EXPÉRIENCES ───────────────────────────────────────
            experience_data = {"experiences": [], "annees_experience_totales": 0}
            try:
                if cv_langue == "en" and self._multilingual and self._nlp_en is not None:
                    _exp_ext = ExperienceExtractor(nlp_model=self._nlp_en)
                else:
                    _exp_ext = self._experience_extractor
                experience_data = _exp_ext.extract(text)
                logger.info("ExperienceExtractor OK — %d expériences", len(experience_data.get("experiences", [])))
            except Exception as e:
                logger.error("Erreur ExperienceExtractor : %s", e, exc_info=True)
                errors.append({"module": "experience_extractor", "error": str(e)})

            # ── 5. LANGUES ───────────────────────────────────────────
            langues = []
            try:
                langues = self._extract_langues(text)
            except Exception as e:
                logger.error("Erreur extraction langues : %s", e, exc_info=True)
                errors.append({"module": "langues", "error": str(e)})

            # ── 6. ASSEMBLER LE RÉSULTAT ─────────────────────────────
            formations = formation_data.get("formations", [])
            experiences = experience_data.get("experiences", [])
            skills = skills_data.get("skills", [])

            # ── Calcul confidence ─────────────────────────────────────────────
            # Score de complétude ET de qualité, 100% répartis sur 8 dimensions.
            # Retourne aussi un breakdown détaillé + liste des champs manquants.
            #
            # Répartition : nom(12) + email(8) + tel(5) + compétences(20)
            #               + formations(20) + expériences(20) + langues(8) + cohérence(7)

            breakdown: dict = {}

            # ── Nom (12%) — qualité selon source ─────────────────────────────
            if full_name:
                if name_source == "entity_extractor+hf_camembert":
                    _nom_s = 0.12   # double confirmation
                    _nom_d = "double confirmation (spaCy + CamemBERT)"
                elif name_source in ("entity_extractor", "hf_camembert"):
                    _nom_s = 0.10
                    _nom_d = f"source unique ({name_source})"
                else:
                    _nom_s = 0.06   # email-based ou fallback
                    _nom_d = "fallback heuristique"
            else:
                _nom_s = 0.0
                _nom_d = "non trouvé"
            breakdown["nom"] = {"score": _nom_s, "max": 0.12, "detail": _nom_d}

            # ── Email (8%) ────────────────────────────────────────────────────
            _email_s = 0.08 if contact_data.get("primary_email") else 0.0
            breakdown["email"] = {"score": _email_s, "max": 0.08,
                                  "detail": contact_data.get("primary_email") or "absent"}

            # ── Téléphone (5%) ────────────────────────────────────────────────
            _tel_s = 0.05 if contact_data.get("primary_phone") else 0.0
            breakdown["telephone"] = {"score": _tel_s, "max": 0.05,
                                      "detail": contact_data.get("primary_phone") or "absent"}

            # ── Compétences (20%) — quantité + diversité catégories + qualité ─
            _n_skills = len(skills)
            _n_cats = len({s.get("category") for s in skills if s.get("category")})
            _n_fuzzy = sum(1 for s in skills if s.get("source") == "fuzzy")
            _fuzzy_ratio = _n_fuzzy / max(_n_skills, 1)
            if _n_skills >= 10 and _n_cats >= 3:
                _sk_s = 0.20
                _sk_d = f"{_n_skills} skills, {_n_cats} catégories — excellent"
            elif _n_skills >= 10 or (_n_skills >= 6 and _n_cats >= 2):
                _sk_s = 0.16
                _sk_d = f"{_n_skills} skills, {_n_cats} catégories — bon"
            elif _n_skills >= 5:
                _sk_s = 0.12
                _sk_d = f"{_n_skills} skills, {_n_cats} catégorie(s) — moyen"
            elif _n_skills > 0:
                _sk_s = 0.06
                _sk_d = f"{_n_skills} skill(s) — faible"
            else:
                _sk_s = 0.0
                _sk_d = "aucune compétence"
            # Malus qualité si > 40% sont corrigés par fuzzy (incertitude orthographique)
            if _fuzzy_ratio > 0.4 and _sk_s > 0:
                _sk_s = max(0.0, _sk_s - 0.04)
                _sk_d += f" (malus -4% : {_n_fuzzy}/{_n_skills} fuzzy)"
            breakdown["competences"] = {"score": _sk_s, "max": 0.20, "detail": _sk_d}

            # ── Formations (20%) ──────────────────────────────────────────────
            if formations:
                has_diplome = any(f.get("diplome") for f in formations)
                has_ecole = any(f.get("etablissement") for f in formations)
                has_annee = any(f.get("annee") for f in formations)
                if has_diplome and has_ecole and has_annee:
                    _fo_s = 0.20
                    _fo_d = "diplôme + établissement + dates"
                elif has_diplome and has_ecole:
                    _fo_s = 0.16
                    _fo_d = "diplôme + établissement (dates manquantes)"
                elif has_diplome or has_ecole:
                    _fo_s = 0.10
                    _fo_d = "partiel (diplôme ou établissement)"
                else:
                    _fo_s = 0.05
                    _fo_d = "formations sans détails"
            else:
                _fo_s = 0.0
                _fo_d = "aucune formation"
            breakdown["formations"] = {"score": _fo_s, "max": 0.20, "detail": _fo_d}

            # ── Expériences (20%) ─────────────────────────────────────────────
            if experiences:
                complete_exps = sum(
                    1 for e in experiences
                    if e.get("poste") and e.get("entreprise") and e.get("date_debut")
                )
                if complete_exps >= 3:
                    _ex_s = 0.20
                    _ex_d = f"{complete_exps} expériences complètes — excellent"
                elif complete_exps == 2:
                    _ex_s = 0.17
                    _ex_d = "2 expériences complètes"
                elif complete_exps == 1:
                    _ex_s = 0.13
                    _ex_d = "1 expérience complète"
                else:
                    _ex_s = 0.07
                    _ex_d = f"{len(experiences)} exp. sans titre/entreprise/dates"
            else:
                _ex_s = 0.0
                _ex_d = "aucune expérience"
            breakdown["experiences"] = {"score": _ex_s, "max": 0.20, "detail": _ex_d}

            # ── Langues (8%) — nouveau ────────────────────────────────────────
            _n_langs = len(langues)
            _n_langs_niv = sum(1 for l in langues if l.get("niveau") and l.get("niveau") != "Non spécifié")
            if _n_langs >= 2 and _n_langs_niv >= 1:
                _la_s = 0.08
                _la_d = f"{_n_langs} langues avec niveaux"
            elif _n_langs >= 2:
                _la_s = 0.06
                _la_d = f"{_n_langs} langues (niveaux non précisés)"
            elif _n_langs == 1:
                _la_s = 0.04
                _la_d = "1 langue"
            else:
                _la_s = 0.0
                _la_d = "aucune langue"
            breakdown["langues"] = {"score": _la_s, "max": 0.08, "detail": _la_d}

            # ── Cohérence globale (7%) ────────────────────────────────────────
            _coh_s = 0.0
            _coh_details = []
            # 1) Email contient un fragment du nom (signal de cohérence identité)
            _email_val = contact_data.get("primary_email") or ""
            if full_name and _email_val:
                name_parts = [p.lower() for p in full_name.split() if len(p) >= 3]
                if any(part in _email_val.lower() for part in name_parts):
                    _coh_s += 0.02
                    _coh_details.append("email cohérent avec le nom")
            # 2) Présence URL (LinkedIn, GitHub, portfolio)
            _urls = contact_data.get("urls") or []
            if _urls:
                _coh_s += 0.02
                _coh_details.append(f"{len(_urls)} URL(s) trouvé(s)")
            # 3) Chronologie cohérente (dates formations ≤ dates expériences)
            _form_years = [
                int(f["annee"]) for f in formations
                if f.get("annee") and str(f["annee"]).isdigit()
            ]
            _exp_years = [
                int(str(e["date_debut"])[:4]) for e in experiences
                if e.get("date_debut") and len(str(e["date_debut"])) >= 4
                and str(e["date_debut"])[:4].isdigit()
            ]
            if _form_years and _exp_years and min(_exp_years) >= min(_form_years):
                _coh_s += 0.02
                _coh_details.append("chronologie cohérente")
            # 4) Au moins un champ de contact (téléphone ou email)
            if contact_data.get("primary_email") and contact_data.get("primary_phone"):
                _coh_s += 0.01
                _coh_details.append("contact complet")
            _coh_s = min(_coh_s, 0.07)
            breakdown["coherence"] = {
                "score": _coh_s, "max": 0.07,
                "detail": "; ".join(_coh_details) if _coh_details else "aucun signal de cohérence",
            }

            # ── Score final + champs manquants ───────────────────────────────
            confidence = sum(v["score"] for v in breakdown.values())
            confidence = round(min(confidence, 1.0), 4)

            champs_manquants = [k for k, v in breakdown.items() if v["score"] == 0.0]
            champs_faibles = [
                k for k, v in breakdown.items()
                if 0.0 < v["score"] < v["max"] * 0.6
            ]

            # Métadonnées calculées
            total_months = sum((e.get("duree_mois") or 0) for e in experiences)
            annees_totales = round(total_months / 12, 1)
            niveau_max = formation_data.get("niveau_max", 0)

            if annees_totales == 0:
                seniorite = "Junior"
            elif annees_totales <= 2:
                seniorite = "Junior"
            elif annees_totales <= 5:
                seniorite = "Confirmé"
            elif annees_totales <= 10:
                seniorite = "Senior"
            else:
                seniorite = "Expert"

            # ── IA : entités spaCy NER brutes sur le texte complet ──────────
            # On analyse les 3000 premiers caractères pour la performance
            ner_entites = []
            try:
                doc_ner = nlp_active(text[:3000])
                _label_fr = {
                    "PER": "Personne", "PERSON": "Personne",
                    "ORG": "Organisation", "LOC": "Lieu", "GPE": "Lieu",
                    "DATE": "Date", "MISC": "Divers",
                }
                for ent in doc_ner.ents:
                    ner_entites.append({
                        "texte": ent.text.strip(),
                        "label_spacy": ent.label_,
                        "label_fr": _label_fr.get(ent.label_, ent.label_),
                        "position_debut": ent.start_char,
                        "position_fin": ent.end_char,
                    })
            except Exception:
                pass

            # ── IA : sources par champ (traçabilité) ─────────────────────────
            sources_par_champ = {
                "nom": {
                    "valeur": full_name,
                    "methode": name_source or "non_trouve",
                    "outils_ia": (
                        ["spaCy NER (PERSON)", "CamemBERT NER"]
                        if name_source and "hf_camembert" in name_source
                        else ["spaCy NER (PERSON)"] if name_source == "entity_extractor"
                        else ["email heuristique"] if name_source == "email"
                        else []
                    ),
                },
                "email": {
                    "valeur": contact_data.get("primary_email"),
                    "methode": "regex",
                    "outils_ia": [],
                },
                "telephone": {
                    "valeur": contact_data.get("primary_phone"),
                    "methode": "regex",
                    "outils_ia": [],
                },
                "competences": {
                    "total": len(skills),
                    "methode": "dictionnaire_300+_termes + regex sections",
                    "outils_ia": [],
                },
                "formations": {
                    "total": len(formations),
                    "methode": "patterns_diplomes + spaCy NER (ORG) etablissements",
                    "outils_ia": ["spaCy NER (ORG)"] if self._spacy_has_ner else [],
                },
                "experiences": {
                    "total": len(experiences),
                    "methode": "patterns_postes + spaCy NER (ORG) entreprises",
                    "outils_ia": ["spaCy NER (ORG)"] if self._spacy_has_ner else [],
                },
                "langues": {
                    "total": len(langues),
                    "methode": "regex_sections_langues",
                    "outils_ia": [],
                },
            }

            # ── IA : résumé lisible pour présentation PFE ─────────────────────
            ia_resume = {
                "spacy_actif": not self._spacy_fallback,
                "spacy_ner_actif": bool(self._spacy_has_ner),
                "spacy_modele": self._spacy_loaded_model,
                "camembert_actif": hf_enabled,
                "camembert_utilise": hf_used,
                "camembert_modele": hf_model if hf_enabled else None,
                "entites_ner_detectees": len(ner_entites),
                "champs_avec_ia": sum(
                    1 for v in sources_par_champ.values()
                    if isinstance(v, dict) and v.get("outils_ia")
                ),
                "competences_ner_decouvertes": skills_data.get("ner_discoveries", 0),
                "secteur_detecte": sector_data.get("secteur"),
                "secteur_confiance": round(sector_data.get("confiance", 0.0), 4),
                "description": (
                    f"Pipeline NLP : spaCy {nlp_active_name} (NER)"
                    + (f" + CamemBERT ({hf_model})" if hf_enabled else "")
                    + f" — langue CV : {cv_langue.upper()} ({round(lang_confiance*100)}%)"
                    + f" — {len(ner_entites)} entités détectées"
                    + f" — {skills_data.get('ner_discoveries', 0)} compétences découvertes par NER"
                    + f" — secteur : {sector_data.get('label', 'inconnu')} ({round(sector_data.get('confiance', 0)*100)}%)"
                    + f" — score confiance {round(min(confidence, 1.0), 2)}"
                ),
            }

            result["parsed_data"] = {
                "identite": {
                    "nom_complet": full_name,
                },
                "contacts": {
                    "email": contact_data.get("primary_email"),
                    "telephone": contact_data.get("primary_phone"),
                    "emails": contact_data.get("emails", []),
                    "phones": contact_data.get("phones", []),
                    "linkedin": contact_data.get("linkedin"),
                    "github": contact_data.get("github"),
                    "website": contact_data.get("website"),
                    "address": contact_data.get("address"),
                },
                "competences": skills,
                "formations": formations,
                "experiences": experiences,
                "langues": langues,
                "competences_par_categorie": skills_data.get("by_category", {}),
                # ── Classification sectorielle IA ────────────────────────────
                "secteur_detecte": {
                    "secteur": sector_data.get("secteur"),
                    "label": sector_data.get("label"),
                    "confiance": round(sector_data.get("confiance", 0.0), 4),
                    "secteurs_secondaires": sector_data.get("secteurs_secondaires", []),
                },
                # ── Section IA (PFE) ─────────────────────────────────────────
                "ia_analyse": {
                    "resume": ia_resume,
                    "ner_entites_spacy": ner_entites,
                    "sources_par_champ": sources_par_champ,
                    "competences_decouvertes_ner": skills_data.get("ner_discoveries", 0),
                    "classification_sectorielle": sector_data,
                },
                "metadata": {
                    "parser_version": "2.5.0",
                    "langue_cv": cv_langue,
                    "langue_confiance": round(lang_confiance, 3),
                    "bilingue": lang_bilingue,
                    "langue_detection_methode": lang_methode,
                    "spacy_model_actif": nlp_active_name,
                    "confidence_score": round(confidence, 2),
                    "confidence_breakdown": {
                        k: {
                            "score": round(v["score"], 3),
                            "max": v["max"],
                            "pct": f"{round(v['score'] / v['max'] * 100) if v['max'] > 0 else 0}%",
                            "detail": v["detail"],
                        }
                        for k, v in breakdown.items()
                    },
                    "champs_manquants": champs_manquants,
                    "champs_faibles": champs_faibles,
                    "parsed_at": datetime.now(timezone.utc).isoformat(),

                    # Trace spaCy
                    "spacy_model": self._spacy_loaded_model,
                    "spacy_version": self._spacy_version,
                    "spacy_has_ner": self._spacy_has_ner,
                    "spacy_fallback": self._spacy_fallback,
                    "spacy_pipes": self._spacy_pipes,

                    # Trace CamemBERT
                    "hf_camembert_enabled": hf_enabled,
                    "hf_camembert_attempted": hf_attempted,
                    "hf_camembert_used": hf_used,
                    "hf_camembert_model": hf_model,
                    "hf_camembert_timeout_seconds": hf_timeout,

                    "name_source": name_source,
                    "name_candidates": name_candidates,
                    "name_conflict": name_conflict,
                    "annees_experience_totales": annees_totales,
                    "niveau_formation_max": niveau_max,
                    "niveau_seniorite": seniorite,
                    "total_competences": len(skills),
                    "total_formations": len(formations),
                    "total_experiences": len(experiences),
                },
                "errors": errors,
            }

            result["success"] = True
            logger.info(
                f"Parsing NLP réussi (cv_id: {cv_id}) — "
                f"{len(skills)} skills, {len(formations)} formations, "
                f"{len(experiences)} expériences"
            )

        except Exception as e:
            result["error"] = f"Erreur parsing NLP : {str(e)}"
            logger.error(result["error"], exc_info=True)

        return result

    def extract_entities(self, text: str) -> Dict[str, list]:
        """
        Extrait les entités nommées du texte.
        
        Args:
            text: Texte à analyser
        
        Returns:
            Dict avec entités par type : {"PERSON": [...], "ORG": [...], ...}
        """
        nlp = self._load_model()
        doc = nlp(text)

        entities = {}
        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            entities[ent.label_].append({
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char
            })

        return entities


# ================================================================
# Fonctions utilitaires
# ================================================================

def test_nlp_parser():
    """Teste le parser NLP de base"""
    print("\n" + "="*70)
    print("TEST - NLP Parser")
    print("="*70)

    parser = NLPParser()

    # Texte de test
    test_text = """
    Marie Martin
    Email: marie.martin@example.com
    Téléphone: +33 6 12 34 56 78
    
    Compétences:
    - Python, FastAPI, Django
    - React, JavaScript
    - Docker, Kubernetes
    
    Expérience:
    Ingénieure DevOps chez TechCorp (2021-Present)
    Développeuse chez StartupXYZ (2019-2021)
    
    Formation:
    Diplôme d'Ingénieur - École Centrale (2019)
    """

    # Parser le texte
    result = parser.parse(test_text, cv_id="test-001")

    print(f"\n✅ Succès: {result['success']}")
    print(f"📄 CV ID: {result['cv_id']}")

    # Extraire entités
    entities = parser.extract_entities(test_text)
    print(f"\n🔍 Entités extraites:")
    for ent_type, ent_list in entities.items():
        print(f"   {ent_type}: {[e['text'] for e in ent_list]}")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║              NLP PARSER - TalentMatch Sprint 2                    ║
║                    Test de base                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)

    test_nlp_parser()

    print("\n" + "="*70)
    print("✅ Test terminé")
    print("="*70)
    print("\n💡 Prochaines étapes:")
    print("   1. Implémenter entity_extractor.py")
    print("   2. Implémenter contact_extractor.py")
    print("   3. Implémenter skills_extractor.py")
    print("   4. Intégrer dans API FastAPI\n")
