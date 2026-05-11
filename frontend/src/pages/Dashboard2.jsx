import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip,
} from 'recharts'
import api from '../services/api'
import './Dashboard2.css'

const RADAR_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

const ALERT_STYLES = {
  warning: { bg: '#fef3c7', border: '#f59e0b', icon: '⚠️' },
  info:    { bg: '#eff6ff', border: '#3b82f6', icon: 'ℹ️' },
  error:   { bg: '#fef2f2', border: '#ef4444', icon: '🔴' },
}

function extractSkills(parsedData) {
  if (!parsedData) return []
  const comps = parsedData.competences || []
  return comps
    .map(c => (typeof c === 'string' ? c : c.name || c.valeur || ''))
    .filter(Boolean)
}

function computeOverlap(cvSkills, offerSkills) {
  if (!offerSkills.length) return 0
  let matched = 0
  for (const req of offerSkills) {
    const r = req.toLowerCase()
    if (cvSkills.some(cv => cv.toLowerCase().includes(r) || r.includes(cv.toLowerCase()))) {
      matched++
    }
  }
  return matched / offerSkills.length
}

function getMatchedSkills(cvSkills, offerSkills) {
  return offerSkills.filter(req => {
    const r = req.toLowerCase()
    return cvSkills.some(cv => cv.toLowerCase().includes(r) || r.includes(cv.toLowerCase()))
  })
}

function buildRadarData(results) {
  const top = (results?.results || []).slice(0, 5)
  if (!top.length) return []
  const dims = [
    { key: 'competences', label: 'Compétences' },
    { key: 'experience',  label: 'Expérience'  },
    { key: 'formation',   label: 'Formation'   },
    { key: 'semantique',  label: 'Sémantique'  },
  ]
  return dims.map(({ key, label }) => {
    const row = { subject: label }
    top.forEach((r, i) => { row[`c${i}`] = r.bert_details?.[key] ?? 0 })
    row.avg = Math.round(top.reduce((s, r) => s + (r.bert_details?.[key] ?? 0), 0) / top.length)
    return row
  })
}

