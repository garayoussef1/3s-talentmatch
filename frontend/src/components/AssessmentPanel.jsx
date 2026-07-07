import { useState } from 'react'
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../services/api'
import './AssessmentPanel.css'

const LABEL = {
  fiable: { txt: 'CV fiable', cls: 'ap-badge-ok' },
  a_verifier: { txt: 'À vérifier', cls: 'ap-badge-mid' },
  ecart_important: { txt: 'Écart important', cls: 'ap-badge-no' },
}
const RECO = { RECRUTER: 'ap-badge-ok', A_APPROFONDIR: 'ap-badge-mid', REJETER: 'ap-badge-no' }

export default function AssessmentPanel({ candidateId, offerId, candidateName, onClose }) {
  const [step, setStep]       = useState('idle')   // idle | link | results
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [link, setLink]       = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [gap, setGap]         = useState(null)
  const [report, setReport]   = useState(null)
  const [detail, setDetail]   = useState(null)     // Q/R pour vérification
  const [showAnswers, setShowAnswers] = useState(false)
  const [copied, setCopied]   = useState(false)
  const [recruiterQs, setRecruiterQs] = useState('')  // 1 question par ligne

  const launch = () => {
    setLoading(true); setError(null)
    const questions = recruiterQs.split('\n').map(q => q.trim()).filter(Boolean)
    // Génération Ollama locale : long (~3-6 min) mais questionnaire unique
    api.post('/assessment/launch',
      { candidate_id: candidateId, offer_id: offerId, recruiter_questions: questions },
      { timeout: 600000 })
      .then(res => {
        setSessionId(res.data.session_id)
        setLink(window.location.origin + res.data.candidate_link)
        setStep('link')
      })
      .catch(e => setError(e?.response?.data?.detail || 'Erreur au lancement.'))
      .finally(() => setLoading(false))
  }

  const copyLink = () => {
    navigator.clipboard.writeText(link).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
  }

  const seeResults = () => {
    setLoading(true); setError(null)
    Promise.all([
      api.get(`/assessment/reality-gap/${candidateId}/${offerId}`).catch(() => ({ data: null })),
      sessionId ? api.post(`/assessment/report/${sessionId}`, null, { timeout: 300000 }).catch(() => ({ data: {} })) : Promise.resolve({ data: {} }),
      sessionId ? api.get(`/assessment/detail/${sessionId}`) : Promise.resolve({ data: null }),
    ])
      .then(([g, r, d]) => {
        setGap(g.data); setReport(r.data.report || null); setDetail(d.data)
        setStep('results')
      })
      .catch(e => setError(e?.response?.data?.detail || "Le candidat n'a pas encore terminé."))
      .finally(() => setLoading(false))
  }

  const radarData = gap?.details?.map(d => ({
    competence: d.competence,
    'Déclaré (CV)': d.niveau_declare,
    'Démontré (test)': d.niveau_demontre,
  })) || []

  return (
    <div className="ap-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="ap-modal">
        <div className="ap-head">
          <h3>🎯 Évaluation technique — {candidateName}</h3>
          <button className="ap-close" onClick={onClose}>✕</button>
        </div>

        {error && <div className="ap-msg">{error}</div>}

        {step === 'idle' && (
          <div className="ap-body">
            <p>L'IA génère un questionnaire <strong>unique pour ce candidat</strong>
               (QCM + questions de raisonnement), ciblé sur l'offre et son profil.
               100% local et confidentiel.</p>

            <label className="ap-label">✍️ Vos questions personnalisées <em>(optionnel, une par ligne)</em></label>
            <textarea
              className="ap-rq" rows={3}
              placeholder={"Ex: Pourquoi voulez-vous rejoindre notre entreprise ?\nEx: Êtes-vous disponible immédiatement ?"}
              value={recruiterQs} onChange={e => setRecruiterQs(e.target.value)}
            />

            <button className="ap-btn" onClick={launch} disabled={loading}>
              {loading ? '⏳ Génération du questionnaire (2 à 6 min, IA locale)…' : '🚀 Générer et lancer l\'évaluation'}
            </button>
          </div>
        )}

        {step === 'link' && (
          <div className="ap-body">
            <div className="ap-ok">✓ Questionnaire unique généré</div>
            <p>Transmettez ce lien au candidat :</p>
            <div className="ap-link-box">
              <input readOnly value={link} onClick={e => e.target.select()} />
              <button onClick={copyLink}>{copied ? 'Copié ✓' : 'Copier'}</button>
            </div>
            <a className="ap-open" href={link} target="_blank" rel="noreferrer">Ouvrir (aperçu candidat) ↗</a>
            <hr className="ap-sep" />
            <button className="ap-btn" onClick={seeResults} disabled={loading}>
              {loading ? 'Analyse (rapport IA local)…' : '📊 Voir les résultats'}
            </button>
          </div>
        )}

        {step === 'results' && (
          <div className="ap-body">
            {/* Badge fiabilité */}
            {gap && (
              <div className="ap-fiab">
                <div className="ap-fiab-score">{Math.round(gap.fiabilite_cv)}<span>/100</span></div>
                <div>
                  <div className="ap-fiab-lbl">Fiabilité du CV</div>
                  <span className={`ap-badge ${LABEL[gap.niveau_label]?.cls}`}>{LABEL[gap.niveau_label]?.txt}</span>
                </div>
              </div>
            )}

            {/* Radar Déclaré vs Démontré */}
            {radarData.length > 0 && (
              <div className="ap-radar">
                <ResponsiveContainer width="100%" height={270}>
                  <RadarChart data={radarData} outerRadius="72%">
                    <PolarGrid />
                    <PolarAngleAxis dataKey="competence" tick={{ fontSize: 12 }} />
                    <PolarRadiusAxis domain={[0, 10]} tick={{ fontSize: 10 }} />
                    <Radar name="Déclaré (CV)" dataKey="Déclaré (CV)" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.35} />
                    <Radar name="Démontré (test)" dataKey="Démontré (test)" stroke="#4338ca" fill="#4338ca" fillOpacity={0.35} />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Rapport IA */}
            {report && (
              <div className="ap-report">
                <div className="ap-rep-head">
                  <span>📝 Rapport IA</span>
                  <span className={`ap-badge ${RECO[report.recommandation] || 'ap-badge-mid'}`}>{report.recommandation}</span>
                </div>
                <p className="ap-synth">{report.synthese}</p>
                <p className="ap-meta">Niveau : <strong>{report.niveau_technique}</strong> · Raisonnement : <strong>{report.qualite_raisonnement}</strong></p>
                {report.coherence_cv && <p className="ap-coh">🔍 {report.coherence_cv}</p>}
              </div>
            )}

            {/* Bouton VOIR LES RÉPONSES (vérification recruteur) */}
            {detail && (
              <button className="ap-btn-ghost" onClick={() => setShowAnswers(v => !v)}>
                {showAnswers ? '▲ Masquer les réponses' : `▼ Voir les réponses du candidat (${(detail.qcm?.length || 0) + (detail.open_answers?.length || 0)})`}
              </button>
            )}

            {showAnswers && detail && (
              <div className="ap-answers">
                {detail.qcm?.length > 0 && <h4 className="ap-ans-title">QCM ({detail.qcm.filter(q => q.correct).length}/{detail.qcm.length} corrects)</h4>}
                {detail.qcm?.map((q, i) => (
                  <div key={`q${i}`} className={`ap-ans ${q.correct ? 'ap-ans-ok' : 'ap-ans-ko'}`}>
                    <div className="ap-ans-q">[{q.competence} · diff {q.difficulte}] {q.question}</div>
                    <div className="ap-ans-r">
                      Candidat : <strong>{q.options?.[q.reponse_candidat] ?? '—'}</strong> {q.correct ? '✓' : '✗'}
                      {!q.correct && <span className="ap-ans-good"> · Bonne réponse : {q.options?.[q.bonne_reponse]}</span>}
                    </div>
                  </div>
                ))}
                {detail.open_answers?.length > 0 && <h4 className="ap-ans-title">Réponses rédigées</h4>}
                {detail.open_answers?.map((a, i) => (
                  <div key={`o${i}`} className="ap-ans">
                    <div className="ap-ans-q">
                      {a.source === 'recruteur' ? '👤 [Votre question] ' : `[${a.competence}] `}{a.question}
                      {a.score != null && <span className="ap-ans-score"> {Math.round(a.score)}/100</span>}
                    </div>
                    <div className="ap-ans-text">{a.answer}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
