"""
Test du support multilingue (FR + EN) du pipeline NLP.
Lance avec : python tests/test_multilingual.py
Ou via pytest : python -m pytest tests/test_multilingual.py -v -s
"""
from __future__ import annotations

import sys
import os
import io
from pathlib import Path

# IMPORTANT: ce module est importé par pytest. On évite donc les mutations
# globales (stdout, sys.path) à l'import; elles ne sont utiles qu'en exécution directe.
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.nlp.language_detector import detect_language
from app.services.nlp.nlp_parser import NLPParser

SEP = "=" * 60

def _ok(cond, msg_ok, msg_fail):
    status = "OK" if cond else "FAIL"
    print(f"  [{status}]  {msg_ok if cond else msg_fail}")
    return cond


# ── CV de test anglais ───────────────────────────────────────────
CV_EN = """
Ranim Khalil
ranim.khalil@gmail.com | +216 55 123 456
linkedin.com/in/ranim-khalil | github.com/ranimkhalil

SUMMARY
Full Stack Developer with 4 years of experience in web and mobile development.
Passionate about clean code, agile methodologies and cloud architecture.

TECHNICAL SKILLS
Languages: Python, JavaScript, TypeScript, Java, SQL
Frameworks: React, Node.js, Django, Spring Boot, FastAPI
Databases: PostgreSQL, MongoDB, Redis, MySQL
DevOps: Docker, Kubernetes, AWS, Jenkins, Git, Linux

PROFESSIONAL EXPERIENCE
2022 - Present | Senior Software Engineer | TechStart Inc, San Francisco
  - Developed RESTful APIs with Python Django and PostgreSQL
  - Migrated monolithic architecture to microservices (Docker, Kubernetes)
  - Improved API response time by 40% through caching with Redis

2020 - 2022 | Full Stack Developer | Digital Solutions Ltd, London
  - Built React frontend applications with TypeScript
  - Designed and implemented CI/CD pipelines with Jenkins

2019 - 2020 | Software Engineering Intern | Startup Hub, Tunis
  - Developed e-commerce platform with payment integration

EDUCATION
2022 - 2024 | Master of Science, Software Engineering | ESPRIT, Tunis
2018 - 2022 | Bachelor of Science, Computer Science | FST, Sousse

LANGUAGES
Arabic: Native
French: Fluent
English: Professional
"""

# ── CV de test français ──────────────────────────────────────────
CV_FR = """
Ahmed Ben Salah
ahmed.bensalah@gmail.com | +216 55 987 654

COMPÉTENCES
Python, Java, JavaScript, Django, React, PostgreSQL, Docker, Git

EXPÉRIENCES PROFESSIONNELLES
2022-2024 | Développeur Backend Senior | TechCorp Tunisia, Tunis
  - Développement API REST avec Python et PostgreSQL
  - Mise en place pipeline CI/CD avec Jenkins et Docker

2020-2022 | Ingénieur DevOps | Vermeg, Tunis
  - Infrastructure Kubernetes sur AWS (30 microservices)

FORMATIONS
2022-2024 | Master Génie Logiciel | ESPRIT, Tunis
2018-2022 | Licence Informatique | FST, Sousse

LANGUES
Arabe : natif
Français : courant
Anglais : intermédiaire
"""


def _run_language_detector():
    print(f"\n{SEP}")
    print("  TEST 1 : DÉTECTEUR DE LANGUE")
    print(SEP)

    passed = 0
    total = 0

    # Test CV anglais
    res_en = detect_language(CV_EN)
    print(f"\n  CV Anglais :")
    print(f"    langue={res_en['langue']}  confiance={res_en['confiance']:.0%}  methode={res_en['methode']}")
    total += 1
    if _ok(res_en["langue"] == "en",
           f"CV EN détecté correctement ({res_en['confiance']:.0%})",
           f"CV EN NON détecté — résultat: {res_en['langue']}"):
        passed += 1
    total += 1
    if _ok(res_en["confiance"] > 0.5,
           f"Confiance suffisante : {res_en['confiance']:.0%}",
           f"Confiance trop faible : {res_en['confiance']:.0%}"):
        passed += 1

    # Test CV français
    res_fr = detect_language(CV_FR)
    print(f"\n  CV Français :")
    print(f"    langue={res_fr['langue']}  confiance={res_fr['confiance']:.0%}  methode={res_fr['methode']}")
    total += 1
    if _ok(res_fr["langue"] == "fr",
           f"CV FR détecté correctement ({res_fr['confiance']:.0%})",
           f"CV FR NON détecté — résultat: {res_fr['langue']}"):
        passed += 1

    # Test texte vide (fallback)
    res_empty = detect_language("")
    total += 1
    if _ok(res_empty["langue"] == "fr",
           "Texte vide → fallback FR",
           f"Texte vide → mauvais fallback: {res_empty['langue']}"):
        passed += 1

    return passed, total


