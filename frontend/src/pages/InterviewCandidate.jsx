import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import './InterviewCandidate.css'

// Axios dédié : pas d'auth JWT (candidat non connecté), timeout long (scoring Groq)
const publicApi = axios.create({ baseURL: '/api', timeout: 60000 })

const PHASE_LABEL = {
  profile:     'Votre parcours',
  technical:   'Compétences techniques',
  situational: 'Mise en situation',
  soft_skills: 'Savoir-être',
  motivation:  'Motivation',
  closing:     'Clôture',
}

export default function InterviewCandidate() {
  const { token } = useParams()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const [idx, setIdx]         = useState(0)       // index question courante
  const [answer, setAnswer]   = useState('')
  const [sending, setSending] = useState(false)
  const [done, setDone]       = useState(false)

  // Chargement initial
  useEffect(() => {
    publicApi.get(`/interviews/public/${token}`)
      .then(res => {
        setData(res.data)
        if (res.data.completed) setDone(true)
        // Reprendre à la première question non répondue
        const firstUnanswered = res.data.questions.findIndex(q => !q.answered)
        setIdx(firstUnanswered === -1 ? res.data.questions.length : firstUnanswered)
      })
      .catch(e => setError(e?.response?.data?.detail || "Lien d'entretien invalide ou expiré."))
      .finally(() => setLoading(false))
  }, [token])

  const questions = data?.questions || []
  const current = questions[idx]
  const total = data?.total_questions || questions.length

  const submit = () => {
    if (!answer.trim() || !current) return
    setSending(true)
    setError(null)
    publicApi.post(`/interviews/public/${token}/answer`, {
      question_id: current.id,
      answer_text: answer.trim(),
    })
      .then(res => {
        setAnswer('')
        if (res.data.done || idx + 1 >= total) {
          setDone(true)
        } else {
          setIdx(idx + 1)
        }
      })
      .catch(e => setError(e?.response?.data?.detail || "Erreur lors de l'envoi. Réessayez."))
      .finally(() => setSending(false))
  }

  // ── États d'écran ──────────────────────────────────────────────
  if (loading) return <div className="itw-screen"><div className="itw-card">Chargement de l'entretien…</div></div>

  if (error && !data) return (
    <div className="itw-screen">
      <div className="itw-card itw-error">
        <h2>Entretien indisponible</h2>
        <p>{error}</p>
      </div>
    </div>
  )

  if (done) return (
    <div className="itw-screen">
      <div className="itw-card itw-done">
        <div className="itw-check">✓</div>
        <h2>Merci {data?.candidate_name?.split(' ')[0]} !</h2>
        <p>Votre entretien pour le poste de <strong>{data?.offer_titre}</strong> est terminé.</p>
        <p className="itw-muted">Vos réponses ont été transmises au recruteur. Vous serez recontacté(e) prochainement.</p>
      </div>
    </div>
  )

  const progress = Math.round((idx / total) * 100)

  return (
    <div className="itw-screen">
      <div className="itw-container">

        {/* En-tête */}
        <div className="itw-header">
          <div>
            <div className="itw-logo">3S TalentMatch</div>
            <div className="itw-poste">Entretien — {data?.offer_titre}</div>
          </div>
          <div className="itw-candidate">{data?.candidate_name}</div>
        </div>

        {/* Progression */}
        <div className="itw-progress-wrap">
          <div className="itw-progress-bar" style={{ width: `${progress}%` }} />
        </div>
        <div className="itw-progress-text">Question {idx + 1} sur {total}</div>

        {/* Carte question */}
        <div className="itw-question-card">
          <div className="itw-phase-badge">{PHASE_LABEL[current?.phase] || current?.phase}</div>
          <h2 className="itw-question">{current?.question}</h2>
          {current?.context_hint && (
            <div className="itw-hint">💡 {current.context_hint}</div>
          )}

          <textarea
            className="itw-textarea"
            placeholder="Rédigez votre réponse ici… Appuyez-vous sur des exemples concrets de votre expérience."
            value={answer}
            onChange={e => setAnswer(e.target.value)}
            rows={8}
            disabled={sending}
          />

          {error && <div className="itw-inline-error">{error}</div>}

          <div className="itw-actions">
            <span className="itw-count">{answer.trim().length} caractères</span>
            <button className="itw-btn" onClick={submit} disabled={sending || !answer.trim()}>
              {sending ? 'Analyse en cours…' : (idx + 1 >= total ? 'Terminer l\'entretien' : 'Valider et continuer')}
            </button>
          </div>
        </div>

        <div className="itw-footer">
          Prenez votre temps pour répondre. Vos réponses sont analysées par notre IA d'évaluation.
        </div>
      </div>
    </div>
  )
}
