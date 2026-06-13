"""
audit_cross_encoder.py — Tâche 3
==================================
1. Vérifie ce qui est passé au cross-encoder (ou fallback bi-encodeur)
2. Compare l'entrée actuelle vs structurée :
   Actuel  : "{titre}\n{description}\nCompétences requises: ..."
   Structuré: "Poste: {titre}. Compétences requises: {skills}. {description}"
3. Compare les scores avant/après sur les 9 cas originaux
4. Garde la version qui donne le meilleur classement (Spearman)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.services.matching.match_engine import (
    _offer_text_for_semantic, _candidate_text_for_semantic, _extract_offer_skills, _normalize_offer_text
)

# ─────────────────────────────────────────────────────────────────────────────
# Nouvelle fonction de construction du texte offre — version structurée
# ─────────────────────────────────────────────────────────────────────────────
def _offer_text_structured(offer) -> str:
    """Texte offre structuré pour le cross-encoder / bi-encodeur.
    Format : "Poste: {titre}. Compétences requises: {skills}. {description}"
    Plus lisible pour le modèle — labels explicites avant chaque section.
    """
    titre = _normalize_offer_text(offer.titre or "")
    desc  = _normalize_offer_text((offer.description or "")[:250])
    skills = _extract_offer_skills(offer)

    parts = []
    if titre:
        parts.append(f"Poste: {titre}.")
    if skills:
        parts.append(f"Compétences requises: {', '.join(skills)}.")
    if desc:
        parts.append(desc)
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Mock objects (mêmes que test_matching_reel.py)
# ─────────────────────────────────────────────────────────────────────────────
class Offer:
    def __init__(self, titre, desc, skills, exp=2, edu=3):
        self.titre=titre; self.description=desc; self.competences_requises=skills
        self.competences_appreciees=[]; self.experience_requise=exp
        self.formation_requise_niveau=edu; self.domaine_metier=""
        self.niveau_seniorite=""; self.type_contrat="CDI"
        self.localisation=None; self.status="active"
        self.raw_text=desc+" "+" ".join(skills)

class Cand:
    def __init__(self, nom, cv, skills, exp=2, edu=3, exps=None, fmts=None):
        self.nom=nom; self.email="x@x.com"; self.raw_text=cv; self.cv_id=None
        self.parsed_data={
            "competences":skills,
            "experiences":exps or [{"poste":nom,"description":cv,"duree_mois":int(exp*12)}],
            "formations":fmts or [],
            "metadata":{"annees_experience_totales":exp,"niveau_formation_max":edu},
        }

O_DEV      = Offer("Développeur Python FastAPI","CDI Python FastAPI PostgreSQL Docker",["Python","FastAPI","PostgreSQL","Docker","Git"],exp=3,edu=5)
O_FINANCE  = Offer("Contrôleur de Gestion","CDI contrôle gestion Excel SAP IFRS",["Comptabilité","Excel","SAP","Contrôle de gestion","Reporting financier","IFRS"],exp=3,edu=5)
O_RH       = Offer("Chargé RH Recrutement","CDI recrutement sourcing LinkedIn paie GPEC",["Recrutement","RH","LinkedIn","Paie","GPEC","Droit du travail"],exp=2,edu=3)
O_INFIRMIER= Offer("Infirmier IDE Soins Intensifs","CDI infirmier IDE soins intensifs réanimation urgences",["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences"],exp=2,edu=3)

C_DEV      = Cand("Dev Python",  "Python 4 ans FastAPI Django PostgreSQL Docker Redis Git Bac+5",["Python","FastAPI","Django","PostgreSQL","Docker","Git","REST API"],exp=4,edu=5)
C_COMPTABLE= Cand("Comptable",   "Comptable 4 ans SAP Excel IFRS bilan contrôle gestion audit Bac+5",["Comptabilité","SAP","Excel","IFRS","Reporting financier","Contrôle de gestion","Audit"],exp=4,edu=5)
C_RH       = Cand("Chargée RH",  "RH 3 ans recrutement LinkedIn paie GPEC droit travail SIRH Bac+3",["RH","Recrutement","LinkedIn","Paie","GPEC","Droit du travail","SIRH"],exp=3,edu=3)
C_INFIRMIER= Cand("Infirmier",   "Infirmier IDE 3 ans soins intensifs réanimation urgences ECG Bac+3",["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences","ECG"],exp=3,edu=3)
C_DEV_FIN  = Cand("Dev→Finance", "Python 4 ans FastAPI Docker PostgreSQL Git Bac+5",["Python","FastAPI","PostgreSQL","Docker","Git"],exp=4,edu=5)
C_COMPT_DEV= Cand("Compta→Dev",  "Comptable 4 ans SAP Excel IFRS audit Bac+5",["Comptabilité","SAP","Excel","IFRS","Audit"],exp=4,edu=5)
C_INF_DEV  = Cand("Inf→Dev",     "Infirmier IDE 3 ans soins intensifs réanimation Bac+3",["Soins infirmiers","IDE","Réanimation","Urgences"],exp=3,edu=3)

PAIRS = [
    (O_DEV,       C_DEV,      "Dev→Dev"),
    (O_FINANCE,   C_COMPTABLE,"Finance→Finance"),
    (O_RH,        C_RH,       "RH→RH"),
    (O_INFIRMIER, C_INFIRMIER,"Infirmier→Infirmier"),
    (O_DEV,       C_COMPT_DEV,"Compta→Dev"),
    (O_FINANCE,   C_DEV_FIN,  "Dev→Finance"),
    (O_DEV,       C_INF_DEV,  "Inf→Dev"),
    (O_FINANCE,   C_RH,       "RH→Finance"),
    (O_RH,        C_COMPTABLE,"Finance→RH"),
]

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()

    # 1. Vérifier quel méthode est utilisée pour la sémantique
    test_offer_text_current  = _offer_text_for_semantic(O_DEV)
    test_offer_text_struct   = _offer_text_structured(O_DEV)
    test_cv_text             = _candidate_text_for_semantic(C_DEV)

    # Tester si le reranker est chargé
    reranker_loaded = scorer._ensure_reranker_loaded()

    print("=" * 70)
    print("  Audit Cross-Encoder — entrée et structuration")
    print("=" * 70)
    print(f"\n  Reranker chargé : {reranker_loaded}")
    if not reranker_loaded:
        print(f"  → Fallback bi-encodeur BGE-M3 (offline mode)")

    print(f"\n  Texte offre ACTUEL (offre Python):")
    print("  " + test_offer_text_current.replace("\n", "\n  "))
    print(f"\n  Texte offre STRUCTURÉ (offre Python):")
    print("  " + test_offer_text_struct)

    # 2. Comparer les scores sem_sim pour les 9 paires
    print(f"\n{'='*70}")
    print(f"  Comparaison sem_sim : actuel vs structuré")
    print(f"{'='*70}")
    print(f"  {'Paire':22s} | {'Actuel':8s} | {'Structuré':10s} | {'Diff':6s} | {'Meilleur'}")
    print(f"  {'-'*22}-+-{'-'*8}-+-{'-'*10}-+-{'-'*6}-+-{'-'*10}")

    better_current = better_struct = equal = 0
    for offer, cand, label in PAIRS:
        offer_text_curr   = _offer_text_for_semantic(offer)
        offer_text_struct = _offer_text_structured(offer)
        cv_text           = _candidate_text_for_semantic(cand)

        # Score sémantique ACTUEL
        sem_curr = scorer.score_semantique(offer_text_curr, cv_text)

        # Score sémantique STRUCTURÉ
        # On patche temporairement en passant directement
        sem_struct = scorer.score_semantique(offer_text_struct, cv_text)

        diff = sem_struct - sem_curr
        better = "struct" if diff > 0.005 else ("actuel" if diff < -0.005 else "=")
        if better == "struct": better_struct += 1
        elif better == "actuel": better_current += 1
        else: equal += 1

        print(f"  {label:22s} | {sem_curr*100:6.1f}% | {sem_struct*100:8.1f}% | {diff*100:+5.1f}% | {better}")

    print(f"\n  Résumé : structuré meilleur={better_struct} | actuel meilleur={better_current} | égaux={equal}")
    winner = "structuré" if better_struct > better_current else ("actuel" if better_current > better_struct else "identiques")
    print(f"  → Recommandation : garder la version {winner}")

    # 3. Conclusion
    print(f"\n{'='*70}")
    print(f"  Conclusions :")
    if not reranker_loaded:
        print(f"  • Cross-encoder BGE-reranker-v2-m3 NON chargé (mode offline).")
        print(f"  • sem_sim/sem_v2 utilise le bi-encodeur BGE-M3 (cosine similarity).")
        print(f"  • Activer le reranker nécessite connexion internet ou modèle local.")
    else:
        print(f"  • Cross-encoder actif → sem_v2 est un signal plus fort.")
    if winner == "structuré":
        print(f"  • Le format structuré améliore sem_sim → à adopter dans _offer_text_for_semantic().")
    elif winner == "actuel":
        print(f"  • Le format actuel est déjà optimal → pas de changement nécessaire.")
    else:
        print(f"  • Les deux formats donnent des scores quasi-identiques.")
        print(f"  • Le format actuel est conservé (moins de code, même résultat).")
    print("=" * 70)
