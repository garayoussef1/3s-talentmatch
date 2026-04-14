import os
import sys


# Setup import path (repo backend)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.nlp.experience_extractor import ExperienceExtractor  # noqa: E402


def test_experience_section_ignores_toc_and_extracts_real_experience():
    text = """
CONTACT
PROFIL
EXPÉRIENCES PROFESSIONNELLES
LANGUES
COMPÉTENCES
CERTIFICATIONS
FORMATIONS

Stage Développement Web – BeeCoders, Tunis
2023 - Présent
Développement d'un site web pour événements sportifs.
""".strip()

    extractor = ExperienceExtractor(nlp_model=None)
    result = extractor.extract(text)

    assert result["total_experiences"] >= 1
    exp = result["experiences"][0]
    assert exp.get("poste")
    assert exp.get("entreprise")
    # L'entreprise ne doit pas être un simple numéro
    assert not str(exp.get("entreprise")).strip().isdigit()
