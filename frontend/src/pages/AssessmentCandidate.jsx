import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import './AssessmentCandidate.css'

// Axios dédié (candidat non connecté), timeout large (scoring local)
const publicApi = axios.create({ baseURL: '/api', timeout: 60000 })

export default function AssessmentCandidate() {
  const { token } = useParams()
  const [data, setData]       = useState(null)   // état renvoyé par /public/{token}
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [sending, setSending] = useState(false)

  // Phase ouverte : index de la question ouverte courante + texte
  const [openIdx, setOpenIdx] = useState(0)
  const [answer, setAnswer]   = useState('')

  const load = useCallback(() => {
    return publicApi.get(`/assessment/public/${token}`)
      .then(res => setData(res.data))
      .catch(e => setError(e?.response?.data?.detail || "Lien d'évaluation invalide."))
  }, [token])

  useEffect(() => { load().finally(() => setLoading(false)) }, [load])

  // Questionnaire en préparation (pool généré en arrière-plan) → re-vérifier
  useEffect(() => {
    if (data?.phase !== 'preparing') return
    const t = setInterval(load, 20000)
    return () => clearInterval(t)
  }, [data?.phase, load])

  // ── Répondre à un QCM ──
  const answerQcm = (displayIndex) => {
    if (sending) return
    setSending(true); setError(null)
    publicApi.post(`/assessment/public/${token}/answer`, {
      session_id: '', question_id: data.question.question_id, reponse: displayIndex,
    })
      .then(() => load())
      .catch(e => setError(e?.response?.data?.detail || 'Erreur.'))
      .finally(() => setSending(false))
  }

  // ── Répondre à une question ouverte ──
  const submitOpen = () => {
    if (sending || !answer.trim()) return
    const oq = data.open_questions[openIdx]
    setSending(true); setError(null)
    publicApi.post(`/assessment/public/${token}/open-answer`, {
      session_id: '', question_id: oq.question_id, answer: answer.trim(),
    })
      .then(() => {
        setAnswer('')
        if (openIdx + 1 < data.open_questions.length) {
          setOpenIdx(openIdx + 1)
        } else {
          return finishTest()
        }
      })
      .catch(e => setError(e?.response?.data?.detail || 'Erreur.'))
      .finally(() => setSending(false))
  }

  const finishTest = () => {
    setSending(true)
    return publicApi.post(`/assessment/public/${token}/finish`)
      .then(() => load())
      .finally(() => setSending(false))
  }

  // ── Écrans ──
  if (loading) return <div className="asv-screen"><div className="asv-card">Chargement de l'évaluation…</div></div>
  if (error && !data) return <div className="asv-screen"><div className="asv-card asv-err"><h2>Indisponible</h2><p>{error}</p></div></div>

  if (data?.phase === 'done' || data?.completed) return (
    <div className="asv-screen">
      <div className="asv-card asv-done">
        <div className="asv-check">✓</div>
        <h2>Merci {data?.candidate_name?.split(' ')[0]} !</h2>
        <p>Votre évaluation pour <strong>{data?.offer_titre}</strong> est terminée.</p>
        <p className="asv-muted">Vos résultats ont été transmis au recruteur.</p>
      </div>
    </div>
  )

  // Questionnaire en préparation (première évaluation de l'offre)
  if (data?.phase === 'preparing') return (
    <div className="asv-screen">
      <div className="asv-card">
        <div className="asv-check" style={{ background: '#4338ca' }}>⏳</div>
        <h2>Préparation en cours</h2>
        <p>Bonjour {data?.candidate_name?.split(' ')[0]}, votre questionnaire pour
           <strong> {data?.offer_titre}</strong> est en cours de préparation par notre IA.</p>
        <p className="asv-muted">Cette page se rafraîchit automatiquement — encore quelques minutes.</p>
      </div>
    </div>
  )

  const isQcm = data?.phase === 'qcm'
  const pct = isQcm && data.total_qcm ? Math.round(data.answered_qcm / data.total_qcm * 100) : 100

  return (
    <div className="asv-screen">
      <div className="asv-container">
        <div className="asv-header">
          <div>
            <div className="asv-logo">3S TalentMatch</div>
            <div className="asv-poste">Évaluation — {data?.offer_titre}</div>
          </div>
          <div className="asv-phase-tag">{isQcm ? 'QCM technique' : 'Raisonnement'}</div>
        </div>

        <div className="asv-progress-wrap"><div className="asv-progress-bar" style={{ width: `${pct}%` }} /></div>
        <div className="asv-progress-text">
          {isQcm
            ? `Question ${data.answered_qcm + 1} sur ${data.total_qcm}`
            : `Question ouverte ${openIdx + 1} sur ${data.open_questions?.length || 0}`}
        </div>

        {/* ── QCM ── */}
        {isQcm && data.question && (
          <div className="asv-qcard">
            <div className="asv-comp">{data.question.competence} · difficulté {data.question.difficulte}/10</div>
            <h2 className="asv-question">{data.question.question}</h2>
            <div className="asv-options">
              {data.question.options.map((opt, i) => (
                <button key={i} className="asv-option" disabled={sending} onClick={() => answerQcm(i)}>
                  <span className="asv-opt-letter">{String.fromCharCode(65 + i)}</span>{opt}
                </button>
              ))}
            </div>
            {sending && <div className="asv-hint-send">Analyse…</div>}
          </div>
        )}

        {/* ── Question ouverte (raisonnement) ── */}
        {data?.phase === 'open' && (
          data.open_questions?.length > 0 ? (
            <div className="asv-qcard">
              <div className="asv-comp">{data.open_questions[openIdx]?.competence} · raisonnement</div>
              <h2 className="asv-question">{data.open_questions[openIdx]?.question}</h2>
              <textarea
                className="asv-textarea" rows={7}
                placeholder="Expliquez votre démarche, appuyez-vous sur des exemples concrets…"
                value={answer} onChange={e => setAnswer(e.target.value)} disabled={sending}
                onPaste={e => e.preventDefault()} onCopy={e => e.preventDefault()}
              />
              <div className="asv-actions">
                <span className="asv-count">{answer.trim().length} caractères</span>
                <button className="asv-btn" onClick={submitOpen} disabled={sending || !answer.trim()}>
                  {sending ? 'Envoi…' : (openIdx + 1 < data.open_questions.length ? 'Suivant' : 'Terminer')}
                </button>
              </div>
            </div>
          ) : (
            <div className="asv-qcard asv-center">
              <p>Partie QCM terminée. Aucune question ouverte pour cette offre.</p>
              <button className="asv-btn" onClick={finishTest} disabled={sending}>Terminer l'évaluation</button>
            </div>
          )
        )}

        {error && <div className="asv-inline-err">{error}</div>}
        <div className="asv-footer">🔒 Évaluation sécurisée · copier-coller désactivé</div>
      </div>
    </div>
  )
}
