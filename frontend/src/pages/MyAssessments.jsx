import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import './MyAssessments.css'

const STATUS = {
  in_progress: { label: 'À passer', cls: 'mas-st-todo' },
  completed:   { label: 'Terminée', cls: 'mas-st-done' },
  abandoned:   { label: 'Interrompue', cls: 'mas-st-wait' },
}

/** Espace candidat — mes évaluations techniques (invitations reçues). */
export default function MyAssessments() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get('/assessment/my')
      .then(res => setSessions(res.data.sessions))
      .catch(() => setError('Impossible de charger vos évaluations.'))
  }, [])

  const fmt = (iso) => iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }) : null

  return (
    <div className="page-wrapper">
      <div className="mas-wrap">
        <h1 className="mas-title">🎯 Mes évaluations</h1>
        <p className="mas-sub">Vos évaluations techniques. Munissez-vous du <strong>code PIN reçu par email</strong> pour commencer.</p>

        {error && <div className="mas-empty mas-err">{error}</div>}
        {sessions && sessions.length === 0 && (
          <div className="mas-empty">Aucune évaluation pour le moment. Vous serez notifié(e) par email si un recruteur vous invite.</div>
        )}

        <div className="mas-list">
          {(sessions || []).map(s => {
            const st = STATUS[s.status] || STATUS.in_progress
            const canStart = s.status === 'in_progress' && s.window === 'open' && s.candidate_link
            return (
              <div key={s.session_id} className="mas-card">
                <div className="mas-card-main">
                  <div className="mas-offer">{s.offer_titre}</div>
                  {s.entreprise && <div className="mas-ent">{s.entreprise}</div>}
                  <div className="mas-dates">
                    {s.opens_at && <span>📅 Ouverture : {fmt(s.opens_at)}</span>}
                    {s.deadline && <span>⏳ Limite : {fmt(s.deadline)}</span>}
                  </div>
                </div>
                <div className="mas-card-side">
                  <span className={`mas-badge ${st.cls}`}>{st.label}</span>
                  {canStart && (
                    <button className="mas-btn" onClick={() => navigate(s.candidate_link)}>
                      Passer l'évaluation →
                    </button>
                  )}
                  {s.status === 'in_progress' && s.window === 'not_open' && (
                    <span className="mas-hint">Pas encore ouverte</span>
                  )}
                  {s.status === 'in_progress' && s.window === 'expired' && (
                    <span className="mas-hint">Date limite dépassée</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
