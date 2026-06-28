import { useEffect, useMemo, useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'
import './Offers.css'

const VALID_CONTRATS = ['CDI', 'CDD', 'Stage', 'Alternance', 'Freelance']

function matchQuality(offer) {
  let score = 0
  const issues = []

  const skills = offer.competences_requises || []
  if (skills.length >= 3) score += 35
  else if (skills.length >= 1) { score += 15; issues.push(`${skills.length} compétence${skills.length > 1 ? 's' : ''} (min. 3 recommandées)`) }
  else issues.push('Aucune compétence requise')

  if (offer.type_contrat && VALID_CONTRATS.includes(offer.type_contrat)) score += 20
  else issues.push('Type de contrat manquant')

  if (offer.description && offer.description.length >= 80) score += 20
  else { score += 5; issues.push('Description trop courte') }

  if (offer.experience_requise != null) score += 15
  else issues.push('Expérience non précisée')

  const desc = (offer.description || '').toLowerCase()
  if (/bac\+?\s*[0-9]|master|ingénieur|doctorat/i.test(desc)) score += 10
  else issues.push('Niveau de formation non précisé')

  const level = score >= 80 ? 'good' : score >= 45 ? 'partial' : 'weak'
  return { score, level, issues }
}


function RecruiterModal({ offer, onClose, onSaved }) {
  const [recruiters, setRecruiters]     = useState([])   // tous les recruteurs
  const [selected, setSelected]         = useState([])   // ids cochés
  const [loading, setLoading]           = useState(true)
  const [saving, setSaving]             = useState(false)
  const [error, setError]               = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/admin/users'),
      api.get(`/offers/${offer.id}/recruiters`),
    ])
      .then(([usersRes, recRes]) => {
        const allUsers   = usersRes.data.users || []
        const recs       = allUsers.filter(u => u.role === 'recruteur')
        const assignedIds = (recRes.data.recruiters || []).map(r => r.id)
        setRecruiters(recs)
        setSelected(assignedIds)
      })
      .catch(() => setError("Impossible de charger les recruteurs."))
      .finally(() => setLoading(false))
  }, [offer.id])

  const toggle = (id) =>
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])

  const handleSave = () => {
    setSaving(true)
    setError(null)
    api.put(`/offers/${offer.id}/recruiters`, { recruiter_ids: selected })
      .then(() => { onSaved(offer.id, selected); onClose() })
      .catch(() => setError("Erreur lors de la sauvegarde."))
      .finally(() => setSaving(false))
  }

  return (
    <div className="rm-overlay" onClick={onClose}>
      <div className="rm-panel" onClick={e => e.stopPropagation()}>
        <div className="rm-header">
          <div>
            <div className="rm-eyebrow">Gestion des accès</div>
            <h2 className="rm-title">{offer.titre}</h2>
          </div>
          <button className="rm-close" onClick={onClose}>✕</button>
        </div>

        <p className="rm-desc">
          Sélectionnez les recruteurs qui peuvent gérer cette offre et voir ses candidatures.
        </p>

        {error && <div className="alert error" style={{ marginBottom: 12 }}>{error}</div>}

        {loading ? (
          <div className="rm-loading">Chargement des recruteurs…</div>
        ) : recruiters.length === 0 ? (
          <div className="rm-empty">Aucun recruteur disponible dans le système.</div>
        ) : (
          <div className="rm-list">
            {recruiters.map(r => {
              const checked  = selected.includes(r.id)
              const initials = ((r.prenom || '') + (r.nom || '') || 'R')[0].toUpperCase()
              return (
                <label key={r.id} className={`rm-item ${checked ? 'rm-item--checked' : ''}`}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(r.id)}
                    className="rm-checkbox"
                  />
                  <div className="rm-avatar">{initials}</div>
                  <div className="rm-info">
                    <div className="rm-name">{r.prenom} {r.nom}</div>
                    <div className="rm-email">{r.email}</div>
                  </div>
                  {checked && <span className="rm-check-badge">✓ Assigné</span>}
                </label>
              )
            })}
          </div>
        )}

        <div className="rm-footer">
          <span className="rm-count">
            {selected.length} recruteur{selected.length !== 1 ? 's' : ''} sélectionné{selected.length !== 1 ? 's' : ''}
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-secondary" onClick={onClose}>Annuler</button>
            <button className="btn-primary" onClick={handleSave} disabled={saving || loading}>
              {saving ? 'Sauvegarde…' : 'Enregistrer les accès'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Page principale ──────────────────────────────────────────── */
export default function OffersList() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [offers, setOffers]       = useState([])
  const [totalPool, setTotalPool] = useState(0)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [searchText, setSearchText]         = useState('')
  const [statusFilter, setStatusFilter]     = useState('all')
  const [contractFilter, setContractFilter] = useState('all')
  const [modalOffer, setModalOffer]         = useState(null)

  // ── Gestion "vu / non vu" par offre ──────────────────────────
  // localStorage key: "offer_seen_counts" → { [offerId]: lastSeenCount }
  const STORAGE_KEY = `offer_seen_${user?.id || 'guest'}`
  const [seenCounts, setSeenCounts] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }
    catch { return {} }
  })

  const markOfferSeen = useCallback((offerId, currentCount) => {
    setSeenCounts(prev => {
      const next = { ...prev, [offerId]: currentCount }
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }, [STORAGE_KEY])

  // Nombre de nouveaux candidats non vus pour une offre
  const getNewCount = useCallback((offerId, currentCount) => {
    if (currentCount === 0) return 0
    const lastSeen = seenCounts[offerId]
    // Jamais ouvert → tout est "nouveau"
    if (lastSeen === undefined) return currentCount
    return Math.max(0, currentCount - lastSeen)
  }, [seenCounts])

  useEffect(() => {
    Promise.all([
      api.get('/offers'),
      api.get('/candidates?limit=1').catch(() => ({ data: { total: 0 } })),
    ])
      .then(([offersRes, candsRes]) => {
        setOffers(offersRes.data.offers || [])
        const pool = offersRes.data.total_pool ?? candsRes.data.total ?? 0
        setTotalPool(pool)
      })
      .catch(() => setError("Impossible de charger les offres."))
      .finally(() => setLoading(false))
  }, [])

  /* Met à jour localement les recruteurs assignés sans recharger */
  const handleAssignSaved = useCallback((offerId, newIds) => {
    setOffers(prev => prev.map(o =>
      o.id === offerId ? { ...o, assigned_recruiter_ids: newIds } : o
    ))
  }, [])

  /* ── Stats ── */
  const stats = useMemo(() => {
    const s = { active: 0, draft: 0, closed: 0, candidates: 0 }
    offers.forEach(o => {
      if (o.status === 'active') s.active++
      else if (o.status === 'draft') s.draft++
      else if (o.status === 'closed') s.closed++
      s.candidates += o.candidate_count ?? 0
    })
    return s
  }, [offers])

  /* ── Filtres ── */
  const filtered = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    return offers.filter(o => {
      if (statusFilter !== 'all' && o.status !== statusFilter) return false
      if (contractFilter !== 'all') {
        const ct = (o.type_contrat || '').toLowerCase()
        if (!ct.includes(contractFilter)) return false
      }
      if (q) {
        const hay = [o.titre, o.description, o.localisation, o.type_contrat, ...(o.competences_requises || [])]
          .filter(Boolean).join(' ').toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [offers, searchText, statusFilter, contractFilter])

  const STATUS_LABEL = { active: 'Active', draft: 'Brouillon', closed: 'Clôturée' }
  const STATUS_CLS   = { active: 'status-active', draft: 'status-draft', closed: 'status-closed' }

  return (
    <div className="page-wrapper">

      {/* ── Hero / En-tête ── */}
      <div className="ol-hero">
        <div className="ol-hero-left">
          <span className="ol-eyebrow">{isAdmin ? 'Administration' : 'Recruteur'}</span>
          <h1>Offres d'emploi</h1>
          <p>{isAdmin
            ? 'Créez et gérez toutes les offres. Assignez les accès aux recruteurs.'
            : 'Consultez vos offres assignées et gérez les candidatures.'
          }</p>
          <div className="ol-hero-actions">
            {isAdmin && <Link to="/offers/new" className="btn-primary">+ Créer une offre</Link>}
            <Link to="/candidates" className="btn-secondary">Voir les candidats</Link>
          </div>
        </div>
        <div className="ol-stats">
          <div className="ol-stat">
            <span className="ol-stat-num">{offers.length}</span>
            <span className="ol-stat-label">Total</span>
          </div>
          <div className="ol-stat-divider" />
          <div className="ol-stat">
            <span className="ol-stat-num" style={{ color: '#22c55e' }}>{stats.active}</span>
            <span className="ol-stat-label">Actives</span>
          </div>
          <div className="ol-stat-divider" />
          <div className="ol-stat">
            <span className="ol-stat-num" style={{ color: '#f59e0b' }}>{stats.draft}</span>
            <span className="ol-stat-label">Brouillons</span>
          </div>
          <div className="ol-stat-divider" />
          <div className="ol-stat">
            <span className="ol-stat-num" style={{ color: '#F7941D' }}>{totalPool}</span>
            <span className="ol-stat-label">Profils</span>
          </div>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      {/* ── Barre de filtres ── */}
      <div className="ol-filter-bar">
        <div className="ol-filter-search">
          <span className="ol-search-icon">⌕</span>
          <input
            placeholder="Rechercher par titre, compétences, localisation…"
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
          />
          {searchText && (
            <button className="ol-search-clear" onClick={() => setSearchText('')}>✕</button>
          )}
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">Tous les statuts</option>
          <option value="active">Active</option>
          <option value="draft">Brouillon</option>
          <option value="closed">Clôturée</option>
        </select>
        <select value={contractFilter} onChange={e => setContractFilter(e.target.value)}>
          <option value="all">Tous les contrats</option>
          <option value="cdi">CDI</option>
          <option value="cdd">CDD</option>
          <option value="stage">Stage</option>
          <option value="freelance">Freelance</option>
        </select>
        {(searchText || statusFilter !== 'all' || contractFilter !== 'all') && (
          <button className="ol-clear-btn" onClick={() => { setSearchText(''); setStatusFilter('all'); setContractFilter('all') }}>
            Réinitialiser
          </button>
        )}
        <span className="ol-count-badge">{filtered.length} offre{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {/* ── Grille d'offres ── */}
      {loading ? (
        <div className="ol-loading">
          <div className="ol-spinner" />
          Chargement des offres…
        </div>
      ) : filtered.length === 0 ? (
        <div className="ol-empty">
          <div className="ol-empty-icon">📋</div>
          <p>{offers.length === 0 ? 'Aucune offre pour le moment.' : 'Aucune offre ne correspond à votre recherche.'}</p>
          {isAdmin && offers.length === 0 && (
            <Link to="/offers/new" className="btn-primary" style={{ marginTop: 12 }}>
              Créer la première offre
            </Link>
          )}
        </div>
      ) : (
        <>
          {/* ── Vue cartes ── */}
          <div className="ol-grid">
            {filtered.map(o => {
              const cnt         = o.candidate_count ?? 0
              const statusLabel = STATUS_LABEL[o.status] || o.status
              const statusCls   = STATUS_CLS[o.status] || 'status-draft'
              const assigned    = o.assigned_recruiter_ids?.length ?? 0
              const newCount    = getNewCount(o.id, cnt)
              // Pas de badge "nouveau" si l'offre est déjà traitée (entretiens lancés)
              const hasNew      = newCount > 0 && !o.has_interviews
              const quality     = matchQuality(o)

              const handleCardClick = () => {
                markOfferSeen(o.id, cnt)
                navigate(`/offers/${o.id}`)
              }

              return (
                <article
                  key={o.id}
                  className={`ol-card ${hasNew ? 'ol-card--has-new' : ''}`}
                  onClick={handleCardClick}
                >
                  {/* ── Badge "nouveaux candidats" ── */}
                  {hasNew && (
                    <div className="ol-new-badge">
                      <span className="ol-new-dot" />
                      +{newCount} nouveau{newCount > 1 ? 'x' : ''}
                    </div>
                  )}

                  <div className="ol-card-head">
                    <div className="ol-card-badges">
                      <span className={`status-badge ${statusCls}`}>{statusLabel}</span>
                      {o.type_contrat && <span className="ol-tag-contract">{o.type_contrat}</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span
                        className={`ol-quality-badge ol-quality-${quality.level}`}
                        title={quality.issues.length > 0 ? `Problèmes : ${quality.issues.join(' · ')}` : 'Offre optimisée pour le matching'}
                      >
                        {quality.level === 'good' ? '✓ Prêt' : quality.level === 'partial' ? '⚠ Partiel' : '✕ Incomplet'}
                      </span>
                      <div className="ol-cand-box">
                        <span className="ol-cand-num">{cnt}</span>
                        <span className="ol-cand-lbl">candidat{cnt !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                  </div>

                  <h3 className="ol-card-title">{o.titre}</h3>
                  {o.localisation && <div className="ol-card-loc">📍 {o.localisation}</div>}

                  {o.competences_requises?.length > 0 && (
                    <div className="chips">
                      {o.competences_requises.slice(0, 5).map((c, i) => (
                        <span key={i} className="chip">{c}</span>
                      ))}
                      {o.competences_requises.length > 5 && (
                        <span className="chip ol-chip-more">+{o.competences_requises.length - 5}</span>
                      )}
                    </div>
                  )}

                  <div className="ol-card-footer">
                    <span className="ol-card-date">
                      {o.created_at ? new Date(o.created_at).toLocaleDateString('fr-FR') : '—'}
                    </span>

                    {/* ── Bouton assignation recruteurs (admin only) ── */}
                    {isAdmin && (
                      <button
                        className={`ol-assign-btn ${assigned > 0 ? 'ol-assign-btn--active' : ''}`}
                        title="Gérer les accès recruteurs"
                        onClick={e => { e.stopPropagation(); setModalOffer(o) }}
                      >
                        🔑 {assigned > 0
                          ? `${assigned} recruteur${assigned > 1 ? 's' : ''}`
                          : 'Assigner'}
                      </button>
                    )}

                    <span className="ol-card-link">Voir →</span>
                  </div>
                </article>
              )
            })}
          </div>

          {/* ── Vue tableau détaillée ── */}
          <div className="offers-table-wrap" style={{ marginTop: 28 }}>
            <div className="offers-table-title">Vue détaillée</div>
            <table className="offers-table">
              <thead>
                <tr>
                  <th>Offre</th>
                  <th>Localisation</th>
                  <th>Contrat</th>
                  <th>Compétences</th>
                  <th>Candidats</th>
                  <th>Statut</th>
                  {isAdmin && <th>Recruteurs</th>}
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(o => {
                  const rowCnt = o.candidate_count ?? 0
                  // Pas de badge "nouveau" si l'offre est déjà traitée (entretiens lancés)
                  const rowNew = o.has_interviews ? 0 : getNewCount(o.id, rowCnt)
                  return (
                  <tr
                    key={`${o.id}-row`}
                    style={{ cursor: 'pointer' }}
                    className={rowNew > 0 ? 'tr-has-new' : ''}
                    onClick={() => { markOfferSeen(o.id, rowCnt); navigate(`/offers/${o.id}`) }}
                  >
                    <td className="td-title">
                      {o.titre}
                      {rowNew > 0 && <span className="td-new-badge">+{rowNew} nouveau{rowNew > 1 ? 'x' : ''}</span>}
                      {o.description && (
                        <div className="td-sub">{o.description.slice(0, 80)}{o.description.length > 80 ? '…' : ''}</div>
                      )}
                    </td>
                    <td>{o.localisation || '—'}</td>
                    <td>{o.type_contrat || '—'}</td>
                    <td>
                      {o.competences_requises?.length ? (
                        <div className="chips compact">
                          {o.competences_requises.slice(0, 3).map((c, i) => (
                            <span key={i} className="chip">{c}</span>
                          ))}
                          {o.competences_requises.length > 3 && (
                            <span className="chip">+{o.competences_requises.length - 3}</span>
                          )}
                        </div>
                      ) : '—'}
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: rowCnt > 0 ? '#F7941D' : '#94a3b8' }}>
                        {rowCnt}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${STATUS_CLS[o.status] || 'status-draft'}`}>
                        {STATUS_LABEL[o.status] || o.status}
                      </span>
                    </td>
                    {isAdmin && (
                      <td onClick={e => e.stopPropagation()}>
                        <button
                          className={`ol-assign-btn ${(o.assigned_recruiter_ids?.length ?? 0) > 0 ? 'ol-assign-btn--active' : ''}`}
                          onClick={() => setModalOffer(o)}
                        >
                          🔑 {(o.assigned_recruiter_ids?.length ?? 0) > 0
                            ? `${o.assigned_recruiter_ids.length} recruteur${o.assigned_recruiter_ids.length > 1 ? 's' : ''}`
                            : 'Assigner'}
                        </button>
                      </td>
                    )}
                    <td>{o.created_at ? new Date(o.created_at).toLocaleDateString('fr-FR') : '—'}</td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ── Modal assignation recruteurs ── */}
      {modalOffer && (
        <RecruiterModal
          offer={modalOffer}
          onClose={() => setModalOffer(null)}
          onSaved={handleAssignSaved}
        />
      )}
    </div>
  )
}
