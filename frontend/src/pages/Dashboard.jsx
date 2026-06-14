import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../services/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import './Dashboard.css'

const STATUS_LABEL = { en_attente: 'En attente', accepte: 'Accepté', refuse: 'Refusé' }
const STATUS_COLOR = { en_attente: '#F7941D', accepte: '#22c55e', refuse: '#ef4444' }
const ALERTE_COLOR = { warning: '#F7941D', info: '#2563eb', error: '#ef4444' }
const ALERTE_BG    = { warning: '#fffbeb', info: '#eff6ff', error: '#fef2f2' }
const ALERTE_ICON  = { warning: '⚠', info: 'ℹ', error: '✕' }

function KpiCard({ icon, label, value, sub, color, to }) {
  const inner = (
    <div className="dk-kpi" style={{ '--accent': color }}>
      <div className="dk-kpi-icon" style={{ background: color + '1a', color }}>{icon}</div>
      <div className="dk-kpi-body">
        <span className="dk-kpi-value">{value ?? '—'}</span>
        <span className="dk-kpi-label">{label}</span>
        {sub && <span className="dk-kpi-sub">{sub}</span>}
      </div>
    </div>
  )
  return to ? <Link to={to} className="dk-kpi-link">{inner}</Link> : inner
}

function ScoreBadge({ score }) {
  if (score == null) return <span className="dk-score-badge dk-score-na">—</span>
  const color = score >= 65 ? '#22c55e' : score >= 35 ? '#F7941D' : '#ef4444'
  return <span className="dk-score-badge" style={{ color, background: color + '18' }}>{score}%</span>
}

