import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'
import InterviewPanel from '../components/InterviewPanel'
import InterviewsTab from '../components/InterviewsTab'
import AssessmentsTab from '../components/AssessmentsTab'
import AssessmentPanel from '../components/AssessmentPanel'
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

const FORMATION_LEVELS = [
  { niveau: null, value: '',     label: 'Non spécifié' },
  { niveau: 0,   value: 'Bac',   label: 'Bac (Bac+0)' },
  { niveau: 2,   value: 'Bac+2', label: 'Bac+2 (BTS, DUT)' },
  { niveau: 3,   value: 'Bac+3', label: 'Bac+3 (Licence)' },
  { niveau: 4,   value: 'Bac+4', label: 'Bac+4 (Master 1)' },
  { niveau: 5,   value: 'Bac+5', label: 'Bac+5 (Master, Ingénieur)' },
  { niveau: 8,   value: 'Bac+8', label: 'Bac+8 (Doctorat)' },
]
const niveauToLabel = (n) => FORMATION_LEVELS.find(f => f.niveau === n)?.label || '—'

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
      competences:     (offer.competences_requises  || []).join(', '),
      competences_apr: (offer.competences_appreciees || []).join(', '),
      localisation: offer.localisation || '',
      type_contrat: offer.type_contrat || '',
      nb_postes: offer.nb_postes ?? 1,
      formation_requise_niveau: offer.formation_requise_niveau ?? null,
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
      competences_appreciees: form.competences_apr
        ? form.competences_apr.split(',').map(s => s.trim()).filter(Boolean)
        : [],
      localisation: form.localisation || null,
      type_contrat: form.type_contrat || null,
      nb_postes: parseInt(form.nb_postes) || 1,
      formation_requise_niveau: form.formation_requise_niveau,
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
            <span className="info-label">Formation requise</span>
            <span className="info-value">{niveauToLabel(offer.formation_requise_niveau ?? null)}</span>
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
            <div className="info-label" style={{ marginBottom: 8 }}>
              Compétences obligatoires
              <span style={{ marginLeft: 6, fontSize: '0.72rem', color: '#ef4444', fontWeight: 500 }}>REQUISES</span>
            </div>
            <div className="chips">
              {offer.competences_requises.map((c, i) => <span key={i} className="chip chip-required">{c}</span>)}
            </div>
          </div>
        )}
        {offer.competences_appreciees?.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div className="info-label" style={{ marginBottom: 8 }}>
              Compétences appréciées
              <span style={{ marginLeft: 6, fontSize: '0.72rem', color: '#7c3aed', fontWeight: 500 }}>BONUS</span>
            </div>
            <div className="chips">
              {offer.competences_appreciees.map((c, i) => <span key={i} className="chip chip-appreciated">{c}</span>)}
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
                <select value={form.type_contrat} onChange={e => set('type_contrat', e.target.value)}>
                  <option value="">-- Choisir --</option>
                  {['CDI','CDD','Stage','Alternance','Freelance'].map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Nb de postes</label>
                <input type="number" min="1" max="20" value={form.nb_postes} onChange={e => set('nb_postes', e.target.value)} style={{ width: 80 }} />
              </div>
              <div className="form-group">
                <label>Formation requise</label>
                <select
                  value={form.formation_requise_niveau ?? ''}
                  onChange={e => {
                    const found = FORMATION_LEVELS.find(f => String(f.niveau) === e.target.value || (e.target.value === '' && f.niveau === null))
                    set('formation_requise_niveau', found ? found.niveau : null)
                  }}
                >
                  {FORMATION_LEVELS.map(f => (
                    <option key={f.value} value={f.niveau ?? ''}>{f.label}</option>
                  ))}
                </select>
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
                <label>Compétences obligatoires <span style={{color:'#9ca3af',fontWeight:400}}>(séparées par virgules)</span></label>
                <textarea value={form.competences} onChange={e => set('competences', e.target.value)} />
              </div>
              <div className="form-group form-full">
                <label>Compétences appréciées <span style={{color:'#9ca3af',fontWeight:400}}>(bonus, non bloquantes)</span></label>
                <textarea
                  value={form.competences_apr}
                  onChange={e => set('competences_apr', e.target.value)}
                  style={{ borderColor: '#a78bfa' }}
                />
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
// Onglet 3 — Matching TalentMatch-BERT
// ─────────────────────────────────────────────
function verdictFromScore(pct) {
  if (pct >= 70) return { label: 'Profil recommandé',  color: '#16a34a', bg: '#f0fdf4' }
  if (pct >= 45) return { label: 'Profil à étudier',   color: '#d97706', bg: '#fffbeb' }
  return              { label: 'Profil insuffisant',   color: '#dc2626', bg: '#fef2f2' }
}

function dimLabel(val) {
  if (val >= 65) return { text: 'Fort',   color: '#16a34a' }
  if (val >= 35) return { text: 'Moyen',  color: '#d97706' }
  return              { text: 'Faible',  color: '#dc2626' }
}

function TabMatching({ offerId, offer }) {
  const nbPostes = offer?.nb_postes ?? 1
  const [results, setResults]         = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [selected, setSelected]       = useState([])
  const [selecting, setSelecting]     = useState(false)
  const [selectResult, setSelectResult] = useState(null)
  const [aiSummaries, setAiSummaries]   = useState({})
  const [cvLoading,   setCvLoading]     = useState({})
  const [interviewFor, setInterviewFor] = useState(null)   // {id, name} ou null
  const [assessmentFor, setAssessmentFor] = useState(null) // {id, name} ou null

  const viewCV = async (cvId, candidateName) => {
    setCvLoading(prev => ({ ...prev, [cvId]: true }))
    try {
      const res = await api.get(`/candidates/${cvId}/original`, {
        responseType: 'blob',
        timeout: 15000,
      })
      const mime = res.headers['content-type'] || 'application/pdf'
      const blob = new Blob([res.data], { type: mime })
      const url  = URL.createObjectURL(blob)
      window.open(url, '_blank')
    } catch (e) {
      const status = e?.response?.status
      if (status === 404) {
        alert(`Fichier CV non disponible pour ${candidateName} (candidat inséré sans fichier).`)
      } else {
        alert(`Impossible d'ouvrir le CV de ${candidateName}.`)
      }
    } finally {
      setCvLoading(prev => ({ ...prev, [cvId]: false }))
    }
  }

  const generateAI = async (r) => {
    const id = r.candidate_id
    setAiSummaries(prev => ({ ...prev, [id]: { loading: true } }))
    try {
      const res = await api.post('/summarize', {
        candidate_id: id,
        offer_id: offerId,
        bert_score: r.bert_score ?? 0,
        bert_details: r.bert_details || {},
      }, { timeout: 90000 })
      setAiSummaries(prev => ({ ...prev, [id]: { loading: false, ...res.data } }))
    } catch {
      setAiSummaries(prev => ({ ...prev, [id]: { loading: false, error: 'Erreur de génération.' } }))
    }
  }

  const toggleSelect = (cvId) => {
    // Sélection libre (plusieurs candidats pour les entretiens, pas de limite)
    setSelected(prev =>
      prev.includes(cvId) ? prev.filter(id => id !== cvId) : [...prev, cvId]
    )
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
    setResults(null)
    api.post(`/match-sandbox/${offerId}?engine=bert`, null, { timeout: 180000 })
      .then(res => setResults(res.data))
      .catch(err => setError(err?.response?.data?.detail || err?.message || "Erreur lors du matching."))
      .finally(() => setLoading(false))
  }

  return (
    <div>
      {/* Panneau Entretien IA (un ou plusieurs candidats) */}
      {interviewFor && (
        <InterviewPanel
          candidates={interviewFor}
          offerId={offerId}
          onClose={() => setInterviewFor(null)}
        />
      )}

      {/* Panneau Évaluation technique (Reality Gap) */}
      {assessmentFor && (
        <AssessmentPanel
          candidateId={assessmentFor.id}
          offerId={offerId}
          candidateName={assessmentFor.name}
          onClose={() => setAssessmentFor(null)}
        />
      )}

      {/* ── Barre supérieure ── */}
      <div className="matching-top">
        <div>
          {results && (
            <>
              <span className="matching-meta">{results.total} candidat(s) analysé(s)</span>
              {' · '}
              <span className={`model-badge ${results.model_ready ? '' : 'unavailable'}`}>
                {results.model_ready ? (results.model_version || 'TalentMatch-BERT') : 'Modèle indisponible'}
              </span>
            </>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-primary" onClick={runMatching} disabled={loading}>
            {loading ? 'Analyse en cours…' : results ? 'Relancer le matching' : 'Lancer le Matching'}
          </button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      {!results && !loading && (
        <div className="empty-state" style={{ paddingTop: 48 }}>
          Cliquez sur "Lancer le Matching" pour analyser les candidats avec TalentMatch-BERT.
        </div>
      )}

      {loading && (
        <div className="empty-state" style={{ paddingTop: 48 }}>
          Analyse TalentMatch-BERT en cours… (30–60s)
        </div>
      )}

      {results && results.results?.length === 0 && (
        <div className="empty-state">Aucun candidat n'a postulé à cette offre.</div>
      )}

      {results && results.results?.length > 0 && (
        <div className="tm-panel" style={{ marginTop: 16 }}>
          {/* ── Barre de sélection pour entretiens ── */}
          <div className="tm-select-bar">
            <div className="tm-select-info">
              <span className="tm-select-title">🎙 Entretiens IA</span>
              <span className="tm-select-count" style={{ color: selected.length ? '#16a34a' : '#94a3b8' }}>
                {selected.length} candidat(s) sélectionné(s)
              </span>
            </div>
            <div className="tm-select-hint">Cochez les candidats à convier à l'entretien</div>
            {/* Lancer les entretiens des candidats sélectionnés */}
            <button
              className="tm-select-btn"
              disabled={selected.length === 0}
              style={{ background: '#4338ca' }}
              onClick={() => {
                const list = selected
                  .map(cvId => results.results.find(r => r.cv_id === cvId))
                  .filter(Boolean)
                  .map(r => ({ id: r.candidate_id, name: r.candidate_name }))
                if (list.length) setInterviewFor(list)
              }}
            >
              🎙 Lancer les entretiens ({selected.length})
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

          {/* ── Cartes candidats ── */}
          <div className="tm-cards">
            {results.results.map((r, idx) => {
              const score     = r.bert_score ?? 0
              const pct       = Math.round(score * 100)
              const bd        = r.bert_details || {}
              const inco      = r.bert?.inconsistencies ?? r.inconsistencies ?? []
              const verdict   = verdictFromScore(pct)
              const initials  = (r.candidate_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
              const circumference = 2 * Math.PI * 28
              const offset        = circumference * (1 - score)

              const dims = [
                { label: 'Compétences', val: bd.competences, icon: '🎯' },
                { label: 'Expérience',  val: bd.experience,  icon: '📅' },
                { label: 'Formation',   val: bd.formation,   icon: '🎓' },
                { label: 'Sémantique',  val: bd.semantique,  icon: '🧠' },
              ].filter(d => d.val != null)

              return (
                <div key={r.candidate_id} className={`tm-card ${idx === 0 ? 'tm-card-top' : ''} ${selected.includes(r.cv_id) ? 'tm-card-selected' : ''}`}>
                  {idx === 0 && <div className="tm-card-crown">&#128081; Meilleur match</div>}

                  <label className="tm-card-checkbox">
                    <input
                      type="checkbox"
                      checked={selected.includes(r.cv_id)}
                      onChange={() => toggleSelect(r.cv_id)}
                    />
                    <span>{selected.includes(r.cv_id) ? 'Sélectionné' : 'Sélectionner'}</span>
                  </label>

                  {/* ── Ligne principale ── */}
                  <div className="tm-card-main">
                    <div className="tm-card-rank">#{idx + 1}</div>
                    <div className="tm-avatar">{initials}</div>
                    <div className="tm-card-info">
                      <div className="tm-card-name">{r.candidate_name || '—'}</div>
                      <div className="tm-card-email">{r.candidate_email || ''}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                        {/* Verdict lisible */}
                        <span className="tm-verdict" style={{ color: verdict.color, background: verdict.bg }}>
                          {verdict.label}
                        </span>
                        {/* Bouton Voir CV */}
                        {r.cv_id && (
                          <button
                            onClick={() => viewCV(r.cv_id, r.candidate_name)}
                            disabled={cvLoading[r.cv_id]}
                            style={{
                              display: 'inline-flex', alignItems: 'center', gap: 5,
                              background: cvLoading[r.cv_id] ? '#e2e8f0' : '#f0f9ff',
                              color: cvLoading[r.cv_id] ? '#94a3b8' : '#0369a1',
                              border: '1px solid #bae6fd',
                              borderRadius: 6, padding: '3px 10px',
                              fontSize: '0.78rem', fontWeight: 600,
                              cursor: cvLoading[r.cv_id] ? 'not-allowed' : 'pointer',
                              transition: 'all 0.15s',
                            }}
                          >
                            {cvLoading[r.cv_id] ? '⏳' : '📄'} Voir CV
                          </button>
                        )}
                        {/* Bouton Entretien IA */}
                        <button
                          onClick={() => setInterviewFor([{ id: r.candidate_id, name: r.candidate_name }])}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: 5,
                            background: '#eef2ff', color: '#4338ca',
                            border: '1px solid #c7d2fe',
                            borderRadius: 6, padding: '3px 10px',
                            fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
                          }}
                        >
                          🎙 Entretien IA
                        </button>
                        {/* Bouton Évaluation technique (Reality Gap) */}
                        <button
                          onClick={() => setAssessmentFor({ id: r.candidate_id, name: r.candidate_name })}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: 5,
                            background: '#f5f3ff', color: '#6d28d9',
                            border: '1px solid #ddd6fe',
                            borderRadius: 6, padding: '3px 10px',
                            fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
                          }}
                        >
                          🎯 Évaluation
                        </button>
                      </div>
                    </div>

                    {/* Score ring */}
                    <div className="tm-score-ring">
                      <svg width="72" height="72" viewBox="0 0 72 72">
                        <circle cx="36" cy="36" r="28" fill="none" stroke="#f1f5f9" strokeWidth="7"/>
                        <circle
                          cx="36" cy="36" r="28" fill="none"
                          stroke={verdict.color} strokeWidth="7"
                          strokeDasharray={circumference}
                          strokeDashoffset={offset}
                          strokeLinecap="round"
                          transform="rotate(-90 36 36)"
                          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
                        />
                      </svg>
                      <div className="tm-score-label" style={{ color: verdict.color }}>{pct}%</div>
                    </div>
                  </div>

                  {/* ── Dimensions ── */}
                  <div className="tm-dims">
                    {dims.map(d => {
                      const v   = Math.round(Number(d.val) || 0)
                      const lbl = dimLabel(v)
                      return (
                        <div key={d.label} className="tm-dim">
                          <span className="tm-dim-icon">{d.icon}</span>
                          <span className="tm-dim-label">{d.label}</span>
                          <div className="tm-dim-bar-wrap">
                            <div className="tm-dim-bar" style={{ width: `${v}%`, background: lbl.color }} />
                          </div>
                          <span className="tm-dim-tag" style={{ color: lbl.color }}>{lbl.text}</span>
                          <span className="tm-dim-val">{v}%</span>
                        </div>
                      )
                    })}
                  </div>

                  {/* ── Profil recherché — critères comparatifs ── */}
                  {(() => {
                    const criteres   = bd.criteres || {}
                    const obligat    = criteres.obligatoires || []
                    const apprecies  = criteres.apprecies    || []
                    const confidence = bd.confidence || null
                    const hasFakeExp = bd.has_fake_expert    || false
                    const incoAffect = bd.inco_penalty_pct   || 0

                    const srcLabel = (s) => {
                      if (!s) return ''
                      if (s === 'extrait')   return ' (CV)'
                      if (s === 'fuzzy')     return ' (alias)'
                      if (s === 'ecosystem') return ' (écosystème)'
                      if (s === 'texte_brut') return ' (texte)'
                      return ''
                    }

                    const incoReasonLabel = (r) => {
                      if (!r) return r
                      if (r === 'absent_from_text')        return 'Absent du texte brut'
                      if (r === 'absent_from_experiences') return 'Absent des expériences'
                      if (r === 'low_context_similarity')  return 'Contexte BERT trop faible'
                      if (r === 'fake_expert_detected')    return 'Niveau déclaré incompatible avec expériences'
                      if (r.startsWith('missing_ecosystem')) return `Écosystème manquant : ${r.split(':')[1]}`
                      return r
                    }

                    return (
                      <>
                        {/* Score de confiance */}
                        {confidence && (
                          <div className="tm-confidence" style={{
                            borderColor: confidence.niveau === 'HAUTE' ? '#86efac'
                                        : confidence.niveau === 'MOYENNE' ? '#fcd34d' : '#fca5a5',
                            background:  confidence.niveau === 'HAUTE' ? '#f0fdf4'
                                        : confidence.niveau === 'MOYENNE' ? '#fffbeb' : '#fef2f2',
                            color:       confidence.niveau === 'HAUTE' ? '#16a34a'
                                        : confidence.niveau === 'MOYENNE' ? '#d97706' : '#dc2626',
                          }}>
                            <span className="tm-conf-icon">
                              {confidence.niveau === 'HAUTE' ? '✓' : confidence.niveau === 'MOYENNE' ? '⚠' : '✗'}
                            </span>
                            <span><strong>{confidence.niveau}</strong> confiance — {confidence.message}</span>
                            {incoAffect > 0 && (
                              <span className="tm-conf-penalty"> (−{incoAffect.toFixed(0)}% pénalité)</span>
                            )}
                          </div>
                        )}

                        {/* Alerte faux expert */}
                        {hasFakeExp && (
                          <div className="tm-fake-expert-alert">
                            ⚠ Faux expert détecté — compétences déclarées non justifiées par les expériences. Score plafonné à 45%.
                          </div>
                        )}

                        {/* Critères obligatoires */}
                        {obligat.length > 0 && (
                          <div className="tm-criteres-section">
                            <div className="tm-criteres-title">Compétences obligatoires</div>
                            <div className="tm-criteres-grid">
                              {obligat.map((c, i) => (
                                <div key={i} className={`tm-critere ${c.matched ? 'matched' : 'missing'}`}>
                                  <span className="tm-critere-icon">{c.matched ? '✓' : '✗'}</span>
                                  <span className="tm-critere-skill">{c.skill}{srcLabel(c.source)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Critères appréciés */}
                        {apprecies.length > 0 && (
                          <div className="tm-criteres-section">
                            <div className="tm-criteres-title" style={{ color: '#7c3aed' }}>
                              Compétences appréciées
                              <span style={{ fontWeight: 400, fontSize: '0.72rem', marginLeft: 6 }}>(bonus si présentes)</span>
                            </div>
                            <div className="tm-criteres-grid">
                              {apprecies.map((c, i) => (
                                <div key={i} className={`tm-critere ${c.matched ? 'appreciated-match' : 'appreciated-miss'}`}>
                                  <span className="tm-critere-icon">{c.matched ? '✓' : '○'}</span>
                                  <span className="tm-critere-skill">{c.skill}{srcLabel(c.source)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Incohérences détaillées */}
                        {inco.length > 0 && (
                          <div className="tm-inco-section">
                            <div className="tm-inco-title">
                              ⚠ Alertes détectées ({inco.length})
                              {incoAffect > 0 && <span style={{ fontWeight: 400, marginLeft: 6 }}>→ −{incoAffect.toFixed(0)}% appliqué</span>}
                            </div>
                            <ul className="tm-inco-list">
                              {inco.map((inc, i) => (
                                <li key={i} style={{ color: inc.level >= 5 ? '#dc2626' : inc.level >= 4 ? '#ea580c' : '#92400e' }}>
                                  <strong>{inc.skill}</strong> — {incoReasonLabel(inc.reason)}
                                  <span style={{ marginLeft: 6, fontSize: '0.72rem', opacity: 0.7 }}>niv.{inc.level}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* ── Analyse IA ── */}
                        {(() => {
                          const ai = aiSummaries[r.candidate_id]
                          return (
                            <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #e2e8f0' }}>
                              {!ai ? (
                                <button
                                  onClick={() => generateAI(r)}
                                  style={{
                                    background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                                    color: '#fff', border: 'none', borderRadius: 8,
                                    padding: '8px 18px', fontSize: '0.85rem',
                                    fontWeight: 600, cursor: 'pointer',
                                  }}
                                >
                                  ✨ Analyse IA (Mistral)
                                </button>
                              ) : ai.loading ? (
                                <span style={{ color: '#6366f1', fontSize: '0.85rem', fontStyle: 'italic' }}>
                                  ⏳ Génération en cours…
                                </span>
                              ) : ai.error ? (
                                <span style={{ color: '#dc2626', fontSize: '0.82rem' }}>{ai.error}</span>
                              ) : (
                                <div style={{
                                  background: 'linear-gradient(135deg,#f5f3ff,#ede9fe)',
                                  border: '1px solid #c4b5fd', borderRadius: 10, padding: '12px 16px',
                                }}>
                                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#5b21b6', marginBottom: 6 }}>
                                    ✨ Analyse IA
                                    <span style={{
                                      background: '#ddd6fe', color: '#4c1d95', borderRadius: 20,
                                      padding: '2px 8px', fontSize: '0.7rem', marginLeft: 8,
                                    }}>
                                      {ai.source === 'ollama' ? 'Mistral local' : ai.source === 'claude' ? 'Claude IA' : 'Auto'}
                                    </span>
                                  </div>
                                  <p style={{ fontSize: '0.875rem', color: '#374151', lineHeight: 1.6, margin: '0 0 8px' }}>
                                    {ai.summary}
                                  </p>
                                  <button
                                    onClick={() => generateAI(r)}
                                    style={{
                                      background: 'none', border: '1px solid #a78bfa',
                                      color: '#6d28d9', borderRadius: 6, padding: '4px 10px',
                                      fontSize: '0.78rem', cursor: 'pointer',
                                    }}
                                  >↺ Régénérer</button>
                                </div>
                              )}
                            </div>
                          )
                        })()}
                      </>
                    )
                  })()}
                </div>
              )
            })}
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
        <button className={`tab-btn ${tab === 'interviews' ? 'active' : ''}`} onClick={() => setTab('interviews')}>
          🎙 Entretiens
        </button>
        <button className={`tab-btn ${tab === 'assessments' ? 'active' : ''}`} onClick={() => setTab('assessments')}>
          🎯 Évaluations
        </button>
      </div>

      {/* Contenu */}
      {tab === 'info'  && <TabInfo offer={offer} onUpdated={setOffer} onDeleted={() => {}} />}
      {tab === 'apps'  && <TabApplications offerId={id} />}
      {tab === 'match' && <TabMatching offerId={id} offer={offer} />}
      {tab === 'interviews' && <InterviewsTab offerId={id} />}
      {tab === 'assessments' && <AssessmentsTab offerId={id} />}
    </div>
  )
}
