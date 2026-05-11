import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'
import CandidateMatchCard from '../components/matching/CandidateMatchCard'
import './Offers.css'

// hook role
function useIsAdmin() {
  const { user } = useAuth()
  return user?.role === 'admin'
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────
const STATUS_LABEL = { active: 'Active', draft: 'Brouillon', closed: 'Clôturée' }
const STATUS_CLS   = { active: 'status-active', draft: 'status-draft', closed: 'status-closed' }
const APP_LABEL    = { pending: 'En attente', accepted: 'Accepté', rejected: 'Refusé' }
const APP_CLS      = { pending: 'badge-pending', accepted: 'badge-accepted', rejected: 'badge-rejected' }

function ScoreBar({ value, type = '' }) {
  return (
    <div className="score-cell">
      <div className="score-bar-bg">
        <div className={`score-bar-fill ${type}`} style={{ width: `${(value || 0) * 100}%` }} />
      </div>
      <span className="score-pct">{((value || 0) * 100).toFixed(1)}%</span>
    </div>
  )
}

function SkillsBreakdown({ items, title }) {
  if (!items?.length) return null
  return (
    <div className="skills-bd">
      <div className="skills-bd-title">{title}</div>
      {items.map((m, i) => {
        const ratio = m.ratio ?? m.calibrated ?? 0
        const matched = m.candidate || m.best_match
        const color = ratio >= 0.8 ? '#22c55e' : ratio >= 0.5 ? '#f59e0b' : '#ef4444'
        return (
          <div key={i} className="skill-row">
            <span className="sk-req">{m.required}</span>
            <span className="sk-arr">→</span>
            <span className="sk-cand">{matched || '∅'}</span>
            <div className="sk-bar-bg">
              <div className="sk-bar-fill" style={{ width: `${ratio * 100}%`, background: color }} />
            </div>
            <span className="sk-pct" style={{ color }}>
              {m.matched === false ? '✗' : `${(ratio * 100).toFixed(0)}%`}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function InconsistenciesList({ items }) {
  if (!items?.length) return null
  const reasonLabel = {
    absent_from_text: 'Absent du texte brut',
    absent_from_experiences: 'Absent des expériences',
    low_context_similarity: 'Contexte BERT trop éloigné',
  }
  return (
    <div className="inco-list-panel">
      <div className="inco-list-title">Incohérences détectées</div>
      {items.map((inc, i) => {
        const reason = inc.reason?.startsWith('missing_ecosystem')
          ? `Écosystème manquant : ${inc.reason.split(':')[1]}`
          : (reasonLabel[inc.reason] || inc.reason)
        return (
          <div key={i} className={`inco-row l${inc.level}`}>
            <span className="inco-sk">{inc.skill}</span>
            <span className="inco-rs">{reason}</span>
            <span className="inco-lv">niv.{inc.level}</span>
          </div>
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────
// Onglet 1 — Informations
// ─────────────────────────────────────────────
function TabInfo({ offer, onUpdated, onDeleted }) {
  const navigate  = useNavigate()
  const isAdmin   = useIsAdmin()
  const [editing, setEditing] = useState(false)
  const [form, setForm]       = useState({})
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(false)

  const startEdit = () => {
    setForm({
      titre: offer.titre || '',
      description: offer.description || '',
      competences: (offer.competences_requises || []).join(', '),
      localisation: offer.localisation || '',
      type_contrat: offer.type_contrat || '',
      nb_postes: offer.nb_postes ?? 1,
      status: offer.status || 'active',
    })
    setEditing(true)
  }

  const handleUpdate = (e) => {
    e.preventDefault()
    setLoading(true)
    api.patch(`/offers/${offer.id}`, {
      titre: form.titre,
      description: form.description,
      competences_requises: form.competences
        ? form.competences.split(',').map(s => s.trim()).filter(Boolean)
        : [],
      localisation: form.localisation || null,
      type_contrat: form.type_contrat || null,
      nb_postes: parseInt(form.nb_postes) || 1,
      status: form.status,
    })
      .then(res => { onUpdated(res.data); setEditing(false) })
      .catch(() => setError("Erreur lors de la modification."))
      .finally(() => setLoading(false))
  }

  const handleDelete = () => {
    if (!window.confirm('Supprimer cette offre définitivement ?')) return
    api.delete(`/offers/${offer.id}`)
      .then(() => { onDeleted(); navigate('/offers') })
      .catch(() => setError("Erreur lors de la suppression."))
  }

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {error && <div className="alert error">{error}</div>}

      <div className="info-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <h3>Informations générales</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-secondary" onClick={startEdit}>Modifier</button>
            {isAdmin && <button className="btn-danger" onClick={handleDelete}>Supprimer</button>}
          </div>
        </div>
        <div className="info-row">
          <div className="info-field">
            <span className="info-label">Statut</span>
            <span className={`status-badge ${STATUS_CLS[offer.status] || 'status-draft'}`}>
              {STATUS_LABEL[offer.status] || offer.status}
            </span>
          </div>
          <div className="info-field">
            <span className="info-label">Localisation</span>
            <span className="info-value">{offer.localisation || '—'}</span>
          </div>
          <div className="info-field">
            <span className="info-label">Contrat</span>
            <span className="info-value">{offer.type_contrat || '—'}</span>
          </div>
          <div className="info-field">
            <span className="info-label">Postes à pourvoir</span>
            <span className="info-value" style={{ fontWeight: 700, color: '#4f46e5' }}>
              {offer.nb_postes ?? 1} poste(s)
            </span>
          </div>
          <div className="info-field">
            <span className="info-label">Créée le</span>
            <span className="info-value">
              {offer.created_at ? new Date(offer.created_at).toLocaleDateString('fr-FR') : '—'}
            </span>
          </div>
        </div>
        {offer.description && (
          <>
            <div className="info-label" style={{ marginBottom: 6 }}>Description</div>
            <div className="info-desc">{offer.description}</div>
          </>
        )}
        {offer.competences_requises?.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div className="info-label" style={{ marginBottom: 8 }}>Compétences requises</div>
            <div className="chips">
              {offer.competences_requises.map((c, i) => <span key={i} className="chip">{c}</span>)}
            </div>
          </div>
        )}
      </div>

      {editing && (
        <div className="edit-form-inline">
          <h4>Modifier l'offre</h4>
          <form onSubmit={handleUpdate}>
            <div className="form-grid">
              <div className="form-group form-full">
                <label>Titre *</label>
                <input value={form.titre} onChange={e => set('titre', e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Localisation</label>
                <input value={form.localisation} onChange={e => set('localisation', e.target.value)} />
              </div>
              <div className="form-group">
                <label>Type de contrat</label>
                <input value={form.type_contrat} onChange={e => set('type_contrat', e.target.value)} />
              </div>
              <div className="form-group">
                <label>Nb de postes</label>
                <input type="number" min="1" max="20" value={form.nb_postes} onChange={e => set('nb_postes', e.target.value)} style={{ width: 80 }} />
              </div>
              <div className="form-group">
                <label>Statut</label>
                <select value={form.status} onChange={e => set('status', e.target.value)}>
                  <option value="active">Active</option>
                  <option value="draft">Brouillon</option>
                  <option value="closed">Clôturée</option>
                </select>
              </div>
              <div className="form-group form-full">
                <label>Description</label>
                <textarea value={form.description} onChange={e => set('description', e.target.value)} />
              </div>
              <div className="form-group form-full">
                <label>Compétences (séparées par virgules)</label>
                <textarea value={form.competences} onChange={e => set('competences', e.target.value)} />
              </div>
            </div>
            <div className="form-actions" style={{ marginTop: 16 }}>
              <button className="btn-primary" type="submit" disabled={loading}>
                {loading ? 'Sauvegarde…' : 'Enregistrer'}
              </button>
              <button className="btn-secondary" type="button" onClick={() => setEditing(false)}>Annuler</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────
// Onglet 2 — Candidatures
// ─────────────────────────────────────────────
function TabApplications({ offerId }) {
  const [apps, setApps]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    api.get(`/offers/${offerId}/applications`)
      .then(res => setApps(res.data.applications || []))
      .catch(() => setError("Impossible de charger les candidatures."))
      .finally(() => setLoading(false))
  }, [offerId])

  const updateStatus = (appId, status) => {
    api.patch(`/offers/${offerId}/applications/${appId}?status=${status}`)
      .then(() => setApps(prev => prev.map(a => a.id === appId ? { ...a, status } : a)))
      .catch(() => setError("Erreur lors de la mise à jour."))
  }

  if (loading) return <div className="loading">Chargement…</div>
  if (error)   return <div className="alert error">{error}</div>
  if (apps.length === 0) return <div className="empty-state">Aucune candidature pour cette offre.</div>

  return (
    <div className="applications-table-wrap">
      <table className="applications-table">
        <thead>
          <tr>
            <th>Candidat</th>
            <th>Date</th>
            <th>Statut</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {apps.map(app => {
            const initials = (app.candidate_name || 'C')
              .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
            return (
              <tr key={app.id}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div className="app-avatar">{initials}</div>
                    <div>
                      <div className="app-name">{app.candidate_name || 'Candidat'}</div>
                      <div className="app-email">{app.candidate_email || '—'}</div>
                    </div>
                  </div>
                </td>
                <td>
                  <div className="app-date">
                    {app.created_at ? new Date(app.created_at).toLocaleDateString('fr-FR') : '—'}
                  </div>
                </td>
                <td>
                  <span className={`status-badge ${APP_CLS[app.status] || 'badge-pending'}`}>
                    {APP_LABEL[app.status] || app.status}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    {app.cv_id && (
                      <Link className="btn-cv" to={`/candidates/${app.cv_id}`}>Voir CV</Link>
                    )}
                    <select
                      className="app-status-select"
                      value={app.status}
                      onChange={e => updateStatus(app.id, e.target.value)}
                    >
                      <option value="pending">En attente</option>
                      <option value="accepted">Accepter</option>
                      <option value="rejected">Refuser</option>
                    </select>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ─────────────────────────────────────────────
// Onglet 3 — Matching
// ─────────────────────────────────────────────
function TabMatching({ offerId, offer }) {
  const nbPostes = offer?.nb_postes ?? 1
  const [data, setData]           = useState(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [bertOnly, setBertOnly]   = useState(null)
  const [loadingBertOnly, setLoadingBertOnly] = useState(false)
  const [selected, setSelected]   = useState([])  // cv_ids sélectionnés
  const [selecting, setSelecting] = useState(false)
  const [selectResult, setSelectResult] = useState(null)

  const toggleSelect = (cvId) => {
    setSelected(prev => {
      if (prev.includes(cvId)) return prev.filter(id => id !== cvId)
      if (prev.length >= nbPostes) return prev  // limite atteinte
      return [...prev, cvId]
    })
    setSelectResult(null)
  }

  const confirmSelection = () => {
    if (selected.length === 0) return
    setSelecting(true)
    setError(null)
    api.post(`/offers/${offerId}/select`, { cv_ids: selected })
      .then(res => { setSelectResult(res.data); setSelected([]) })
      .catch(err => setError(err?.response?.data?.detail || "Erreur lors de la sélection."))
      .finally(() => setSelecting(false))
  }

  const runMatching = () => {
    setLoading(true)
    setError(null)
    api.post(`/match-sandbox/${offerId}?engine=compare_all`, null, { timeout: 180000 })
      .then(res => setData(res.data))
      .catch(err => setError(err?.response?.data?.detail || err?.message || "Erreur lors du matching."))
      .finally(() => setLoading(false))
  }

  const runMatchYoussef = () => {
    setLoadingBertOnly(true)
    setError(null)
    api.post(`/match-sandbox/${offerId}?engine=bert`, null, { timeout: 180000 })
      .then(res => setBertOnly(res.data))
      .catch(err => setError(err?.response?.data?.detail || err?.message || "Erreur MatchYoussef."))
      .finally(() => setLoadingBertOnly(false))
  }

  return (
    <div>
      <div className="matching-top">
        <div>
          {data && (
            <>
              <span className="matching-meta">{data.total} candidat(s) scoré(s)</span>
              {' · '}
              <span className={`model-badge ${data.model_ready ? '' : 'unavailable'}`}>
                {data.model_ready
                  ? (data.model_version || 'TalentMatch-BERT v1.0')
                  : 'BERT indisponible'}
              </span>
            </>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-primary" onClick={runMatching} disabled={loading}>
            {loading ? 'Calcul en cours…' : data ? 'Relancer le matching' : 'Lancer le Matching'}
          </button>
          <button className="btn-light" onClick={runMatchYoussef} disabled={loadingBertOnly}>
            {loadingBertOnly ? 'Calcul…' : 'MatchYoussef'}
          </button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      {!data && !loading && (
        <div className="empty-state" style={{ paddingTop: 48 }}>
          Cliquez sur "Lancer le Matching" pour comparer les candidats.
        </div>
      )}

      {loading && (
        <div className="empty-state" style={{ paddingTop: 48 }}>
          Calcul en cours… (peut prendre 30–60s)
        </div>
      )}

      {data && data.results?.length === 0 && (
        <div className="empty-state">Aucun candidat n'a postulé à cette offre.</div>
      )}

      {data && data.results?.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {data.results.map((r, idx) => (
            <CandidateMatchCard key={r.candidate_id} candidate={r} rank={idx + 1} />
          ))}
        </div>
      )}

      {bertOnly && (
        <div className="tm-panel" style={{ marginTop: 16 }}>
          <div className="tm-panel-header">
            <div className="tm-panel-brand">
              <span className="tm-panel-logo">&#9889;</span>
              <div>
                <div className="tm-panel-title">TalentMatch-BERT</div>
                <div className="tm-panel-sub">Scoring — modèle fine-tuné v1.3</div>
              </div>
            </div>
            <button className="tm-refresh-btn" onClick={runMatchYoussef}>
              Actualiser
            </button>
          </div>

          <div className="tm-summary-bar">
            <span className="tm-summary-count">{bertOnly.total} candidat(s) analysé(s)</span>
            <span className={`tm-model-badge ${bertOnly.model_ready ? 'tm-model-ok' : 'tm-model-err'}`}>
              {bertOnly.model_ready ? '● Modèle prêt' : '● Modèle indisponible'}
            </span>
          </div>

          {bertOnly.results?.length === 0 ? (
            <div className="tm-empty">Aucun candidat pour cette offre.</div>
          ) : (
            <>
            {/* ── Barre de sélection ── */}
            <div className="tm-select-bar">
              <div className="tm-select-info">
                <span className="tm-select-title">&#10003; Sélection finale</span>
                <span className="tm-select-count" style={{
                  color: selected.length === nbPostes ? '#22c55e' : '#F7941D'
                }}>
                  {selected.length} / {nbPostes} poste(s) sélectionné(s)
                </span>
              </div>
              <div className="tm-select-hint">
                Cochez les candidats retenus (max {nbPostes})
              </div>
              <button
                className="tm-select-btn"
                disabled={selected.length === 0 || selecting}
                onClick={confirmSelection}
              >
                {selecting ? 'Confirmation…' : `Confirmer la sélection (${selected.length})`}
              </button>
            </div>
            {selectResult && (
              <div className="tm-select-result" style={{
                background: selectResult.offer_closed ? '#f0fdf4' : '#eff6ff',
                borderColor: selectResult.offer_closed ? '#86efac' : '#bfdbfe',
                color: selectResult.offer_closed ? '#16a34a' : '#1d4ed8',
              }}>
                &#10003; {selectResult.message}
              </div>
            )}
            <div className="tm-cards">
              {bertOnly.results.map((r, idx) => {
                const score = r.bert_score ?? 0
                const pct   = Math.round(score * 100)
                const bd    = r.bert_details || {}
                const inco  = r.bert?.inconsistencies?.length ?? 0
                const scoreColor = pct >= 65 ? '#22c55e' : pct >= 40 ? '#F7941D' : '#ef4444'
                const initials   = (r.candidate_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
                const dims = [
                  { label: 'Compétences', val: bd.competences, icon: '🎯' },
                  { label: 'Expérience',  val: bd.experience,  icon: '📅' },
                  { label: 'Formation',   val: bd.formation,   icon: '🎓' },
                  { label: 'Sémantique',  val: bd.semantique,  icon: '🧠' },
                ]
                const circumference = 2 * Math.PI * 28
                const offset = circumference * (1 - score)
                return (
                  <div key={r.candidate_id} className={`tm-card ${idx === 0 ? 'tm-card-top' : ''} ${selected.includes(r.cv_id) ? 'tm-card-selected' : ''}`}>
                    {idx === 0 && <div className="tm-card-crown">&#128081; Meilleur match</div>}
                    <label className="tm-card-checkbox" title={selected.length >= nbPostes && !selected.includes(r.cv_id) ? `Limite de ${nbPostes} poste(s) atteinte` : ''}>
                      <input
                        type="checkbox"
                        checked={selected.includes(r.cv_id)}
                        disabled={selected.length >= nbPostes && !selected.includes(r.cv_id)}
                        onChange={() => toggleSelect(r.cv_id)}
                      />
                      <span>{selected.includes(r.cv_id) ? 'Sélectionné' : 'Sélectionner'}</span>
                    </label>
                    <div className="tm-card-main">
                      <div className="tm-card-rank">#{idx + 1}</div>
                      <div className="tm-avatar">{initials}</div>
                      <div className="tm-card-info">
                        <div className="tm-card-name">{r.candidate_name || '—'}</div>
                        <div className="tm-card-email">{r.candidate_email || ''}</div>
                      </div>
                      <div className="tm-score-ring">
                        <svg width="72" height="72" viewBox="0 0 72 72">
                          <circle cx="36" cy="36" r="28" fill="none" stroke="#f1f5f9" strokeWidth="7"/>
                          <circle
                            cx="36" cy="36" r="28" fill="none"
                            stroke={scoreColor} strokeWidth="7"
                            strokeDasharray={circumference}
                            strokeDashoffset={offset}
                            strokeLinecap="round"
                            transform="rotate(-90 36 36)"
                            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
                          />
                        </svg>
                        <div className="tm-score-label" style={{ color: scoreColor }}>{pct}%</div>
                      </div>
                      {inco > 0 && (
                        <span className={`inco-badge ${inco <= 2 ? 'inco-warn' : 'inco-bad'}`}>
                          &#9888; {inco}
                        </span>
                      )}
                    </div>
                    <div className="tm-dims">
                      {dims.map(d => d.val != null && (
                        <div key={d.label} className="tm-dim">
                          <span className="tm-dim-icon">{d.icon}</span>
                          <span className="tm-dim-label">{d.label}</span>
                          <div className="tm-dim-bar-wrap">
                            <div className="tm-dim-bar" style={{
                              width: `${Number(d.val) || 0}%`,
                              background: Number(d.val) >= 65 ? '#22c55e' : Number(d.val) >= 35 ? '#F7941D' : '#ef4444'
                            }} />
                          </div>
                          <span className="tm-dim-val">{Math.round(Number(d.val) || 0)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────
// Onglet 4 — Évaluation
// ─────────────────────────────────────────────
function TabEvaluation({ offerId }) {
  const [matchData, setMatchData]       = useState(null)
  const [loadingMatch, setLoadingMatch] = useState(false)
  const [annotations, setAnnotations]   = useState({})
  const [saving, setSaving]             = useState(false)
  const [metrics, setMetrics]           = useState(null)
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [error, setError]               = useState(null)
  const [success, setSuccess]           = useState(null)

  const loadCandidates = () => {
    setLoadingMatch(true)
    api.post(`/match-sandbox/${offerId}?engine=heuristic`, null, { timeout: 120000 })
      .then(res => setMatchData(res.data))
      .catch(err => setError(err?.response?.data?.detail || "Erreur chargement candidats."))
      .finally(() => setLoadingMatch(false))
  }

  const setNote = (candidateId, value) => {
    setAnnotations(prev => ({ ...prev, [candidateId]: value }))
  }

  const saveAnnotations = () => {
    const payload = annotations
    if (Object.keys(payload).length === 0) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    api.post(`/match-sandbox/${offerId}/annotate`, payload, { timeout: 15000 })
      .then(() => setSuccess(`${Object.keys(payload).length} annotation(s) sauvegardée(s).`))
      .catch(err => setError(err?.response?.data?.detail || "Erreur lors de la sauvegarde."))
      .finally(() => setSaving(false))
  }

  const computeMetrics = () => {
    setLoadingMetrics(true)
    setMetrics(null)
    setError(null)
    setSuccess(null)
    api.post(`/match-sandbox/${offerId}/evaluate`, null, { timeout: 120000 })
      .then(res => setMetrics(res.data))
      .catch(err => setError(err?.response?.data?.detail || "Erreur calcul métriques."))
      .finally(() => setLoadingMetrics(false))
  }

  return (
    <div>
      {error   && <div className="alert error">{error}</div>}
      {success && <div className="alert success">{success}</div>}

      <div className="eval-instructions">
        <strong>Comment évaluer ?</strong><br />
        1. Chargez les candidats → 2. Notez chaque candidat (0 = non pertinent, 1 = pertinent, 2 = très pertinent) → 3. Sauvegardez → 4. Calculez les métriques
      </div>

      {!matchData && (
        <div style={{ marginBottom: 16 }}>
          <button className="btn-primary" onClick={loadCandidates} disabled={loadingMatch}>
            {loadingMatch ? 'Chargement…' : 'Charger les candidats'}
          </button>
        </div>
      )}

      {matchData && matchData.results?.length === 0 && (
        <div className="empty-state">Aucun candidat n'a postulé à cette offre.</div>
      )}

      {matchData && matchData.results?.length > 0 && (
        <>
          <div className="eval-table-wrap">
            <table className="eval-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Candidat</th>
                  <th>Score système</th>
                  <th>Note manuelle (0 / 1 / 2)</th>
                </tr>
              </thead>
              <tbody>
                {matchData.results.map((r, idx) => (
                  <tr key={r.candidate_id}>
                    <td style={{ fontWeight: 700, color: '#4f46e5' }}>{idx + 1}</td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{r.candidate_name || '—'}</div>
                      <div style={{ fontSize: '0.78rem', color: '#6b7280' }}>{r.candidate_email || ''}</div>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: '#374151' }}>
                        {((r.score || 0) * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td>
                      <div className="note-btns">
                        {[0, 1, 2].map(v => (
                          <button
                            key={v}
                            className={`note-btn note-${v}${annotations[r.candidate_id] === v ? ' active' : ''}`}
                            onClick={() => setNote(r.candidate_id, v)}
                            title={v === 0 ? 'Non pertinent' : v === 1 ? 'Pertinent' : 'Très pertinent'}
                          >
                            {v}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="eval-actions">
            <button
              className="btn-secondary"
              onClick={saveAnnotations}
              disabled={saving || Object.keys(annotations).length === 0}
            >
              {saving ? 'Sauvegarde…' : 'Sauvegarder les annotations'}
            </button>
            <button
              className="btn-primary"
              onClick={computeMetrics}
              disabled={loadingMetrics}
            >
              {loadingMetrics ? 'Calcul…' : 'Calculer les métriques'}
            </button>
          </div>
        </>
      )}

      {metrics && (
        <div className="metrics-panel">
          <div className="metrics-panel-title">
            Résultats d'évaluation — <em>{metrics.offer_title}</em>
          </div>
          <div className="metrics-grid">
            {Object.entries(metrics.metrics?.precision || {}).map(([k, v]) => (
              <div key={k} className="metric-card">
                <div className="metric-name">{k}</div>
                <div className="metric-val">{(v * 100).toFixed(1)}%</div>
              </div>
            ))}
            {Object.entries(metrics.metrics?.ndcg || {}).map(([k, v]) => (
              <div key={k} className="metric-card">
                <div className="metric-name">{k}</div>
                <div className="metric-val">{(v * 100).toFixed(1)}%</div>
              </div>
            ))}
            <div className="metric-card mrr">
              <div className="metric-name">MRR</div>
              <div className="metric-val">{((metrics.metrics?.mrr || 0) * 100).toFixed(1)}%</div>
            </div>
          </div>

          <div className="metrics-ranking-title">Classement détaillé :</div>
          <table className="ranking-table">
            <thead>
              <tr><th>#</th><th>Candidat</th><th>Score hybride</th><th>Pertinence annotée</th></tr>
            </thead>
            <tbody>
              {(metrics.metrics?.ranking || []).map(row => (
                <tr key={row.rank}>
                  <td style={{ fontWeight: 700 }}>{row.rank}</td>
                  <td>{row.name}</td>
                  <td style={{ fontWeight: 700 }}>{(row.hybrid * 100).toFixed(1)}%</td>
                  <td>
                    <span className={`rel-badge rel-${row.relevance}`}>
                      {row.relevance === 2 ? 'Très pertinent' : row.relevance === 1 ? 'Pertinent' : 'Non pertinent'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="metrics-footer">
            {metrics.metrics?.annotated_count} candidat(s) annoté(s) ·{' '}
            {metrics.metrics?.relevant_count} pertinent(s)
          </div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────
// Page principale — OfferDetail
// ─────────────────────────────────────────────
export default function OfferDetail() {
  const { id } = useParams()
  const [offer, setOffer]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [tab, setTab]       = useState('info')
  const [appCount, setAppCount] = useState(null)

  useEffect(() => {
    api.get('/offers')
      .then(res => {
        const found = (res.data.offers || []).find(o => o.id === id)
        if (found) setOffer(found)
        else setError("Offre introuvable.")
      })
      .catch(() => setError("Impossible de charger l'offre."))
      .finally(() => setLoading(false))

    api.get(`/offers/${id}/applications`)
      .then(res => setAppCount(res.data.total ?? res.data.applications?.length ?? 0))
      .catch(() => {})
  }, [id])

  if (loading) return <div className="page-wrapper"><div className="loading">Chargement…</div></div>
  if (error)   return <div className="page-wrapper"><div className="alert error">{error}</div></div>
  if (!offer)  return null

  return (
    <div className="page-wrapper">
      {/* Breadcrumb */}
      <div className="od-breadcrumb">
        <Link to="/offers" className="btn-back">← Offres</Link>
        <span className="od-bread-sep">/</span>
        <span className="od-bread-cur">{offer.titre}</span>
      </div>

      {/* Hero offre */}
      <div className="od-hero">
        <div className="od-hero-body">
          <div className="od-hero-badges">
            <span className={`status-badge ${STATUS_CLS[offer.status] || 'status-draft'}`}>
              {STATUS_LABEL[offer.status] || offer.status}
            </span>
            {offer.type_contrat && <span className="od-tag-contract">{offer.type_contrat}</span>}
            {offer.localisation && <span className="od-tag-loc">📍 {offer.localisation}</span>}
          </div>
          <h1 className="od-hero-title">{offer.titre}</h1>
          <div className="od-hero-meta">
            {offer.nb_postes > 1 && <span>{offer.nb_postes} postes</span>}
            {offer.created_at && <span>Créée le {new Date(offer.created_at).toLocaleDateString('fr-FR')}</span>}
            {appCount !== null && (
              <span className="od-cand-hint">
                <strong style={{ color: '#F7941D' }}>{appCount}</strong> candidature{appCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Onglets */}
      <div className="tabs">
        <button className={`tab-btn ${tab === 'info'  ? 'active' : ''}`} onClick={() => setTab('info')}>
          Informations
        </button>
        <button className={`tab-btn ${tab === 'apps'  ? 'active' : ''}`} onClick={() => setTab('apps')}>
          Candidatures
          {appCount !== null && appCount > 0 && <span className="tab-badge">{appCount}</span>}
        </button>
        <button className={`tab-btn ${tab === 'match' ? 'active' : ''}`} onClick={() => setTab('match')}>
          Matching
        </button>
        <button className={`tab-btn ${tab === 'eval'  ? 'active' : ''}`} onClick={() => setTab('eval')}>
          Évaluation
        </button>
      </div>

      {/* Contenu */}
      {tab === 'info'  && <TabInfo offer={offer} onUpdated={setOffer} onDeleted={() => {}} />}
      {tab === 'apps'  && <TabApplications offerId={id} />}
      {tab === 'match' && <TabMatching offerId={id} offer={offer} />}
      {tab === 'eval'  && <TabEvaluation offerId={id} />}
    </div>
  )
}