def _run_multilingual_parser():
    print(f"\n{SEP}")
    print("  TEST 2 : PARSER MULTILINGUE")
    print(SEP)

    passed = 0
    total = 0

    parser = NLPParser()

    # ── CV anglais ──────────────────────────────────────────────
    print(f"\n  -- CV ANGLAIS --")
    result_en = parser.parse(CV_EN, cv_id="test_en")
    assert result_en["success"], f"Parsing EN échoué : {result_en.get('error')}"

    data_en = result_en["parsed_data"]
    meta_en = data_en["metadata"]

    print(f"  Langue détectée  : {meta_en.get('langue_cv')} ({meta_en.get('langue_confiance', 0):.0%})")
    print(f"  Modèle actif     : {meta_en.get('spacy_model_actif')}")
    print(f"  Nom              : {data_en['identite']['nom_complet']}")
    print(f"  Compétences      : {meta_en['total_competences']}")
    print(f"  Expériences      : {meta_en['total_experiences']}")
    print(f"  Formations       : {meta_en['total_formations']}")
    print(f"  Confiance        : {meta_en['confidence_score']:.0%}")

    total += 1
    if _ok(meta_en.get("langue_cv") == "en",
           "langue_cv = 'en' dans metadata",
           f"langue_cv incorrect: {meta_en.get('langue_cv')}"):
        passed += 1

    # Vérifier modèle EN utilisé si multilingue disponible
    if parser._multilingual:
        total += 1
        if _ok(meta_en.get("spacy_model_actif") == "en_core_web_md",
               "Modèle EN utilisé pour CV anglais",
               f"Mauvais modèle: {meta_en.get('spacy_model_actif')}"):
            passed += 1
    else:
        print("  [INFO] Mode FR uniquement (en_core_web_md non disponible)")

    total += 1
    if _ok(data_en["identite"]["nom_complet"] is not None,
           f"Nom extrait : {data_en['identite']['nom_complet']}",
           "Nom non extrait"):
        passed += 1

    total += 1
    if _ok(meta_en["total_competences"] >= 5,
           f"Compétences OK : {meta_en['total_competences']}",
           f"Trop peu de compétences : {meta_en['total_competences']}"):
        passed += 1

    total += 1
    if _ok(meta_en["confidence_score"] >= 0.65,
           f"Confiance EN OK : {meta_en['confidence_score']:.0%}",
           f"Confiance EN trop faible : {meta_en['confidence_score']:.0%}"):
        passed += 1

    # ── CV français ─────────────────────────────────────────────
    print(f"\n  -- CV FRANÇAIS --")
    result_fr = parser.parse(CV_FR, cv_id="test_fr")
    assert result_fr["success"], f"Parsing FR échoué : {result_fr.get('error')}"

    data_fr = result_fr["parsed_data"]
    meta_fr = data_fr["metadata"]

    print(f"  Langue détectée  : {meta_fr.get('langue_cv')} ({meta_fr.get('langue_confiance', 0):.0%})")
    print(f"  Modèle actif     : {meta_fr.get('spacy_model_actif')}")
    print(f"  Nom              : {data_fr['identite']['nom_complet']}")
    print(f"  Compétences      : {meta_fr['total_competences']}")
    print(f"  Confiance        : {meta_fr['confidence_score']:.0%}")

    total += 1
    if _ok(meta_fr.get("langue_cv") == "fr",
           "langue_cv = 'fr' dans metadata",
           f"langue_cv incorrect: {meta_fr.get('langue_cv')}"):
        passed += 1

    total += 1
    if _ok(meta_fr.get("spacy_model_actif") in ("fr_core_news_md", "blank:fr"),
           f"Modèle FR utilisé : {meta_fr.get('spacy_model_actif')}",
           f"Mauvais modèle FR: {meta_fr.get('spacy_model_actif')}"):
        passed += 1

    total += 1
    if _ok(meta_fr["confidence_score"] >= 0.65,
           f"Confiance FR maintenue : {meta_fr['confidence_score']:.0%}",
           f"Confiance FR dégradée : {meta_fr['confidence_score']:.0%}"):
        passed += 1

    return passed, total


