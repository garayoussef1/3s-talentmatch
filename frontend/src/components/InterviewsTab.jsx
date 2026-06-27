import { useEffect, useState } from 'react'
import api from '../services/api'
import './InterviewsTab.css'

const STATUS_BADGE = {
  created:     { label: 'En attente', cls: 'itb-st-wait' },
  in_progress: { label: 'En cours',   cls: 'itb-st-prog' },
  completed:   { label: 'Terminé',    cls: 'itb-st-done' },
  abandoned:   { label: 'Abandonné',  cls: 'itb-st-wait' },
}
const RECO = {
  RECRUTER: { label: 'Recruter', cls: 'itb-reco-ok' },
  HESITER:  { label: 'Hésiter',  cls: 'itb-reco-mid' },
  REJETER:  { label: 'Rejeter',  cls: 'itb-reco-no' },
  recruit:  { label: 'Recruter', cls: 'itb-reco-ok' },
  hesitate: { label: 'Hésiter',  cls: 'itb-reco-mid' },
  reject:   { label: 'Rejeter',  cls: 'itb-reco-no' },
}
const PHASE = {
  profile: 'Parcours', technical: 'Technique', situational: 'Mise en situation',
  soft_skills: 'Savoir-être', motivation: 'Motivation', closing: 'Clôture',
}

