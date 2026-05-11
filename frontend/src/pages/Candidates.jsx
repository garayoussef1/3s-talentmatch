import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'
import './Candidates.css'

const STATUS = {
  en_attente: { label: 'En attente', color: '#F7941D', bg: '#FFF8EE' },
  accepte:    { label: 'Accepté',    color: '#22c55e', bg: '#F0FDF4' },
  refuse:     { label: 'Refusé',     color: '#ef4444', bg: '#FEF2F2' },
}
const METHOD_COLOR = {
  pypdf: { bg: '#eff6ff', color: '#2563eb' },
  ocr:   { bg: '#fef3c7', color: '#92400e' },
  docx:  { bg: '#f0fdf4', color: '#16a34a' },
}

// ── Export CSV helpers ──────────────────────────────────────
function buildCSVRows(candidates) {
  const rows = [['Nom', 'Email', 'Téléphone', 'Score', 'Méthode', 'Statut', 'Date']]
  candidates.forEach(c => rows.push([
    c.nom || '',
    c.email || '',
    c.telephone || '',
    c.score != null ? `${c.score}%` : '',
    c.extraction_method || '',
    c.candidature_status || '',
    c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : '',
  ]))
  return rows
}

function downloadCSV(rows, filename) {
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}


// ══════════════════════════════════════════════════════════════
// VUE LISTE (existante)
// ══════════════════════════════════════════════════════════════
function ListView({ candidates, total, onRefresh, isAdmin }) {
  const [deleting, setDeleting]         = useState(null)
  const [search, setSearch]             = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [updatingStatus, setUpdatingStatus] = useState(null)
  const [sortKey, setSortKey]           = useState('created_at')
  const [sortDir, setSortDir]           = useState('desc')

  const handleDelete = (cvId) => {
    if (!window.confirm('Supprimer ce candidat ?')) return
    setDeleting(cvId)
    api.delete(`/candidates/${cvId}`)
      .then(() => onRefresh())
      .catch(() => {})
      .finally(() => setDeleting(null))
  }

  const handleDeleteAll = () => {
    if (!window.confirm(`Supprimer les ${total} candidat(s) ? Action irréversible.`)) return
    setDeleting('all')
    api.delete('/candidates')
      .then(() => onRefresh())
      .catch(() => {})
      .finally(() => setDeleting(null))
  }

  const handleStatusChange = (cvId, newStatus) => {
    setUpdatingStatus(cvId)
    api.patch(`/candidates/${cvId}/status`, null, { params: { status: newStatus } })
      .then(() => onRefresh())
      .catch(() => {})
      .finally(() => setUpdatingStatus(null))
  }

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span style={{ color: '#d1d5db', marginLeft: 4 }}>↕</span>
    return <span style={{ color: '#1b4f8a', marginLeft: 4 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  const statusCounts = candidates.reduce((acc, c) => {
    const s = c.candidature_status || 'en_attente'; acc[s] = (acc[s] || 0) + 1; return acc
  }, {})

  const filtered = candidates
    .filter(c => {
      const q = search.toLowerCase()
      const matchSearch = !q || (
        (c.nom || '').toLowerCase().includes(q) ||
        (c.email || '').toLowerCase().includes(q) ||
        (c.filename || '').toLowerCase().includes(q)
      )
      return matchSearch && (filterStatus === 'all' || c.candidature_status === filterStatus)
    })
    .sort((a, b) => {
      let va, vb
      if (sortKey === 'nom')        { va = (a.nom || a.filename || '').toLowerCase(); vb = (b.nom || b.filename || '').toLowerCase() }
      else if (sortKey === 'status') { va = a.candidature_status || ''; vb = b.candidature_status || '' }
      else                           { va = a.created_at || ''; vb = b.created_at || '' }
      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ? 1 : -1
      return 0
    })

  return (
    <>
      {/* KPI statuts */}
      <div className="cand-kpi-row">
        {Object.entries(STATUS).map(([key, s]) => (
          <button key={key} className={`cand-kpi-btn ${filterStatus === key ? 'active' : ''}`}
            style={{ '--c': s.color, '--bg': s.bg }}
            onClick={() => setFilterStatus(filterStatus === key ? 'all' : key)}>
            <span className="cand-kpi-val">{statusCounts[key] ?? 0}</span>
            <span className="cand-kpi-lbl">{s.label}</span>
          </button>
        ))}
        <button className={`cand-kpi-btn ${filterStatus === 'all' ? 'active' : ''}`}
          style={{ '--c': '#4f46e5', '--bg': '#eef2ff' }}
          onClick={() => setFilterStatus('all')}>
          <span className="cand-kpi-val">{total}</span>
          <span className="cand-kpi-lbl">Total</span>
        </button>
      </div>

      {/* Recherche */}
      <div className="cand-search-bar">
        <span className="cand-search-icon">&#128269;</span>
        <input className="cand-search-input" placeholder="Rechercher par nom, email, fichier…"
          value={search} onChange={e => setSearch(e.target.value)} />
        {search && <button className="cand-search-clear" onClick={() => setSearch('')}>&#10005;</button>}
        <span className="cand-search-count">{filtered.length} résultat(s)</span>
        {filtered.length > 0 && (
          <button className="cand-btn-export"
            onClick={() => downloadCSV(buildCSVRows(filtered), `candidats-${Date.now()}.csv`)}>
            ⬇ Export CSV
          </button>
        )}
        {isAdmin && total > 0 && (
          <button className="cand-btn-danger" style={{ marginLeft: 8 }}
            onClick={handleDeleteAll} disabled={deleting === 'all'}>
            {deleting === 'all' ? 'Suppression…' : 'Tout supprimer'}
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="cand-empty">
          <div className="cand-empty-icon">&#128196;</div>
          <p>{search || filterStatus !== 'all' ? 'Aucun résultat.' : 'Aucun candidat.'}</p>
          <Link to="/upload" className="cand-btn-primary" style={{ marginTop: 12 }}>Uploader un CV</Link>
        </div>
      ) : (
        <div className="cand-table-wrap">
          <table className="cand-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('nom')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                  Candidat<SortIcon col="nom" />
                </th>
                <th>Compétences</th>
                <th>Offre(s)</th>
                <th>Extraction</th>
                <th onClick={() => handleSort('status')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                  Statut<SortIcon col="status" />
                </th>
                <th onClick={() => handleSort('created_at')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                  Date<SortIcon col="created_at" />
                </th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => {
                const status = c.candidature_status || 'en_attente'
                const s = STATUS[status] || STATUS.en_attente
                const initials = (c.nom || c.filename || 'C').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
                const skills = c.parsed_data?.competences?.slice(0, 3) || []
                const methodMeta = METHOD_COLOR[c.extraction_method] || { bg: '#f3f4f6', color: '#6b7280' }
                return (
                  <tr key={c.cv_id}>
                    <td>
                      <div className="cand-person">
                        <div className="cand-avatar">{initials}</div>
                        <div className="cand-person-info">
                          <span className="cand-name">{c.nom || <span className="cand-na">Nom non extrait</span>}</span>
                          <span className="cand-email">{c.email || c.filename}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      {skills.length > 0 ? (
                        <div className="cand-skills">
                          {skills.map((sk, i) => <span key={i} className="cand-skill-chip">{sk}</span>)}
                          {(c.parsed_data?.competences?.length || 0) > 3 && (
                            <span className="cand-skill-more">+{c.parsed_data.competences.length - 3}</span>
                          )}
                        </div>
                      ) : <span className="cand-na">—</span>}
                    </td>
                    <td>
                      {c.offer_titles?.length ? (
                        <div className="cand-offers">
                          {c.offer_titles.slice(0, 2).map((t, i) => <span key={i} className="cand-offer-chip">{t}</span>)}
                          {c.offer_titles.length > 2 && <span className="cand-skill-more">+{c.offer_titles.length - 2}</span>}
                        </div>
                      ) : <span className="cand-na">—</span>}
                    </td>
                    <td>
                      <span className="cand-method" style={{ background: methodMeta.bg, color: methodMeta.color }}>
                        {c.extraction_method || '—'}
                      </span>
                    </td>
                    <td>
                      <select className="cand-status-select" value={status}
                        disabled={updatingStatus === c.cv_id}
                        style={{ borderColor: s.color, color: s.color, background: s.bg }}
                        onChange={e => handleStatusChange(c.cv_id, e.target.value)}>
                        <option value="en_attente">En attente</option>
                        <option value="accepte">Accepté</option>
                        <option value="refuse">Refusé</option>
                      </select>
                    </td>
                    <td className="cand-date">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : '—'}
                    </td>
                    <td>
                      <div className="cand-actions">
                        <Link to={`/candidates/${c.cv_id}`} className="cand-btn-view">Voir</Link>
                        <button className="cand-btn-del" onClick={() => handleDelete(c.cv_id)}
                          disabled={deleting === c.cv_id}>
                          {deleting === c.cv_id ? '…' : '🗑'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}


// ══════════════════════════════════════════════════════════════
// VUE KANBAN — colonnes drag & drop par statut
// ══════════════════════════════════════════════════════════════
const KB_COLS = [
  { key: 'en_attente', label: 'En attente', color: '#F7941D', bg: '#FFF8EE', icon: '⏳' },
  { key: 'accepte',    label: 'Accepté',    color: '#22c55e', bg: '#F0FDF4', icon: '✅' },
  { key: 'refuse',     label: 'Refusé',     color: '#ef4444', bg: '#FEF2F2', icon: '❌' },
]

function KanbanView({ candidates, onRefresh }) {
  const dragRef    = useRef(null)
  const [updating, setUpdating]   = useState(null)
  const [dragOver, setDragOver]   = useState(null)

  const grouped = { en_attente: [], accepte: [], refuse: [] }
  candidates.forEach(c => {
    const s = c.candidature_status || 'en_attente'
    if (grouped[s]) grouped[s].push(c)
  })

  const handleDrop = (colKey) => {
    const c = dragRef.current
    setDragOver(null)
    if (!c || c.candidature_status === colKey) { dragRef.current = null; return }
    setUpdating(c.cv_id)
    api.patch(`/candidates/${c.cv_id}/status`, null, { params: { status: colKey } })
      .then(() => onRefresh())
      .catch(() => {})
      .finally(() => { setUpdating(null); dragRef.current = null })
  }

  return (
    <div className="kb-board">
      {KB_COLS.map(col => (
        <div key={col.key}
          className={`kb-col ${dragOver === col.key ? 'kb-col-over' : ''}`}
          style={{ '--col-color': col.color, '--col-bg': col.bg }}
          onDragOver={e => { e.preventDefault(); setDragOver(col.key) }}
          onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setDragOver(null) }}
          onDrop={() => handleDrop(col.key)}
        >
          <div className="kb-col-header">
            <span className="kb-col-icon">{col.icon}</span>
            <span className="kb-col-title">{col.label}</span>
            <span className="kb-col-count">{grouped[col.key].length}</span>
          </div>

          <div className="kb-cards">
            {grouped[col.key].map(c => {
              const initials = (c.nom || c.filename || 'C')
                .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
              const score = c.score
              return (
                <div key={c.cv_id}
                  className={`kb-card ${updating === c.cv_id ? 'kb-card-loading' : ''}`}
                  draggable
                  onDragStart={() => { dragRef.current = c }}
                  onDragEnd={() => { setDragOver(null) }}
                >
                  <div className="kb-card-top">
                    <div className="kb-avatar">{initials}</div>
                    <div className="kb-card-info">
                      <span className="kb-card-name">{c.nom || <span className="cand-na">Sans nom</span>}</span>
                      <span className="kb-card-email">{c.email || c.filename}</span>
                    </div>
                    {score != null && (
                      <span className="kb-score" style={{
                        color:      score >= 65 ? '#16a34a' : score >= 35 ? '#d97706' : '#dc2626',
                        background: score >= 65 ? '#f0fdf4' : score >= 35 ? '#fffbeb' : '#fef2f2',
                      }}>{score}%</span>
                    )}
                  </div>
                  {c.offer_titles?.length > 0 && (
                    <div className="kb-card-offer">{c.offer_titles[0]}</div>
                  )}
                  <div className="kb-card-footer">
                    <Link to={`/candidates/${c.cv_id}`} className="kb-btn-view"
                      onClick={e => e.stopPropagation()}>Voir</Link>
                  </div>
                </div>
              )
            })}
            {grouped[col.key].length === 0 && (
              <div className="kb-empty-col">Glisser ici</div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}


// ══════════════════════════════════════════════════════════════
// VUE PAR OFFRE — une section par offre, divisée active/clôturée
// ══════════════════════════════════════════════════════════════
function OfferSection({ title, offerGroups, sectionKey, onRefresh }) {
  const [expanded, setExpanded] = useState({})
  const [updatingStatus, setUpdatingStatus] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const toggle = (id) => setExpanded(prev => ({ ...prev, [id]: !prev[id] }))

  const handleStatusChange = (cvId, newStatus) => {
    setUpdatingStatus(cvId)
    api.patch(`/candidates/${cvId}/status`, null, { params: { status: newStatus } })
      .then(() => onRefresh())
      .catch(() => {})
      .finally(() => setUpdatingStatus(null))
  }

  const handleDelete = (cvId) => {
    if (!window.confirm('Supprimer ce candidat ?')) return
    setDeleting(cvId)
    api.delete(`/candidates/${cvId}`)
      .then(() => onRefresh())
      .catch(() => {})
      .finally(() => setDeleting(null))
  }

  const exportSection = () => {
    const all = offerGroups.flatMap(g => g.candidates.map(c => ({ ...c, _offer: g.titre })))
    if (!all.length) return
    const rows = [['Offre', 'Nom', 'Email', 'Téléphone', 'Score', 'Méthode', 'Statut', 'Date']]
    all.forEach(c => rows.push([
      c._offer, c.nom || '', c.email || '', c.telephone || '',
      c.score != null ? `${c.score}%` : '', c.extraction_method || '',
      c.candidature_status || '',
      c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : '',
    ]))
    downloadCSV(rows, `candidats-${sectionKey}-${Date.now()}.csv`)
  }

  const totalCands = offerGroups.reduce((s, g) => s + g.nb_candidats, 0)

  if (!offerGroups.length) return null

  return (
    <div className="og-section">
      <div className="og-section-header">
        <div className="og-section-title">
          <span className={`og-section-dot ${sectionKey}`} />
          {title}
          <span className="og-section-count">{offerGroups.length} offre(s) · {totalCands} candidat(s)</span>
        </div>
        {totalCands > 0 && (
          <button className="cand-btn-export" onClick={exportSection}>
            ⬇ Exporter tous ({sectionKey === 'active' ? 'actifs' : 'clôturés'})
          </button>
        )}
      </div>

      <div className="og-offers">
        {offerGroups.map(group => {
          const isOpen = expanded[group.offer_id] === true  // fermé par défaut
          return (
            <div key={group.offer_id} className="og-offer-card">
              {/* Header offre */}
              <div className="og-offer-header" onClick={() => toggle(group.offer_id)}>
                <div className="og-offer-meta">
                  <div className="og-offer-title">
                    <span className="og-offer-chevron">{isOpen ? '▼' : '▶'}</span>
                    {group.titre}
                  </div>
                  <div className="og-offer-tags">
                    <span className="og-tag og-tag-contract">{group.type_contrat}</span>
                    {group.localisation !== '—' && <span className="og-tag og-tag-loc">📍 {group.localisation}</span>}
                    <span className="og-tag og-tag-postes">{group.nb_postes} poste(s)</span>
                  </div>
                </div>
                <div className="og-offer-right">
                  <span className="og-cand-count">{group.nb_candidats} candidat(s)</span>
                  {group.candidates.length > 0 && (
                    <button className="og-btn-export" onClick={e => {
                      e.stopPropagation()
                      downloadCSV(
                        buildCSVRows(group.candidates),
                        `${group.titre.replace(/\s+/g, '_')}-${Date.now()}.csv`
                      )
                    }}>
                      ⬇ CSV
                    </button>
                  )}
                  <Link to={`/offers/${group.offer_id}`} className="og-btn-view"
                    onClick={e => e.stopPropagation()}>
                    Voir l'offre
                  </Link>
                </div>
              </div>

              {/* Tableau candidats */}
              {isOpen && (
                group.candidates.length === 0 ? (
                  <div className="og-empty">Aucun candidat pour cette offre.</div>
                ) : (
                  <div className="og-candidates-table-wrap">
                    <table className="og-candidates-table">
                      <thead>
                        <tr>
                          <th>Candidat</th>
                          <th>Score</th>
                          <th>Méthode</th>
                          <th>Statut</th>
                          <th>Date</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.candidates.map((c, i) => {
                          const st = c.candidature_status || 'en_attente'
                          const s = STATUS[st] || STATUS.en_attente
                          const initials = (c.nom || c.filename || 'C').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
                          const mm = METHOD_COLOR[c.extraction_method] || { bg: '#f3f4f6', color: '#6b7280' }
                          return (
                            <tr key={c.cv_id || i}>
                              <td>
                                <div className="cand-person">
                                  <div className="cand-avatar" style={{ width: 32, height: 32, fontSize: '0.75rem' }}>{initials}</div>
                                  <div className="cand-person-info">
                                    <span className="cand-name">{c.nom || <span className="cand-na">Non extrait</span>}</span>
                                    <span className="cand-email">{c.email || c.filename}</span>
                                  </div>
                                </div>
                              </td>
                              <td>
                                {c.score != null ? (
                                  <span className={`og-score ${c.score >= 65 ? 'high' : c.score >= 35 ? 'mid' : 'low'}`}>
                                    {c.score}%
                                  </span>
                                ) : <span className="cand-na">—</span>}
                              </td>
                              <td>
                                <span className="cand-method" style={{ background: mm.bg, color: mm.color }}>
                                  {c.extraction_method || '—'}
                                </span>
                              </td>
                              <td>
                                <select className="cand-status-select" value={st}
                                  disabled={updatingStatus === c.cv_id}
                                  style={{ borderColor: s.color, color: s.color, background: s.bg }}
                                  onChange={e => handleStatusChange(c.cv_id, e.target.value)}>
                                  <option value="en_attente">En attente</option>
                                  <option value="accepte">Accepté</option>
                                  <option value="refuse">Refusé</option>
                                </select>
                              </td>
                              <td className="cand-date">
                                {c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : '—'}
                              </td>
                              <td>
                                <div className="cand-actions">
                                  <Link to={`/candidates/${c.cv_id}`} className="cand-btn-view">Voir</Link>
                                  <button className="cand-btn-del" onClick={() => handleDelete(c.cv_id)}
                                    disabled={deleting === c.cv_id}>
                                    {deleting === c.cv_id ? '…' : '🗑'}
                                  </button>
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ══════════════════════════════════════════════════════════════
// COMPOSANT PRINCIPAL
// ══════════════════════════════════════════════════════════════
export default function Candidates() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [viewMode, setViewMode]     = useState('list')
  const [candidates, setCandidates] = useState([])
  const [total, setTotal]           = useState(0)
  const [grouped, setGrouped]       = useState(null)
  const [loadingList, setLoadingList]     = useState(true)
  const [loadingGrouped, setLoadingGrouped] = useState(false)
  const [errorList, setErrorList]         = useState(null)
  const [errorGrouped, setErrorGrouped]   = useState(null)

  const fetchList = () => {
    setLoadingList(true)
    setErrorList(null)
    api.get('/candidates?limit=200')
      .then(res => { setCandidates(res.data.candidates); setTotal(res.data.total) })
      .catch(() => setErrorList('Impossible de charger les candidats.'))
      .finally(() => setLoadingList(false))
  }

  const fetchGrouped = () => {
    setLoadingGrouped(true)
    setErrorGrouped(null)
    api.get('/candidates/grouped')
      .then(res => setGrouped(res.data))
      .catch(() => setErrorGrouped('Impossible de charger la vue par offre. Redémarre le serveur backend.'))
      .finally(() => setLoadingGrouped(false))
  }

  const fetchAll = () => { fetchList(); if (viewMode === 'grouped') fetchGrouped() }

  useEffect(() => { fetchList() }, [])

  const switchView = (mode) => {
    setViewMode(mode)
    if (mode === 'grouped' && !grouped && !loadingGrouped) fetchGrouped()
  }

  return (
    <div className="cand-wrapper">

      {/* ── Hero header ── */}
      <div className="cand-hero">
        <div className="cand-hero-left">
          <span className="cand-eyebrow">{isAdmin ? 'Administration' : 'Recruteur'}</span>
          <h1>Candidats</h1>
          <p>{total} profil{total !== 1 ? 's' : ''} — gérez les candidatures et suivez les statuts</p>
        </div>
        <div className="cand-hero-right">
          <Link to="/upload" className="cand-btn-primary">+ Uploader un CV</Link>
          <div className="cand-view-toggle">
            <button className={`cand-toggle-btn ${viewMode === 'list' ? 'active' : ''}`} onClick={() => switchView('list')}>☰ Liste</button>
            <button className={`cand-toggle-btn ${viewMode === 'grouped' ? 'active' : ''}`} onClick={() => switchView('grouped')}>⊞ Par offre</button>
            <button className={`cand-toggle-btn ${viewMode === 'kanban' ? 'active' : ''}`} onClick={() => switchView('kanban')}>⬛ Kanban</button>
          </div>
        </div>
      </div>

      {/* ── Vue Liste ── */}
      {viewMode === 'list' && (
        <>
          {errorList && <div className="cand-error">⚠ {errorList}</div>}
          {loadingList
            ? <div className="cand-loading"><div className="cand-spinner" /><span>Chargement…</span></div>
            : <ListView candidates={candidates} total={total} onRefresh={fetchList} isAdmin={isAdmin} />
          }
        </>
      )}

      {/* ── Vue Kanban ── */}
      {viewMode === 'kanban' && (
        <>
          {loadingList
            ? <div className="cand-loading"><div className="cand-spinner" /><span>Chargement…</span></div>
            : <KanbanView candidates={candidates} onRefresh={fetchList} />
          }
        </>
      )}

      {/* ── Vue Par offre ── */}
      {viewMode === 'grouped' && (
        <>
          {loadingGrouped && (
            <div className="cand-loading"><div className="cand-spinner" /><span>Chargement par offre…</span></div>
          )}
          {errorGrouped && !loadingGrouped && (
            <div className="cand-error" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              ⚠ {errorGrouped}
              <button className="cand-btn-primary" style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                onClick={fetchGrouped}>
                Réessayer
              </button>
            </div>
          )}
          {!loadingGrouped && grouped && (
            <div className="og-root">
              <OfferSection
                title="Offres actives"
                offerGroups={grouped.active}
                sectionKey="active"
                onRefresh={() => { fetchList(); fetchGrouped() }}
              />
              <OfferSection
                title="Offres clôturées"
                offerGroups={grouped.closed}
                sectionKey="closed"
                onRefresh={() => { fetchList(); fetchGrouped() }}
              />
              {grouped.draft?.length > 0 && (
                <OfferSection
                  title="Brouillons"
                  offerGroups={grouped.draft}
                  sectionKey="draft"
                  onRefresh={() => { fetchList(); fetchGrouped() }}
                />
              )}
              {!grouped.active?.length && !grouped.closed?.length && (
                <div className="cand-empty">
                  <div className="cand-empty-icon">📋</div>
                  <p>Aucune offre trouvée. Créez une offre pour commencer.</p>
                  <Link to="/offers/new" className="cand-btn-primary" style={{ marginTop: 12 }}>
                    Créer une offre
                  </Link>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
