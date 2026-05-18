"""
TalentMatch — Test matching sur vrais CVs
==========================================
Scanne automatiquement tous les CVs (PDF/DOCX) dans data/Cv/,
les parse via le pipeline complet, et les classe contre plusieurs offres.

Usage (depuis backend/) :
    python ../data/scripts/test_real_cvs.py

Ajouter des CVs : copiez vos fichiers PDF/DOCX dans data/Cv/ et relancez.
"""
from __future__ import annotations
import os, sys, time

BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

CV_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'Cv'))

from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.nlp_parser import NLPParser
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer

# ─────────────────────────────────────────────────────────────────────────────
# Offres de test — modifiez selon vos besoins
# ─────────────────────────────────────────────────────────────────────────────

OFFRES = [
    JobOffer(
        titre="Développeur Python Senior",
        description="Python senior 5 ans minimum. FastAPI, PostgreSQL, Docker obligatoire. Kubernetes AWS apprécié. Bac+5.",
        competences_requises=["Python", "FastAPI", "PostgreSQL", "Docker"],
        competences_appreciees=["Kubernetes", "AWS", "Redis"],
    ),
    JobOffer(
        titre="Développeur Full Stack React / Node.js",
        description="Full Stack 3 ans. React TypeScript frontend, Node.js backend, MongoDB REST API. Docker Git obligatoire.",
        competences_requises=["React", "Node.js", "TypeScript", "MongoDB"],
        competences_appreciees=["Docker", "GraphQL", "AWS"],
    ),
    JobOffer(
        titre="Ingénieur DevOps Cloud",
        description="DevOps 4 ans. Docker Kubernetes Terraform AWS CI/CD GitLab obligatoire. Prometheus Grafana apprécié.",
        competences_requises=["Docker", "Kubernetes", "Terraform", "AWS", "CI/CD"],
        competences_appreciees=["Prometheus", "Grafana", "Ansible"],
    ),
    JobOffer(
        titre="Data Scientist / ML Engineer",
        description="Data Scientist 3 ans. Python TensorFlow PyTorch SQL Machine Learning requis. MLOps Spark apprécié.",
        competences_requises=["Python", "Machine Learning", "TensorFlow", "SQL"],
        competences_appreciees=["MLOps", "PyTorch", "Spark", "NLP"],
    ),
    JobOffer(
        titre="Ingénieur Mécanique Conception",
        description="Ingénieur mécanique 3 ans. SolidWorks CATIA calcul structure RDM obligatoire. ANSYS ISO apprécié. Bac+5.",
        competences_requises=["SolidWorks", "CATIA", "Calcul de structure", "Résistance des matériaux"],
        competences_appreciees=["ANSYS", "Normes ISO", "Gestion de projet"],
    ),
    JobOffer(
        titre="Responsable Comptable",
        description="Comptable confirmé 5 ans. Sage Excel TVA fiscalité bilan obligatoire. IFRS audit apprécié. Bac+3.",
        competences_requises=["Comptabilité", "Sage", "Excel", "Fiscalité", "TVA"],
        competences_appreciees=["IFRS", "Audit", "Contrôle de gestion"],
    ),
]

DECISIONS_FR = {
    "Excellent candidat":               "✅ Excellent",
    "Bon profil - Entretien recommandé": "🟢 Bon profil",
    "Profil partiel - A evaluer":        "🟡 A évaluer",
    "Profil non adapté":                "🔴 Non adapté",
}

DOMAINES_FR = {
    "it":                "Informatique",
    "ingenierie":        "Ingénierie",
    "finance":           "Finance",
    "droit":             "Droit",
    "rh":                "Ressources Humaines",
    "marketing":         "Marketing",
    "commerce":          "Commerce",
    "sante":             "Santé",
    "sante_paramedical": "Paramédical",
    "sante_pharma":      "Pharmacie",
    "education":         "Éducation",
    "supply_chain":      "Supply Chain",
    "gestion_projet":    "Gestion Projet",
    "design_ux":         "Design / UX",
}

# ─────────────────────────────────────────────────────────────────────────────
# Scan des CVs
# ─────────────────────────────────────────────────────────────────────────────

