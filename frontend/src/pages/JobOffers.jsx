import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'
import { MatchInsightPanel, MatchComparePanel } from '../components/matching/MatchInsightPanel'
import MatchReport from '../components/MatchReport'
import './JobOffers.css'

const COLORS_RADAR = ["#F7941D", "#1B4F8A", "#22a05a", "#9b59b6", "#e53935"]

function deadlineBadge(date_limite) {
  if (!date_limite) return null
  const dl = new Date(date_limite)
  const now = new Date()
  const daysLeft = Math.ceil((dl - now) / (1000 * 60 * 60 * 24))
  if (daysLeft < 0) return { label: 'Expirée', cls: 'dl-expired' }
  if (daysLeft <= 3) return { label: `⚠ J-${daysLeft}`, cls: 'dl-urgent' }
  if (daysLeft <= 7) return { label: `⏳ J-${daysLeft}`, cls: 'dl-soon' }
  return { label: `📅 ${dl.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}`, cls: 'dl-normal' }
}

function JobOffers() {
  const { user } = useAuth()
  const isAdmin = (user?.role ?? '').toString().trim().toLowerCase() === 'admin'

  const [offers, setOffers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState('')
  const [openOffer, setOpenOffer] = useState(null)
  const [applications, setApplications] = useState({})
  const [loadingApps, setLoadingApps] = useState(null)
  const [bertResults, setBertResults] = useState({})
  const [loadingBert, setLoadingBert] = useState(null)
  const [openBert, setOpenBert] = useState(null)
  const [bertOnlyResults, setBertOnlyResults] = useState({})
  const [loadingBertOnly, setLoadingBertOnly] = useState(null)
  const [openBertOnly, setOpenBertOnly] = useState(null)
  const [openDetail, setOpenDetail] = useState(null) // candidate_id dont le détail est ouvert
  // comparaison: { offerId: Set<candidateId> }
  const [compareSelected, setCompareSelected] = useState({})
  const toggleCompare = (offerId, candidateId) => {
    setCompareSelected(prev => {
      const set = new Set(prev[offerId] || [])
      set.has(candidateId) ? set.delete(candidateId) : set.add(candidateId)
      return { ...prev, [offerId]: set }
    })
  }

  // annotations: { offerId: { candidateId: 0|1|2 } }
  const [reportOffer, setReportOffer] = useState(null) // { offer, results, modelInfo }
  const [expandedBertCard, setExpandedBertCard] = useState({}) // candidateId → bool

  const [annotations, setAnnotations] = useState({})
  const [savingAnnotations, setSavingAnnotations] = useState(null)
  const [metrics, setMetrics] = useState({})
  const [loadingMetrics, setLoadingMetrics] = useState(null)

  // Assignation recruteurs (admin)
  const [allRecruiters, setAllRecruiters] = useState([])
  const [openAssign, setOpenAssign] = useState(null) // offerId ouvert
  const [savingAssign, setSavingAssign] = useState(null)

  useEffect(() => {
    if (isAdmin) {
      api.get('/admin/users?role=recruteur&limit=100')
        .then(res => setAllRecruiters(res.data.users || []))
        .catch(() => {})
    }
  }, [isAdmin])

  const saveAssign = (offerId, recruiterIds) => {
    setSavingAssign(offerId)
    api.put(`/offers/${offerId}/recruiters`, { recruiter_ids: recruiterIds })
      .then(() => {
        setOffers(prev => prev.map(o =>
          o.id === offerId ? { ...o, assigned_recruiter_ids: recruiterIds } : o
        ))
        setSuccess('Accès recruteurs mis à jour.')
      })
      .catch(() => setError('Erreur lors de la mise à jour des accès.'))
      .finally(() => setSavingAssign(null))
  }

  const [form, setForm] = useState({
    titre: '',
    description: '',
    competences: '',
    localisation: '',
    type_contrat: '',
    status: 'active',
    date_limite: '',
  })
  const [editingOffer, setEditingOffer] = useState(null)
  const [editForm, setEditForm] = useState({})

  const stats = useMemo(() => {
    const s = { total: offers.length, active: 0, draft: 0, closed: 0, candidates: 0 }
    offers.forEach(o => {
      if (o.status === 'active') s.active++
      else if (o.status === 'draft') s.draft++
      else if (o.status === 'closed') s.closed++
      s.candidates += o.candidate_count ?? 0
    })
    return s
  }, [offers])

  const fetchOffers = () => {
    setLoading(true)
    setError(null)
    setSuccess('')
    api.get('/offers')
      .then(res => setOffers(res.data.offers || []))
      .catch(() => setError("Impossible de charger les offres."))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchOffers()
  }, [])

  const handleCreate = (e) => {
    e.preventDefault()
    setSuccess('')
    const payload = {
      titre: form.titre,
      description: form.description,
      competences_requises: form.competences
        ? form.competences.split(',').map(s => s.trim()).filter(Boolean)
        : [],
      localisation: form.localisation || null,
      type_contrat: form.type_contrat || null,
      status: form.status || 'active',
      date_limite: form.date_limite ? new Date(form.date_limite).toISOString() : null,
    }
    api.post('/offers', payload)
      .then(() => {
        setForm({ titre: '', description: '', competences: '', localisation: '', type_contrat: '', status: 'active', date_limite: '' })
        fetchOffers()
        setSuccess("Offre créée avec succès.")
      })
      .catch(() => setError("Erreur lors de la création."))
  }

  const handleDelete = (id) => {
    if (!window.confirm('Supprimer cette offre ?')) return
    api.delete(`/offers/${id}`)
      .then(() => fetchOffers())
      .catch((err) => setError(err?.response?.data?.detail || "Erreur lors de la suppression."))
  }

  const handleStatus = (id, status) => {
    api.patch(`/offers/${id}`, { status })
      .then(() => fetchOffers())
      .catch(() => setError("Erreur lors de la mise à jour."))
  }

  const startEdit = (o) => {
    setEditingOffer(o.id)
    setEditForm({
      titre: o.titre || '',
      description: o.description || '',
      competences: (o.competences_requises || []).join(', '),
      localisation: o.localisation || '',
      type_contrat: o.type_contrat || '',
      status: o.status || 'active',
      date_limite: o.date_limite ? o.date_limite.slice(0, 10) : '',
    })
  }

  const cancelEdit = () => {
    setEditingOffer(null)
    setEditForm({})
  }

  const handleUpdate = (e, id) => {
    e.preventDefault()
    const payload = {
      titre: editForm.titre,
      description: editForm.description,
      competences_requises: editForm.competences
        ? editForm.competences.split(',').map(s => s.trim()).filter(Boolean)
        : [],
      localisation: editForm.localisation || null,
      type_contrat: editForm.type_contrat || null,
      status: editForm.status || 'active',
      date_limite: editForm.date_limite ? new Date(editForm.date_limite).toISOString() : null,
    }
    api.patch(`/offers/${id}`, payload)
      .then(() => {
        cancelEdit()
        fetchOffers()
        setSuccess("Offre mise à jour.")
      })
      .catch(() => setError("Erreur lors de la modification."))
  }

  const setAnnotation = (offerId, candidateId, value) => {
    setAnnotations(prev => ({
      ...prev,
      [offerId]: { ...(prev[offerId] || {}), [candidateId]: value },
    }))
  }

  const saveAnnotations = (offerId) => {
    const payload = annotations[offerId] || {}
    if (Object.keys(payload).length === 0) return
    setSavingAnnotations(offerId)
    api.post(`/match-sandbox/${offerId}/annotate`, payload)
      .then(() => setSuccess("Annotations sauvegardées."))
      .catch(() => setError("Erreur lors de la sauvegarde des annotations."))
      .finally(() => setSavingAnnotations(null))
  }

  const computeMetrics = (offerId) => {
    setLoadingMetrics(offerId)
    setMetrics(prev => ({ ...prev, [offerId]: null }))
    api.post(`/match-sandbox/${offerId}/evaluate`)
      .then(res => setMetrics(prev => ({ ...prev, [offerId]: res.data })))
      .catch(err => setError(err?.response?.data?.detail || "Erreur lors du calcul des métriques."))
      .finally(() => setLoadingMetrics(null))
  }

  const runBertMatching = (offerId, forceRefresh = false) => {
    if (openBert === offerId) {
      setOpenBert(null)
      return
    }
    setOpenBert(offerId)
    setOpenBertOnly(null)
    if (!forceRefresh && bertResults[offerId]) return
    setLoadingBert(offerId)
    api.post(`/match-sandbox/${offerId}?engine=compare_all`, null, { timeout: 180000 })
      .then(res => {
        setBertResults(prev => ({ ...prev, [offerId]: res.data }))
      })
      .catch(err => setError(err?.response?.data?.detail || err?.message || "Erreur lors du matching."))
      .finally(() => setLoadingBert(null))
  }

  const runMatchYoussef = (offerId, forceRefresh = false) => {
    if (openBertOnly === offerId) {
      setOpenBertOnly(null)
      return
    }
    setOpenBertOnly(offerId)
    setOpenBert(null)
    if (!forceRefresh && bertOnlyResults[offerId]) return
    setLoadingBertOnly(offerId)
    api.post(`/match-sandbox/${offerId}?engine=bert`, null, { timeout: 180000 })
      .then(res => {
        setBertOnlyResults(prev => ({ ...prev, [offerId]: res.data }))
      })
      .catch(err => setError(err?.response?.data?.detail || err?.message || "Erreur MatchYoussef."))
      .finally(() => setLoadingBertOnly(null))
  }

  const toggleApplications = (offerId) => {
    if (openOffer === offerId) {
      setOpenOffer(null)
      return
    }
    setOpenOffer(offerId)
    if (applications[offerId]) return
    setLoadingApps(offerId)
    api.get(`/offers/${offerId}/applications`)
      .then(res => {
        setApplications(prev => ({ ...prev, [offerId]: res.data.applications || [] }))
      })
      .catch(() => setError("Impossible de charger les candidatures."))
      .finally(() => setLoadingApps(null))
  }

  const updateApplicationStatus = (offerId, appId, status) => {
    api.patch(`/offers/${offerId}/applications/${appId}?status=${status}`)
      .then(() => {
        setApplications(prev => ({
          ...prev,
          [offerId]: (prev[offerId] || []).map(a => a.id === appId ? { ...a, status } : a)
        }))
      })
      .catch(() => setError("Erreur lors de la mise à jour du statut."))
  }

  return (
    <div className="offers-page">

      {/* ── Hero header ── */}
      <header className="offers-hero">
        <div className="offers-hero-left">
          <span className="offers-eyebrow">{isAdmin ? 'Backoffice' : 'Recruteur'}</span>
          <h1>Offres d'emploi</h1>
          <p>{isAdmin ? 'Créez, gérez et assignez vos offres aux recruteurs.' : 'Consultez et gérez vos offres assignées.'}</p>
        </div>
        <div className="offers-hero-stats">
          <div className="ohs-stat">
            <span className="ohs-num">{stats.total}</span>
            <span className="ohs-label">Total</span>
          </div>
          <div className="ohs-divider" />
          <div className="ohs-stat">
            <span className="ohs-num ohs-active">{stats.active}</span>
            <span className="ohs-label">Actives</span>
          </div>
          <div className="ohs-divider" />
          <div className="ohs-stat">
            <span className="ohs-num ohs-draft">{stats.draft}</span>
            <span className="ohs-label">Brouillons</span>
          </div>
          <div className="ohs-divider" />
          <div className="ohs-stat">
            <span className="ohs-num ohs-cand">{stats.candidates}</span>
            <span className="ohs-label">Candidatures</span>
          </div>
        </div>
      </header>

      {error && <div className="alert error">❌ {error}</div>}
      {success && <div className="alert success">✅ {success}</div>}

      {/* ── Formulaire création (admin only) ── */}
      {isAdmin && (
        <section className="offers-card offers-create-card">
          <div className="card-title-row">
            <h2>Nouvelle offre</h2>
            <span className="pill-badge">Admin uniquement</span>
          </div>
          <p className="card-subtitle">Remplissez les informations ci-dessous pour publier une offre.</p>
          <form className="offers-form-v2" onSubmit={handleCreate}>
            <div className="ofv2-row">
              <label className="ofv2-field ofv2-field--grow">
                <span>Titre du poste *</span>
                <input placeholder="Ex : Développeur Full Stack" value={form.titre} onChange={e => setForm(f => ({ ...f, titre: e.target.value }))} required />
              </label>
              <label className="ofv2-field">
                <span>Statut</span>
                <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                  <option value="active">Active</option>
                  <option value="draft">Brouillon</option>
                  <option value="closed">Clôturée</option>
                </select>
              </label>
            </div>
            <div className="ofv2-row">
              <label className="ofv2-field">
                <span>Localisation</span>
                <input placeholder="Ex : Tunis, Télétravail…" value={form.localisation} onChange={e => setForm(f => ({ ...f, localisation: e.target.value }))} />
              </label>
              <label className="ofv2-field">
                <span>Type de contrat</span>
                <input placeholder="CDI, CDD, Stage…" value={form.type_contrat} onChange={e => setForm(f => ({ ...f, type_contrat: e.target.value }))} />
              </label>
            </div>
            <label className="ofv2-field">
              <span>Description</span>
              <textarea rows={3} placeholder="Décrivez le poste, les missions, le contexte…" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </label>
            <div className="ofv2-row">
              <label className="ofv2-field ofv2-field--grow">
                <span>Compétences requises <small>(séparées par virgule)</small></span>
                <input placeholder="Python, React, SQL, Docker…" value={form.competences} onChange={e => setForm(f => ({ ...f, competences: e.target.value }))} />
              </label>
              <label className="ofv2-field">
                <span>Date limite de candidature</span>
                <input type="date" value={form.date_limite} onChange={e => setForm(f => ({ ...f, date_limite: e.target.value }))} />
              </label>
            </div>
            <button className="btn-primary" type="submit">+ Créer l'offre</button>
          </form>
        </section>
      )}

      <section className="offers-card">
        <div className="offers-section-header">
          <div>
            <h2>{isAdmin ? 'Toutes les offres' : 'Mes offres assignées'}</h2>
            <p className="offers-section-sub">{offers.length} offre{offers.length !== 1 ? 's' : ''} — triées par nombre de candidats</p>
          </div>
        </div>
        {loading ? (
          <div className="loading">⏳ Chargement...</div>
        ) : (
          <div className="offers-list">
            {offers.length === 0 ? (
              <div className="empty-state">Aucune offre pour le moment.</div>
            ) : (
              offers.map(o => {
                const statusCfg = {
                  active: { label: 'Active',     cls: 'os-active' },
                  draft:  { label: 'Brouillon',  cls: 'os-draft'  },
                  closed: { label: 'Clôturée',   cls: 'os-closed' },
                }[o.status] || { label: o.status, cls: '' }
                const cnt = o.candidate_count ?? 0
                const dl = deadlineBadge(o.date_limite)
                return (
                <div key={o.id} className="offer-card-v2">

                  {/* ── En-tête de la carte ── */}
                  <div className="oc2-head">
                    <div className="oc2-badges">
                      <span className={`oc2-status ${statusCfg.cls}`}>{statusCfg.label}</span>
                      {o.type_contrat && <span className="oc2-contract">{o.type_contrat}</span>}
                      {o.localisation && <span className="oc2-loc">📍 {o.localisation}</span>}
                      {dl && <span className={`oc2-deadline ${dl.cls}`}>{dl.label}</span>}
                    </div>
                    {/* Stat candidats toujours visible */}
                    <div className="oc2-stat-box">
                      <span className="oc2-stat-num">{cnt}</span>
                      <span className="oc2-stat-label">candidat{cnt !== 1 ? 's' : ''}</span>
                    </div>
                  </div>

                  {/* ── Titre ── */}
                  <h3 className="oc2-title">{o.titre}</h3>

                  {/* ── Compétences ── */}
                  {o.competences_requises?.length > 0 && (
                    <div className="oc2-chips">
                      {o.competences_requises.slice(0, 6).map((c, i) => (
                        <span key={i} className="oc2-chip">{c}</span>
                      ))}
                      {o.competences_requises.length > 6 && (
                        <span className="oc2-chip oc2-chip--more">+{o.competences_requises.length - 6}</span>
                      )}
                    </div>
                  )}

                  {isAdmin && o.assigned_recruiter_ids?.length > 0 && (
                    <p className="oc2-assigned">🔑 {o.assigned_recruiter_ids.length} recruteur{o.assigned_recruiter_ids.length > 1 ? 's' : ''} assigné{o.assigned_recruiter_ids.length > 1 ? 's' : ''}</p>
                  )}

                  {/* ── Actions ── */}
                  <div className="oc2-actions">
                    {/* Groupe 1 : candidatures + matching */}
                    <div className="oc2-action-group">
                      <button className="oc2-btn oc2-btn--primary" onClick={() => toggleApplications(o.id)}>
                        👥 Candidatures {cnt > 0 && <span className="oc2-btn-badge">{cnt}</span>}
                      </button>
                      <button className="oc2-btn oc2-btn--blue" onClick={() => runBertMatching(o.id)}>
                        📊 Matching
                      </button>
                      <button className="oc2-btn oc2-btn--orange" onClick={() => runMatchYoussef(o.id)}>
                        ⚡ TalentMatch
                      </button>
                    </div>

                    {/* Groupe 2 : administration */}
                    <div className="oc2-action-group">
                      {isAdmin && (
                        <select className="oc2-status-sel" value={o.status} onChange={e => handleStatus(o.id, e.target.value)}>
                          <option value="active">Active</option>
                          <option value="draft">Brouillon</option>
                          <option value="closed">Clôturée</option>
                        </select>
                      )}
                      <button className="oc2-btn oc2-btn--ghost" onClick={() => editingOffer === o.id ? cancelEdit() : startEdit(o)}>
                        ✏️ {editingOffer === o.id ? 'Annuler' : 'Modifier'}
                      </button>
                      {isAdmin && (
                        <>
                          <button className="oc2-btn oc2-btn--assign" onClick={() => setOpenAssign(openAssign === o.id ? null : o.id)}>
                            🔑 Accès
                          </button>
                          <button className="oc2-btn oc2-btn--danger" onClick={() => handleDelete(o.id)}>
                            🗑
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Panneau assignation recruteurs (admin) */}
                  {isAdmin && openAssign === o.id && (
                    <div className="assign-panel">
                      <div className="assign-title">Recruteurs ayant accès à cette offre</div>
                      <div className="assign-list">
                        {allRecruiters.length === 0 && <p className="muted">Aucun recruteur enregistré.</p>}
                        {allRecruiters.map(r => {
                          const checked = (o.assigned_recruiter_ids || []).includes(r.id)
                          const toggle = () => {
                            const current = o.assigned_recruiter_ids || []
                            const next = checked ? current.filter(id => id !== r.id) : [...current, r.id]
                            saveAssign(o.id, next)
                          }
                          return (
                            <label key={r.id} className="assign-item">
                              <input type="checkbox" checked={checked} onChange={toggle} />
                              <span>{r.prenom} {r.nom}</span>
                              <span className="assign-email">{r.email}</span>
                            </label>
                          )
                        })}
                      </div>
                      {savingAssign === o.id && <p className="assign-saving">Sauvegarde…</p>}
                    </div>
                  )}

                  {editingOffer === o.id && (
                    <form className="offers-form edit-form" onSubmit={e => handleUpdate(e, o.id)}>
                      <input placeholder="Titre" value={editForm.titre} onChange={e => setEditForm(f => ({ ...f, titre: e.target.value }))} required />
                      <input placeholder="Localisation" value={editForm.localisation} onChange={e => setEditForm(f => ({ ...f, localisation: e.target.value }))} />
                      <input placeholder="Type de contrat" value={editForm.type_contrat} onChange={e => setEditForm(f => ({ ...f, type_contrat: e.target.value }))} />
                      <select value={editForm.status} onChange={e => setEditForm(f => ({ ...f, status: e.target.value }))}>
                        <option value="active">Active</option>
                        <option value="draft">Brouillon</option>
                        <option value="closed">Clôturée</option>
                      </select>
                      <textarea placeholder="Description" value={editForm.description} onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))} />
                      <textarea placeholder="Compétences (séparées par virgules)" value={editForm.competences} onChange={e => setEditForm(f => ({ ...f, competences: e.target.value }))} />
                      <label style={{fontSize:13,color:'#475569'}}>
                        Date limite
                        <input type="date" style={{marginLeft:8}} value={editForm.date_limite} onChange={e => setEditForm(f => ({ ...f, date_limite: e.target.value }))} />
                      </label>
                      <div className="form-actions">
                        <button className="btn-primary" type="submit">Enregistrer</button>
                        <button className="btn-light" type="button" onClick={cancelEdit}>Annuler</button>
                      </div>
                    </form>
                  )}

                  {openOffer === o.id && (
                    <div className="offer-applications">
                      {loadingApps === o.id ? (
                        <div className="loading">⏳ Chargement...</div>
                      ) : (
                        (applications[o.id] || []).length === 0 ? (
                          <div className="empty-state">Aucune candidature pour cette offre.</div>
                        ) : (
                          <div className="applications-list">
                            <div className="app-count">{(applications[o.id] || []).length} candidature(s)</div>
                            {(applications[o.id] || []).map(app => {
                              const initials = (app.candidate_name || 'C').split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase()
                              const statusMap = { pending: { label: 'En attente', cls: 'status-pending' }, accepted: { label: 'Accepté', cls: 'status-accepted' }, rejected: { label: 'Refusé', cls: 'status-rejected' } }
                              const st = statusMap[app.status] || statusMap.pending
                              return (
                                <div key={app.id} className="application-row">
                                  <div className="app-avatar">{initials}</div>
                                  <div className="app-info">
                                    <div className="app-name">{app.candidate_name || 'Candidat'}</div>
                                    <div className="app-email">{app.candidate_email || '—'}</div>
                                    <div className="app-date">{app.created_at ? new Date(app.created_at).toLocaleDateString('fr-FR') : ''}</div>
                                  </div>
                                  <div className="app-status-badge">
                                    <span className={`status-badge ${st.cls}`}>{st.label}</span>
                                  </div>
                                  <div className="app-actions">
                                    {app.cv_id ? (
                                      <Link className="btn-cv" to={`/candidates/${app.cv_id}`} title="Voir CV">
                                        Voir CV
                                      </Link>
                                    ) : null}
                                    <select
                                      value={app.status}
                                      onChange={e => updateApplicationStatus(o.id, app.id, e.target.value)}
                                    >
                                      <option value="pending">En attente</option>
                                      <option value="accepted">Accepter</option>
                                      <option value="rejected">Refuser</option>
                                    </select>
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        )
                      )}
                    </div>
                  )}
                  {openBert === o.id && (
                    <div className="bert-panel">
                      <div className="bert-panel-title">
                        Matching — compare_all
                        <button className="btn-light" onClick={() => runBertMatching(o.id, true)}>
                          Actualiser
                        </button>
                      </div>
                      {loadingBert === o.id ? (
                        <div className="loading">Calcul en cours (BERT + heuristique)…</div>
                      ) : bertResults[o.id] ? (
                        <>
                          <div className="bert-meta">
                            {bertResults[o.id].total} candidat(s) — modele BERT : {bertResults[o.id].model_ready ? 'pret' : 'indisponible'}
                          </div>
                          {bertResults[o.id].results?.length === 0 ? (
                            <div className="empty-state">Aucun candidat pour cette offre.</div>
                          ) : (
                            <>
                            <table className="bert-table">
                              <thead>
                                <tr>
                                  <th>#</th>
                                  <th>Candidat</th>
                                  <th>Heuristique</th>
                                  <th>BERT</th>
                                  <th>Hybride</th>
                                  <th>Incohérences</th>
                                  <th>Note</th>
                                  <th>Comparer</th>
                                  <th>Détail</th>
                                </tr>
                              </thead>
                              <tbody>
                                {bertResults[o.id].results.map((r, idx) => {
                                  const inco = r.bert?.inconsistencies?.length ?? 0
                                  const detailKey = `${o.id}-${r.candidate_id}`
                                  const isOpen = openDetail === detailKey
                                  const hd = r.heuristic_details?.components || {}
                                  const bd = r.bert_details || {}
                                  const bertRaw = r.bert_score ?? 0
                                  const weights = r.weights || { bert: 0.6, heuristic: 0.4 }
                                  const hybridRaw = r.hybrid_score ?? ((weights.bert * (bertRaw || 0)) + (weights.heuristic * (r.heuristic_score || 0)))
                                  return (
                                    <>
                                      <tr key={r.candidate_id} className={idx === 0 ? 'bert-row-best' : ''}>
                                        <td className="bert-rank">{idx + 1}</td>
                                        <td className="bert-name">{r.candidate_name || '—'}</td>
                                        <td>
                                          <div className="score-cell">
                                            <div className="score-bar" style={{ width: `${(r.heuristic_score || 0) * 100}%` }} />
                                            <span>{((r.heuristic_score || 0) * 100).toFixed(1)}%</span>
                                          </div>
                                        </td>
                                        <td>
                                          <div className="score-cell">
                                            <div className="score-bar score-bar-bert" style={{ width: `${(bertRaw || 0) * 100}%` }} />
                                            <span>{((bertRaw || 0) * 100).toFixed(1)}%</span>
                                          </div>
                                        </td>
                                        <td className="bert-hybrid">{((hybridRaw || 0) * 100).toFixed(1)}%</td>
                                        <td>
                                          <span className={`inco-badge ${inco === 0 ? 'inco-ok' : inco <= 2 ? 'inco-warn' : 'inco-bad'}`}>
                                            {inco}
                                          </span>
                                        </td>
                                        <td>
                                          <div className="note-btns">
                                            {[0, 1, 2].map(v => {
                                              const cur = (annotations[o.id] || {})[r.candidate_id]
                                              return (
                                                <button
                                                  key={v}
                                                  className={`note-btn note-${v}${cur === v ? ' note-active' : ''}`}
                                                  onClick={() => setAnnotation(o.id, r.candidate_id, v)}
                                                  title={v === 0 ? 'Non pertinent' : v === 1 ? 'Pertinent' : 'Très pertinent'}
                                                >
                                                  {v}
                                                </button>
                                              )
                                            })}
                                          </div>
                                        </td>
                                        <td>
                                          <input
                                            type="checkbox"
                                            className="compare-chk"
                                            checked={!!(compareSelected[o.id]?.has(r.candidate_id))}
                                            onChange={() => toggleCompare(o.id, r.candidate_id)}
                                            title="Ajouter à la comparaison"
                                          />
                                        </td>
                                        <td>
                                          <button className="btn-detail" onClick={() => setOpenDetail(isOpen ? null : detailKey)}>
                                            {isOpen ? '▲' : '▼'}
                                          </button>
                                        </td>
                                      </tr>
                                      {isOpen && (
                                        <tr className="detail-row" key={`detail-${r.candidate_id}`}>
                                          <td colSpan={9}>
                                            <div className="detail-panel">

                                              {/* ANALYSE INTELLIGENTE */}
                                              <MatchInsightPanel
                                                result={r}
                                                offerTitle={o.titre}
                                                color={COLORS_RADAR[idx % COLORS_RADAR.length]}
                                              />

                                              {/* HEURISTIQUE */}
                                              <div className="detail-section">
                                                <div className="detail-title">Heuristique — {((r.heuristic_score||0)*100).toFixed(1)}%</div>
                                                <div className="detail-formula">
                                                  Skills×40% + Expérience×22% + Formation×18% + Localisation×9% + Sémantique×11%
                                                </div>
                                                <div className="detail-grid">
                                                  <div className="detail-item">
                                                    <span className="detail-label">Skills</span>
                                                    <span className="detail-val">{((hd.skills?.score||0)*100).toFixed(0)}%</span>
                                                  </div>
                                                  <div className="detail-item">
                                                    <span className="detail-label">Expérience</span>
                                                    <span className="detail-val">
                                                      {hd.experience?.candidate_years ?? '?'} ans / {hd.experience?.required_years ?? '?'} requis
                                                      → {((hd.experience?.score||0)*100).toFixed(0)}%
                                                    </span>
                                                  </div>
                                                  <div className="detail-item">
                                                    <span className="detail-label">Formation</span>
                                                    <span className="detail-val">
                                                      Bac+{hd.education?.candidate_level ?? '?'} / Bac+{hd.education?.required_level ?? '?'}
                                                      → {((hd.education?.score||0)*100).toFixed(0)}%
                                                    </span>
                                                  </div>
                                                  <div className="detail-item">
                                                    <span className="detail-label">Localisation</span>
                                                    <span className="detail-val">{hd.location?.score === 1 ? '✅ Trouvée' : '❌ Absente'}</span>
                                                  </div>
                                                </div>
                                                {hd.skills?.matched?.length > 0 && (
                                                  <div className="skills-breakdown">
                                                    <div className="detail-label" style={{marginBottom:4}}>Correspondance skills :</div>
                                                    {hd.skills.matched.map((m, i) => (
                                                      <div key={i} className="skill-match-row">
                                                        <span className="skill-req">{m.required}</span>
                                                        <span className="skill-arrow">→</span>
                                                        <span className="skill-cand">{m.candidate || '∅'}</span>
                                                        <div className="skill-bar-wrap">
                                                          <div className="skill-bar" style={{width:`${(m.ratio||0)*100}%`, background: m.ratio>=0.8?'#22c55e':m.ratio>=0.5?'#f59e0b':'#ef4444'}} />
                                                        </div>
                                                        <span className="skill-pct">{((m.ratio||0)*100).toFixed(0)}%</span>
                                                      </div>
                                                    ))}
                                                  </div>
                                                )}
                                              </div>

                                              {/* BERT */}
                                              <div className="detail-section">
                                                <div className="detail-title">
                                                  BERT — {((bertRaw||0)*100).toFixed(1)}%
                                                  {r.bert_percentile != null && (
                                                    <span className="detail-sub"> (percentile: {(r.bert_percentile * 100).toFixed(0)}%)</span>
                                                  )}
                                                </div>
                                                <div className="detail-formula">
                                                  0.50×Sémantique + 0.30×Skills + 0.20×Base − Pénalité
                                                </div>
                                                <div className="detail-grid">
                                                  <div className="detail-item">
                                                    <span className="detail-label">Sémantique (50%)</span>
                                                    <span className="detail-val">
                                                      {((bd.bert_semantic||0)*100).toFixed(1)}%
                                                      {bd.semantic?.raw_similarity != null && (
                                                        <span className="detail-sub"> (cosine brut : {bd.semantic.raw_similarity})</span>
                                                      )}
                                                    </span>
                                                  </div>
                                                  <div className="detail-item">
                                                    <span className="detail-label">Skills BERT (30%)</span>
                                                    <span className="detail-val">{((bd.bert_skills||0)*100).toFixed(1)}%</span>
                                                  </div>
                                                  <div className="detail-item">
                                                    <span className="detail-label">Base exp+edu (20%)</span>
                                                    <span className="detail-val">{((bd.base||0)*100).toFixed(1)}%</span>
                                                  </div>
                                                  <div className="detail-item">
                                                    <span className="detail-label">Pénalité incohérences</span>
                                                    <span className="detail-val" style={{color:'#ef4444'}}>−{((bd.penalty||0)*100).toFixed(0)}%</span>
                                                  </div>
                                                </div>
                                                {/* Per-skill BERT breakdown */}
                                                {bd.skills?.per_skill?.length > 0 && (
                                                  <div className="skills-breakdown">
                                                    <div className="detail-label" style={{marginBottom:4}}>
                                                      Matching BERT par skill ({bd.skills.matched_count}/{bd.skills.offer_skills_count} matchées, seuil θ={bd.skills.threshold}) :
                                                    </div>
                                                    {bd.skills.per_skill.map((ps, i) => (
                                                      <div key={i} className="skill-match-row">
                                                        <span className="skill-req">{ps.required}</span>
                                                        <span className="skill-arrow">→</span>
                                                        <span className="skill-cand">{ps.best_match || '∅'}</span>
                                                        <div className="skill-bar-wrap">
                                                          <div className="skill-bar" style={{
                                                            width: `${(ps.calibrated||0)*100}%`,
                                                            background: ps.matched ? (ps.calibrated>=0.6?'#22c55e':'#f59e0b') : '#ef4444'
                                                          }} />
                                                        </div>
                                                        <span className="skill-pct">{ps.matched ? `${(ps.calibrated*100).toFixed(0)}%` : '✗'}</span>
                                                      </div>
                                                    ))}
                                                  </div>
                                                )}
                                                {bd.inconsistencies?.length > 0 && (
                                                  <div className="inco-list">
                                                    <div className="detail-label" style={{marginBottom:4}}>Incohérences détectées :</div>
                                                    {bd.inconsistencies.map((inc, i) => (
                                                      <div key={i} className={`inco-item level-${inc.level}`}>
                                                        <span className="inco-skill">{inc.skill}</span>
                                                        <span className="inco-reason">
                                                          {inc.reason === 'absent_from_text' && 'Absent du texte brut'}
                                                          {inc.reason === 'absent_from_experiences' && 'Absent des expériences'}
                                                          {inc.reason?.startsWith('missing_ecosystem') && `Écosystème manquant : ${inc.reason.split(':')[1]}`}
                                                          {inc.reason === 'low_context_similarity' && 'Contexte BERT trop éloigné'}
                                                        </span>
                                                        <span className="inco-level">niv.{inc.level}</span>
                                                      </div>
                                                    ))}
                                                  </div>
                                                )}
                                              </div>

                                              {/* HYBRIDE */}
                                              <div className="detail-section detail-hybrid">
                                                <div className="detail-title">Hybride final — {((hybridRaw||0)*100).toFixed(1)}%</div>
                                                <div className="detail-formula">
                                                  {weights.bert.toFixed(2)} × BERT ({((bertRaw||0)*100).toFixed(1)}%) + {weights.heuristic.toFixed(2)} × Heuristique ({((r.heuristic_score||0)*100).toFixed(1)}%)
                                                  = <strong>{((hybridRaw||0)*100).toFixed(1)}%</strong>
                                                </div>
                                              </div>

                                            </div>
                                          </td>
                                        </tr>
                                      )}
                                    </>
                                  )
                                })}
                              </tbody>
                            </table>
                          {/* Comparaison multi-candidats */}
                          {(compareSelected[o.id]?.size ?? 0) >= 2 && (
                            <MatchComparePanel
                              results={bertResults[o.id].results.filter(r =>
                                compareSelected[o.id]?.has(r.candidate_id)
                              )}
                              offerTitle={o.titre}
                              onClose={() => setCompareSelected(prev => ({ ...prev, [o.id]: new Set() }))}
                            />
                          )}

                          {/* Barre d'actions annotations + métriques */}
                          <div className="eval-bar">
                            <span className="eval-hint">
                              Notez chaque candidat (0 = non pertinent, 1 = pertinent, 2 = très pertinent)
                            </span>
                            <button
                              className="btn-save-annot"
                              disabled={savingAnnotations === o.id || !annotations[o.id] || Object.keys(annotations[o.id]).length === 0}
                              onClick={() => saveAnnotations(o.id)}
                            >
                              {savingAnnotations === o.id ? 'Sauvegarde…' : 'Sauvegarder annotations'}
                            </button>
                            <button
                              className="btn-metrics"
                              disabled={loadingMetrics === o.id}
                              onClick={() => computeMetrics(o.id)}
                            >
                              {loadingMetrics === o.id ? 'Calcul…' : 'Calculer métriques'}
                            </button>
                          </div>

                          {/* Panneau métriques */}
                          {metrics[o.id] && (
                            <div className="metrics-panel">
                              <div className="metrics-title">
                                Évaluation — <em>{metrics[o.id].offer_title}</em>
                              </div>
                              <div className="metrics-grid">
                                {Object.entries(metrics[o.id].metrics?.precision || {}).map(([k, v]) => (
                                  <div key={k} className="metric-card">
                                    <div className="metric-name">{k}</div>
                                    <div className="metric-val">{(v * 100).toFixed(1)}%</div>
                                  </div>
                                ))}
                                {Object.entries(metrics[o.id].metrics?.ndcg || {}).map(([k, v]) => (
                                  <div key={k} className="metric-card">
                                    <div className="metric-name">{k}</div>
                                    <div className="metric-val">{(v * 100).toFixed(1)}%</div>
                                  </div>
                                ))}
                                <div className="metric-card metric-mrr">
                                  <div className="metric-name">MRR</div>
                                  <div className="metric-val">{((metrics[o.id].metrics?.mrr || 0) * 100).toFixed(1)}%</div>
                                </div>
                              </div>
                              <div className="metrics-ranking">
                                <div className="metrics-ranking-title">Classement annoté :</div>
                                <table className="ranking-table">
                                  <thead>
                                    <tr><th>#</th><th>Candidat</th><th>Score hybride</th><th>Pertinence</th></tr>
                                  </thead>
                                  <tbody>
                                    {(metrics[o.id].metrics?.ranking || []).map(row => (
                                      <tr key={row.rank}>
                                        <td>{row.rank}</td>
                                        <td>{row.name}</td>
                                        <td>{(row.hybrid * 100).toFixed(1)}%</td>
                                        <td>
                                          <span className={`rel-badge rel-${row.relevance}`}>
                                            {row.relevance === 2 ? 'Très pertinent' : row.relevance === 1 ? 'Pertinent' : 'Non pertinent'}
                                          </span>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                                <div className="metrics-counts">
                                  {metrics[o.id].metrics?.annotated_count} candidat(s) annoté(s),{' '}
                                  {metrics[o.id].metrics?.relevant_count} pertinent(s)
                                </div>
                              </div>
                            </div>
                          )}
                            </>
                          )}
                        </>
                      ) : null}
                    </div>
                  )}
                  {openBertOnly === o.id && (
                    <div className="tm-panel">
                      <div className="tm-panel-header">
                        <div className="tm-panel-brand">
                          <span className="tm-panel-logo">⚡</span>
                          <div>
                            <div className="tm-panel-title">TalentMatch-BERT</div>
                            <div className="tm-panel-sub">Scoring — modèle fine-tuné v1.3</div>
                          </div>
                        </div>
                        <button className="tm-refresh-btn" onClick={() => runMatchYoussef(o.id, true)}>
                          Actualiser
                        </button>
                        {bertOnlyResults[o.id]?.results?.length > 0 && (
                          <button
                            className={"tm-refresh-btn tm-rapport-btn"}
                            onClick={() => setReportOffer({
                              offer: o,
                              results: bertOnlyResults[o.id].results,
                              modelInfo: bertOnlyResults[o.id].model_version || 'TalentMatch-BERT',
                            })}
                          >
                            Rapport
                          </button>
                        )}
                      </div>

                      {loadingBertOnly === o.id ? (
                        <div className="tm-loading">
                          <span className="tm-spinner" />
                          Analyse en cours…
                        </div>
                      ) : bertOnlyResults[o.id] ? (
                        <>
                          <div className="tm-summary-bar">
                            <span className="tm-summary-count">
                              {bertOnlyResults[o.id].total} candidat(s) analysé(s)
                            </span>
                            <span className={`tm-model-badge ${bertOnlyResults[o.id].model_ready ? 'tm-model-ok' : 'tm-model-err'}`}>
                              {bertOnlyResults[o.id].model_ready ? '● Modèle prêt' : '● Modèle indisponible'}
                            </span>
                          </div>

                          {bertOnlyResults[o.id].results?.length === 0 ? (
                            <div className="tm-empty">Aucun candidat pour cette offre.</div>
                          ) : (
                            <div className="tm-cards">
                              {bertOnlyResults[o.id].results.map((r, idx) => {
                                const score = r.bert_score ?? 0
                                const pct = Math.round(score * 100)
                                const bd = r.bert_details || {}
                                const inco = r.bert?.inconsistencies?.length ?? 0
                                const scoreColor = pct >= 65 ? '#22c55e' : pct >= 40 ? '#F7941D' : '#ef4444'
                                const initials = (r.candidate_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
                                const dims = [
                                  { label: 'Compétences', val: bd.competences, icon: '🎯' },
                                  { label: 'Expérience',  val: bd.experience,  icon: '📅' },
                                  { label: 'Formation',   val: bd.formation,   icon: '🎓' },
                                  { label: 'Sémantique',  val: bd.semantique,  icon: '🧠' },
                                ]
                                const circumference = 2 * Math.PI * 28
                                const offset = circumference * (1 - score)
                                const isExpanded = !!expandedBertCard[r.candidate_id]
                                const matched  = bd.skills_matched || []
                                const missing  = bd.skills_missing  || []
                                const expYears = bd.candidate_years != null ? bd.candidate_years : null
                                const reqYears = bd.required_years  != null ? bd.required_years  : null
                                const candEdu  = bd.candidate_edu   != null ? bd.candidate_edu   : null
                                const reqEdu   = bd.required_edu    != null ? bd.required_edu    : null

                                return (
                                  <div key={r.candidate_id} className={`tm-card ${idx === 0 ? 'tm-card-top' : ''}`}>
                                    {idx === 0 && <div className="tm-card-crown">Meilleur match</div>}
                                    <div
                                      className="tm-card-main"
                                      style={{ cursor: 'pointer' }}
                                      onClick={() => setExpandedBertCard(prev => ({ ...prev, [r.candidate_id]: !prev[r.candidate_id] }))}
                                    >
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
                                        <span className={`inco-badge ${inco <= 2 ? 'inco-warn' : 'inco-bad'}`}>{inco}</span>
                                      )}
                                      <span className="tm-expand-chevron">{isExpanded ? '▲' : '▼'}</span>
                                    </div>

                                    <div className="tm-dims">
                                      {dims.map(d => {
                                        if (d.val == null) return null
                                        const v = Number(d.val) || 0
                                        const bg = v >= 65 ? '#22c55e' : v >= 35 ? '#F7941D' : '#ef4444'
                                        return (
                                          <div key={d.label} className="tm-dim">
                                            <span className="tm-dim-icon">{d.icon}</span>
                                            <span className="tm-dim-label">{d.label}</span>
                                            <div className="tm-dim-bar-wrap">
                                              <div className="tm-dim-bar" style={{ width: `${v}%`, background: bg }} />
                                            </div>
                                            <span className="tm-dim-val">{Math.round(v)}%</span>
                                          </div>
                                        )
                                      })}
                                    </div>

                                    {isExpanded && (
                                      <div className="tm-explain">
                                        {/* Skills matchées */}
                                        {matched.length > 0 && (
                                          <div className="tm-explain-block">
                                            <div className="tm-explain-label tm-explain-ok">
                                              Competences trouvees ({matched.length})
                                            </div>
                                            <div className="tm-chip-row">
                                              {matched.map((m, i) => (
                                                <span key={i} className={`tm-chip tm-chip-ok${m.source === 'texte_brut' ? ' tm-chip-partial' : ''}`}
                                                  title={m.source === 'texte_brut' ? 'Detecte dans le texte (non extrait par le parser)' : 'Extrait du CV'}>
                                                  {m.skill}
                                                  {m.source === 'texte_brut' && <span className="tm-chip-src"> ~</span>}
                                                </span>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                        {/* Skills manquantes */}
                                        {missing.length > 0 && (
                                          <div className="tm-explain-block">
                                            <div className="tm-explain-label tm-explain-ko">
                                              Competences manquantes ({missing.length})
                                            </div>
                                            <div className="tm-chip-row">
                                              {missing.map((s, i) => (
                                                <span key={i} className="tm-chip tm-chip-ko">{s}</span>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                        {/* Experience + Formation */}
                                        <div className="tm-explain-meta">
                                          <span className="tm-meta-item">
                                            Experience : {expYears != null ? `${expYears} ans` : 'non detectee'}
                                            {reqYears > 0 ? ` / ${reqYears} requis` : ''}
                                          </span>
                                          <span className="tm-meta-sep">|</span>
                                          <span className="tm-meta-item">
                                            Formation : {candEdu != null ? `Bac+${candEdu}` : 'non detectee'}
                                            {reqEdu > 0 ? ` / Bac+${reqEdu} requis` : ''}
                                          </span>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="tm-empty">Cliquez sur "TalentMatch" pour lancer l'analyse.</div>
                      )}
                    </div>
                  )}
                </div>
              )
              })
            )}
          </div>
        )}
      </section>

      {reportOffer && (
        <MatchReport
          offer={reportOffer.offer}
          results={reportOffer.results}
          modelInfo={reportOffer.modelInfo}
          onClose={() => setReportOffer(null)}
        />
      )}
    </div>
  )
}

export default JobOffers
