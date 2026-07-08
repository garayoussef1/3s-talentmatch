import { useState } from 'react'
import api from '../services/api'
import './AssessmentPanel.css'

/**
 * Panneau Évaluation technique — gère un OU plusieurs candidats.
 * props.candidates : [{ id, name }]
 * Lancement instantané (pool de l'offre généré en arrière-plan) ; pour chaque
 * candidat : lien + email automatique. Les résultats se consultent dans
 * l'onglet "🎯 Évaluations" de l'offre.
 */
export default function AssessmentPanel({ candidates, offerId, onClose }) {
  const [items, setItems] = useState(() =>
    Object.fromEntries(candidates.map(c => [c.id, { name: c.name, status: 'idle' }]))
  )
  const [launchingAll, setLaunchingAll] = useState(false)
  const [recruiterQs, setRecruiterQs] = useState('')   // 1 question par ligne
  const [opensAt, setOpensAt]   = useState('')
  const [deadline, setDeadline] = useState('')
  const [poolGenerating, setPoolGenerating] = useState(false)

  const update = (id, patch) =>
    setItems(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }))

  const launchOne = (id) => {
    update(id, { loading: true, error: null })
    const questions = recruiterQs.split('\n').map(q => q.trim()).filter(Boolean)
    return api.post('/assessment/launch', {
      candidate_id: id, offer_id: offerId,
      recruiter_questions: questions,
      opens_at: opensAt || null,
      deadline: deadline || null,
    }, { timeout: 30000 })
      .then(res => {
        update(id, {
          loading: false, status: 'link',
          link: window.location.origin + res.data.candidate_link,
          emailSent: res.data.email_sent,
          candidateEmail: res.data.candidate_email,
          accessPin: res.data.access_pin,
        })
        if (res.data.pool_generating) setPoolGenerating(true)
      })
      .catch(e => update(id, { loading: false, error: e?.response?.data?.detail || 'Erreur.' }))
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

  const allIdle = candidates.every(c => items[c.id]?.status === 'idle')
  const datesInvalid = opensAt && deadline && deadline <= opensAt

  return (
    <div className="ap-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="ap-modal">
        <div className="ap-head">
          <h3>🎯 Évaluation technique — {candidates.length} candidat{candidates.length > 1 ? 's' : ''}</h3>
          <button className="ap-close" onClick={onClose}>✕</button>
        </div>

        {/* Étape 1 : configuration + lancement */}
        {allIdle && (
          <div className="ap-body">
            <p>L'IA génère un questionnaire <strong>différent pour chaque candidat</strong>
               (QCM + questions rédigées), ciblé sur l'offre. Chaque candidat reçoit
               automatiquement un <strong>email avec son lien</strong>. 100% local.</p>

            {/* Fenêtre de passation */}
            <div className="ap-dates">
              <label className="ap-date-field">
                <span>📅 Ouverture <em>(optionnel)</em></span>
                <input type="datetime-local" value={opensAt} onChange={e => setOpensAt(e.target.value)} />
              </label>
              <label className="ap-date-field">
                <span>⏳ Date limite <em>(optionnel)</em></span>
                <input type="datetime-local" value={deadline} onChange={e => setDeadline(e.target.value)} />
              </label>
            </div>
            {datesInvalid && <div className="ap-warn">⚠️ La date limite doit être après l'ouverture.</div>}

            <label className="ap-label">✍️ Vos questions personnalisées <em>(optionnel, une par ligne — posées à tous)</em></label>
            <textarea
              className="ap-rq" rows={3}
              placeholder={"Ex: Pourquoi voulez-vous rejoindre notre entreprise ?"}
              value={recruiterQs} onChange={e => setRecruiterQs(e.target.value)}
            />

            <button className="ap-btn" onClick={launchAll} disabled={launchingAll || datesInvalid}>
              {launchingAll ? '⏳ Envoi en cours…'
                : `🚀 Lancer ${candidates.length > 1 ? `les ${candidates.length} évaluations` : "l'évaluation"} (instantané)`}
            </button>
            <p className="ap-note">💡 Première évaluation d'une offre : l'IA prépare le questionnaire en
               arrière-plan (~5 min, une seule fois). Les candidats sont prévenus par email.</p>
          </div>
        )}

        {/* Étape 2 : liste des candidats lancés */}
        {!allIdle && (
          <div className="ap-body ap-list">
            {poolGenerating && (
              <div className="ap-warn">⏳ Le questionnaire de l'offre se prépare en arrière-plan (~5 min).
                Les liens sont déjà valables et les emails envoyés.</div>
            )}
            {candidates.map(c => {
              const it = items[c.id] || {}
              return (
                <div key={c.id} className="ap-cand">
                  <div className="ap-cand-head"><strong>{it.name}</strong></div>
                  {it.error && <div className="ap-err-inline">{it.error}</div>}
                  {it.status === 'idle' && (
                    <button className="ap-btn-mini" onClick={() => launchOne(c.id)} disabled={it.loading}>
                      {it.loading ? '…' : 'Lancer'}
                    </button>
                  )}
                  {it.status === 'link' && (
                    <>
                      {it.emailSent
                        ? <div className="ap-mail-ok">📧 Invitation envoyée à <strong>{it.candidateEmail}</strong></div>
                        : <div className="ap-mail-warn">⚠️ Email non envoyé — transmettez le lien manuellement</div>}
                      {it.accessPin && (
                        <div className="ap-pin">🔒 Code d'accès : <strong>{it.accessPin}</strong>
                          <span> (envoyé au candidat par email)</span></div>
                      )}
                      <div className="ap-link-box">
                        <input readOnly value={it.link} onClick={e => e.target.select()} />
                        <button onClick={() => copyLink(c.id, it.link)}>{it.copied ? 'Copié ✓' : 'Copier'}</button>
                      </div>
                    </>
                  )}
                </div>
              )
            })}
            <p className="ap-note">📊 Suivez les réponses et les rapports dans l'onglet
               <strong> 🎯 Évaluations</strong> de l'offre.</p>
          </div>
        )}
      </div>
    </div>
  )
}
