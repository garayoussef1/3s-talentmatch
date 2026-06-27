import { useState } from 'react'
import api from '../services/api'
import './InterviewPanel.css'

const RECO_STYLE = {
  RECRUTER: { label: 'Recruter', color: '#16a34a', bg: '#dcfce7' },
  HESITER:  { label: 'Hésiter',  color: '#d97706', bg: '#fef3c7' },
  REJETER:  { label: 'Rejeter',  color: '#dc2626', bg: '#fee2e2' },
}

/**
 * Panneau Entretien IA — gère un OU plusieurs candidats.
 * props.candidates : [{ id, name }]
 */
export default function InterviewPanel({ candidates, offerId, onClose }) {
  // état par candidat : { [candidateId]: {status,link,interviewId,report,loading,error,copied} }
  const [items, setItems] = useState(() =>
    Object.fromEntries(candidates.map(c => [c.id, { name: c.name, status: 'idle' }]))
  )
  const [launchingAll, setLaunchingAll] = useState(false)

  const update = (id, patch) =>
    setItems(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }))

  const launchOne = (id) => {
    update(id, { loading: true, error: null })
    return api.post('/interviews/start',
      { candidate_id: id, offer_id: offerId }, { timeout: 90000 })
      .then(res => update(id, {
        loading: false, status: 'link',
        interviewId: res.data.interview_id,
        link: window.location.origin + res.data.candidate_link,
        emailSent: res.data.email_sent,
        candidateEmail: res.data.candidate_email,
      }))
      .catch(e => update(id, { loading: false,
        error: e?.response?.data?.detail || "Erreur au lancement." }))
  }

  const launchAll = async () => {
    setLaunchingAll(true)
    for (const c of candidates) {
      if (items[c.id]?.status === 'idle') await launchOne(c.id)
    }
    setLaunchingAll(false)
  }

  const copyLink = (id, link) => {
    navigator.clipboard.writeText(link).then(() => {
      update(id, { copied: true })
      setTimeout(() => update(id, { copied: false }), 2000)
    })
  }

  const fetchReport = (id, interviewId) => {
    update(id, { loading: true, error: null })
    api.post(`/interviews/${interviewId}/report`, null, { timeout: 60000 })
      .then(res => update(id, { loading: false, status: 'report', report: res.data }))
      .catch(e => update(id, { loading: false,
        error: e?.response?.data?.detail || "Le candidat n'a pas encore répondu." }))
  }

  const allIdle = candidates.every(c => items[c.id]?.status === 'idle')

  return (
    <div className="ip-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="ip-modal ip-modal-wide">
        <div className="ip-head">
          <h3>Entretiens IA — {candidates.length} candidat{candidates.length > 1 ? 's' : ''}</h3>
          <button className="ip-close" onClick={onClose}>✕</button>
        </div>

        {/* Bouton global */}
        {allIdle && (
          <div className="ip-body">
            <p>Lancez un entretien d'évaluation par IA pour {candidates.length > 1
              ? 'les candidats sélectionnés' : 'ce candidat'}. Le système génère des
              questions personnalisées (techniques, mises en situation, soft skills)
              à partir du CV et de l'offre.</p>
            <button className="ip-btn-primary" onClick={launchAll} disabled={launchingAll}>
              {launchingAll ? 'Génération des entretiens…'
                : `🎙 Lancer ${candidates.length > 1 ? `les ${candidates.length} entretiens` : "l'entretien"}`}
            </button>
          </div>
        )}

        {/* Liste des candidats */}
        {!allIdle && (
          <div className="ip-body ip-list">
            {candidates.map(c => {
              const it = items[c.id] || {}
              const reco = it.report ? RECO_STYLE[it.report.recommandation] || RECO_STYLE.HESITER : null
              return (
                <div key={c.id} className="ip-cand-card">
                  <div className="ip-cand-head">
                    <strong>{it.name}</strong>
                    {it.report && (
                      <span className="ip-reco-mini" style={{ background: reco.bg, color: reco.color }}>
                        {it.report.score_global_100}/100 · {reco.label}
                      </span>
                    )}
                  </div>

                  {it.error && <div className="ip-error-inline">{it.error}</div>}

                  {it.status === 'idle' && (
                    <button className="ip-btn-mini" onClick={() => launchOne(c.id)} disabled={it.loading}>
                      {it.loading ? 'Génération…' : 'Lancer'}
                    </button>
                  )}

                  {(it.status === 'link' || it.status === 'report') && (
                    <>
                      {it.emailSent
                        ? <div className="ip-email-ok">📧 Invitation envoyée à <strong>{it.candidateEmail}</strong></div>
                        : <div className="ip-email-warn">⚠️ Pas d'email envoyé (adresse manquante) — transmettez le lien manuellement</div>}
                      <div className="ip-link-box">
                        <input readOnly value={it.link} onClick={e => e.target.select()} />
                        <button onClick={() => copyLink(c.id, it.link)}>
                          {it.copied ? 'Copié ✓' : 'Copier'}
                        </button>
                      </div>
                      <div className="ip-cand-actions">
                        <a href={it.link} target="_blank" rel="noreferrer" className="ip-open-link">
                          Aperçu candidat ↗
                        </a>
                        {it.status !== 'report' && (
                          <button className="ip-btn-mini" onClick={() => fetchReport(c.id, it.interviewId)} disabled={it.loading}>
                            {it.loading ? 'Analyse…' : '📊 Générer le rapport'}
                          </button>
                        )}
                      </div>
                    </>
                  )}

                  {/* Rapport */}
                  {it.status === 'report' && it.report && (
                    <div className="ip-report-inline">
                      <p className="ip-synth">{it.report.synthese_executive}</p>
                      {it.report.competences?.validees?.length > 0 && (
                        <div className="ip-mini-sec">
                          <span className="ip-mini-title">✅ Validées :</span>{' '}
                          {it.report.competences.validees.map(v => v.competence).join(', ')}
                        </div>
                      )}
                      {it.report.competences?.non_validees?.length > 0 && (
                        <div className="ip-mini-sec">
                          <span className="ip-mini-title">🔴 Non validées :</span>{' '}
                          {it.report.competences.non_validees.map(v => typeof v === 'string' ? v : v.competence).join(', ')}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
