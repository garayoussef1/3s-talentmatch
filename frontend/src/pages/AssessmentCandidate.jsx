import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import './AssessmentCandidate.css'

// Axios dédié (candidat non connecté), timeout large (scoring local)
const publicApi = axios.create({ baseURL: '/api', timeout: 60000 })

const QCM_SECONDS = 90   // timer par QCM (anti-recherche externe)

export default function AssessmentCandidate() {
  const { token } = useParams()
  const [data, setData]       = useState(null)   // état renvoyé par /public/{token}
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [sending, setSending] = useState(false)

  // Phase ouverte : index de la question ouverte courante + texte
  const [openIdx, setOpenIdx] = useState(0)
  const [answer, setAnswer]   = useState('')

  // Code PIN (2ᵉ facteur reçu par email)
  const [pin, setPin]         = useState('')
  const [pinInput, setPinInput] = useState('')
  const [verifying, setVerifying] = useState(false)

  // ── Anti-triche (mode examen) ──
  const [security, setSecurity] = useState('')   // '' | 'warning' | 'blocked'
  const [remaining, setRemaining] = useState(null)  // sorties restantes avant blocage
  const [rulesOk, setRulesOk] = useState(false)     // règles acceptées (écran dédié)
  const [timeLeft, setTimeLeft] = useState(QCM_SECONDS)
  const keystrokes = useRef(0)         // frappes dans la zone de rédaction
  const pasteTried = useRef(false)     // collage tenté (bloqué)
  const qStart = useRef(Date.now())    // début de la question courante
  const wasFullscreen = useRef(false)
  const phaseRef = useRef('')          // phase courante (le comptage ne vaut qu'en test)
  useEffect(() => { phaseRef.current = data?.phase || '' }, [data?.phase])

  const enterFullscreen = () => {
    const el = document.documentElement
    if (el.requestFullscreen) el.requestFullscreen().catch(() => {})
  }

  const reportEvent = useCallback((type) => {
    return publicApi.post(`/assessment/public/${token}/event`, { pin, type })
      .then(res => {
        if (res.data.blocked) setSecurity('blocked')
        else if (res.data.warning) { setSecurity('warning'); setRemaining(res.data.remaining) }
      })
      .catch(() => {})
  }, [token, pin])

  // Détection onglet + sortie plein écran — UNIQUEMENT pendant le test
  // (phases qcm/open, après acceptation des règles)
  useEffect(() => {
    if (!pin || !rulesOk) return
    const inTest = () => ['qcm', 'open'].includes(phaseRef.current)
    const onVisibility = () => { if (document.hidden && inTest()) reportEvent('tab_switch') }
    const onFsChange = () => {
      if (document.fullscreenElement) wasFullscreen.current = true
      else if (wasFullscreen.current && inTest()) reportEvent('fullscreen_exit')
    }
    document.addEventListener('visibilitychange', onVisibility)
    document.addEventListener('fullscreenchange', onFsChange)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      document.removeEventListener('fullscreenchange', onFsChange)
    }
  }, [pin, rulesOk, reportEvent])

  const load = useCallback((pinValue) => {
    const p = pinValue !== undefined ? pinValue : pin
    return publicApi.get(`/assessment/public/${token}`, { params: p ? { pin: p } : {} })
      .then(res => setData(res.data))
      .catch(e => setError(e?.response?.data?.detail || "Lien d'évaluation invalide."))
  }, [token, pin])

  const verifyPin = () => {
    setVerifying(true); setError(null)
    publicApi.get(`/assessment/public/${token}`, { params: { pin: pinInput.trim() } })
      .then(res => {
        setData(res.data)
        // Le plein écran ne démarre PAS ici : le candidat lit d'abord les
        // règles et clique "Commencer" (écran dédié).
        if (res.data.phase !== 'pin') setPin(pinInput.trim())
      })
      .catch(e => setError(e?.response?.data?.detail || 'Erreur.'))
      .finally(() => setVerifying(false))
  }

  // Timer par QCM : à 0, la question est soumise comme non répondue (-1)
  const currentQcmId = data?.phase === 'qcm' ? data?.question?.question_id : null
  useEffect(() => {
    if (!currentQcmId || security === 'blocked') return
    setTimeLeft(QCM_SECONDS)
    qStart.current = Date.now()
    const t = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) { clearInterval(t); answerQcmRef.current(-1); return 0 }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentQcmId, security])
  const answerQcmRef = useRef(() => {})

  useEffect(() => { load().finally(() => setLoading(false)) }, [load])

  // Questionnaire en préparation (pool généré en arrière-plan) → re-vérifier
  useEffect(() => {
    if (data?.phase !== 'preparing') return
    const t = setInterval(load, 20000)
    return () => clearInterval(t)
  }, [data?.phase, load])

  // ── Répondre à un QCM ──
  const answerQcm = (displayIndex) => {
    if (sending || security === 'blocked') return
    setSending(true); setError(null)
    publicApi.post(`/assessment/public/${token}/answer`, {
      session_id: '', question_id: data.question.question_id, reponse: displayIndex, pin,
      response_time: (Date.now() - qStart.current) / 1000,
    })
      .then(() => load())
      .catch(e => {
        if (e?.response?.status === 423) setSecurity('blocked')
        else setError(e?.response?.data?.detail || 'Erreur.')
      })
      .finally(() => setSending(false))
  }
  answerQcmRef.current = answerQcm

  // ── Répondre à une question ouverte ──
  const submitOpen = () => {
    if (sending || !answer.trim() || security === 'blocked') return
    const oq = data.open_questions[openIdx]
    setSending(true); setError(null)
    publicApi.post(`/assessment/public/${token}/open-answer`, {
      session_id: '', question_id: oq.question_id, answer: answer.trim(), pin,
      response_time: (Date.now() - qStart.current) / 1000,
      keystrokes: keystrokes.current,
      paste_detected: pasteTried.current,
    })
      .then(() => {
        setAnswer(''); keystrokes.current = 0; pasteTried.current = false
        qStart.current = Date.now()
        if (openIdx + 1 < data.open_questions.length) {
          setOpenIdx(openIdx + 1)
        } else {
          return finishTest()
        }
      })
      .catch(e => {
        if (e?.response?.status === 423) setSecurity('blocked')
        else setError(e?.response?.data?.detail || 'Erreur.')
      })
      .finally(() => setSending(false))
  }

  const finishTest = () => {
    setSending(true)
    return publicApi.post(`/assessment/public/${token}/finish`, null, { params: pin ? { pin } : {} })
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

  // Code d'accès requis (PIN reçu par email)
  if (data?.phase === 'pin') return (
    <div className="asv-screen">
      <div className="asv-card">
        <div className="asv-check" style={{ background: '#4338ca' }}>🔒</div>
        <h2>Accès sécurisé</h2>
        <p>Bonjour {data?.candidate_name?.split(' ')[0]}, évaluation pour <strong>{data?.offer_titre}</strong>.</p>
        <p className="asv-muted">Saisissez le code d'accès reçu par email.</p>
        <input
          className="asv-pin"
          inputMode="numeric" maxLength={6} placeholder="••••••"
          value={pinInput}
          onChange={e => setPinInput(e.target.value.replace(/\D/g, ''))}
          onKeyDown={e => e.key === 'Enter' && pinInput.length >= 4 && verifyPin()}
        />
        {data.pin_invalid && <p className="asv-inline-err">Code incorrect, réessayez.</p>}
        {error && <p className="asv-inline-err">{error}</p>}
        <button className="asv-btn" style={{ width: '100%', marginTop: 14 }}
          onClick={verifyPin} disabled={verifying || pinInput.length < 4}>
          {verifying ? 'Vérification…' : 'Démarrer l\'évaluation'}
        </button>
      </div>
    </div>
  )

  // Fenêtre de passation : pas encore ouvert ou expiré
  if (data?.phase === 'window') {
    const fmt = (iso) => iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' }) : null
    const notOpen = data.access === 'not_open'
    return (
      <div className="asv-screen">
        <div className="asv-card">
          <div className="asv-check" style={{ background: notOpen ? '#4338ca' : '#dc2626' }}>{notOpen ? '🕒' : '⏳'}</div>
          <h2>{notOpen ? 'Évaluation pas encore ouverte' : 'Évaluation clôturée'}</h2>
          <p>Bonjour {data?.candidate_name?.split(' ')[0]}, évaluation pour <strong>{data?.offer_titre}</strong>.</p>
          <p className="asv-muted">{data.message}</p>
          {notOpen && data.opens_at && <p><strong>Ouverture :</strong> {fmt(data.opens_at)}</p>}
          {!notOpen && data.deadline && <p><strong>Date limite passée :</strong> {fmt(data.deadline)}</p>}
        </div>
      </div>
    )
  }

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

  // Écran des RÈGLES : annoncées AVANT de commencer (le plein écran démarre
  // sur le clic du candidat — geste explicite, pas de sanction surprise)
  if (pin && !rulesOk && ['qcm', 'open'].includes(data?.phase)) return (
    <div className="asv-screen">
      <div className="asv-card" style={{ maxWidth: 560, textAlign: 'left' }}>
        <h2 style={{ textAlign: 'center' }}>📋 Règles de l'évaluation</h2>
        <p style={{ textAlign: 'center' }}>Bonjour {data?.candidate_name?.split(' ')[0]},
           avant de commencer, prenez connaissance des règles :</p>
        <ul className="asv-rules">
          <li>🖥️ L'évaluation se déroule <strong>en plein écran</strong>. Vous disposez de
              <strong> 3 sorties maximum</strong> (Échap, rafraîchissement…) — au-delà,
              l'évaluation est arrêtée définitivement.</li>
          <li>⏱️ Chaque QCM est limité à <strong>90 secondes</strong> — temps écoulé = question comptée fausse.</li>
          <li>🚫 Le <strong>copier-coller est désactivé</strong> ; les changements d'onglet sont enregistrés.</li>
          <li>✍️ Rédigez vos réponses vous-même : l'activité du clavier est analysée.</li>
          <li>🎯 Répondez en une seule session, dans un endroit calme (20-30 min).</li>
        </ul>
        <button className="asv-btn" style={{ width: '100%', marginTop: 16 }}
          onClick={() => { enterFullscreen(); setRulesOk(true); qStart.current = Date.now() }}>
          ✓ J'ai compris — Commencer en plein écran
        </button>
      </div>
    </div>
  )

  const isQcm = data?.phase === 'qcm'
  const pct = isQcm && data.total_qcm ? Math.round(data.answered_qcm / data.total_qcm * 100) : 100
  const lowTime = timeLeft <= 15

  return (
    <div className="asv-screen" onCopy={e => e.preventDefault()} onContextMenu={e => e.preventDefault()}>
      {/* Overlay sécurité : avertissement (dernière chance) */}
      {security === 'warning' && (
        <div className="asv-fs-overlay">
          <div className="asv-fs-box">
            <div className="asv-fs-icon">⚠️</div>
            <h2>Avertissement</h2>
            <p>Vous avez quitté le plein écran. Cet incident est enregistré.</p>
            <p><strong>{remaining === 1
              ? "Dernière chance : encore une sortie et l'évaluation sera arrêtée définitivement."
              : `Il vous reste ${remaining} sorties avant l'arrêt définitif de l'évaluation.`}</strong></p>
            <button className="asv-btn" onClick={() => { enterFullscreen(); setSecurity('') }}>
              Reprendre l'évaluation
            </button>
          </div>
        </div>
      )}

      {/* Overlay sécurité : évaluation bloquée (définitif) */}
      {security === 'blocked' && (
        <div className="asv-fs-overlay">
          <div className="asv-fs-box">
            <div className="asv-fs-icon">🚫</div>
            <h2 style={{ color: '#dc2626' }}>Évaluation interrompue</h2>
            <p>Votre évaluation a été <strong>arrêtée</strong> en raison de sorties répétées du
               mode sécurisé. Cet incident a été transmis au recruteur.</p>
            <p className="asv-muted" style={{ fontSize: 13 }}>Vous pouvez fermer cette page.</p>
          </div>
        </div>
      )}

      <div className="asv-container">
        <div className="asv-header">
          <div>
            <div className="asv-logo">3S TalentMatch</div>
            <div className="asv-poste">Évaluation — {data?.offer_titre}</div>
          </div>
          {isQcm
            ? <div className={`asv-timer ${lowTime ? 'asv-timer-low' : ''}`}>⏱ {String(Math.floor(timeLeft / 60)).padStart(2, '0')}:{String(timeLeft % 60).padStart(2, '0')}</div>
            : <div className="asv-phase-tag">Raisonnement</div>}
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
                placeholder="Rédigez votre réponse… (copier-coller désactivé)"
                value={answer} onChange={e => setAnswer(e.target.value)} disabled={sending}
                onKeyDown={() => { keystrokes.current += 1 }}
                onPaste={e => { e.preventDefault(); pasteTried.current = true }}
                onCopy={e => e.preventDefault()} onCut={e => e.preventDefault()}
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