export default function InterviewsTab({ offerId }) {
  const [list, setList]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [detailId, setDetailId] = useState(null)

  const load = () => {
    setLoading(true)
    api.get('/interviews', { params: { offer_id: offerId } })
      .then(res => setList(res.data.interviews))
      .catch(e => setError(e?.response?.data?.detail || 'Erreur de chargement.'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [offerId])

  if (loading) return <div className="itb-empty">Chargement des entretiens…</div>
  if (error)   return <div className="itb-empty itb-err">{error}</div>
  if (!list || list.length === 0)
    return <div className="itb-empty">Aucun entretien lancé pour cette offre. Lancez-en depuis l'onglet <strong>Matching</strong>.</div>

  return (
    <div className="itb-wrap">
      <div className="itb-head-row">
        <h3>Entretiens IA — {list.length} candidat{list.length > 1 ? 's' : ''}</h3>
        <button className="itb-refresh" onClick={load}>↻ Actualiser</button>
      </div>

      <table className="itb-table">
        <thead>
          <tr>
            <th>Candidat</th><th>Progression</th><th>Statut</th>
            <th>Score</th><th>Recommandation</th><th></th>
          </tr>
        </thead>
        <tbody>
          {list.map(it => {
            const pct = it.total_questions ? Math.round(it.answered_count / it.total_questions * 100) : 0
            const st = STATUS_BADGE[it.status] || STATUS_BADGE.created
            const reco = it.recommendation ? RECO[it.recommendation] : null
            return (
              <tr key={it.interview_id}>
                <td>
                  <div className="itb-cand">{it.candidate_name}</div>
                  <div className="itb-mail">{it.candidate_email}</div>
                </td>
                <td>
                  <div className="itb-bar"><div className="itb-bar-fill" style={{ width: `${pct}%` }} /></div>
                  <span className="itb-bar-txt">{it.answered_count}/{it.total_questions}</span>
                </td>
                <td><span className={`itb-badge ${st.cls}`}>{st.label}</span></td>
                <td>{it.has_report ? <strong>{Math.round(it.global_score)}/100</strong> : <span className="itb-dash">—</span>}</td>
                <td>{reco ? <span className={`itb-badge ${reco.cls}`}>{reco.label}</span> : <span className="itb-dash">—</span>}</td>
                <td><button className="itb-view" onClick={() => setDetailId(it.interview_id)}>Voir →</button></td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {detailId && (
        <InterviewDetail
          interviewId={detailId}
          onClose={() => setDetailId(null)}
          onReportGenerated={load}
        />
      )}
    </div>
  )
}

// ─── Détail d'un entretien : réponses + analyse + rapport ───
function InterviewDetail({ interviewId, onClose, onReportGenerated }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [genLoading, setGen]  = useState(false)
  const [error, setError]     = useState(null)

  const load = () => {
    setLoading(true)
    api.get(`/interviews/${interviewId}`)
      .then(res => setData(res.data))
      .catch(e => setError(e?.response?.data?.detail || 'Erreur.'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [interviewId])

  const generateReport = () => {
    setGen(true); setError(null)
    api.post(`/interviews/${interviewId}/report`, null, { timeout: 60000 })
      .then(() => { load(); onReportGenerated && onReportGenerated() })
      .catch(e => setError(e?.response?.data?.detail || "Le candidat n'a pas assez répondu."))
      .finally(() => setGen(false))
  }

  const report = data?.report
  const reco = report ? RECO[report.recommandation] : null
  const answeredCount = data?.questions?.filter(q => q.answered).length || 0

  return (
    <div className="itb-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="itb-modal">
        <div className="itb-modal-head">
          <h3>{data?.candidate_name || 'Entretien'}</h3>
          <button className="itb-close" onClick={onClose}>✕</button>
        </div>

        {loading && <div className="itb-empty">Chargement…</div>}
        {error && <div className="itb-empty itb-err">{error}</div>}

        {data && !loading && (
          <div className="itb-modal-body">
            {/* Rapport ou bouton de génération */}
            {report ? (
              <div className="itb-report">
                <div className="itb-report-top">
                  <div className="itb-score-big">{Math.round(report.score_global_100)}<span>/100</span></div>
                  {reco && <span className={`itb-badge itb-badge-lg ${reco.cls}`}>{reco.label}</span>}
                </div>
                <p className="itb-synth">{report.synthese_executive}</p>
                {report.competences?.validees?.length > 0 && (
                  <p className="itb-cmp"><strong>✅ Validées :</strong> {report.competences.validees.map(c => c.competence).join(', ')}</p>
                )}
                {report.competences?.non_validees?.length > 0 && (
                  <p className="itb-cmp"><strong>🔴 Non validées :</strong> {report.competences.non_validees.map(c => typeof c === 'string' ? c : c.competence).join(', ')}</p>
                )}

                {/* Cross-check CV ↔ Entretien */}
                {report.cross_check && (report.cross_check.ecarts?.length > 0 || report.cross_check.confirmes?.length > 0) && (
                  <div className="itb-xcheck">
                    <div className="itb-xcheck-title">🔍 Cross-check CV ↔ Entretien</div>
                    {report.cross_check.ecarts?.length > 0 && report.cross_check.ecarts.map((e, i) => (
                      <div key={`e${i}`} className="itb-xc-row itb-xc-gap">
                        <span className={`itb-xc-tag ${e.gravite === 'majeur' ? 'itb-xc-major' : 'itb-xc-minor'}`}>
                          {e.gravite === 'majeur' ? '⚠ Écart majeur' : 'Écart mineur'}
                        </span>
                        <span><strong>{e.element_cv}</strong> → {e.constat_entretien}</span>
                      </div>
                    ))}
                    {report.cross_check.confirmes?.length > 0 && report.cross_check.confirmes.map((c, i) => (
                      <div key={`c${i}`} className="itb-xc-row itb-xc-ok">
                        <span className="itb-xc-tag itb-xc-conf">✓ Confirmé</span>
                        <span><strong>{c.element_cv}</strong> — {c.preuve_entretien}</span>
                      </div>
                    ))}
                    {report.cross_check.non_aborde?.length > 0 && (
                      <div className="itb-xc-na">Non vérifié : {report.cross_check.non_aborde.join(', ')}</div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="itb-gen-box">
                <p>{answeredCount} réponse{answeredCount > 1 ? 's' : ''} sur {data.questions.length}.
                   {answeredCount === 0 ? ' Le candidat n\'a pas encore répondu.' : ' Générez le rapport d\'évaluation IA.'}</p>
                {answeredCount > 0 && (
                  <button className="itb-gen-btn" onClick={generateReport} disabled={genLoading}>
                    {genLoading ? 'Analyse en cours…' : '📊 Générer le rapport'}
                  </button>
                )}
              </div>
            )}

            {/* Réponses détaillées */}
            <h4 className="itb-qa-title">Réponses ({answeredCount}/{data.questions.length})</h4>
            <div className="itb-qa-list">
              {data.questions.map((q, i) => (
                <div key={q.id} className={`itb-qa ${q.answered ? '' : 'itb-qa-empty'}`}>
                  <div className="itb-qa-q">
                    <span className="itb-qa-phase">{PHASE[q.phase] || q.phase}</span>
                    <span className="itb-qa-num">Q{i + 1}</span>
                    {q.score != null && <span className="itb-qa-score">{Math.round(q.score * 100)}%</span>}
                    {q.cv_contradiction && <span className="itb-qa-flag">⚠ écart CV</span>}
                  </div>
                  <p className="itb-qa-text">{q.question}</p>
                  {q.answered
                    ? <p className="itb-qa-ans">{q.answer_text}</p>
                    : <p className="itb-qa-none">— Pas de réponse —</p>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
