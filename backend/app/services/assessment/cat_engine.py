"""
Moteur de test adaptatif (CAT — Computerized Adaptive Testing) via `catsim`.

Principe (Item Response Theory) : à chaque étape, on choisit la question la plus
INFORMATIVE pour le niveau estimé du candidat (theta), on enregistre sa réponse,
puis on ré-estime theta. Le test converge vers le vrai niveau en peu de questions.

- Paramètres IRT par item : a (discrimination), b (difficulté), c (pseudo-chance),
  d (asymptote haute). On mappe la difficulté 1-10 (DB) sur b ∈ [-3, 3].
- theta (échelle IRT ~[-3, 3]) est reconverti en niveau 0-10 pour l'affichage.

100% local : catsim + numpy, aucune API externe.
"""
from __future__ import annotations

import numpy as np
from catsim.item_bank import ItemBank
from catsim.selection import MaxInfoSelector
from catsim.estimation import NumericalSearchEstimator

# QCM à 4 options → probabilité de réussite au hasard ≈ 0.25
GUESSING = 0.25
# Longueur cible du test adaptatif (borne haute)
TEST_LENGTH = 12

_selector = MaxInfoSelector()
_estimator = NumericalSearchEstimator()


def difficulte_to_b(difficulte: int) -> float:
    """Mappe une difficulté 1-10 sur le paramètre IRT b ∈ [-3, 3]."""
    d = max(1, min(10, int(difficulte)))
    return round(-3.0 + (d - 1) * (6.0 / 9.0), 3)


def theta_to_niveau(theta: float) -> float:
    """Convertit theta (~[-3, 3]) en niveau démontré 0-10."""
    if theta is None:
        return 0.0
    return round(max(0.0, min(10.0, (float(theta) + 3.0) / 6.0 * 10.0)), 1)


def build_item_bank(questions) -> ItemBank:
    """Construit la banque IRT (matrice [a, b, c, d]) depuis les questions DB.

    L'ORDRE de `questions` fixe l'index catsim de chaque item.
    """
    arr = np.array(
        [[float(q.discrimination or 1.0), difficulte_to_b(q.difficulte), GUESSING, 1.0]
         for q in questions],
        dtype=float,
    )
    return ItemBank(arr)


def select_next_index(bank: ItemBank, administered_indices: list[int], theta: float) -> int | None:
    """Choisit l'index de la prochaine question (max information à theta)."""
    if len(administered_indices) >= bank.n_items:
        return None
    return _selector.select(
        item_bank=bank,
        administered_items=administered_indices,
        est_theta=theta if theta is not None else 0.0,
    )


def estimate_theta(bank: ItemBank, administered_indices: list[int],
                   responses: list[bool], theta: float) -> float:
    """Ré-estime theta à partir des réponses observées (True=correct)."""
    if not administered_indices:
        return 0.0
    return float(_estimator.estimate(
        item_bank=bank,
        administered_items=administered_indices,
        response_vector=responses,
        est_theta=theta if theta is not None else 0.0,
    ))


def is_finished(administered_count: int, pool_size: int) -> bool:
    """Le test s'arrête à TEST_LENGTH questions (ou quand la banque est épuisée)."""
    return administered_count >= min(TEST_LENGTH, pool_size)


def competence_scores(administered: list[dict]) -> dict:
    """Niveau démontré 0-10 par compétence, à partir des items administrés.

    Pour chaque compétence : part de difficulté « maîtrisée » (somme des
    difficultés des items réussis / somme des difficultés des items posés) × 10.
    """
    par_comp: dict[str, list[dict]] = {}
    for item in administered:
        par_comp.setdefault(item["competence"], []).append(item)

    scores = {}
    for comp, items in par_comp.items():
        total = sum(it["difficulte"] for it in items)
        reussi = sum(it["difficulte"] for it in items if it["correct"])
        scores[comp] = round((reussi / total) * 10, 1) if total else 0.0
    return scores
