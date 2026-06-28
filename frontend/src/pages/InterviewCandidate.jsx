import { useEffect, useState, useRef, useCallback } from 'react'
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
const SECONDS_PER_QUESTION = 180  // 3 min par question

export default function InterviewCandidate() {
  const { token } = useParams()
  const [meta, setMeta]       = useState(null)   // infos d'accès (GET)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  // PIN
  const [pin, setPin]         = useState('')
  const [verifying, setVerifying] = useState(false)
  const [verified, setVerified]   = useState(false)

  // Entretien
  const [questions, setQuestions] = useState([])
  const [idx, setIdx]         = useState(0)
  const [answer, setAnswer]   = useState('')
  const [sending, setSending] = useState(false)
  const [done, setDone]       = useState(false)
  const [timeLeft, setTimeLeft] = useState(SECONDS_PER_QUESTION)

  // Anti-triche (compteurs)
  const tabSwitches = useRef(0)
  const fsExits     = useRef(0)
  const pasteDetected = useRef(false)
  const qStartTime  = useRef(Date.now())
  const submitRef   = useRef(null)
  const wasFullscreen = useRef(false)
  const [security, setSecurity] = useState('')  // '' | 'warning' | 'blocked'

  // ── Chargement initial (métadonnées) ──
  useEffect(() => {
    publicApi.get(`/interviews/public/${token}`)
      .then(res => {
        setMeta(res.data)
        if (res.data.completed) setDone(true)
      })
      .catch(e => setError(e?.response?.data?.detail || "Lien d'entretien invalide ou expiré."))
      .finally(() => setLoading(false))
  }, [token])

  // ── Signalement temps réel des événements d'intégrité ──
  const reportEvent = useCallback((type) => {
    return publicApi.post(`/interviews/public/${token}/event`, { pin: pin.trim(), type })
      .then(res => {
        if (res.data.blocked) setSecurity('blocked')
        else if (res.data.warning) setSecurity('warning')
      })
      .catch(() => {})
  }, [token, pin])

  // ── Détection changement d'onglet + sortie plein écran ──
  useEffect(() => {
    if (!verified) return
    const onVisibility = () => { if (document.hidden) { tabSwitches.current += 1; reportEvent('tab_switch') } }
    const onFsChange = () => {
      if (document.fullscreenElement) {
        wasFullscreen.current = true
      } else if (wasFullscreen.current) {
        fsExits.current += 1
        reportEvent('fullscreen_exit')   // le backend décide : avertir ou bloquer
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    document.addEventListener('fullscreenchange', onFsChange)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      document.removeEventListener('fullscreenchange', onFsChange)
    }
  }, [verified, reportEvent])

  // ── Timer par question ──
  useEffect(() => {
    if (!verified || done) return
    setTimeLeft(SECONDS_PER_QUESTION)
    qStartTime.current = Date.now()
    const t = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) { clearInterval(t); submitRef.current && submitRef.current(true); return 0 }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [idx, verified, done])

  const enterFullscreen = () => {
    const el = document.documentElement
    if (el.requestFullscreen) el.requestFullscreen().catch(() => {})
  }

  // ── Vérification du PIN → démarre l'entretien ──
  const verify = () => {
    setVerifying(true); setError(null)
    publicApi.post(`/interviews/public/${token}/verify`, { pin: pin.trim() })
      .then(res => {
        const qs = res.data.questions || []
        const first = qs.findIndex(q => !q.answered)
        setQuestions(qs)
        setIdx(first === -1 ? qs.length : first)
        setVerified(true)
        enterFullscreen()
      })
      .catch(e => setError(e?.response?.data?.detail || 'Code incorrect.'))
      .finally(() => setVerifying(false))
  }

  const current = questions[idx]
  const total = questions.length

  // ── Soumission d'une réponse ──
  const submit = useCallback((auto = false) => {
    if (security === 'blocked') return
    const cur = questions[idx]
    if (!cur) return
    const text = (auto && !answer.trim()) ? '(Pas de réponse — temps écoulé)' : answer.trim()
    if (!text) return
    setSending(true); setError(null)
    const responseTime = (Date.now() - qStartTime.current) / 1000
    publicApi.post(`/interviews/public/${token}/answer`, {
      question_id: cur.id,
      answer_text: text,
      pin: pin.trim(),
      response_time: responseTime,
      paste_detected: pasteDetected.current,
      tab_switches: tabSwitches.current,
      fullscreen_exits: fsExits.current,
    })
      .then(res => {
        setAnswer(''); pasteDetected.current = false
        if (res.data.followup) {
          const fu = res.data.followup
          setQuestions(prev => { const a = [...prev]; a.splice(idx + 1, 0, { ...fu, answered: false }); return a })
          setIdx(idx + 1)
        } else if (res.data.done) {
          setDone(true)
        } else {
          setIdx(idx + 1)
        }
      })
      .catch(e => {
        if (e?.response?.status === 423) setSecurity('blocked')
        else setError(e?.response?.data?.detail || "Erreur lors de l'envoi. Réessayez.")
      })
      .finally(() => setSending(false))
  }, [questions, idx, answer, pin, token, security])
  submitRef.current = submit

  // ── Écrans ──
  if (loading) return <div className="itw-screen"><div className="itw-card">Chargement…</div></div>

  if (error && !meta) return (
    <div className="itw-screen"><div className="itw-card itw-error"><h2>Entretien indisponible</h2><p>{error}</p></div></div>
  )

  if (done) return (
    <div className="itw-screen">
      <div className="itw-card itw-done">
        <div className="itw-check">✓</div>
        <h2>Merci {meta?.candidate_name?.split(' ')[0]} !</h2>
        <p>Votre entretien pour le poste de <strong>{meta?.offer_titre}</strong> est terminé.</p>
        <p className="itw-muted">Vos réponses ont été transmises au recruteur.</p>
      </div>
    </div>
  )

  // Fenêtre non ouverte / expirée
  if (meta && meta.access && meta.access !== 'open') {
    const fmt = (iso) => iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' }) : null
    const notOpen = meta.access === 'not_open'
    return (
      <div className="itw-screen">
        <div className="itw-card">
          <div className="itw-check" style={{ background: notOpen ? '#1B4F8A' : '#dc2626' }}>{notOpen ? '🕒' : '⏳'}</div>
          <h2>{notOpen ? 'Entretien pas encore ouvert' : 'Entretien clôturé'}</h2>
          <p>Bonjour {meta.candidate_name?.split(' ')[0]}, entretien pour <strong>{meta.offer_titre}</strong>.</p>
          <p className="itw-muted">{meta.access_message}</p>
          {notOpen && meta.opens_at && <p><strong>Ouverture :</strong> {fmt(meta.opens_at)}</p>}
          {!notOpen && meta.deadline && <p><strong>Date limite passée :</strong> {fmt(meta.deadline)}</p>}
        </div>
      </div>
    )
  }

  // Écran PIN (avant de démarrer)
  if (!verified) return (
    <div className="itw-screen">
      <div className="itw-card">
        <div className="itw-check" style={{ background: '#1B4F8A' }}>🔒</div>
        <h2>Accès sécurisé</h2>
        <p>Bonjour {meta?.candidate_name?.split(' ')[0]}, votre entretien pour le poste de <strong>{meta?.offer_titre}</strong>.</p>
        <p className="itw-muted">Saisissez le code d'accès reçu par email.</p>
        <input
          className="itw-pin-input"
          inputMode="numeric"
          maxLength={6}
          placeholder="••••••"
          value={pin}
          onChange={e => setPin(e.target.value.replace(/\D/g, ''))}
          onKeyDown={e => e.key === 'Enter' && pin.length >= 4 && verify()}
        />
        {error && <div className="itw-inline-error">{error}</div>}
        <button className="itw-btn" style={{ width: '100%', marginTop: 14 }}
          onClick={verify} disabled={verifying || pin.length < 4}>
          {verifying ? 'Vérification…' : 'Démarrer l\'entretien'}
        </button>
        <p className="itw-muted" style={{ marginTop: 14, fontSize: 12 }}>
          ⚠️ L'entretien se déroule en plein écran. Le copier-coller est désactivé et
          les changements d'onglet sont enregistrés.
        </p>
      </div>
    </div>
  )

  // Écran entretien
  const progress = Math.round((idx / total) * 100)
  const mm = String(Math.floor(timeLeft / 60)).padStart(2, '0')
  const ss = String(timeLeft % 60).padStart(2, '0')
  const lowTime = timeLeft <= 30

  return (
    <div className="itw-screen" onCopy={e => e.preventDefault()} onContextMenu={e => e.preventDefault()}>
      {/* Overlay sécurité : 1er avertissement (dernière chance) */}
      {security === 'warning' && (
        <div className="itw-fs-overlay">
          <div className="itw-fs-box">
            <div className="itw-fs-icon">⚠️</div>
            <h2>Avertissement</h2>
            <p>Vous avez quitté le plein écran. <strong>C'est votre dernière chance</strong> :
               une nouvelle sortie entraînera l'<strong>arrêt définitif</strong> de l'entretien.
               Cet incident est enregistré et signalé au recruteur.</p>
            <button className="itw-btn" onClick={() => { enterFullscreen(); setSecurity('') }}>
              Reprendre l'entretien
            </button>
          </div>
        </div>
      )}

      {/* Overlay sécurité : entretien bloqué (définitif) */}
      {security === 'blocked' && (
        <div className="itw-fs-overlay">
          <div className="itw-fs-box">
            <div className="itw-fs-icon">🚫</div>
            <h2 style={{ color: '#dc2626' }}>Entretien interrompu</h2>
            <p>Votre entretien a été <strong>arrêté</strong> en raison de sorties répétées du
               mode sécurisé. Cet incident a été transmis au recruteur, qui prendra la
               décision finale.</p>
            <p className="itw-muted" style={{ fontSize: 13 }}>Vous pouvez fermer cette page.</p>
          </div>
        </div>
      )}

      <div className="itw-container">
        <div className="itw-header">
          <div>
            <div className="itw-logo">3S TalentMatch</div>
            <div className="itw-poste">Entretien — {meta?.offer_titre}</div>
          </div>
          <div className={`itw-timer ${lowTime ? 'itw-timer-low' : ''}`}>⏱ {mm}:{ss}</div>
        </div>

        <div className="itw-progress-wrap">
          <div className="itw-progress-bar" style={{ width: `${progress}%` }} />
        </div>
        <div className="itw-progress-text">Question {idx + 1} sur {total}</div>

        <div className="itw-question-card">
          <div className="itw-phase-badge">
            {current?.is_followup ? '↳ Question de suivi' : (PHASE_LABEL[current?.phase] || current?.phase)}
          </div>
          {/* Question : copie interdite */}
          <h2 className="itw-question" onCopy={e => e.preventDefault()} style={{ userSelect: 'none' }}>
            {current?.question}
          </h2>
          {current?.context_hint && <div className="itw-hint">💡 {current.context_hint}</div>}

          <textarea
            className="itw-textarea"
            placeholder="Rédigez votre réponse ici… (copier-coller désactivé)"
            value={answer}
            onChange={e => setAnswer(e.target.value)}
            onPaste={e => { e.preventDefault(); pasteDetected.current = true }}
            onCopy={e => e.preventDefault()}
            onCut={e => e.preventDefault()}
            rows={8}
            disabled={sending}
          />

          {error && <div className="itw-inline-error">{error}</div>}

          <div className="itw-actions">
            <span className="itw-count">{answer.trim().length} caractères</span>
            <button className="itw-btn" onClick={() => submit(false)} disabled={sending || !answer.trim()}>
              {sending ? 'Analyse en cours…' : (idx + 1 >= total ? 'Terminer l\'entretien' : 'Valider et continuer')}
            </button>
          </div>
        </div>

        <div className="itw-footer">
          🔒 Entretien sécurisé · copier-coller désactivé · activité surveillée
        </div>
      </div>
    </div>
  )
}
