"""
Parser de CV  â€“ Pipeline 4 Ã©tapes
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
[1] Normalisation intelligente    â†’ texte propre, lignes nettoyÃ©es
[2] DÃ©tection des sections        â†’ dict {section: [lignes]}
[3] Extraction ciblÃ©e / section   â†’ regex + heuristiques par zone
[4] spaCy + rÃ¨gles hybrides       â†’ NER sur la zone identitÃ© seulement
"""

import re
import unicodedata
import spacy
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  UTILITAIRES GLOBAUX
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _strip_accents(text: str) -> str:
    """Supprime les accents et met en minuscules."""
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8").lower()


_n = _strip_accents  # alias court


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Ã‰TAPE 1 â€“ NORMALISATION INTELLIGENTE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# Patterns pour re-decouper les PDFs plats (tout sur 1 ligne)
_SECTION_SPLITTERS = [
    r"Formation\b",
    r"Exp[^\w\s]{0,3}\s?[e\xe9]rience",
    r"Comp[^\s]{0,5}tences?",
    r"Langues?\b",
    r"Projets?\b",
    r"Certifications?\b",
    r"Loisirs?\b",
    r"Objectif\b",
]
_RESPLIT_RE = re.compile(
    r"(?<!\n)(" + "|".join(_SECTION_SPLITTERS) + r")",
    re.IGNORECASE,
)


def _resplit_flat(text: str) -> str:
    """Insere des sauts de ligne avant les titres de section si PDF plat."""
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return text
    long_lines = sum(1 for l in lines if len(l) > 300)
    if long_lines / len(lines) < 0.3:
        return text  # deja bien decoupe
    return _RESPLIT_RE.sub(lambda m: "\n" + m.group(0) + "\n", text)


def normalize_text(raw: str) -> Tuple[str, List[str]]:
    """
    Nettoie le texte brut (PDF / Word / OCR).
    Retourne (texte_propre, liste_de_lignes).
    """
    text = _resplit_flat(raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines: List[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"^[\sâ€¢â–ªâ—¦\-â€“â€”]+", "", raw_line)   # supprime puces
        line = re.sub(r"\s+", " ", line).strip()           # espaces multiples
        lines.append(line)

    # DÃ©doublonner les lignes vides consÃ©cutives
    clean_lines: List[str] = []
    prev_empty = False
    for line in lines:
        if line == "":
            if not prev_empty:
                clean_lines.append("")
            prev_empty = True
        else:
            clean_lines.append(line)
            prev_empty = False

    return "\n".join(clean_lines), clean_lines


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Ã‰TAPE 2 â€“ DÃ‰TECTION DES SECTIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

SECTION_PATTERNS: Dict[str, List[str]] = {
    "identite":      [r"profil", r"informations?\s*personnelles?", r"coordonn"],
    "experience":    [r"exp.{0,2}rience", r"parcours\s*professionnel", r"emploi"],
    "formation":     [r"formation", r"[e]ducation|etude", r"dipl.me", r"cursus", r"[e]tude"],
    "competence":    [r"comp.{0,2}tence", r"skill", r"technique", r"outil", r"technologie"],
    "langue":        [r"langue", r"language", r"linguistique"],
    "projet":        [r"projet", r"r.alisation", r"portfolio"],
    "certification": [r"certif", r"attestation"],
    "loisir":        [r"loisir", r"int.r.t", r"hobby"],
}


def _identify_section(line: str) -> Optional[str]:
    line_n = _n(line)
    for sec, patterns in SECTION_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, line_n):
                return sec
    return None


def _is_section_title(line: str) -> bool:
    if not line.strip() or len(line) > 70:
        return False
    # Un titre de section commence toujours par une majuscule
    first_alpha = next((c for c in line if c.isalpha()), "")
    if not first_alpha.isupper():
        return False
    line_alpha = re.sub(r"[^a-zA-Z ]", "", line)
    if line_alpha and line_alpha == line_alpha.upper() and len(line_alpha.strip()) > 3:
        return True
    return _identify_section(line) is not None


