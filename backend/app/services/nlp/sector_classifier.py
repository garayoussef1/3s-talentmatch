"""
Classification sectorielle d'un CV — Sprint 2 (Option C)

Détermine le secteur professionnel principal à partir de :
  1. Distribution des compétences par catégorie (scoring pondéré)
  2. Signaux textuels : titres de postes et mots-clés sectoriels

Catégories → secteurs (sans ML externe, tout NLP local) :
  - informatique_dev  : langages, frameworks_web/mobile, bases_de_donnees, outils_dev, tests_qualite, methodologies
  - data_ia           : data_ml_ia
  - devops_cloud      : devops_cloud, systemes_reseaux
  - cybersecurite     : securite
  - marketing_digital : marketing_digital
  - finance_comptabilite : comptabilite_finance
  - sante_medical     : sante_medical
  - rh_recrutement    : rh_recrutement
  - droit_juridique   : droit_juridique
  - architecture_btp  : architecture_btp
  - sciences_recherche : sciences_recherche
  - enseignement      : enseignement_pedagogie
  - logistique_supply_chain : logistique_supply_chain
  - agroalimentaire_qualite : agroalimentaire_qualite
  - metiers_manuels   : metiers_manuels
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Poids par catégorie de compétences pour chaque secteur ───────────────────
# clé   : identifiant secteur
# valeur: { catégorie_skills → poids par compétence }
# (plus le poids est élevé, plus la catégorie est discriminante pour ce secteur)

SECTOR_WEIGHTS: Dict[str, Dict[str, float]] = {
    "informatique_dev": {
        "langages": 3.0,
        "frameworks_web": 3.0,
        "frameworks_mobile": 3.0,
        "bases_de_donnees": 2.0,
        "outils_dev": 2.0,
        "tests_qualite": 2.0,
        "methodologies": 1.0,
    },
    "data_ia": {
        "data_ml_ia": 5.0,
        "langages": 0.5,          # Python est souvent partagé
        "bases_de_donnees": 0.5,
    },
    "devops_cloud": {
        "devops_cloud": 5.0,
        "systemes_reseaux": 3.0,
        "methodologies": 0.5,
    },
    "cybersecurite": {
        "securite": 5.0,
        "systemes_reseaux": 2.0,
    },
    "marketing_digital": {
        "marketing_digital": 5.0,
        "soft_skills": 0.5,
    },
    "finance_comptabilite": {
        "comptabilite_finance": 5.0,
    },
    "sante_medical": {
        "sante_medical": 5.0,
    },
    "rh_recrutement": {
        "rh_recrutement": 5.0,
        "soft_skills": 0.5,
    },
    "droit_juridique": {
        "droit_juridique": 5.0,
    },
    "architecture_btp": {
        "architecture_btp": 5.0,
        "metiers_manuels": 0.5,
    },
    "sciences_recherche": {
        "sciences_recherche": 5.0,
    },
    "enseignement": {
        "enseignement_pedagogie": 5.0,
    },
    "logistique_supply_chain": {
        "logistique_supply_chain": 5.0,
        "methodologies": 0.3,
    },
    "agroalimentaire_qualite": {
        "agroalimentaire_qualite": 5.0,
    },
    "metiers_manuels": {
        "metiers_manuels": 5.0,
    },
}

# Libellés lisibles pour affichage
SECTOR_LABELS: Dict[str, str] = {
    "informatique_dev": "Informatique & Développement",
    "data_ia": "Data Science & Intelligence Artificielle",
    "devops_cloud": "DevOps & Cloud",
    "cybersecurite": "Cybersécurité",
    "marketing_digital": "Marketing Digital & Communication",
    "finance_comptabilite": "Finance & Comptabilité",
    "sante_medical": "Santé & Médical",
    "rh_recrutement": "Ressources Humaines & Recrutement",
    "droit_juridique": "Droit & Juridique",
    "architecture_btp": "Architecture & BTP",
    "sciences_recherche": "Sciences & Recherche",
    "enseignement": "Enseignement & Formation",
    "logistique_supply_chain": "Logistique & Supply Chain",
    "agroalimentaire_qualite": "Agroalimentaire & Qualité",
    "metiers_manuels": "Métiers Manuels & Technique",
}

# Mots-clés textuels bonus (signaux faibles qui renforcent un secteur)
# Scannés dans le texte brut du CV (titre de poste, résumé…)
_TEXT_SIGNALS: Dict[str, re.Pattern] = {
    "informatique_dev": re.compile(
        r"\b(?:d[ée]veloppeur|developer|software\s+engineer|programmeur|"
        r"ing[ée]nieur\s+(?:logiciel|informatique)|web\s+developer|"
        r"full[\s\-]?stack|front[\s\-]?end|back[\s\-]?end|"
        r"mobile\s+developer|application\s+developer)\b",
        re.IGNORECASE,
    ),
    "data_ia": re.compile(
        r"\b(?:data\s+(?:scientist|engineer|analyst|architect)|"
        r"machine\s+learning\s+engineer|ml\s+engineer|"
        r"ing[ée]nieur\s+(?:ia|machine\s+learning|data)|"
        r"analyste\s+(?:data|donn[ée]es)|"
        r"intelligence\s+artificielle|deep\s+learning)\b",
        re.IGNORECASE,
    ),
    "devops_cloud": re.compile(
        r"\b(?:devops|sre|site\s+reliability|cloud\s+(?:engineer|architect)|"
        r"infrastructure\s+(?:engineer|architect)|"
        r"administrateur\s+(?:syst[eè]mes?|r[eé]seaux?)|"
        r"system\s+administrator)\b",
        re.IGNORECASE,
    ),
    "cybersecurite": re.compile(
        r"\b(?:pentester|cybersecurity|s[eé]curit[eé]\s+informatique|"
        r"analyste\s+(?:s[eé]curit[eé]|soc)|soc\s+analyst|"
        r"ethical\s+hack(?:er|ing)|threat\s+(?:hunter|analyst))\b",
        re.IGNORECASE,
    ),
    "marketing_digital": re.compile(
        r"\b(?:marketing|community\s+manager|traffic\s+manager|"
        r"responsable\s+(?:marketing|communication|digital)|"
        r"directeur\s+marketing|chef\s+de\s+projet\s+(?:digital|web)|"
        r"content\s+(?:manager|creator|strategist))\b",
        re.IGNORECASE,
    ),
    "finance_comptabilite": re.compile(
        r"\b(?:comptable|expert[\s\-]comptable|contr[oô]leur\s+de\s+gestion|"
        r"auditeur|analyste\s+financier|directeur\s+(?:financier|comptable)|"
        r"responsable\s+(?:comptable|financier|tresorerie)|"
        r"charg[eé]\s+de\s+(?:comptabilit[eé]|finance)|"
        r"DAF|CFO|chief\s+financial)\b",
        re.IGNORECASE,
    ),
    "sante_medical": re.compile(
        r"\b(?:m[eé]decin|infirmier|infirmi[eè]re|chirurgien|sage[\s\-]femme|"
        r"pharmacien|kinesither[aà]peute|aide[\s\-]soignant|"
        r"praticien|p[eé]diatre|dermatologue|cardiologue|"
        r"technicien\s+de\s+laboratoire|laborantin)\b",
        re.IGNORECASE,
    ),
    "rh_recrutement": re.compile(
        r"\b(?:responsable\s+(?:rh|ressources\s+humaines)|"
        r"charg[eé]\s+(?:de\s+recrutement|rh)|drh|"
        r"directeur\s+(?:rh|ressources\s+humaines)|"
        r"hr\s+(?:manager|director|business\s+partner)|"
        r"talent\s+acquisition|recruiter|recruteur)\b",
        re.IGNORECASE,
    ),
    "droit_juridique": re.compile(
        r"\b(?:avocat|juriste|notaire|conseiller\s+juridique|"
        r"responsable\s+juridique|directeur\s+juridique|"
        r"paralegal|legal\s+(?:counsel|advisor|manager)|"
        r"magistrat|greffier)\b",
        re.IGNORECASE,
    ),
    "architecture_btp": re.compile(
        r"\b(?:architecte|conducteur\s+de\s+travaux|chef\s+de\s+chantier|"
        r"ma[îi]tre\s+d['''](?:oeuvre|œuvre)|ing[ée]nieur\s+(?:civil|btp|structure)|"
        r"projeteur|dessinateur\s+(?:btp|b[ée]ton|structure)|"
        r"responsable\s+(?:travaux|chantier|btp))\b",
        re.IGNORECASE,
    ),
    "sciences_recherche": re.compile(
        r"\b(?:chercheur|researcher|doctorant|post[\s\-]?doc|"
        r"ing[ée]nieur\s+(?:recherche|r&d|chimiste|biologiste)|"
        r"biologiste|chimiste|physicien|microbiologiste|biochimiste)\b",
        re.IGNORECASE,
    ),
    "enseignement": re.compile(
        r"\b(?:professeur|enseignant|formateur|p[ée]dagogue|"
        r"directeur\s+(?:p[ée]dagogique|[eé]tablissement)|"
        r"conseiller\s+p[ée]dagogique|charg[eé]\s+de\s+cours|"
        r"tuteur|mentor\s+p[ée]dagogique)\b",
        re.IGNORECASE,
    ),
    "logistique_supply_chain": re.compile(
        r"\b(?:responsable\s+(?:logistique|supply\s+chain|achats?)|"
        r"acheteur|logisticien|supply\s+chain\s+(?:manager|analyst)|"
        r"directeur\s+(?:logistique|achats?)|chef\s+(?:d[''']entrepôt|magasinier)|"
        r"coordinateur\s+logistique)\b",
        re.IGNORECASE,
    ),
    "agroalimentaire_qualite": re.compile(
        r"\b(?:ing[ée]nieur\s+(?:qualit[ée]|agroalimentaire|process)|"
        r"responsable\s+(?:qualit[ée]|hse|qhse|haccp)|"
        r"technicien\s+(?:qualit[ée]|agroalimentaire|laboratoire)|"
        r"auditeur\s+qualit[ée]|animateur\s+qualit[ée])\b",
        re.IGNORECASE,
    ),
    "metiers_manuels": re.compile(
        r"\b(?:[eé]lectricien|plombier|chaudronnier|soudeur|m[eé]canicien|"
        r"technicien\s+(?:de\s+maintenance|[eé]lectrique|industriel)|"
        r"agent\s+de\s+maintenance|r[eé]parateur|monteur)\b",
        re.IGNORECASE,
    ),
}


class SectorClassifier:
    """
    Classifieur sectoriel d'un CV basé sur :
      1. Distribution des compétences par catégorie (scoring pondéré NLP)
      2. Signaux textuels : titres de postes et expressions sectorielles

    Retourne le secteur dominant + score de confiance + secteurs secondaires.
    """

    # Seuil minimum pour déclarer un secteur secondaire
    _SECONDARY_THRESHOLD = 0.15

    def classify(
        self,
        by_category: Dict[str, List[str]],
        raw_text: str = "",
    ) -> Dict:
        """
        Classifie le CV dans un secteur professionnel.

        Args:
            by_category: Dict catégorie → liste de compétences (sortie de SkillsExtractor)
            raw_text: Texte brut du CV (pour signaux textuels)

        Returns:
            {
                "secteur": "informatique_dev",
                "label": "Informatique & Développement",
                "confiance": 0.87,
                "secteurs_secondaires": [
                    {"secteur": "devops_cloud", "label": "DevOps & Cloud", "score_relatif": 0.32}
                ],
                "methode": "skills_distribution+text_signals",
                "scores_detail": { ... }
            }
        """
        # ── Phase 1 : score basé sur les compétences ─────────────────────────
        skill_scores: Dict[str, float] = {}
        counts: Dict[str, int] = {cat: len(skills) for cat, skills in by_category.items()
                                   if cat != "découverte_ia"}  # exclure NER inconnu

        for sector, weights in SECTOR_WEIGHTS.items():
            score = 0.0
            for cat, weight in weights.items():
                n = counts.get(cat, 0)
                score += n * weight
            skill_scores[sector] = score

        # ── Phase 2 : bonus signaux textuels ────────────────────────────────
        text_scores: Dict[str, float] = {}
        if raw_text:
            for sector, pattern in _TEXT_SIGNALS.items():
                matches = len(pattern.findall(raw_text[:5000]))
                text_scores[sector] = matches * 8.0  # bonus fixe par occurrence

        # ── Fusion ──────────────────────────────────────────────────────────
        combined: Dict[str, float] = {}
        for sector in SECTOR_WEIGHTS:
            combined[sector] = skill_scores.get(sector, 0.0) + text_scores.get(sector, 0.0)

        total = sum(combined.values())
        if total == 0:
            return {
                "secteur": "inconnu",
                "label": "Secteur non déterminé",
                "confiance": 0.0,
                "secteurs_secondaires": [],
                "methode": "skills_distribution+text_signals",
                "scores_detail": {},
            }

        # Normaliser en pourcentages
        normalized = {s: round(v / total, 4) for s, v in combined.items()}

        # Secteur principal
        top_sector = max(normalized, key=lambda s: normalized[s])
        top_score = normalized[top_sector]

        # Secteurs secondaires (> seuil, différent du principal)
        secondaires = [
            {
                "secteur": s,
                "label": SECTOR_LABELS.get(s, s),
                "score_relatif": normalized[s],
            }
            for s, v in sorted(normalized.items(), key=lambda x: x[1], reverse=True)
            if s != top_sector and v >= self._SECONDARY_THRESHOLD
        ]

        logger.info(
            "[SectorClassifier] Secteur détecté : %s (confiance %.0f%%) "
            "— secondaires : %s",
            top_sector,
            top_score * 100,
            [s["secteur"] for s in secondaires],
        )

        return {
            "secteur": top_sector,
            "label": SECTOR_LABELS.get(top_sector, top_sector),
            "confiance": top_score,
            "secteurs_secondaires": secondaires,
            "methode": "skills_distribution+text_signals",
            "scores_detail": {
                s: normalized[s]
                for s, v in sorted(normalized.items(), key=lambda x: x[1], reverse=True)
                if v > 0
            },
        }
