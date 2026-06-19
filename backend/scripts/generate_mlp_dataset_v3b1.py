"""
generate_mlp_dataset_v3b1.py  — version rapide (batch encoding)
================================================================
Encode TOUS les textes en une seule passe BGE-M3, puis calcule les
features vectoriellement. ~300 paires en <2 minutes sur CPU.

Zero train/prod gap : les 10 features sont celles de _compute_mlp_features().
"""
from __future__ import annotations
import sys, os, csv, random, math
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",   "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
from app.services.matching_sandbox.bert_scorer import (
    BERTMatchingScorer, _normalize_skill,
    _detect_edu_domain, _edu_domain_compatibility,
    _TECH_EXPANSION,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_CSV   = REPO_ROOT / "data" / "mlp_training_fusion" / "dataset_v3b1.csv"
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

random.seed(42)

COLS = [
    "offre", "candidat",
    "sem_sim", "skill_rate_w", "exp_score", "form_score",
    "sem_v2", "edu_dom_compat", "exp_dom_ratio",
    "title_skill_match", "crit_skill_ratio", "offer_type_enc",
    "label",
]

# ─────────────────────────────────────────────────────────────────────────────
# Données : offres + candidats structurés
# ─────────────────────────────────────────────────────────────────────────────
OFFERS = [
    # IT
    dict(titre="Développeur Python FastAPI", dom="it", skills=["Python","FastAPI","PostgreSQL","Docker","Git","REST API"], exp=3, edu=5, ote=0.5),
    dict(titre="Développeur Python Senior",  dom="it", skills=["Python","FastAPI","Django","PostgreSQL","Redis","Kubernetes"], exp=5, edu=5, ote=1.0),
    dict(titre="Stage Développeur Python",   dom="it", skills=["Python","Django","REST API","Git"], exp=0, edu=4, ote=0.0),
    dict(titre="Développeur React Frontend", dom="it", skills=["React","TypeScript","Node.js","CSS","Figma"], exp=2, edu=3, ote=0.5),
    dict(titre="Ingénieur DevOps Cloud",     dom="it", skills=["DevOps","Kubernetes","Docker","Terraform","AWS","CI/CD"], exp=3, edu=5, ote=0.5),
    dict(titre="Data Scientist ML",          dom="it", skills=["Machine Learning","Python","TensorFlow","scikit-learn","Pandas","SQL"], exp=3, edu=5, ote=0.5),
    dict(titre="Architecte Cloud AWS Senior",dom="it", skills=["AWS","Kubernetes","Terraform","Docker","CI/CD","Python"], exp=8, edu=5, ote=1.0),
    dict(titre="Développeur Java Backend",   dom="it", skills=["Java","Spring Boot","PostgreSQL","Docker","Maven"], exp=3, edu=5, ote=0.5),
    # Finance
    dict(titre="Contrôleur de Gestion",     dom="finance", skills=["Contrôle de gestion","Excel","SAP","Reporting financier","IFRS","Comptabilité"], exp=3, edu=5, ote=0.5),
    dict(titre="Comptable Senior",           dom="finance", skills=["Comptabilité générale","SAP","IFRS","Audit interne","Fiscalité","Excel"], exp=5, edu=5, ote=1.0),
    dict(titre="Auditeur Interne Junior",    dom="finance", skills=["Audit interne","Comptabilité","Excel","Reporting financier"], exp=1, edu=3, ote=0.0),
    dict(titre="Analyste Financier",         dom="finance", skills=["Analyse financière","Excel","SAP","Gestion budgétaire","Trésorerie"], exp=3, edu=5, ote=0.5),
    # RH
    dict(titre="Chargé RH Recrutement",      dom="rh", skills=["Recrutement","RH","LinkedIn","Paie","GPEC","Droit du travail"], exp=2, edu=3, ote=0.0),
    dict(titre="Responsable RH Senior",      dom="rh", skills=["RH","SIRH","GPEC","Gestion paie","Relations sociales","Droit du travail"], exp=7, edu=5, ote=1.0),
    dict(titre="Gestionnaire Paie",          dom="rh", skills=["Gestion paie","SIRH","Charges sociales","Droit du travail","Excel"], exp=2, edu=3, ote=0.0),
    # Santé
    dict(titre="Infirmier IDE Soins Intensifs", dom="sante", skills=["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences","ECG"], exp=2, edu=3, ote=0.5),
    dict(titre="Infirmier Urgences Senior",     dom="sante", skills=["Soins infirmiers","Urgences","Réanimation","Soins critiques","ECG"], exp=5, edu=3, ote=1.0),
    # Droit
    dict(titre="Juriste Droit des Affaires",  dom="droit", skills=["Droit des affaires","Contrats","RGPD","Conformité","Droit commercial"], exp=3, edu=5, ote=0.5),
    dict(titre="Juriste Droit Social Senior", dom="droit", skills=["Droit du travail","Contentieux","Relations sociales","Droit social"], exp=6, edu=5, ote=1.0),
    # BTP
    dict(titre="Ingénieur Génie Civil",      dom="btp", skills=["Génie civil","BIM","AutoCAD","Revit","Suivi de chantier"], exp=3, edu=5, ote=0.5),
    dict(titre="Conducteur de Travaux Senior",dom="btp", skills=["Conduite de travaux","Suivi de chantier","Maîtrise d'œuvre","BIM"], exp=7, edu=3, ote=1.0),
    # Logistique
    dict(titre="Responsable Logistique",     dom="logistique", skills=["Logistique","Supply chain","Gestion des stocks","SAP","WMS","Transport"], exp=3, edu=5, ote=0.5),
    dict(titre="Acheteur Senior",            dom="logistique", skills=["Achats","Négociation","SAP","Gestion des fournisseurs","Supply chain"], exp=6, edu=5, ote=1.0),
    # Marketing
    dict(titre="Chef de Projet Marketing Digital", dom="marketing", skills=["Marketing digital","SEO","Google Ads","CRM","HubSpot","Community Management"], exp=3, edu=5, ote=0.5),
    dict(titre="Community Manager Junior",         dom="marketing", skills=["Community Management","Réseaux sociaux","Canva","Marketing"], exp=1, edu=3, ote=0.0),
]

CANDS = [
    # IT
    dict(nom="Dev Python 5ans",  dom="it", skills=["Python","FastAPI","Django","PostgreSQL","Docker","Redis","Git","REST API"], exp=5, edu=5, spec="Génie Logiciel", cv="Python 5 ans FastAPI Django PostgreSQL Docker Redis Kubernetes CI/CD REST API Bac+5"),
    dict(nom="Dev Python 2ans",  dom="it", skills=["Python","FastAPI","PostgreSQL","Docker","Git"], exp=2, edu=5, spec="Informatique", cv="Python 2 ans FastAPI PostgreSQL Docker Git REST Bac+5"),
    dict(nom="Stage Python",     dom="it", skills=["Python","Django","REST API","Git"], exp=0, edu=4, spec="Informatique", cv="Etudiant Python Django REST stage Bac+4"),
    dict(nom="Dev React 3ans",   dom="it", skills=["React","TypeScript","Node.js","CSS","Redux"], exp=3, edu=3, spec="Informatique", cv="React TypeScript Node.js CSS Redux 3 ans Bac+3"),
    dict(nom="Dev React Débutant",dom="it", skills=["React","JavaScript","HTML","CSS"], exp=1, edu=3, spec="Informatique", cv="React JavaScript HTML CSS débutant stage 1 an Bac+3"),
    dict(nom="DevOps 4ans",      dom="it", skills=["DevOps","Kubernetes","Docker","Terraform","AWS","CI/CD","Jenkins"], exp=4, edu=5, spec="Infrastructure Cloud", cv="DevOps Kubernetes Docker Terraform AWS CI/CD Jenkins 4 ans Bac+5"),
    dict(nom="Data Scientist 3ans",dom="it", skills=["Machine Learning","Python","TensorFlow","scikit-learn","Pandas","SQL","NLP"], exp=3, edu=5, spec="Data Science", cv="Machine Learning Python TensorFlow scikit-learn Pandas SQL NLP 3 ans Bac+5"),
    dict(nom="Dev Java 4ans",    dom="it", skills=["Java","Spring Boot","PostgreSQL","Docker","Maven","Git"], exp=4, edu=5, spec="Informatique", cv="Java Spring Boot Hibernate PostgreSQL Docker Maven 4 ans Bac+5"),
    dict(nom="Dev Java Junior",  dom="it", skills=["Java","Spring Boot","MySQL","Git"], exp=1, edu=3, spec="Informatique", cv="Java Spring Boot MySQL débutant 1 an Bac+3"),
    # Finance
    dict(nom="Comptable 5ans",   dom="finance", skills=["Comptabilité générale","SAP","IFRS","Audit interne","Fiscalité","Contrôle de gestion","Excel"], exp=5, edu=5, spec="Finance Comptabilité", cv="Comptabilité générale SAP IFRS bilan audit interne fiscalité contrôle gestion 5 ans Bac+5"),
    dict(nom="Contrôleur Gestion 3ans", dom="finance", skills=["Contrôle de gestion","Reporting financier","SAP","Excel","IFRS","Analyse financière"], exp=3, edu=5, spec="Finance", cv="Contrôle de gestion reporting financier SAP Excel IFRS 3 ans Bac+5"),
    dict(nom="Auditeur 2ans",    dom="finance", skills=["Audit interne","Comptabilité","Excel","Reporting financier"], exp=2, edu=3, spec="Comptabilité", cv="Audit interne comptabilité Excel reporting 2 ans Bac+3"),
    dict(nom="Analyste Financier 3ans", dom="finance", skills=["Analyse financière","Excel","SAP","Gestion budgétaire","Trésorerie"], exp=3, edu=5, spec="Finance", cv="Analyse financière modélisation Excel SAP gestion budgétaire trésorerie 3 ans Bac+5"),
    # RH
    dict(nom="Chargée RH 3ans", dom="rh", skills=["RH","Recrutement","LinkedIn","Paie","GPEC","Droit du travail","SIRH"], exp=3, edu=3, spec="Ressources Humaines", cv="RH recrutement sourcing LinkedIn paie GPEC droit travail SIRH 3 ans Bac+3"),
    dict(nom="Responsable RH 7ans", dom="rh", skills=["RH","SIRH","GPEC","Gestion paie","Relations sociales","Droit du travail"], exp=7, edu=5, spec="Ressources Humaines", cv="RH SIRH GPEC gestion paie relations sociales droit travail management 7 ans Bac+5"),
    dict(nom="Gestionnaire Paie 2ans", dom="rh", skills=["Gestion paie","SIRH","Charges sociales","Droit du travail","Excel"], exp=2, edu=3, spec="RH", cv="Gestion paie SIRH charges sociales droit travail Excel 2 ans Bac+3"),
    dict(nom="Recruteur Junior", dom="rh", skills=["Recrutement","LinkedIn","Sourcing"], exp=1, edu=3, spec="RH", cv="Recrutement sourcing LinkedIn annonces stage 1 an Bac+3"),
    # Santé
    dict(nom="Infirmier IDE 4ans", dom="sante", skills=["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences","ECG"], exp=4, edu=3, spec="Soins Infirmiers", cv="Infirmier IDE soins intensifs réanimation urgences ECG 4 ans Bac+3"),
    dict(nom="Infirmier Urgences 2ans", dom="sante", skills=["Soins infirmiers","Urgences","Réanimation","Soins critiques","ECG"], exp=2, edu=3, spec="Soins Infirmiers", cv="Infirmier urgences soins critiques réanimation ECG 2 ans Bac+3"),
    # Droit
    dict(nom="Juriste Affaires 4ans", dom="droit", skills=["Droit des affaires","Contrats","RGPD","Conformité","Droit commercial"], exp=4, edu=5, spec="Droit des Affaires", cv="Juriste droit des affaires contrats RGPD conformité droit commercial 4 ans Bac+5"),
    dict(nom="Juriste Social 6ans",   dom="droit", skills=["Droit du travail","Contentieux","Relations sociales","Droit social"], exp=6, edu=5, spec="Droit Social", cv="Juriste droit social contentieux relations sociales droit travail 6 ans Bac+5"),
    dict(nom="Juriste Junior",        dom="droit", skills=["Droit des affaires","Contrats","Droit commercial"], exp=1, edu=5, spec="Droit", cv="Juriste droit affaires contrats débutant 1 an Bac+5"),
    # BTP
    dict(nom="Ingénieur GC 4ans", dom="btp", skills=["Génie civil","BIM","AutoCAD","Revit","Suivi de chantier","Béton armé"], exp=4, edu=5, spec="Génie Civil", cv="Ingénieur génie civil BIM AutoCAD Revit chantier structures 4 ans Bac+5"),
    dict(nom="Conducteur Travaux 7ans", dom="btp", skills=["Conduite de travaux","Suivi de chantier","Maîtrise d'œuvre","BIM"], exp=7, edu=3, spec="Génie Civil", cv="Conducteur travaux BTP chantier maîtrise oeuvre suivi budget 7 ans Bac+3"),
    # Logistique
    dict(nom="Resp Logistique 4ans", dom="logistique", skills=["Logistique","Supply chain","Gestion des stocks","SAP","WMS","Transport"], exp=4, edu=5, spec="Logistique", cv="Logistique supply chain gestion stocks SAP WMS transport 4 ans Bac+5"),
    dict(nom="Acheteur 6ans",        dom="logistique", skills=["Achats","Négociation","SAP","Gestion des fournisseurs","Supply chain"], exp=6, edu=5, spec="Supply Chain", cv="Achats négociation fournisseurs SAP supply chain appels offres 6 ans Bac+5"),
    # Marketing
    dict(nom="Chef Projet Mktg 3ans", dom="marketing", skills=["Marketing digital","SEO","Google Ads","CRM","HubSpot","Community Management"], exp=3, edu=5, spec="Marketing", cv="Marketing digital SEO Google Ads CRM HubSpot community management 3 ans Bac+5"),
    dict(nom="Community Manager 1an", dom="marketing", skills=["Community Management","Réseaux sociaux","Canva","Marketing"], exp=1, edu=3, spec="Marketing", cv="Community manager réseaux sociaux contenus Canva 1 an Bac+3"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Calcul des features sans appel à score() — rapide et fidèle
# ─────────────────────────────────────────────────────────────────────────────
DOMAIN_ADJACENT = {
    "it":        {"logistique"},
    "finance":   {"rh","droit"},
    "rh":        {"finance","droit"},
    "droit":     {"rh","finance"},
    "sante":     set(),
    "btp":       set(),
    "logistique":{"it","finance"},
    "marketing": {"rh"},
}

def skill_overlap_fuzzy(offer_skills, cand_skills) -> float:
    from rapidfuzz import fuzz as _rfuzz
    if not offer_skills: return 0.5
    matched = 0
    for req in offer_skills:
        rn = _normalize_skill(req)
        for cs in cand_skills:
            cn = _normalize_skill(cs)
            if rn == cn or _rfuzz.token_set_ratio(rn, cn) >= 80:
                # check expansion
                if rn in _TECH_EXPANSION.get(cn, frozenset()) or cn in _TECH_EXPANSION.get(rn, frozenset()):
                    matched += 1; break
                matched += 1; break
    return round(min(1.0, matched / len(offer_skills)), 4)


def exp_score(cand_exp, req_exp) -> float:
    if req_exp <= 0: return 0.8
    ratio = cand_exp / max(req_exp, 1)
    if ratio >= 1.0: return min(1.0, 0.7 + 0.3 * min(ratio / 1.5, 1.0))
    return round(max(0.0, ratio * 0.8), 4)


def form_score(cand_edu, req_edu) -> float:
    if req_edu <= 0: return 0.8
    if cand_edu >= req_edu: return 1.0
    gap = req_edu - cand_edu
    return round(max(0.0, 1.0 - 0.2 * gap), 4)


def crit_skill_ratio(title_skill, offer_skills, cand_skills) -> float:
    """Ratio skills critiques (titre) matchees."""
    if not title_skill: return 1.0
    ts_norm = _normalize_skill(title_skill)
    crit = [s for s in offer_skills if _normalize_skill(s) == ts_norm]
    if not crit: return 1.0
    from rapidfuzz import fuzz as _rfuzz
    matched = sum(1 for s in crit if any(
        _rfuzz.token_set_ratio(_normalize_skill(s), _normalize_skill(cs)) >= 80
        for cs in cand_skills
    ))
    return round(matched / len(crit), 4)


def compute_label(o, c, sem_sim, s_comp, s_exp, s_form, dom_compat, crit_ratio=1.0) -> float:
    """Label = formule calibrée (approximation offline)."""
    od = o["dom"]; cd = c["dom"]
    if od == cd:
        dom_mult = 1.0
    elif cd in DOMAIN_ADJACENT.get(od, set()):
        dom_mult = 0.70
    elif od[:3] == cd[:3]:
        dom_mult = 0.50
    else:
        dom_mult = 0.15
    base = 0.55 * s_comp + 0.20 * sem_sim + 0.15 * s_exp + 0.10 * s_form
    return round(max(0.04, min(0.95, base * dom_mult)), 4)


def run_fast(scorer: BERTMatchingScorer):
    """Batch encode, puis calcul vectoriel de toutes les features."""
    # ── 1. Collecter tous les textes uniques à encoder ────────────────────────
    texts = []
    for o in OFFERS:
        texts.append(o["titre"] + " " + " ".join(o["skills"]))
    for c in CANDS:
        texts.append(c["cv"])
    unique_texts = list(dict.fromkeys(texts))   # dédupliqué, ordre préservé
    txt_idx = {t: i for i, t in enumerate(unique_texts)}

    print(f"Encoding {len(unique_texts)} textes en batch BGE-M3...")
    embs = scorer._st_model.encode(unique_texts, batch_size=16,
                                   normalize_embeddings=True, show_progress_bar=True)
    print("Encoding terminé.")

    # Embeddings offre et candidat
    offer_embs = np.array([embs[txt_idx[o["titre"] + " " + " ".join(o["skills"])]] for o in OFFERS])
    cand_embs  = np.array([embs[txt_idx[c["cv"]]] for c in CANDS])

    # ── 2. Calculer semantic sim (cosine — embeddings normalisés = dot product) ─
    # shape: (n_offers, n_cands)
    sim_matrix = offer_embs @ cand_embs.T

    # ── 3. Construire les paires ───────────────────────────────────────────────
    pairs = []
    seen  = set()

    def add(oi, ci, label_override=None):
        key = (oi, ci)
        if key in seen: return
        seen.add(key)
        o = OFFERS[oi]; c = CANDS[ci]
        sem = float(np.clip(sim_matrix[oi, ci], 0, 1))

        s_comp  = skill_overlap_fuzzy(o["skills"], c["skills"])
        s_exp   = exp_score(c["exp"], o["exp"])
        s_form  = form_score(c["edu"], o["edu"])

        od = o["dom"]; cd = c["dom"]
        edu_compat = (_edu_domain_compatibility(
            _detect_edu_domain(c["spec"]),
            _detect_edu_domain(" ".join(o["skills"])),
        ))
        dom_same = 1.0 if od == cd else (0.75 if cd in DOMAIN_ADJACENT.get(od,set()) else 0.45)
        exp_dom_r = min(1.0, c["exp"] / max(o["exp"], 1)) if od == cd else 0.3

        # title_skill : premier mot significatif du titre (hors marqueurs seniorite)
        import re, unicodedata as ud
        def _n(t):
            t = ud.normalize("NFKD", t.lower())
            return "".join(c2 for c2 in t if not ud.combining(c2))
        title_n = _n(o["titre"])
        SENIOR_PAT = re.compile(r"\b(senior|junior|expert|stage|alternance|lead|chef|responsable)\b")
        title_clean = SENIOR_PAT.sub(" ", title_n).strip()
        title_words = [w for w in title_clean.split() if len(w) >= 3]
        # cherche si un mot du titre est dans les skills offre
        title_skill = None
        for tw in title_words:
            for sk in o["skills"]:
                if tw in _n(sk):
                    title_skill = sk; break
            if title_skill: break
        if not title_skill and title_words:
            title_skill = title_words[0]
        t_match = 1.0 if title_skill and any(
            title_skill.lower() in _n(cs) or _n(cs) in title_skill.lower()
            for cs in c["skills"]
        ) else 0.0
        c_ratio = crit_skill_ratio(title_skill, o["skills"], c["skills"])

        label = label_override if label_override is not None else \
                compute_label(o, c, sem, s_comp, s_exp, s_form, dom_same, crit_ratio=c_ratio)

        pairs.append({
            "offre":    o["titre"], "candidat": c["nom"],
            "sem_sim":           round(sem, 4),
            "skill_rate_w":      round(s_comp, 4),
            "exp_score":         round(s_exp, 4),
            "form_score":        round(s_form, 4),
            "sem_v2":            round(sem, 4),
            "edu_dom_compat":    round(edu_compat, 4),
            "exp_dom_ratio":     round(exp_dom_r, 4),
            "title_skill_match": round(t_match, 4),
            "crit_skill_ratio":  round(c_ratio, 4),
            "offer_type_enc":    round(o["ote"], 4),
            "label":             round(label, 4),
        })

    # ── 4. Paires positives (même domaine) ────────────────────────────────────
    print("Paires positives (même domaine)...")
    for oi, o in enumerate(OFFERS):
        for ci, c in enumerate(CANDS):
            if c["dom"] == o["dom"]:
                add(oi, ci)

    # ── 5. Paires adjacentes ───────────────────────────────────────────────────
    print("Paires adjacentes...")
    for oi, o in enumerate(OFFERS):
        for ci, c in enumerate(CANDS):
            if c["dom"] in DOMAIN_ADJACENT.get(o["dom"], set()):
                add(oi, ci)

    # ── 6. Paires négatives (~30%) ─────────────────────────────────────────────
    print("Paires négatives (hors-domaine)...")
    NEG = {
        "it":        ["finance","rh","sante","droit","btp"],
        "finance":   ["it","sante","btp","marketing"],
        "rh":        ["it","sante","btp","logistique"],
        "sante":     ["it","finance","droit","marketing"],
        "droit":     ["it","sante","btp","logistique"],
        "btp":       ["finance","rh","marketing","sante"],
        "logistique":["sante","droit","marketing"],
        "marketing": ["sante","droit","btp"],
    }
    for oi, o in enumerate(OFFERS):
        neg_doms = NEG.get(o["dom"], [])
        neg_cands = [ci for ci, c in enumerate(CANDS) if c["dom"] in neg_doms]
        for ci in random.sample(neg_cands, min(5, len(neg_cands))):
            add(oi, ci)

    return pairs


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Chargement BGE-M3...")
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    print("Scorer OK\n")

    import time
    t0 = time.time()
    pairs = run_fast(scorer)
    elapsed = time.time() - t0

    labels = [p["label"] for p in pairs]
    n_pos  = sum(1 for l in labels if l >= 0.65)
    n_neg  = sum(1 for l in labels if l < 0.35)
    n_med  = len(labels) - n_pos - n_neg

    print(f"\nTerminé en {elapsed:.1f}s")
    print(f"Total : {len(pairs)} paires")
    print(f"  Positives (>=65%) : {n_pos} ({100*n_pos//max(len(pairs),1)}%)")
    print(f"  Moyennes  (35-65%): {n_med} ({100*n_med//max(len(pairs),1)}%)")
    print(f"  Negatives (<35%)  : {n_neg} ({100*n_neg//max(len(pairs),1)}%)")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(pairs)

    print(f"\nDataset : {OUT_CSV}")
    print("Aperçu :")
    for p in pairs[:3]:
        feats = [p[c] for c in COLS[2:-1]]
        print(f"  {p['offre'][:28]:28s} x {p['candidat'][:18]:18s} "
              f"label={p['label']:.2f} sem={p['sem_sim']:.2f} "
              f"skill={p['skill_rate_w']:.2f} title={p['title_skill_match']:.0f}")