export default function Dashboard() {
  const { user }  = useAuth()
  const navigate  = useNavigate()
  const [stats, setStats]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const load = () => {
    setLoading(true)
    api.get('/dashboard/stats')
      .then(r => { setStats(r.data); setLoading(false) })
      .catch(e => { setError(e.response?.data?.detail || 'Erreur de chargement'); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="dk-loading"><div className="dk-spinner" /><span>Chargement…</span></div>
  )
  if (error) return <div className="dk-error">⚠ {error}</div>

  const t        = stats?.totaux ?? {}
  const a7       = stats?.activite_7j ?? {}
  const statuts  = stats?.candidatures_statuts ?? {}
  const dist     = stats?.score_distribution ?? {}
  const alertes  = stats?.alertes ?? []
  const pipeline = stats?.pipeline_offres ?? []
  const topCandidats  = stats?.top_candidats ?? []
  const recentCandidats = stats?.recents_candidats ?? []
  const isAdmin  = user?.role === 'admin'

  const totalScored = (dist.excellent ?? 0) + (dist.moyen ?? 0) + (dist.faible ?? 0)
  const scoreCoverage = t.matchings
    ? Math.round(((t.matchings_avec_score ?? 0) / t.matchings) * 100)
    : null

  return (
    <div className="dk-wrapper">

      {/* ══ Header ══════════════════════════════════════════ */}
      <div className="dk-header">
        <div>
          <h1 className="dk-title">Tableau de bord</h1>
          <p className="dk-sub">
            Bonjour <strong>{user?.prenom || user?.email}</strong> — état du recrutement en temps réel
          </p>
        </div>
        <div className="dk-header-actions">
          <button className="dk-btn-outline" onClick={load}>↻ Actualiser</button>
          <Link to="/offers/new" className="dk-btn-primary">+ Nouvelle offre</Link>
        </div>
      </div>

      {/* ══ KPIs ════════════════════════════════════════════ */}
      <div className="dk-kpi-grid">
        <KpiCard
          icon="📄" label="Candidats"
          value={t.candidats}
          sub={`${t.candidats_non_matchés ?? 0} sans évaluation`}
          color="#4f46e5" to="/candidates"
        />
        <KpiCard
          icon="💼" label="Offres actives"
          value={t.offres_actives}
          sub={`${t.offres_total ?? 0} au total`}
          color="#F7941D" to="/offers"
        />
        <KpiCard
          icon="🎯" label="Matchings"
          value={t.matchings}
          sub={scoreCoverage != null ? `${scoreCoverage}% avec score` : `${t.matchings_avec_score ?? 0} avec score`}
          color="#22c55e"
        />
        <KpiCard
          icon="⭐" label="Score moyen"
          value={t.score_moyen_global != null ? `${t.score_moyen_global}%` : '—'}
          sub="Tous les matchings scorés"
          color="#06b6d4"
        />
        {isAdmin && (
          <KpiCard
            icon="👤" label="Utilisateurs"
            value={t.utilisateurs}
            sub="sur la plateforme"
            color="#8b5cf6"
          />
        )}
      </div>

      {/* ══ Graphiques ══════════════════════════════════════════════ */}
      {(() => {
        const barData = pipeline
          .filter(o => o.nb_candidats > 0)
          .map(o => ({
            name: o.titre.length > 20 ? o.titre.slice(0, 20) + '…' : o.titre,
            Candidats: o.nb_candidats,
            Score: o.avg_score ?? 0,
          }))

        const pieData = [
          { name: 'Excellent ≥65%', value: dist.excellent ?? 0, color: '#22c55e' },
          { name: 'Moyen 35-65%',   value: dist.moyen ?? 0,     color: '#F7941D' },
          { name: 'Faible <35%',    value: dist.faible ?? 0,    color: '#ef4444' },
        ].filter(d => d.value > 0)

        const statusData = [
          { name: 'En attente', value: statuts.en_attente ?? 0, color: '#F7941D' },
          { name: 'Accepté',    value: statuts.accepte ?? 0,    color: '#22c55e' },
          { name: 'Refusé',     value: statuts.refuse ?? 0,     color: '#ef4444' },
        ].filter(d => d.value > 0)

        if (!barData.length && !pieData.length) return null
        return (
          <div className="dk-charts-row">
            {barData.length > 0 && (
              <div className="dk-card dk-chart-card">
                <div className="dk-card-head">
                  <span className="dk-card-title">📊 Candidats par offre</span>
                </div>
                <div className="dk-chart-body">
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={barData} margin={{ top: 8, right: 8, left: -24, bottom: 48 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }}
                        angle={-32} textAnchor="end" interval={0} />
                      <YAxis tick={{ fontSize: 11, fill: '#64748b' }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ border: 'none', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: 13 }}
                        formatter={(v) => [v, 'Candidats']}
                      />
                      <Bar dataKey="Candidats" fill="#4f46e5" radius={[6, 6, 0, 0]} maxBarSize={48} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {pieData.length > 0 && (
              <div className="dk-card dk-chart-card">
                <div className="dk-card-head">
                  <span className="dk-card-title">🎯 Qualité des scores</span>
                </div>
                <div className="dk-chart-body">
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie data={pieData} cx="50%" cy="50%" outerRadius={76} innerRadius={38}
                        dataKey="value" paddingAngle={3}
                        label={({ percent }) => `${Math.round(percent * 100)}%`}
                        labelLine={false}>
                        {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                      </Pie>
                      <Tooltip
                        contentStyle={{ border: 'none', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: 13 }}
                        formatter={(v, n) => [v + ' profil(s)', n]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="dk-pie-legend">
                    {pieData.map(d => (
                      <span key={d.name} className="dk-pie-leg-item">
                        <span className="dk-pie-dot" style={{ background: d.color }} />
                        {d.name}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {statusData.length > 0 && (
              <div className="dk-card dk-chart-card">
                <div className="dk-card-head">
                  <span className="dk-card-title">📋 Statuts candidatures</span>
                </div>
                <div className="dk-chart-body">
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={statusData} layout="vertical"
                      margin={{ top: 8, right: 24, left: 16, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} width={80} />
                      <Tooltip
                        contentStyle={{ border: 'none', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: 13 }}
                        formatter={(v) => [v, 'Candidats']}
                      />
                      <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={36}>
                        {statusData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  {t.taux_acceptation != null && (
                    <div className="dk-taux-chip">
                      Taux d'acceptation <strong>{t.taux_acceptation}%</strong>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )
      })()}

      {/* ══ Ligne principale : Pipeline (large) + Qualité (étroit) ══ */}
      <div className="dk-main-row">

        {/* ── Pipeline par offre ── */}
        <div className="dk-card dk-pipeline-card">
          <div className="dk-card-head">
            <span className="dk-card-title">📋 Pipeline par offre</span>
            <Link to="/offers" className="dk-link-more">Gérer les offres ›</Link>
          </div>
          <div className="dk-card-body">
            {pipeline.length === 0 ? (
              <div className="dk-empty-block">
                <span className="dk-empty-icon">📭</span>
                <p>Aucune offre créée pour le moment.</p>
                <Link to="/offers/new" className="dk-btn-primary" style={{ marginTop: 8 }}>
                  + Créer une offre
                </Link>
              </div>
            ) : (
              <table className="dk-table">
                <thead>
                  <tr>
                    <th>Offre</th>
                    <th>Contrat</th>
                    <th style={{ textAlign: 'center' }}>Candidats</th>
                    <th style={{ textAlign: 'center' }}>Meilleur score</th>
                    <th style={{ textAlign: 'center' }}>Score moy.</th>
                    <th style={{ textAlign: 'center' }}>Distribution</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pipeline.map(o => {
                    const tot = (o.distribution?.excellent ?? 0) + (o.distribution?.moyen ?? 0) + (o.distribution?.faible ?? 0)
                    return (
                      <tr key={o.id}>
                        <td className="dk-offer-name" title={o.titre}>{o.titre}</td>
                        <td>
                          {o.type_contrat
                            ? <span className="dk-contrat-badge">{o.type_contrat}</span>
                            : <span className="dk-na">—</span>
                          }
                        </td>
                        <td className="dk-center">
                          <span className="dk-count-badge">{o.nb_candidats}</span>
                        </td>
                        <td className="dk-center"><ScoreBadge score={o.best_score} /></td>
                        <td className="dk-center"><ScoreBadge score={o.avg_score} /></td>
                        <td className="dk-center">
                          {tot > 0 ? (
                            <div className="dk-mini-dist">
                              <span className="dk-mini-dist-seg" title="Excellent"
                                style={{ width: `${Math.round((o.distribution?.excellent ?? 0) / tot * 100)}%`, background: '#22c55e' }} />
                              <span className="dk-mini-dist-seg" title="Moyen"
                                style={{ width: `${Math.round((o.distribution?.moyen ?? 0) / tot * 100)}%`, background: '#F7941D' }} />
                              <span className="dk-mini-dist-seg" title="Faible"
                                style={{ width: `${Math.round((o.distribution?.faible ?? 0) / tot * 100)}%`, background: '#ef4444' }} />
                            </div>
                          ) : <span className="dk-na">—</span>}
                        </td>
                        <td>
                          <Link to={`/offers/${o.id}`} className="dk-table-action">Voir ›</Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ── Qualité des matchings ── */}
        <div className="dk-card dk-quality-card">
          <div className="dk-card-head">
            <span className="dk-card-title">✨ Qualité des matchings</span>
          </div>
          <div className="dk-card-body">

            {/* Distribution scores */}
            {totalScored === 0 ? (
              <div className="dk-empty-block">
                <span className="dk-empty-icon">📊</span>
                <p>Aucun score calculé.<br/>Lancez un matching depuis une offre.</p>
              </div>
            ) : (
              <>
                <div className="dk-dist-bars">
                  {[
                    { key: 'excellent', label: 'Excellent', color: '#22c55e', range: '≥ 65%' },
                    { key: 'moyen',     label: 'Moyen',     color: '#F7941D', range: '35–65%' },
                    { key: 'faible',    label: 'Faible',    color: '#ef4444', range: '< 35%' },
                  ].map(({ key, label, color, range }) => {
                    const val = dist[key] ?? 0
                    const pct = totalScored > 0 ? Math.round(val / totalScored * 100) : 0
                    return (
                      <div key={key} className="dk-dist-row">
                        <div className="dk-dist-meta">
                          <span className="dk-dist-dot" style={{ background: color }} />
                          <span className="dk-dist-label">{label}</span>
                          <span className="dk-dist-range">{range}</span>
                        </div>
                        <div className="dk-dist-bar-track">
                          <div className="dk-dist-bar-fill" style={{ width: `${pct}%`, background: color }} />
                        </div>
                        <span className="dk-dist-num" style={{ color }}>{val}</span>
                      </div>
                    )
                  })}
                </div>
                <div className="dk-dist-footer">
                  <span>{totalScored} profil(s) scoré(s)</span>
                  {t.score_moyen_global != null && (
                    <strong style={{ color: '#111827' }}>{t.score_moyen_global}% moy.</strong>
                  )}
                </div>
              </>
            )}

            {/* Décisions recruteur */}
            <div className="dk-decisions">
              <div className="dk-decisions-title">Décisions recruteur</div>
              {Object.entries(statuts).map(([k, v]) => (
                <div key={k} className="dk-decision-row">
                  <span className="dk-decision-dot" style={{ background: STATUS_COLOR[k] }} />
                  <span className="dk-decision-lbl">{STATUS_LABEL[k]}</span>
                  <span className="dk-decision-bar-wrap">
                    <span
                      className="dk-decision-bar"
                      style={{
                        width: t.candidats ? `${Math.round(v / t.candidats * 100)}%` : '0%',
                        background: STATUS_COLOR[k],
                      }}
                    />
                  </span>
                  <span className="dk-decision-val">{v}</span>
                </div>
              ))}
              {t.taux_acceptation != null && (
                <div className="dk-taux-row">
                  Taux d'acceptation : <strong>{t.taux_acceptation}%</strong>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ══ Ligne secondaire : Top profils + Activité récente ══ */}
      <div className="dk-secondary-row">

        {/* ── Meilleurs profils ── */}
        <div className="dk-card">
          <div className="dk-card-head">
            <span className="dk-card-title">🏆 Meilleurs profils</span>
            <Link to="/candidates" className="dk-link-more">Tous les candidats ›</Link>
          </div>
          <div className="dk-card-body">
            {topCandidats.length === 0 ? (
              <div className="dk-empty-block">
                <span className="dk-empty-icon">🎖</span>
                <p>Les meilleurs profils apparaîtront ici après le matching.</p>
              </div>
            ) : (
              <div className="dk-top-list">
                {topCandidats.map((c, i) => {
                  const rankColors = [
                    { bg: '#FFF3E0', color: '#F7941D' },
                    { bg: '#F5F5F5', color: '#9ca3af' },
                    { bg: '#FFF8E1', color: '#F59E0B' },
                  ]
                  const rc = rankColors[i] ?? { bg: '#f3f4f6', color: '#6b7280' }
                  return (
                    <div key={i} className="dk-top-row">
                      <span className="dk-top-rank" style={{ background: rc.bg, color: rc.color }}>
                        #{i + 1}
                      </span>
                      <div className="dk-avatar">
                        {(c.candidate_nom || '?')[0].toUpperCase()}
                      </div>
                      <div className="dk-top-info">
                        <span className="dk-top-name">{c.candidate_nom}</span>
                        <span className="dk-top-offer">{c.offer_titre}</span>
                      </div>
                      <div className="dk-top-right">
                        <ScoreBadge score={c.score} />
                        <Link to={`/offers/${c.offer_id}`} className="dk-mini-link">Voir ›</Link>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* ── Activité récente ── */}
        <div className="dk-card">
          <div className="dk-card-head">
            <span className="dk-card-title">🕐 Activité (7 derniers jours)</span>
            <Link to="/candidates" className="dk-link-more">Tous ›</Link>
          </div>
          <div className="dk-card-body">

            {/* Compteurs semaine */}
            <div className="dk-act-strip">
              <div className="dk-act-item">
                <span className="dk-act-val" style={{ color: '#4f46e5' }}>{a7.cvs ?? 0}</span>
                <span className="dk-act-lbl">CVs uploadés</span>
              </div>
              <div className="dk-act-sep" />
              <div className="dk-act-item">
                <span className="dk-act-val" style={{ color: '#22c55e' }}>{a7.matchings ?? 0}</span>
                <span className="dk-act-lbl">Matchings lancés</span>
              </div>
            </div>

            {/* Derniers candidats */}
            {recentCandidats.length === 0 ? (
              <p className="dk-empty" style={{ padding: '14px 0' }}>Aucun candidat récent.</p>
            ) : (
              <div className="dk-recent-list">
                {recentCandidats.map(c => (
                  <div key={c.cv_id} className="dk-recent-row">
                    <div className="dk-avatar">{(c.nom || '?')[0].toUpperCase()}</div>
                    <div className="dk-recent-info">
                      <span className="dk-recent-name">{c.nom || c.filename}</span>
                      <span className="dk-recent-date">
                        {c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : ''}
                      </span>
                    </div>
                    <span
                      className="dk-status-badge"
                      style={{
                        background: (STATUS_COLOR[c.status] ?? '#6b7280') + '18',
                        color: STATUS_COLOR[c.status] ?? '#6b7280',
                      }}
                    >
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