export default function Dashboard2() {
  const navigate = useNavigate()

  const [offers, setOffers]               = useState([])
  const [stats, setStats]                 = useState(null)
  const [pageLoading, setPageLoading]     = useState(true)

  const [selectedOfferId, setSelectedOfferId] = useState('')
  const [radarResults, setRadarResults]   = useState(null)
  const [radarLoading, setRadarLoading]   = useState(false)
  const [radarError, setRadarError]       = useState(null)

  const [recommendations, setRecommendations] = useState([])
  const [recLoading, setRecLoading]       = useState(false)

  useEffect(() => {
    Promise.all([
      api.get('/offers'),
      api.get('/dashboard/stats'),
    ])
      .then(([offersRes, statsRes]) => {
        const fetchedOffers = offersRes.data.offers || []
        setOffers(fetchedOffers)
        setStats(statsRes.data)
        setPageLoading(false)
        loadRecommendations(fetchedOffers)
      })
      .catch(() => setPageLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedOfferId) { setRadarResults(null); return }
    setRadarLoading(true)
    setRadarError(null)
    api.post(`/match-sandbox/${selectedOfferId}?engine=bert`)
      .then(res => { setRadarResults(res.data); setRadarLoading(false) })
      .catch(e => { setRadarError(e.response?.data?.detail || 'Erreur matching BERT'); setRadarLoading(false) })
  }, [selectedOfferId])

  async function loadRecommendations(fetchedOffers) {
    setRecLoading(true)
    try {
      const candRes = await api.get('/candidates?limit=100')
      const allCands = candRes.data.candidates || []
      const refused  = allCands.filter(c => c.candidature_status === 'refuse').slice(0, 10)
      const active   = (fetchedOffers || offers).filter(o => o.status === 'active')

      if (!refused.length || !active.length) { setRecLoading(false); return }

      const withSkills = await Promise.all(
        refused.map(c =>
          api.get(`/candidates/${c.cv_id}`)
            .then(r => ({ ...c, skills: extractSkills(r.data.parsed_data) }))
            .catch(() => ({ ...c, skills: [] }))
        )
      )

      const recs = []
      for (const cand of withSkills) {
        if (!cand.skills.length) continue
        for (const offer of active) {
          const reqSkills = offer.competences_requises || []
          if (!reqSkills.length) continue
          if ((cand.offer_titles || []).includes(offer.titre)) continue
          const overlap = computeOverlap(cand.skills, reqSkills)
          if (overlap >= 0.45) {
            recs.push({
              candidate: cand,
              offer,
              score: Math.round(overlap * 100),
              matchedSkills: getMatchedSkills(cand.skills, reqSkills),
            })
          }
        }
      }
      recs.sort((a, b) => b.score - a.score)
      setRecommendations(recs.slice(0, 12))
    } catch { /* silent */ }
    setRecLoading(false)
  }

  if (pageLoading) {
    return (
      <div className="d2-page-load">
        <div className="d2-spinner" />
        Chargement Scoring avancé…
      </div>
    )
  }

  const radarData  = buildRadarData(radarResults)
  const topResults = (radarResults?.results || []).slice(0, 5)
  const alertes    = stats?.alertes || []

  return (
    <div className="d2-wrapper">

      {/* ── Header ─────────────────────────────────── */}
      <div className="d2-header">
        <div>
          <h1 className="d2-title">Scoring avancé</h1>
          <p className="d2-subtitle">
            Analyse sémantique multi-dimensionnelle — TalentMatch-BERT v1.3
          </p>
        </div>
        <button className="d2-btn-back" onClick={() => navigate('/dashboard')}>
          ← Dashboard
        </button>
      </div>

      {/* ── Top row: Radar + Alertes ──────────────── */}
      <div className="d2-top-row">

        {/* Radar Chart */}
        <div className="d2-card d2-radar-card">
          <div className="d2-card-header">
            <h2 className="d2-card-title">Radar BERT — Profil par offre</h2>
            <select
              className="d2-select"
              value={selectedOfferId}
              onChange={e => setSelectedOfferId(e.target.value)}
            >
              <option value="">Sélectionner une offre…</option>
              {offers.map(o => (
                <option key={o.id} value={o.id}>{o.titre}</option>
              ))}
            </select>
          </div>

          {!selectedOfferId ? (
            <div className="d2-empty">Choisissez une offre pour afficher le radar</div>
          ) : radarLoading ? (
            <div className="d2-loading-inner">
              <div className="d2-spinner" />
              Calcul des scores BERT…
            </div>
          ) : radarError ? (
            <div className="d2-error">{radarError}</div>
          ) : !radarData.length ? (
            <div className="d2-empty">Aucun candidat évalué pour cette offre</div>
          ) : (
            <>
              <div className="d2-chart-wrap">
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="subject" tick={{ fontSize: 13, fill: '#374151' }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10, fill: '#9ca3af' }} />
                    {topResults.map((r, i) => (
                      <Radar
                        key={r.candidate_id}
                        name={r.candidate_name || `Candidat ${i + 1}`}
                        dataKey={`c${i}`}
                        stroke={RADAR_COLORS[i % RADAR_COLORS.length]}
                        fill={RADAR_COLORS[i % RADAR_COLORS.length]}
                        fillOpacity={0.07}
                        strokeWidth={1.5}
                      />
                    ))}
                    <Radar
                      name="Moyenne"
                      dataKey="avg"
                      stroke="#1b4f8a"
                      fill="#1b4f8a"
                      fillOpacity={0.15}
                      strokeWidth={2.5}
                    />
                    <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
                    <Tooltip formatter={v => `${v}%`} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              <div className="d2-radar-table-wrap">
                <table className="d2-radar-table">
                  <thead>
                    <tr>
                      <th>Candidat</th>
                      <th>Score</th>
                      <th>Compét.</th>
                      <th>Exp.</th>
                      <th>Form.</th>
                      <th>Sém.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topResults.map((r, i) => (
                      <tr key={r.candidate_id}>
                        <td>
                          <span
                            className="d2-dot"
                            style={{ background: RADAR_COLORS[i % RADAR_COLORS.length] }}
                          />
                          {r.candidate_name || `Candidat ${i + 1}`}
                        </td>
                        <td><strong>{Math.round((r.bert_score ?? r.score ?? 0) * 100)}%</strong></td>
                        <td>{r.bert_details?.competences ?? '—'}{r.bert_details?.competences != null ? '%' : ''}</td>
                        <td>{r.bert_details?.experience  ?? '—'}{r.bert_details?.experience  != null ? '%' : ''}</td>
                        <td>{r.bert_details?.formation   ?? '—'}{r.bert_details?.formation   != null ? '%' : ''}</td>
                        <td>{r.bert_details?.semantique  ?? '—'}{r.bert_details?.semantique  != null ? '%' : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Alertes intelligentes */}
        <div className="d2-card d2-alerts-card">
          <div className="d2-card-header">
            <h2 className="d2-card-title">Alertes intelligentes</h2>
            <span className="d2-badge">{alertes.length}</span>
          </div>

          {!alertes.length ? (
            <div className="d2-empty d2-empty-ok">✓ Aucune alerte — tout est en ordre</div>
          ) : (
            <div className="d2-alerts-list">
              {alertes.map((a, i) => {
                const lvl = ALERT_STYLES[a.niveau] || ALERT_STYLES.info
                return (
                  <div
                    key={i}
                    className="d2-alert-item"
                    style={{ background: lvl.bg, borderLeftColor: lvl.border }}
                  >
                    <div className="d2-alert-top">
                      <span className="d2-alert-icon">{lvl.icon}</span>
                      <span className="d2-alert-msg">{a.message}</span>
                    </div>
                    {a.action && (
                      <button
                        className="d2-alert-action"
                        onClick={() => navigate(a.offer_id ? `/offers/${a.offer_id}` : '/candidates')}
                      >
                        {a.action} →
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {stats && (
            <div className="d2-stats-mini">
              <div className="d2-stats-row">
                <div className="d2-stat-item">
                  <div className="d2-stat-num">{stats.totaux?.candidats ?? 0}</div>
                  <div className="d2-stat-lbl">Candidats</div>
                </div>
                <div className="d2-stat-item">
                  <div className="d2-stat-num">{stats.totaux?.offres_actives ?? 0}</div>
                  <div className="d2-stat-lbl">Offres actives</div>
                </div>
                <div className="d2-stat-item">
                  <div className="d2-stat-num">
                    {stats.totaux?.taux_acceptation != null ? `${stats.totaux.taux_acceptation}%` : '—'}
                  </div>
                  <div className="d2-stat-lbl">Acceptation</div>
                </div>
                <div className="d2-stat-item">
                  <div className="d2-stat-num">
                    {stats.totaux?.score_moyen_global != null ? `${stats.totaux.score_moyen_global}%` : '—'}
                  </div>
                  <div className="d2-stat-lbl">Score moyen</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Recommandations ───────────────────────── */}
      <div className="d2-card d2-rec-card">
        <div className="d2-card-header">
          <h2 className="d2-card-title">Recommandations inter-offres</h2>
          <span className="d2-badge d2-badge-green">
            {recommendations.length} suggestion{recommendations.length !== 1 ? 's' : ''}
          </span>
        </div>
        <p className="d2-rec-desc">
          Candidats refusés détectés comme compatibles avec d'autres offres actives (overlap compétences ≥ 45 %).
        </p>

        {recLoading ? (
          <div className="d2-loading-inner">
            <div className="d2-spinner" />
            Analyse des profils refusés…
          </div>
        ) : !recommendations.length ? (
          <div className="d2-empty">
            Aucune suggestion — pas de candidats refusés compatibles avec d'autres offres actives.
          </div>
        ) : (
          <div className="d2-rec-grid">
            {recommendations.map((rec, i) => {
              const scoreColor = rec.score >= 70 ? '#10b981' : rec.score >= 55 ? '#f59e0b' : '#6b7280'
              return (
                <div key={i} className="d2-rec-item">
                  <div className="d2-rec-top">
                    <div className="d2-rec-score" style={{ color: scoreColor }}>
                      {rec.score}%
                    </div>
                    <div className="d2-rec-names">
                      <div className="d2-rec-cand">{rec.candidate.nom || rec.candidate.filename}</div>
                      <div className="d2-rec-arrow">→</div>
                      <div className="d2-rec-offer">{rec.offer.titre}</div>
                    </div>
                  </div>
                  {rec.matchedSkills.length > 0 && (
                    <div className="d2-rec-skills">
                      {rec.matchedSkills.slice(0, 4).map((s, j) => (
                        <span key={j} className="d2-skill-chip">{s}</span>
                      ))}
                      {rec.matchedSkills.length > 4 && (
                        <span className="d2-skill-more">+{rec.matchedSkills.length - 4}</span>
                      )}
                    </div>
                  )}
                  <div className="d2-rec-actions">
                    <button
                      className="d2-rec-btn"
                      onClick={() => navigate(`/candidates/${rec.candidate.cv_id}`)}
                    >
                      Voir profil
                    </button>
                    <button
                      className="d2-rec-btn d2-rec-btn-primary"
                      onClick={() => navigate(`/offers/${rec.offer.id}`)}
                    >
                      Voir offre
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
