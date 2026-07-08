import { useEffect, useState } from 'react'
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../services/api'
import './AssessmentsTab.css'

const STATUS = {
  in_progress: { label: 'En cours', cls: 'ast-st-prog' },
  completed:   { label: 'Terminé',  cls: 'ast-st-done' },
  abandoned:   { label: 'Abandonné', cls: 'ast-st-wait' },
}
const FIAB = (label) => label === 'fiable' ? { txt: 'CV fiable', cls: 'ast-ok' }
  : label === 'a_verifier' ? { txt: 'À vérifier', cls: 'ast-mid' }
  : label === 'ecart_important' ? { txt: 'Écart important', cls: 'ast-no' } : null

export default function AssessmentsTab({ offerId }) {
  const [list, setList]       = useState(null)
  const [titre, setTitre]     = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [detail, setDetail]   = useState(null)   // session sélectionnée
  const [deleting, setDeleting] = useState(null)

  const load = () => {
    setLoading(true)
    api.get('/assessment/list', { params: { offer_id: offerId } })
      .then(res => { setList(res.data.sessions); setTitre(res.data.offer_titre || '') })
      .catch(e => setError(e?.response?.data?.detail || 'Erreur de chargement.'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [offerId])

  const remove = (s) => {
    if (!window.confirm(`Supprimer l'évaluation de ${s.candidate_name} ?`)) return
    setDeleting(s.session_id)
    api.delete(`/assessment/${s.session_id}`)
      .then(() => setList(prev => prev.filter(x => x.session_id !== s.session_id)))
      .catch(e => alert(e?.response?.data?.detail || 'Suppression impossible.'))
      .finally(() => setDeleting(null))
  }

  if (loading) return <div className="ast-empty">Chargement des évaluations…</div>
  if (error)   return <div className="ast-empty ast-err">{error}</div>
  if (!list || list.length === 0)
    return <div className="ast-empty">Aucune évaluation lancée pour cette offre.
      Lancez-en depuis l'onglet <strong>Matching</strong> (bouton 🎯 Évaluation).</div>

  return (
    <div className="ast-wrap">
      <div className="ast-head">
        <div>
          <h3>🎯 Évaluations — {titre}</h3>
          <div className="ast-sub">{list.length} candidat{list.length > 1 ? 's' : ''} évalué{list.length > 1 ? 's' : ''}</div>
        </div>
        <button className="ast-refresh" onClick={load}>↻ Actualiser</button>
      </div>

      <table className="ast-table">
        <thead>
          <tr><th>Candidat</th><th>Progression</th><th>Statut</th><th>Niveau</th><th>Fiabilité CV</th><th></th></tr>
        </thead>
        <tbody>
          {list.map(s => {
            const st = STATUS[s.status] || STATUS.in_progress
            const fiab = FIAB(s.niveau_label)
            const pct = s.total_qcm ? Math.round(s.answered_qcm / s.total_qcm * 100) : 0
            return (
              <tr key={s.session_id}>
                <td>
                  <div className="ast-cand">{s.candidate_name}</div>
                  <div className="ast-mail">{s.candidate_email}</div>
                </td>
                <td>
                  <div className="ast-bar"><div className="ast-bar-fill" style={{ width: `${pct}%` }} /></div>
                  <span className="ast-bar-txt">{s.answered_qcm}/{s.total_qcm ?? '—'} QCM · {s.answered_open}/{s.total_open} rédigées</span>
                </td>
                <td><span className={`ast-badge ${st.cls}`}>{st.label}</span></td>
                <td>{s.niveau_global != null ? <strong>{s.niveau_global}/10</strong> : <span className="ast-dash">—</span>}</td>
                <td>{fiab
                  ? <span className={`ast-badge ${fiab.cls}`}>{Math.round(s.fiabilite_cv)}% · {fiab.txt}</span>
                  : <span className="ast-dash">—</span>}</td>
                <td className="ast-actions">
                  <button className="ast-view" onClick={() => setDetail(s)}>Voir →</button>
                  <button className="ast-del" disabled={deleting === s.session_id} onClick={() => remove(s)}>
                    {deleting === s.session_id ? '…' : '🗑'}
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {detail && <AssessmentDetail session={detail} offerId={offerId} onClose={() => setDetail(null)} />}
    </div>
  )
}

// ─── Détail : radar + rapport IA + toutes les réponses ───
function AssessmentDetail({ session, offerId, onClose }) {
  const [tab, setTab]       = useState('resultats')  // resultats | reponses
  const [gap, setGap]       = useState(null)
  const [report, setReport] = useState(null)
  const [answers, setAnswers] = useState(null)
  const [loading, setLoading] = useState(true)
  const [genLoading, setGen] = useState(false)
  const [error, setError]   = useState(null)

  useEffect(() => {
    Promise.all([
      api.get(`/assessment/reality-gap/${session.candidate_id}/${offerId}`).catch(() => ({ data: null })),
      api.get(`/assessment/detail/${session.session_id}`).catch(() => ({ data: null })),
    ])
      .then(([g, d]) => { setGap(g.data); setAnswers(d.data) })
      .finally(() => setLoading(false))
  }, [session, offerId])

  const generateReport = () => {
    setGen(true); setError(null)
    api.post(`/assessment/report/${session.session_id}`, null, { timeout: 300000 })
      .then(res => setReport(res.data.report))
      .catch(e => setError(e?.response?.data?.detail || 'Erreur rapport.'))
      .finally(() => setGen(false))
  }

  const radarData = gap?.details?.map(d => ({
    competence: d.competence,
    'Déclaré (CV)': d.niveau_declare,
    'Démontré (test)': d.niveau_demontre,
  })) || []

  return (
    <div className="ast-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="ast-modal">
        <div className="ast-modal-head">
          <h3>{session.candidate_name}</h3>
          <button className="ast-close" onClick={onClose}>✕</button>
        </div>

        <div className="ast-tabs">
          <button className={`ast-tab ${tab === 'resultats' ? 'active' : ''}`} onClick={() => setTab('resultats')}>📊 Résultats</button>
          <button className={`ast-tab ${tab === 'reponses' ? 'active' : ''}`} onClick={() => setTab('reponses')}>
            💬 Réponses ({(answers?.qcm?.length || 0) + (answers?.open_answers?.length || 0)})
          </button>
        </div>

        {loading && <div className="ast-empty">Chargement…</div>}
        {error && <div className="ast-empty ast-err">{error}</div>}

        {!loading && tab === 'resultats' && (
          <div className="ast-body">
            {/* Score d'intégrité (anti-triche) */}
            {answers?.integrity && (
              <div className={`ast-integ ast-integ-${answers.integrity.level}`}>
                <div className="ast-integ-head">
                  <span>🛡️ Intégrité de l'évaluation</span>
                  <strong>{answers.integrity.score}/100</strong>
                </div>
                {answers.integrity.flags?.length > 0
                  ? <ul className="ast-integ-flags">{answers.integrity.flags.map((f, i) => <li key={i}>⚠ {f}</li>)}</ul>
                  : <p className="ast-integ-ok">✓ Aucun comportement suspect détecté.</p>}
              </div>
            )}

            {gap && (
              <div className="ast-fiab-row">
                <div className="ast-fiab-score">{Math.round(gap.fiabilite_cv)}<span>/100</span></div>
                <div>
                  <div className="ast-fiab-lbl">Fiabilité du CV</div>
                  <span className={`ast-badge ${FIAB(gap.niveau_label)?.cls || ''}`}>{FIAB(gap.niveau_label)?.txt}</span>
                </div>
                {answers?.niveau_global != null && (
                  <div className="ast-niveau">Niveau démontré : <strong>{answers.niveau_global}/10</strong></div>
                )}
              </div>
            )}

            {radarData.length > 0 && (
              <ResponsiveContainer width="100%" height={260}>
                <RadarChart data={radarData} outerRadius="72%">
                  <PolarGrid />
                  <PolarAngleAxis dataKey="competence" tick={{ fontSize: 12 }} />
                  <PolarRadiusAxis domain={[0, 10]} tick={{ fontSize: 10 }} />
                  <Radar name="Déclaré (CV)" dataKey="Déclaré (CV)" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.35} />
                  <Radar name="Démontré (test)" dataKey="Démontré (test)" stroke="#4338ca" fill="#4338ca" fillOpacity={0.35} />
                  <Legend />
                </RadarChart>
              </ResponsiveContainer>
            )}

            {report ? (
              <div className="ast-report">
                <div className="ast-rep-head"><span>📝 Rapport IA</span><strong>{report.recommandation}</strong></div>
                <p>{report.synthese}</p>
                <p className="ast-meta">Niveau : <strong>{report.niveau_technique}</strong> · Raisonnement : <strong>{report.qualite_raisonnement}</strong></p>
                {report.coherence_cv && <p className="ast-coh">🔍 {report.coherence_cv}</p>}
              </div>
            ) : (
              <button className="ast-btn" onClick={generateReport} disabled={genLoading}>
                {genLoading ? '⏳ Rédaction du rapport (IA locale)…' : '📝 Générer le rapport IA'}
              </button>
            )}
          </div>
        )}

        {!loading && tab === 'reponses' && answers && (
          <div className="ast-body">
            {answers.qcm?.length > 0 && (
              <h4 className="ast-sec">QCM — {answers.qcm.filter(q => q.correct).length}/{answers.qcm.length} corrects</h4>
            )}
            {answers.qcm?.map((q, i) => (
              <div key={`q${i}`} className={`ast-ans ${q.correct ? 'ast-ans-ok' : 'ast-ans-ko'}`}>
                <div className="ast-ans-q">[{q.competence} · diff {q.difficulte}] {q.question}</div>
                <div className="ast-ans-r">
                  Candidat : <strong>{q.options?.[q.reponse_candidat] ?? '—'}</strong> {q.correct ? '✓' : '✗'}
                  {!q.correct && <span className="ast-good"> · Bonne réponse : {q.options?.[q.bonne_reponse]}</span>}
                </div>
              </div>
            ))}
            {answers.open_answers?.length > 0 && <h4 className="ast-sec">Réponses rédigées</h4>}
            {answers.open_answers?.map((a, i) => (
              <div key={`o${i}`} className="ast-ans">
                <div className="ast-ans-q">
                  {a.source === 'recruteur' ? '👤 [Votre question] ' : `[${a.competence}] `}{a.question}
                  {a.score != null && <span className="ast-score"> {Math.round(a.score)}/100</span>}
                </div>
                <div className="ast-ans-text">{a.answer}</div>
              </div>
            ))}
            {!answers.qcm?.length && !answers.open_answers?.length && (
              <div className="ast-empty">Le candidat n'a pas encore répondu.</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
