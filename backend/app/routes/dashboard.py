from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_recruteur_or_admin
from app.models.candidate import Candidate, CandidatureStatus
from app.models.job_offer import JobOffer, JobStatus
from app.models.match import Match
from app.models.user import User, UserRole

router = APIRouter()


@router.get("/dashboard/stats", summary="Tableau de bord recruteur")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    # ── Totaux ───────────────────────────────────────────────
    total_candidates = db.query(func.count(Candidate.id)).scalar() or 0
    total_offers     = db.query(func.count(JobOffer.id)).scalar() or 0
    active_offers    = db.query(func.count(JobOffer.id)).filter(JobOffer.status == JobStatus.active).scalar() or 0
    total_matchings  = db.query(func.count(Match.id)).scalar() or 0

    # Candidats avec score calculé (score > 0)
    matched_with_score = db.query(func.count(Match.id)).filter(Match.score > 0).scalar() or 0

    # Candidats non encore matchés
    matched_candidate_ids = db.query(Match.candidate_id).distinct().subquery()
    unmatched_candidates  = db.query(func.count(Candidate.id))\
        .filter(~Candidate.id.in_(matched_candidate_ids)).scalar() or 0

    # ── Statuts candidatures ─────────────────────────────────
    status_counts = (
        db.query(Candidate.candidature_status, func.count(Candidate.id))
        .group_by(Candidate.candidature_status).all()
    )
    statuts = {s.value: 0 for s in CandidatureStatus}
    for status, count in status_counts:
        if status:
            statuts[status.value if hasattr(status, "value") else str(status)] = count

    # Taux d'acceptation
    total_decided = statuts["accepte"] + statuts["refuse"]
    taux_acceptation = round(statuts["accepte"] / total_decided * 100) if total_decided > 0 else None

    # ── Utilisateurs (admin) ──────────────────────────────────
    total_users   = 0
    users_by_role = {}
    if current_user.role == UserRole.admin:
        total_users = db.query(func.count(User.id)).scalar() or 0
        role_counts = db.query(User.role, func.count(User.id)).group_by(User.role).all()
        users_by_role = {r.value: c for r, c in role_counts}

    # ── Pipeline par offre ────────────────────────────────────
    offers = db.query(JobOffer).order_by(JobOffer.created_at.desc()).all()
    pipeline_offres = []
    alertes = []

    for offer in offers:
        matches = db.query(Match).filter(Match.job_offer_id == offer.id).all()
        nb_matches   = len(matches)
        scores_reels = [m.score for m in matches if m.score > 0]
        best_score   = round(max(scores_reels) * 100, 1) if scores_reels else None
        avg_score    = round(sum(scores_reels) / len(scores_reels) * 100, 1) if scores_reels else None

        # Score distribution (seulement si scores calculés)
        dist = {"excellent": 0, "moyen": 0, "faible": 0}
        for s in scores_reels:
            pct = s * 100
            if pct >= 65:   dist["excellent"] += 1
            elif pct >= 35: dist["moyen"]     += 1
            else:           dist["faible"]    += 1

        pipeline_offres.append({
            "id":          str(offer.id),
            "titre":       offer.titre,
            "type_contrat": offer.type_contrat or "Non précisé",
            "status":      offer.status.value if offer.status else "active",
            "nb_candidats": nb_matches,
            "nb_scores_calcules": len(scores_reels),
            "best_score":  best_score,
            "avg_score":   avg_score,
            "distribution": dist,
        })

        # Alertes
        if nb_matches == 0:
            alertes.append({
                "type":    "no_match",
                "niveau":  "warning",
                "message": f"Aucun candidat évalué pour « {offer.titre} »",
                "action":  f"Lancer le matching",
                "offer_id": str(offer.id),
            })
        elif len(scores_reels) == 0 and nb_matches > 0:
            alertes.append({
                "type":    "score_pending",
                "niveau":  "info",
                "message": f"{nb_matches} candidat(s) en attente de scoring pour « {offer.titre} »",
                "action":  "Recalculer les scores",
                "offer_id": str(offer.id),
            })
        elif best_score is not None and best_score < 35:
            alertes.append({
                "type":    "low_scores",
                "niveau":  "warning",
                "message": f"Meilleur score = {best_score}% pour « {offer.titre} » — profils peu adaptés",
                "action":  "Revoir les critères",
                "offer_id": str(offer.id),
            })

    if unmatched_candidates > 0:
        alertes.append({
            "type":    "unmatched_cvs",
            "niveau":  "info",
            "message": f"{unmatched_candidates} CV(s) uploadés non encore évalués",
            "action":  "Associer à une offre",
            "offer_id": None,
        })

    if statuts["en_attente"] > 0:
        alertes.append({
            "type":    "pending_decision",
            "niveau":  "info",
            "message": f"{statuts['en_attente']} candidature(s) en attente de décision (accepter / refuser)",
            "action":  "Voir les candidats",
            "offer_id": None,
        })

    # ── Distribution globale des scores ──────────────────────
    all_scores = [m.score for m in db.query(Match).filter(Match.score > 0).all()]
    score_distribution = {"excellent": 0, "moyen": 0, "faible": 0}
    for s in all_scores:
        pct = s * 100
        if pct >= 65:   score_distribution["excellent"] += 1
        elif pct >= 35: score_distribution["moyen"]     += 1
        else:           score_distribution["faible"]    += 1
    avg_score_global = round(sum(all_scores) / len(all_scores) * 100, 1) if all_scores else None

    # ── Activité 7 jours ──────────────────────────────────────
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_cvs      = db.query(func.count(Candidate.id)).filter(Candidate.created_at >= seven_days_ago).scalar() or 0
    recent_matchings = db.query(func.count(Match.id)).filter(Match.created_at >= seven_days_ago).scalar() or 0

    # ── Top candidats (meilleurs scores toutes offres) ────────
    top_matches = (
        db.query(Match, Candidate, JobOffer)
        .join(Candidate, Match.candidate_id == Candidate.id)
        .join(JobOffer,  Match.job_offer_id  == JobOffer.id)
        .filter(Match.score > 0)
        .order_by(Match.score.desc())
        .limit(8).all()
    )
    top_candidats = [
        {
            "score":         round(float(m.score) * 100, 1),
            "candidate_nom": c.nom or c.filename,
            "cv_id":         c.cv_id,
            "offer_titre":   o.titre,
            "offer_id":      str(o.id),
        }
        for m, c, o in top_matches
    ]

    # ── 5 derniers candidats ──────────────────────────────────
    latest_candidates = db.query(Candidate).order_by(Candidate.created_at.desc()).limit(5).all()
    recents_candidats = [
        {
            "cv_id":      c.cv_id,
            "nom":        c.nom or c.filename,
            "email":      c.email or "",
            "status":     c.candidature_status.value if c.candidature_status else "en_attente",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in latest_candidates
    ]

    return {
        "totaux": {
            "candidats":           total_candidates,
            "offres_actives":      active_offers,
            "offres_total":        total_offers,
            "matchings":           total_matchings,
            "matchings_avec_score": matched_with_score,
            "candidats_non_matchés": unmatched_candidates,
            "utilisateurs":        total_users,
            "score_moyen_global":  avg_score_global,
            "taux_acceptation":    taux_acceptation,
        },
        "candidatures_statuts":  statuts,
        "utilisateurs_par_role": users_by_role,
        "score_distribution":    score_distribution,
        "pipeline_offres":       pipeline_offres,
        "alertes":               alertes,
        "top_candidats":         top_candidats,
        "recents_candidats":     recents_candidats,
        "activite_7j": {
            "cvs":       recent_cvs,
            "matchings": recent_matchings,
        },
    }