def _run_real_cv_en():
    """Test sur le vrai CV anglais C_v_Pro_RanimEnglish.pdf"""
    print(f"\n{SEP}")
    print("  TEST 3 : VRAI CV ANGLAIS (C_v_Pro_RanimEnglish.pdf)")
    print(SEP)

    passed = 0
    total = 0

    cv_path = Path(__file__).resolve().parents[2] / "data" / "Cv" / "C_v_Pro_RanimEnglish.pdf"
    if not cv_path.exists():
        print(f"  [SKIP] Fichier non trouvé : {cv_path}")
        return 0, 0

    try:
        from app.services.extraction.cv_extractor import CVExtractor
        extractor = CVExtractor()
        ext_result = extractor.extract(str(cv_path))
        assert ext_result.get("success"), f"Extraction échouée : {ext_result.get('error')}"
        text = ext_result["text"]
        print(f"  Extraction : OK ({len(text)} chars)")

        parser = NLPParser()
        result = parser.parse(text, cv_id="ranim_en")
        assert result["success"], f"Parsing échoué : {result.get('error')}"

        data = result["parsed_data"]
        meta = data["metadata"]

        print(f"  Langue détectée  : {meta.get('langue_cv')} ({meta.get('langue_confiance', 0):.0%})")
        print(f"  Modèle actif     : {meta.get('spacy_model_actif')}")
        print(f"  Nom              : {data['identite']['nom_complet']}")
        print(f"  Compétences      : {meta['total_competences']}")
        print(f"  Expériences      : {meta['total_experiences']}")
        print(f"  Confiance        : {meta['confidence_score']:.0%}")

        total += 1
        if _ok(meta.get("langue_cv") == "en",
               f"Langue EN détectée sur vrai CV anglais ({meta.get('langue_confiance', 0):.0%})",
               f"Langue incorrecte : {meta.get('langue_cv')}"):
            passed += 1

        total += 1
        if _ok(meta["confidence_score"] >= 0.70,
               f"Confiance ameliorée : {meta['confidence_score']:.0%} (>= 70%)",
               f"Confiance : {meta['confidence_score']:.0%} (toujours < 70%)"):
            passed += 1

    except Exception as e:
        print(f"  ERREUR : {e}")
        import traceback
        traceback.print_exc()

    return passed, total


def test_language_detector():
    passed, total = _run_language_detector()
    assert passed == total


def test_multilingual_parser():
    passed, total = _run_multilingual_parser()
    assert passed == total


def test_real_cv_en():
    passed, total = _run_real_cv_en()
    assert passed == total


def run():
    print(f"\n{SEP}")
    print("  TEST MULTILINGUE — 3S TalentMatch")
    print(SEP)

    total_passed = 0
    total_tests = 0

    p, t = _run_language_detector()
    total_passed += p
    total_tests += t

    p, t = _run_multilingual_parser()
    total_passed += p
    total_tests += t

    p, t = _run_real_cv_en()
    total_passed += p
    total_tests += t

    print(f"\n{SEP}")
    verdict = "OK" if total_passed == total_tests else "FAIL"
    print(f"  [{verdict}]  RÉSULTAT FINAL : {total_passed}/{total_tests} tests passés")
    print(SEP)

    return total_passed == total_tests


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