def detect_sections(lines: List[str]) -> Dict[str, List[str]]:
    """
    DÃ©coupe la liste de lignes en sections nommÃ©es.
    La clÃ© '_header_' contient les lignes avant la 1Ã¨re section.
    """
    sections: Dict[str, List[str]] = {"_header_": []}
    current = "_header_"

    for line in lines:
        if _is_section_title(line):
            sec = _identify_section(line)
            if sec:
                current = sec
                sections.setdefault(current, [])
                continue      # titre non inclus dans le bloc
        sections.setdefault(current, [])
        sections[current].append(line)

    # Nettoyer les lignes vides en dÃ©but/fin de chaque bloc
    for key in sections:
        b = sections[key]
        while b and b[0] == "":
            b.pop(0)
        while b and b[-1] == "":
            b.pop()

    return sections


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  PATTERNS DE DATE (rÃ©utilisÃ©s par expÃ©riences et formations)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

_MONTH_PAT = (
    r"(?:janvier|f[eÃ©]vrier|mars|avril|mai|juin|juillet|ao[uÃ»]t"
    r"|septembre|octobre|novembre|d[eÃ©]cembre"
    r"|jan|f[eÃ©]v|avr|juil|sep|oct|nov|d[eÃ©]c)"
)
_DATE_UNIT = rf"(?:{_MONTH_PAT}\.?\s*\d{{4}}|\d{{4}})"
_DATE_RANGE = re.compile(
    rf"({_DATE_UNIT})\s*[-â€“]\s*({_DATE_UNIT}|[Pp]r[eÃ©]sent|[Aa]ctuel|[Aa]ujourd'hui)",
    re.IGNORECASE,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Ã‰TAPE 3 â€“ EXTRACTEURS CIBLÃ‰S PAR SECTION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _extract_contacts_from_lines(lines: List[str]) -> Dict:
    text = "\n".join(lines)

    email   = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    phone   = re.search(r"(\+(?:33|216|212|213|32|41|1)\s?|0033\s?|0)[\d][\d\s.\-]{6,14}\d", text)
    linkedin = re.search(r"linkedin\.com/in/([\w\-]+)|LinkedIn\s*:\s*([\w\-]+)", text, re.IGNORECASE)
    github   = re.search(r"github\.com/([\w\-]+)|GitHub\s*:\s*/?([\w\-]+)", text, re.IGNORECASE)

    linkedin_user = (linkedin.group(1) or linkedin.group(2)) if linkedin else None
    github_user   = (github.group(1)   or github.group(2))   if github   else None

    return {
        "email":     email.group(0).strip() if email else None,
        "telephone": phone.group(0).strip() if phone else None,
        "linkedin":  f"https://linkedin.com/in/{linkedin_user}" if linkedin_user else None,
        "github":    f"https://github.com/{github_user}"        if github_user   else None,
    }


def _extract_experiences_from_lines(lines: List[str]) -> List[Dict]:
    """Extrait les expÃ©riences dans le bloc 'experience' uniquement."""
    # Re-decouper les lignes qui contiennent plusieurs entrees collees par bullets
    expanded = []
    for _l in lines:
        if _l.count("•") > 1 or (len(_l) > 120 and "•" in _l):
            sub = [s.strip() for s in _l.split("•") if s.strip()]
            expanded.extend(sub)
        else:
            expanded.append(_l)
    lines = expanded

    experiences = []
    for line in lines:
        if len(line) > 200 or len(line) < 8:
            continue
        match = _DATE_RANGE.search(line)
        if not match:
            continue

        clean = _DATE_RANGE.sub("", line).strip(" |â€“â€”â€¢-")
        parts = re.split(r"\s*[â€“â€”|â€¢]\s*|(?<=\w)\s{2,}(?=\w)", clean)
        parts = [p.strip(" -â€¢") for p in parts if p.strip(" -â€¢") and len(p.strip()) > 2]

        experiences.append({
            "poste":      parts[0] if len(parts) >= 1 else "Non extrait",
            "entreprise": parts[1] if len(parts) >= 2 else "Non extrait",
            "dates":      f"{match.group(1)} - {match.group(2)}",
            "missions":   [],
        })
    return experiences[:6]


def _extract_formations_from_lines(lines: List[str]) -> List[Dict]:
    """Extrait les formations dans le bloc 'formation' uniquement."""
    # Re-decouper les lignes qui contiennent plusieurs entrees collees par bullets
    expanded = []
    for l in lines:
        if l.count("•") > 1 or (len(l) > 120 and "•" in l):
            sub = [s.strip() for s in l.split("•") if s.strip()]
            expanded.extend(sub)
        else:
            expanded.append(l)
    lines = expanded

    _KW = [
        "master", "licence", "bachelor", "bts", "dut",
        "ingenieur", "ingenierie", "these", "doctorat",
        "diplome", "baccalaureat", "baccalaur",
        "universite", "ecole", "iut", "cpge",
        "preparatoire", "cycle",
    ]
    formations = []
    for line in lines:
        if len(line) < 8 or len(line) > 200:
            continue
        line_n = _n(line)
        has_kw    = any(kw in line_n for kw in _KW)
        date_m    = _DATE_RANGE.search(line)
        year_only = re.search(r"\b(20\d{2}|19\d{2})\b", line)

        if not (has_kw or date_m):
            continue

        diplome_raw = _DATE_RANGE.sub("", line).strip(" |â€“â€”â€¢-")
        parts = re.split(r"\s*[â€“â€”|]\s*", diplome_raw)
        parts = [p.strip(" -â€¢") for p in parts if p.strip(" -â€¢") and len(p.strip()) > 2]

        annee = (f"{date_m.group(1)} - {date_m.group(2)}" if date_m
                 else (year_only.group(0) if year_only else None))

        formations.append({
            "diplome":       parts[0][:120] if parts else line[:120],
            "etablissement": parts[1][:80]  if len(parts) >= 2 else "Non extrait",
            "annee":         annee,
        })
        if len(formations) >= 5:
            break
    return formations


def _extract_skills_from_lines(lines: List[str]) -> List[str]:
    _DB = [
        "Python", "JavaScript", "Java", "C++", "C#", "PHP", "Ruby", "Go",
        "TypeScript", "Swift", "Kotlin", "Rust", "Scala", "R", "MATLAB",
        "React", "Angular", "Vue.js", "Django", "Flask", "FastAPI",
        "Node.js", "Express", "Spring", "Laravel", "Symfony", "Next.js",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Oracle", "SQL Server",
        "Elasticsearch", "Cassandra", "SQLite", "MariaDB",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Jenkins",
        "Git", "Linux", "Ansible", "Terraform", "GitLab CI", "GitHub Actions",
        "TensorFlow", "PyTorch", "Pandas", "NumPy", "Scikit-learn",
        "Spark", "Hadoop", "Kafka", "spaCy", "BERT", "CamemBERT",
        "Matplotlib", "Seaborn", "OpenCV",
        "REST API", "GraphQL", "Microservices", "Agile", "Scrum", "DevOps",
        "HTML", "CSS", "Bootstrap", "Tailwind",
    ]
    text = " ".join(lines).lower()
    return list(dict.fromkeys(s for s in _DB if s.lower() in text))


def _extract_languages_from_lines(lines: List[str]) -> List[str]:
    _MAP = {
        "francais":    "FranÃ§ais",  "anglais":    "Anglais",
        "espagnol":    "Espagnol",  "allemand":   "Allemand",
        "arabe":       "Arabe",     "italien":    "Italien",
        "chinois":     "Chinois",   "japonais":   "Japonais",
        "portugais":   "Portugais", "russe":      "Russe",
        "neerlandais": "NÃ©erlandais", "turc":     "Turc",
    }
    text_n = _n(" ".join(lines))
    return [label for key, label in _MAP.items() if key in text_n]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Ã‰TAPE 4 â€“ spaCy HYBRIDE (NER sur la zone header uniquement)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

_BLACKLIST_NAME = {
    "telephone", "email", "adresse", "linkedin", "github", "poste",
    "profil", "contact", "cv", "curriculum", "tel", "stage",
    "formation", "competence", "langue",
}


def _name_spacy(header_lines: List[str], nlp) -> Optional[str]:
    zone = " ".join(header_lines[:8])[:500]
    doc = nlp(zone)
    for ent in doc.ents:
        if ent.label_ == "PER":
            words = ent.text.strip().split()
            clean = []
            for w in words[:3]:
                if _n(w) in _BLACKLIST_NAME:
                    break
                clean.append(w)
            if clean and _n(clean[0]) not in _BLACKLIST_NAME:
                return " ".join(clean)
    return None


def _name_fallback(header_lines: List[str]) -> Optional[str]:
    for line in header_lines[:8]:
        w = line.split()
        if (2 <= len(w) <= 4
                and not any(c.isdigit() for c in line)
                and "@" not in line
                and not any(c in line for c in [":", "/", "\\", "|"])
                and _n(w[0]) not in _BLACKLIST_NAME):
            return line
    return None


# ══════════════════════════════════════════════════════════════════════
#  CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════

class CVParser:
    """
    Pipeline :
      [1] normalize_text  →  [2] detect_sections
      →  [3] extraction ciblée  →  [4] spaCy NER header
    """

    def __init__(self):
        try:
            self.nlp = spacy.load("fr_core_news_md")
            self.has_spacy = True
            logger.info("✅ spaCy chargé : fr_core_news_md")
        except OSError:
            self.has_spacy = False
            logger.warning("⚠️  spaCy non disponible, mode regex uniquement")

    def parse(self, raw_text: str) -> Dict:
        # [1] Normalisation
        _, lines = normalize_text(raw_text)

        # [2] Détection des sections
        sections = detect_sections(lines)
        detected = [k for k in sections if k != "_header_" and sections[k]]
        logger.info(f"Sections détectées : {detected}")

        # [3+4] Extraction ciblée + NER
        header = sections.get("_header_", []) + sections.get("identite", [])

        # Identité (spaCy → fallback regex)
        name = (_name_spacy(header, self.nlp) if self.has_spacy else None) \
               or _name_fallback(header) \
               or "Non détecté"
        parts = name.split()
        identite = {
            "nom_complet": name,
            "prenom":      parts[0]  if len(parts) >= 1 else None,
            "nom":         parts[-1] if len(parts) >= 2 else None,
        }

        # Contacts (cherchés dans le header)
        contacts = _extract_contacts_from_lines(header)

        # Compétences (section dédiée, sinon tout le texte en fallback)
        comp_lines = sections.get("competence") or lines
        competences = _extract_skills_from_lines(comp_lines)
        if not competences:
            competences = _extract_skills_from_lines(lines)

        # Expériences (section dédiée uniquement → zéro pollution)
        experiences = _extract_experiences_from_lines(sections.get("experience", []))

        # Formations (section dédiée uniquement)
        formations = _extract_formations_from_lines(sections.get("formation", []))

        # Langues (section dédiée, sinon tout le texte)
        lang_lines = sections.get("langue") or lines
        langues = _extract_languages_from_lines(lang_lines)
        if not langues:
            langues = _extract_languages_from_lines(lines)

        return {
            "identite":    identite,
            "contacts":    contacts,
            "competences": competences,
            "experiences": experiences,
            "formations":  formations,
            "langues":     langues,
            "stats": {
                "nb_mots":            len(raw_text.split()),
                "nb_competences":     len(competences),
                "nb_experiences":     len(experiences),
                "nb_formations":      len(formations),
                "sections_detectees": detected,
            },
        }


# ── Helper public ──────────────────────────────────────────────────────
def parse_cv(text: str) -> Dict:
    return CVParser().parse(text)

