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
const RECO = {
  RECRUTER: 'ap-badge-ok', A_APPROFONDIR: 'ap-badge-mid', REJETER: 'ap-badge-no',
}

export default function AssessmentPanel({ candidateId, offerId, candidateName, onClose }) {
  const [step, setStep]       = useState('idle')   // idle | link | results
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [link, setLink]       = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [gap, setGap]         = useState(null)
  const [report, setReport]   = useState(null)
  const [copied, setCopied]   = useState(false)

  const prepare = () => {
    setLoading(true); setError(null)
    api.post('/assessment/prepare', { offer_id: offerId }, { timeout: 600000 })
      .then(() => setError('✓ Questions préparées (cache). Vous pouvez lancer.'))
      .catch(e => setError(e?.response?.data?.detail || 'Erreur de préparation.'))
      .finally(() => setLoading(false))
  }

  const launch = () => {
    setLoading(true); setError(null)
    api.post('/assessment/launch', { candidate_id: candidateId, offer_id: offerId }, { timeout: 60000 })
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
      api.get(`/assessment/reality-gap/${candidateId}/${offerId}`),
      sessionId ? api.post(`/assessment/report/${sessionId}`, null, { timeout: 120000 }) : Promise.resolve({ data: {} }),
    ])
      .then(([g, r]) => { setGap(g.data); setReport(r.data.report || null); setStep('results') })
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
            <p>Évaluez ce candidat par un <strong>test adaptatif + questions de raisonnement</strong>
               (100% local). Le système mesure le niveau réel et le compare au CV.</p>
            <button className="ap-btn-ghost" onClick={prepare} disabled={loading}>
              {loading ? 'Génération des questions…' : '⚙️ Préparer les questions (si compétences nouvelles)'}
            </button>
            <button className="ap-btn" onClick={launch} disabled={loading}>
              {loading ? '…' : '🚀 Lancer l\'évaluation'}
            </button>
          </div>
        )}

        {step === 'link' && (
          <div className="ap-body">
            <div className="ap-ok">✓ Évaluation créée</div>
            <p>Transmettez ce lien au candidat :</p>
            <div className="ap-link-box">
              <input readOnly value={link} onClick={e => e.target.select()} />
              <button onClick={copyLink}>{copied ? 'Copié ✓' : 'Copier'}</button>
            </div>
            <a className="ap-open" href={link} target="_blank" rel="noreferrer">Ouvrir (aperçu candidat) ↗</a>
            <hr className="ap-sep" />
            <button className="ap-btn" onClick={seeResults} disabled={loading}>
              {loading ? 'Analyse…' : '📊 Voir les résultats'}
            </button>
          </div>
        )}

        {step === 'results' && gap && (
          <div className="ap-body">
            {/* Badge fiabilité */}
            <div className="ap-fiab">
              <div className="ap-fiab-score">{Math.round(gap.fiabilite_cv)}<span>/100</span></div>
              <div>
                <div className="ap-fiab-lbl">Fiabilité du CV</div>
                <span className={`ap-badge ${LABEL[gap.niveau_label]?.cls}`}>{LABEL[gap.niveau_label]?.txt}</span>
              </div>
            </div>

            {/* Radar Déclaré vs Démontré */}
            {radarData.length > 0 && (
              <div className="ap-radar">
                <ResponsiveContainer width="100%" height={280}>
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

            {/* Détail par compétence */}
            <div className="ap-details">
              {gap.details?.map((d, i) => (
                <div key={i} className="ap-drow">
                  <span className="ap-dcomp">{d.competence}</span>
                  <span className="ap-dvals">CV {d.niveau_declare} → test <strong>{d.niveau_demontre}</strong></span>
                  {d.gap >= 0.3 && <span className="ap-dgap">🚨 écart</span>}
                </div>
              ))}
            </div>

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
          </div>
        )}
      </div>
    </div>
  )
}
