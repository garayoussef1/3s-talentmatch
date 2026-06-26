import { useState } from 'react'
import api from '../services/api'
import './InterviewPanel.css'

const RECO_STYLE = {
  RECRUTER: { label: 'Recruter',  color: '#16a34a', bg: '#dcfce7' },
  HESITER:  { label: 'Hésiter',   color: '#d97706', bg: '#fef3c7' },
  REJETER:  { label: 'Rejeter',   color: '#dc2626', bg: '#fee2e2' },
}

export default function InterviewPanel({ candidateId, offerId, candidateName, onClose }) {
  const [step, setStep]       = useState('idle')   // idle | link | report
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [link, setLink]       = useState('')
  const [interviewId, setInterviewId] = useState(null)
  const [report, setReport]   = useState(null)
  const [copied, setCopied]   = useState(false)

  const launch = () => {
    setLoading(true); setError(null)
    api.post('/interviews/start',
      { candidate_id: candidateId, offer_id: offerId },
      { timeout: 90000 })
      .then(res => {
        setInterviewId(res.data.interview_id)
        const full = window.location.origin + res.data.candidate_link
        setLink(full)
        setStep('link')
      })
      .catch(e => setError(e?.response?.data?.detail || "Erreur au lancement de l'entretien."))
      .finally(() => setLoading(false))
  }

  const copyLink = () => {
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 2000)
    })
  }

  const fetchReport = () => {
    setLoading(true); setError(null)
    api.post(`/interviews/${interviewId}/report`, null, { timeout: 60000 })
      .then(res => { setReport(res.data); setStep('report') })
      .catch(e => setError(e?.response?.data?.detail || "Le candidat n'a pas encore répondu, ou erreur."))
      .finally(() => setLoading(false))
  }

  const reco = report ? RECO_STYLE[report.recommandation] || RECO_STYLE.HESITER : null

  return (
    <div className="ip-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="ip-modal">
        <div className="ip-head">
          <h3>Entretien IA — {candidateName}</h3>
          <button className="ip-close" onClick={onClose}>✕</button>
        </div>

        {error && <div className="ip-error">{error}</div>}

        {/* Étape 1 : lancer */}
        {step === 'idle' && (
          <div className="ip-body">
            <p>Lancez un entretien d'évaluation par IA pour ce candidat. Le système
               génère des questions personnalisées (techniques, mises en situation,
               soft skills) à partir du CV et de l'offre.</p>
            <button className="ip-btn-primary" onClick={launch} disabled={loading}>
              {loading ? 'Génération des questions…' : '🎙 Lancer l\'entretien IA'}
            </button>
          </div>
        )}

        {/* Étape 2 : lien candidat */}
        {step === 'link' && (
          <div className="ip-body">
            <div className="ip-success">✓ Entretien créé ({15} questions générées)</div>
            <p>Transmettez ce lien au candidat pour qu'il réalise l'entretien :</p>
            <div className="ip-link-box">
              <input readOnly value={link} onClick={e => e.target.select()} />
              <button onClick={copyLink}>{copied ? 'Copié ✓' : 'Copier'}</button>
            </div>
            <a className="ip-open-link" href={link} target="_blank" rel="noreferrer">
              Ouvrir l'entretien (aperçu candidat) ↗
            </a>
            <hr className="ip-sep" />
            <p className="ip-muted">Une fois le candidat a répondu, générez le rapport d'évaluation :</p>
            <button className="ip-btn-primary" onClick={fetchReport} disabled={loading}>
              {loading ? 'Analyse en cours…' : '📊 Générer le rapport'}
            </button>
          </div>
        )}

        {/* Étape 3 : rapport */}
        {step === 'report' && report && (
          <div className="ip-body ip-report">
            <div className="ip-score-row">
              <div className="ip-score-circle">
                <span className="ip-score-num">{report.score_global_100}</span>
                <span className="ip-score-max">/100</span>
              </div>
              <div className="ip-reco" style={{ background: reco.bg, color: reco.color }}>
                {reco.label}
              </div>
            </div>

            <div className="ip-section">
              <h4>Synthèse</h4>
              <p>{report.synthese_executive}</p>
            </div>

            {report.recommandation_justification && (
              <div className="ip-section">
                <h4>Justification</h4>
                <p>{report.recommandation_justification}</p>
              </div>
            )}

            {report.competences?.validees?.length > 0 && (
              <div className="ip-section">
                <h4>✅ Compétences validées</h4>
                <ul>
                  {report.competences.validees.map((c, i) => (
                    <li key={i}><strong>{c.competence}</strong>
                      {c.preuve && <span className="ip-proof"> — « {c.preuve} »</span>}</li>
                  ))}
                </ul>
              </div>
            )}

            {report.competences?.partiellement_validees?.length > 0 && (
              <div className="ip-section">
                <h4>🟡 Partiellement validées</h4>
                <ul>
                  {report.competences.partiellement_validees.map((c, i) => (
                    <li key={i}><strong>{c.competence}</strong>
                      {c.nuance && <span className="ip-proof"> — {c.nuance}</span>}</li>
                  ))}
                </ul>
              </div>
            )}

            {report.competences?.non_validees?.length > 0 && (
              <div className="ip-section">
                <h4>🔴 Non validées</h4>
                <ul>
                  {report.competences.non_validees.map((c, i) => (
                    <li key={i}>{typeof c === 'string' ? c : c.competence}</li>
                  ))}
                </ul>
              </div>
            )}

            {report.soft_skills_detectes?.length > 0 && (
              <div className="ip-section">
                <h4>Soft skills détectés</h4>
                <div className="ip-chips">
                  {report.soft_skills_detectes.map((s, i) => (
                    <span key={i} className="ip-chip">
                      {s.label} {s.niveau && <em>({s.niveau})</em>}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
