import { useRef } from 'react'
import './MatchReport.css'

const DIMS = [
  { key: 'competences', label: 'Compétences', icon: '🎯', weight: '52%' },
  { key: 'formation',   label: 'Formation',   icon: '🎓', weight: '23%' },
  { key: 'experience',  label: 'Expérience',  icon: '📅', weight: '12%' },
  { key: 'semantique',  label: 'Sémantique',  icon: '🧠', weight: '13%' },
]

const MEDALS = ['🥇', '🥈', '🥉']

function scoreColor(pct) {
  if (pct >= 70) return '#16a34a'
  if (pct >= 45) return '#F7941D'
  return '#dc2626'
}

function scoreLabel(pct) {
  if (pct >= 75) return 'Excellent'
  if (pct >= 55) return 'Bon'
  if (pct >= 35) return 'Moyen'
  return 'Insuffisant'
}

function initials(name) {
  return (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

function LogoHeader() {
  return (
    <div className="mr-logo-block">
      <div className="mr-logo-text">3S</div>
      <div>
        <div className="mr-logo-title">TalentMatch</div>
        <div className="mr-logo-sub">Rapport de matching IA</div>
      </div>
    </div>
  )
}

export default function MatchReport({ offer, results, modelInfo, onClose }) {
  const reportRef = useRef(null)
  const now = new Date().toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })

  const sorted = [...(results || [])].sort((a, b) => (b.bert_score ?? 0) - (a.bert_score ?? 0))
  const nbPostes = offer?.nb_postes || 1
  const topScore = sorted.length > 0 ? Math.round((sorted[0].bert_score ?? 0) * 100) : 0
  const avgComp = sorted.length > 0
    ? Math.round(sorted.reduce((s, r) => s + (Number((r.bert_details || {}).competences) || 0), 0) / sorted.length)
    : 0

  const handlePrint = () => window.print()

  return (
    <div className="mr-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="mr-modal" ref={reportRef}>

        {/* ── Barre d'actions ── */}
        <div className="mr-actions no-print">
          <button className="mr-btn-print" onClick={handlePrint}>
            🖨 Exporter PDF
          </button>
          <button className="mr-btn-close" onClick={onClose}>✕ Fermer</button>
        </div>

        {/* ── En-tête ── */}
        <div className="mr-header">
          <LogoHeader />
          <div className="mr-header-center">
            <div className="mr-header-offer">{offer?.titre || '—'}</div>
            <div className="mr-header-tags">
              {offer?.type_contrat && <span className="mr-tag">{offer.type_contrat}</span>}
              {offer?.localisation && <span className="mr-tag">📍 {offer.localisation}</span>}
              <span className="mr-tag">{nbPostes} poste{nbPostes > 1 ? 's' : ''}</span>
            </div>
          </div>
          <div className="mr-header-meta">
            <div className="mr-meta-row"><span className="mr-meta-label">Modèle</span><span className="mr-meta-val">{modelInfo || 'TalentMatch-BERT'}</span></div>
            <div className="mr-meta-row"><span className="mr-meta-label">Généré le</span><span className="mr-meta-val">{now}</span></div>
            <div className="mr-meta-row"><span className="mr-meta-label">Candidats</span><span className="mr-meta-val">{sorted.length}</span></div>
          </div>
        </div>

        {/* ── Résumé exécutif ── */}
        <div className="mr-kpis no-print">
          <div className="mr-kpi">
            <div className="mr-kpi-num">{sorted.length}</div>
            <div className="mr-kpi-label">Candidats analysés</div>
          </div>
          <div className="mr-kpi mr-kpi--blue">
            <div className="mr-kpi-num">{topScore}%</div>
            <div className="mr-kpi-label">Meilleur score</div>
          </div>
          <div className="mr-kpi mr-kpi--green">
            <div className="mr-kpi-num">{nbPostes}</div>
            <div className="mr-kpi-label">Poste{nbPostes > 1 ? 's' : ''} à pourvoir</div>
          </div>
          <div className="mr-kpi mr-kpi--orange">
            <div className="mr-kpi-num">{avgComp}%</div>
            <div className="mr-kpi-label">Compétences moy.</div>
          </div>
        </div>

        {/* ── Tableau classement ── */}
        <section className="mr-section">
          <h2 className="mr-section-title">Classement final</h2>
          <table className="mr-table">
            <thead>
              <tr>
                <th>Rang</th>
                <th>Candidat</th>
                <th>Score</th>
                {DIMS.map(d => (
                  <th key={d.key}>{d.icon} {d.label}<span className="mr-th-weight">{d.weight}</span></th>
                ))}
                <th>Décision</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, idx) => {
                const pct = Math.round((r.bert_score ?? 0) * 100)
                const bd = r.bert_details || {}
                const retained = idx < nbPostes
                return (
                  <tr key={r.candidate_id} className={retained ? 'mr-row-retained' : ''}>
                    <td className="mr-rank">
                      {idx < 3 ? <span className="mr-medal">{MEDALS[idx]}</span> : `#${idx + 1}`}
                    </td>
                    <td className="mr-cand-cell">
                      <span className="mr-avatar" style={{ background: retained ? '#1B4F8A' : '#94a3b8' }}>
                        {initials(r.candidate_name)}
                      </span>
                      <div>
                        <div className="mr-cand-name">{r.candidate_name || '—'}</div>
                        <div className="mr-cand-email">{r.candidate_email || ''}</div>
                      </div>
                    </td>
                    <td>
                      <div className="mr-score-cell">
                        <div className="mr-score-bar-wrap">
                          <div className="mr-score-bar" style={{ width: `${pct}%`, background: scoreColor(pct) }} />
                        </div>
                        <span className="mr-score-pill" style={{ color: scoreColor(pct) }}>{pct}%</span>
                      </div>
                    </td>
                    {DIMS.map(d => {
                      const v = bd[d.key] != null ? Math.round(Number(bd[d.key])) : null
                      return (
                        <td key={d.key} className="mr-dim-cell">
                          {v != null ? (
                            <span style={{ color: scoreColor(v), fontWeight: 600 }}>{v}%</span>
                          ) : '—'}
                        </td>
                      )
                    })}
                    <td>
                      {retained
                        ? <span className="mr-badge mr-badge--ok">Recommandé</span>
                        : <span className="mr-badge mr-badge--no">Non retenu</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>

        {/* ── Analyse détaillée ── */}
        <section className="mr-section">
          <h2 className="mr-section-title">Analyse détaillée par candidat</h2>
          <div className="mr-cards">
            {sorted.map((r, idx) => {
              const pct = Math.round((r.bert_score ?? 0) * 100)
              const bd = r.bert_details || {}
              const retained = idx < nbPostes
              const incos = bd.inconsistencies || []
              const matched = bd.skills_matched || []
              const missing = bd.skills_missing || []
              const expYears = bd.candidate_years
              const reqYears = bd.required_years
              const candEdu = bd.candidate_edu
              const reqEdu = bd.required_edu

              const dimVals = DIMS.map(d => ({
                ...d,
                v: bd[d.key] != null ? Math.round(Number(bd[d.key])) : null,
              })).filter(d => d.v != null)

              const strengths = dimVals.filter(d => d.v >= 65).map(d => d.label)
              const weaknesses = dimVals.filter(d => d.v < 40).map(d => d.label)
              const explain = retained
                ? strengths.length > 0
                  ? `Profil recommandé — points forts en ${strengths.join(', ')}.`
                  : `Profil recommandé avec un score global de ${pct}%.`
                : weaknesses.length > 0
                  ? `Non retenu — axes d'amélioration : ${weaknesses.join(', ')}.`
                  : `Score global (${pct}%) insuffisant par rapport aux autres candidats.`

              return (
                <div key={r.candidate_id} className={`mr-card ${retained ? 'mr-card--retained' : ''}`}>

                  {/* Header candidat */}
                  <div className="mr-card-header">
                    <div className="mr-card-rank-medal">
                      {idx < 3 ? MEDALS[idx] : `#${idx + 1}`}
                    </div>
                    <span className="mr-avatar mr-avatar--lg" style={{ background: retained ? '#1B4F8A' : '#94a3b8' }}>
                      {initials(r.candidate_name)}
                    </span>
                    <div className="mr-card-name-block">
                      <div className="mr-card-name">{r.candidate_name || '—'}</div>
                      <div className="mr-card-email">{r.candidate_email || ''}</div>
                      <div className="mr-card-meta-inline">
                        {expYears != null && (
                          <span>📅 {expYears} an{expYears !== 1 ? 's' : ''}{reqYears > 0 ? ` / ${reqYears} requis` : ''}</span>
                        )}
                        {candEdu != null && (
                          <span>🎓 Bac+{candEdu}{reqEdu > 0 ? ` / Bac+${reqEdu} requis` : ''}</span>
                        )}
                      </div>
                    </div>
                    <div className="mr-card-score-big" style={{ color: scoreColor(pct) }}>
                      <span className="mr-score-num">{pct}%</span>
                      <span className="mr-score-qual">{scoreLabel(pct)}</span>
                    </div>
                    {retained
                      ? <span className="mr-badge mr-badge--ok">Recommandé</span>
                      : <span className="mr-badge mr-badge--no">Non retenu</span>}
                  </div>

                  <div className="mr-card-body">
                    <div className="mr-card-body-cols">

                      {/* Barres dimensions */}
                      <div className="mr-dims">
                        {dimVals.map(d => (
                          <div key={d.key} className="mr-dim-row">
                            <span className="mr-dim-icon">{d.icon}</span>
                            <span className="mr-dim-label">{d.label}</span>
                            <div className="mr-dim-bar-wrap">
                              <div className="mr-dim-bar" style={{ width: `${d.v}%`, background: scoreColor(d.v) }} />
                            </div>
                            <span className="mr-dim-pct" style={{ color: scoreColor(d.v) }}>{d.v}%</span>
                          </div>
                        ))}
                      </div>

                      {/* Skills matchées / manquantes */}
                      {(matched.length > 0 || missing.length > 0) && (
                        <div className="mr-skills-col">
                          {matched.length > 0 && (
                            <div className="mr-skills-block">
                              <div className="mr-skills-title mr-skills-title--ok">
                                Compétences présentes ({matched.length})
                              </div>
                              <div className="mr-chips">
                                {matched.map((m, i) => (
                                  <span key={i} className="mr-chip mr-chip--ok">
                                    {typeof m === 'object' ? m.skill : m}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          {missing.length > 0 && (
                            <div className="mr-skills-block">
                              <div className="mr-skills-title mr-skills-title--ko">
                                Compétences manquantes ({missing.length})
                              </div>
                              <div className="mr-chips">
                                {missing.map((s, i) => (
                                  <span key={i} className="mr-chip mr-chip--ko">
                                    {typeof s === 'object' ? s.skill : s}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Explication */}
                    <div className="mr-explain">
                      <span className="mr-explain-icon">{retained ? '💡' : '📋'}</span>
                      {explain}
                    </div>

                    {/* Incohérences */}
                    {incos.length > 0 && (
                      <div className="mr-incos">
                        <span className="mr-incos-title">Points d'attention ({incos.length})</span>
                        <ul className="mr-incos-list">
                          {incos.slice(0, 3).map((inc, i) => (
                            <li key={i}>
                              {typeof inc === 'string' ? inc : (inc.message || `${inc.skill} — ${inc.reason || ''}`)}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {/* ── Pied de page ── */}
        <div className="mr-footer">
          <span>3S Group — Rapport généré automatiquement par TalentMatch IA</span>
          <span>{now}</span>
        </div>

      </div>
    </div>
  )
}