def scan_cvs(cv_dir: str) -> list[str]:
    """Retourne tous les PDF/DOCX du dossier (pas les sous-dossiers generated_tests)."""
    supported = {'.pdf', '.docx'}
    files = []
    for f in os.listdir(cv_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in supported:
            files.append(os.path.join(cv_dir, f))
    return sorted(files)


def parse_cv(path: str, extractor: CVExtractor, parser: NLPParser) -> tuple[Candidate | None, str]:
    """Parse un fichier CV → Candidate. Retourne (candidate, nom_fichier)."""
    filename = os.path.basename(path)
    try:
        extracted = extractor.extract(path)
        if not extracted.get('success') or not extracted.get('text', '').strip():
            return None, filename

        raw_text = extracted['text']
        nlp_result = parser.parse(raw_text)

        # Le NLP parser retourne {'success', 'parsed_data', ...}
        if isinstance(nlp_result, dict) and 'parsed_data' in nlp_result:
            pd = nlp_result['parsed_data']
        else:
            pd = nlp_result

        # Normaliser les compétences : liste de dicts → liste de strings
        raw_skills = pd.get('competences', [])
        if raw_skills and isinstance(raw_skills[0], dict):
            skills_list = [s['name'] for s in raw_skills if s.get('name')]
        else:
            skills_list = [s for s in raw_skills if isinstance(s, str)]

        # Normaliser les expériences
        experiences = pd.get('experiences', [])
        if not isinstance(experiences, list):
            experiences = []

        # Normaliser les formations
        formations = pd.get('formations', [])
        if not isinstance(formations, list):
            formations = []

        # Extraire les années d'expérience
        meta = pd.get('metadata', {}) or {}
        exp_years = meta.get('annees_experience_totales', None)
        if exp_years is None:
            # Chercher dans identite ou contacts
            identite = pd.get('identite', {}) or {}
            exp_years = identite.get('annees_experience', None)

        # Fallback : extraire les années depuis le texte brut si le parser a échoué
        # Cas typique : "4 ans d'expérience" mentionné dans le résumé/profil du CV
        if exp_years is None or exp_years < 0.5:
            import re as _re
            m_exp = _re.search(
                r'(\d+(?:[.,]\d+)?)\s+ans?\s+d[\'e’]exp[ée]rience',
                raw_text, _re.IGNORECASE
            )
            if m_exp:
                exp_years = float(m_exp.group(1).replace(',', '.'))

        # Niveau de formation
        form_level = meta.get('niveau_formation_max', 4)

        parsed_data = {
            'competences': skills_list,
            'formations': formations,
            'experiences': experiences,
            'metadata': {
                'annees_experience_totales': exp_years if exp_years is not None else 3,
                'niveau_formation_max': form_level,
            },
        }

        candidate = Candidate(raw_text=raw_text, parsed_data=parsed_data)
        return candidate, filename
    except Exception as e:
        print(f"  ⚠ Erreur parsing {filename}: {e}")
        return None, filename


def get_display_name(filename: str, parsed_data: dict) -> str:
    """Construit un nom lisible : prénom + nom si dispo, sinon nom de fichier."""
    # Chercher dans les différentes structures possibles
    nlp_result = parsed_data  # parsed_data ici est déjà le dict normalisé
    name = ''
    if not name:
        name = os.path.splitext(filename)[0][:35]
    return name

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 75)
    print("TalentMatch — Test matching sur vrais CVs")
    print("=" * 75)

    # ── 1. Charger les outils ────────────────────────────────────────────────
    print("\nChargement des modèles...")
    extractor = CVExtractor(enable_ocr_fallback=False)  # OCR désactivé pour rapidité
    parser    = NLPParser()
    scorer    = BERTMatchingScorer()
    scorer._ensure_loaded()
    print(f"  BERT v2.0 chargé  |  MLP actif")

    # ── 2. Scanner le dossier CVs ────────────────────────────────────────────
    cv_files = scan_cvs(CV_DIR)
    print(f"\nCVs trouvés dans data/Cv/ : {len(cv_files)}")
    for f in cv_files:
        print(f"  • {os.path.basename(f)}")

    if not cv_files:
        print("\n  → Aucun CV trouvé. Copiez vos fichiers PDF/DOCX dans data/Cv/ et relancez.")
        return

    # ── 3. Parser tous les CVs ───────────────────────────────────────────────
    print(f"\nParsing des {len(cv_files)} CVs...")
    candidates: list[tuple[Candidate, str, str]] = []  # (candidate, filename, display_name)
    for path in cv_files:
        cv, fname = parse_cv(path, extractor, parser)
        if cv:
            dname = get_display_name(fname, cv.parsed_data)
            skills = cv.parsed_data.get('competences', [])
            exp    = cv.parsed_data.get('metadata', {}).get('annees_experience_totales', '?')
            print(f"  ✓ {dname:<30}  {exp} ans exp  |  skills: {', '.join(skills[:4])}{'...' if len(skills) > 4 else ''}")
            candidates.append((cv, fname, dname))
        else:
            print(f"  ✗ {fname} — ignoré (texte vide ou erreur)")

    if not candidates:
        print("\n  → Aucun CV parsé avec succès.")
        return

    # ── 4. Matching contre chaque offre ─────────────────────────────────────
    print(f"\n{'='*75}")
    print(f"RÉSULTATS DU MATCHING — {len(candidates)} candidats × {len(OFFRES)} offres")
    print(f"{'='*75}")

    for offer in OFFRES:
        print(f"\n{'─'*75}")
        print(f"OFFRE : {offer.titre}")
        print(f"Skills requises : {', '.join(offer.competences_requises)}")
        print(f"{'─'*75}")
        print(f"  {'#':<3} {'Candidat':<32} {'Score':>6}  {'Décision':<20}  {'Domaine':<12}  Skills matchées")
        print(f"  {'─'*3} {'─'*32} {'─'*6}  {'─'*20}  {'─'*12}  {'─'*20}")

        results = []
        for cv, fname, dname in candidates:
            try:
                score, details = scorer.score(offer, cv)
                pct      = score * 100 if score <= 1.0 else score
                decision = DECISIONS_FR.get(details.get('decision', ''), details.get('decision', '?'))
                _raw_domain = details.get('candidate_domain') or ''
                domain   = DOMAINES_FR.get(_raw_domain, _raw_domain) if _raw_domain else '—'
                capped   = ' [CAP]' if details.get('domain_cap_applied') else ''
                # Skills matched
                criteres = details.get('criteres', {}).get('obligatoires', [])
                matched  = [c['skill'] for c in criteres if c.get('matched')]
                results.append((pct, dname, decision, domain, capped, matched))
            except Exception as e:
                results.append((0.0, dname, '🔴 Erreur', '—', '', []))

        results.sort(key=lambda x: x[0], reverse=True)

        for i, (pct, dname, decision, domain, capped, matched) in enumerate(results, 1):
            matched_str = ', '.join(matched[:3]) + ('...' if len(matched) > 3 else '') if matched else '—'
            print(f"  {i:<3} {dname:<32} {pct:5.1f}%  {decision:<20}  {domain:<12}  {matched_str}{capped}")

    print(f"\n{'='*75}")
    print(f"Test terminé — {len(candidates)} candidats, {len(OFFRES)} offres")
    print(f"{'='*75}")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\nDurée totale : {time.time()-t0:.1f}s")
