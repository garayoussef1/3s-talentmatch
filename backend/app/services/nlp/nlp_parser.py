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
import spacy
from app.services.nlp.contact_extractor import ContactExtractor
from app.services.nlp.entity_extractor import EntityExtractor
from app.services.nlp.skills_extractor import SkillsExtractor
from app.services.nlp.formation_extractor import FormationExtractor
from app.services.nlp.experience_extractor import ExperienceExtractor

logger = logging.getLogger(__name__)


# ── Extraction simple de langues ─────────────────────────────────
_LANGUES_KW = re.compile(
    r"(?:ma[îi]trise\s+des\s+langues"
    r"|langues?\s+parl[ée]es"
    r"|langues?\s+ma[îi]tris[ée]es"
    r"|langues?|languages?|sprachen|idiomas)\s*[:\-–]?\s*\n?",
    re.IGNORECASE,
)
_LANGUE_LINE = re.compile(
    r"^\s*[-•▪►●◆]?\s*"
    r"(Fran[çc]ais|French|Anglais|English|Arabe|Arabic|Espagnol|Spanish|Allemand|German"
    r"|Italien|Italian|Portugais|Portuguese|Chinois|Chinese|Japonais|Japanese"
    r"|Russe|Russian|Turc|Turkish|Cor[ée]en|Korean|Hindi|N[ée]erlandais|Dutch|Polonais|Polish)"
    r"\s*(?:[:\-–—/|]\s*|\s*\(\s*)?"
    r"(Natif|Maternelle?|Langue\s+maternelle|Courant|Bilingue|Professionnel|Interm[ée]diaire|Avanc[ée]|D[ée]butant|Scolaire"
    r"|Notions?\s*(?:de\s+)?base"
    r"|Native|Fluent|Bilingual|Professional|Intermediate|Advanced|Beginner|Basic"
    r"|Op[ée]rationnel(?:le)?|Technique"
    r"|C2|C1|B2|B1|A2|A1"
    r"|TOEIC\s*\d+|TOEFL\s*\d+|IELTS\s*[\d.]+)?"
    r"\)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_LANGUE_INLINE = re.compile(
    r"\b"
    r"(Fran[çc]ais|French|Anglais|English|Arabe|Arabic|Espagnol|Spanish|Allemand|German"
    r"|Italien|Italian|Portugais|Portuguese|Chinois|Chinese|Japonais|Japanese"
    r"|Russe|Russian|Turc|Turkish|Cor[ée]en|Korean|Hindi|N[ée]erlandais|Dutch|Polonais|Polish)"
    r"\s*(?:[:\-–—/|]\s*|\s*\(\s*)?"
    r"(Natif|Maternelle?|Langue\s+maternelle|Courant|Bilingue|Professionnel|Interm[ée]diaire|Avanc[ée]|D[ée]butant|Scolaire"
    r"|Notions?\s*(?:de\s+)?base"
    r"|Native|Fluent|Bilingual|Professional|Intermediate|Advanced|Beginner|Basic"
    r"|Op[ée]rationnel(?:le)?|Technique"
    r"|C2|C1|B2|B1|A2|A1"
    r"|TOEIC\s*\d+|TOEFL\s*\d+|IELTS\s*[\d.]+)?"
    r"\)?\s*",
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
            r")"
            r"(?!\w)",
            re.IGNORECASE,
        )
        text = section_pattern.sub(r"\n\n\1\n", text)

        # ── 2. Inject \n AVANT les titres de postes (pour CV compacts inline) ──
        # Permet de séparer "...WebAgency 2023 - Présent Développeur Junior..."
        text = re.sub(
            r"(?<!\n)\s+(?="
            r"(?:DRH|Responsable|Charg[ée]e?|Assistant(?:e)?|Ing[ée]nieur"
            r"|D[ée]veloppeur|Consultant|Manager|Directeur|Chef\s+de"
            r"|Analyste|Coordinateur|Gestionnaire|Technicien)\b"
            r")",
            r"\n",
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


    def __init__(self, model_name: str = "fr_core_news_md"):
        self.model_name = model_name
        self._nlp = None  # Lazy loading
        self._contact_extractor = ContactExtractor()
        self._skills_extractor = SkillsExtractor()
        self._formation_extractor = None   # Needs spaCy model
        self._experience_extractor = None  # Needs spaCy model
        logger.info(f"NLPParser initialisé (modèle: {model_name})")

    def _load_model(self):
        """Charge le modèle spaCy (lazy loading) et initialise les extracteurs."""
        if self._nlp is None:
            logger.info(f"Chargement modèle spaCy : {self.model_name}...")
            self._nlp = spacy.load(self.model_name)
            self._formation_extractor = FormationExtractor(nlp_model=self._nlp)
            self._experience_extractor = ExperienceExtractor(nlp_model=self._nlp)
            logger.info("Modèle spaCy + extracteurs chargés")
        return self._nlp

    @staticmethod
    def _extract_langues(text: str):
        """Extraction simple des langues depuis la section Langues."""
        langues = []
        m = _LANGUES_KW.search(text)
        if not m:
            return langues
        section = text[m.end(): m.end() + 1200]

        # Couper à la prochaine section (fallback compact sans lignes vides)
        end = re.search(
            r"\b(?:comp[ée]tences?|savoir[\s\-]faire|formation|dipl[ôo]mes?|"
            r"exp[ée]rience|parcours|projets?|engagements?|publications?|"
            r"passions?|loisirs?|r[ée]f[ée]rences?)\b",
            section,
            re.IGNORECASE,
        )
        if end and end.start() > 40:
            section = section[: end.start()]

        seen = set()
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
            entity_extractor = EntityExtractor(nlp)

            # Liste des erreurs partielles (pipeline continue malgré tout)
            errors: list = []

            # ── 1. CONTACT ───────────────────────────────────────────
            contact_data = {}
            full_name = None
            try:
                contact_data = self._contact_extractor.extract(text)
                logger.info("ContactExtractor OK — email=%s, phone=%s, linkedin=%s",
                            contact_data.get("primary_email"), contact_data.get("primary_phone"),
                            contact_data.get("linkedin"))
            except Exception as e:
                logger.error("Erreur ContactExtractor : %s", e, exc_info=True)
                errors.append({"module": "contact_extractor", "error": str(e)})

            try:
                full_name = entity_extractor.extract_full_name(text)
            except Exception as e:
                logger.error("Erreur EntityExtractor : %s", e, exc_info=True)
                errors.append({"module": "entity_extractor", "error": str(e)})

            # ── 2. COMPÉTENCES ───────────────────────────────────────
            skills_data = {"skills": [], "by_category": {}, "total_skills": 0}
            try:
                skills_data = self._skills_extractor.extract(text)
                logger.info("SkillsExtractor OK — %d compétences", skills_data.get("total_skills", 0))
            except Exception as e:
                logger.error("Erreur SkillsExtractor : %s", e, exc_info=True)
                errors.append({"module": "skills_extractor", "error": str(e)})

            # ── 3. FORMATIONS ────────────────────────────────────────
            formation_data = {"formations": [], "niveau_max": 0}
            try:
                formation_data = self._formation_extractor.extract(text)
                logger.info("FormationExtractor OK — %d formations", len(formation_data.get("formations", [])))
            except Exception as e:
                logger.error("Erreur FormationExtractor : %s", e, exc_info=True)
                errors.append({"module": "formation_extractor", "error": str(e)})

            # ── 4. EXPÉRIENCES ───────────────────────────────────────
            experience_data = {"experiences": [], "annees_experience_totales": 0}
            try:
                experience_data = self._experience_extractor.extract(text)
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

            # Calcul confidence
            confidence = 0.0
            if full_name:
                confidence += 0.15
            if contact_data.get("primary_email"):
                confidence += 0.15
            if contact_data.get("primary_phone"):
                confidence += 0.10
            if len(skills) >= 5:
                confidence += 0.20
            elif skills:
                confidence += 0.10
            if formations:
                confidence += 0.20
            if experiences:
                confidence += 0.20

            # Métadonnées calculées
            total_months = sum(e.get("duree_mois", 0) for e in experiences)
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
                "metadata": {
                    "parser_version": "2.1.0",
                    "confidence_score": round(min(confidence, 1.0), 2),
                    "parsed_at": datetime.now(timezone.utc).isoformat(),
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
