import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import './CandidateOffers.css'

const CONTRACT_META = {
  CDI:       { color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe' },
  CDD:       { color: '#d97706', bg: '#fffbeb', border: '#fde68a' },
  Stage:     { color: '#059669', bg: '#f0fdf4', border: '#86efac' },
  Freelance: { color: '#7c3aed', bg: '#f5f3ff', border: '#c4b5fd' },
  Alternance:{ color: '#db2777', bg: '#fdf2f8', border: '#fbcfe8' },
}
const DEFAULT_META = { color: '#475569', bg: '#f8fafc', border: '#e2e8f0' }

function deadlineBadge(date_limite) {
  if (!date_limite) return null
  const dl = new Date(date_limite)
  const now = new Date()
  const daysLeft = Math.ceil((dl - now) / (1000 * 60 * 60 * 24))
  if (daysLeft < 0) return { label: 'Clôturée', color: '#64748b', bg: '#f1f5f9' }
  if (daysLeft <= 3) return { label: `⚠ Expire dans ${daysLeft}j`, color: '#dc2626', bg: '#fef2f2' }
  if (daysLeft <= 7) return { label: `⏳ ${daysLeft} jours restants`, color: '#d97706', bg: '#fffbeb' }
  return { label: `📅 Limite : ${dl.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}`, color: '#475569', bg: '#f8fafc' }
}

function contractMeta(type) {
  if (!type) return DEFAULT_META
  const key = Object.keys(CONTRACT_META).find(k => type.toLowerCase().includes(k.toLowerCase()))
  return key ? CONTRACT_META[key] : DEFAULT_META
}

const CONTRACT_TYPES = ['Tous', 'CDI', 'CDD', 'Stage', 'Alternance', 'Freelance']

function OfferCard({ offer, onOpen }) {
  const meta = contractMeta(offer.type_contrat)
  const skills = offer.competences_requises || []
  const visibleSkills = skills.slice(0, 4)
  const extraSkills = skills.length - 4

  return (
    <article className="co-card" onClick={() => onOpen(offer.id)}>
      <div className="co-card-accent" style={{ background: meta.color }} />

      <div className="co-card-body">
        {/* Badges */}
        <div className="co-badges">
          {offer.type_contrat && (
            <span className="co-badge"
              style={{ color: meta.color, background: meta.bg, borderColor: meta.border }}>
              {offer.type_contrat}
            </span>
          )}
          {offer.localisation && (
            <span className="co-badge co-badge-loc">
              📍 {offer.localisation}
            </span>
          )}
          {offer.nb_postes > 1 && (
            <span className="co-badge co-badge-postes">
              {offer.nb_postes} postes
            </span>
          )}
        </div>

        {/* Titre */}
        <h3 className="co-card-title">{offer.titre}</h3>

        {/* Description */}
        {offer.description && (
          <p className="co-card-desc">{offer.description}</p>
        )}

        {/* Compétences */}
        {visibleSkills.length > 0 && (
          <div className="co-skills">
            {visibleSkills.map((s, i) => (
              <span key={i} className="co-skill-chip">{s}</span>
            ))}
            {extraSkills > 0 && (
              <span className="co-skill-more">+{extraSkills}</span>
            )}
          </div>
        )}
      </div>

      <div className="co-card-footer">
        {(() => { const dl = deadlineBadge(offer.date_limite); return dl ? (
          <span className="co-deadline-badge" style={{ color: dl.color, background: dl.bg }}>
            {dl.label}
          </span>
        ) : (
          <span className="co-card-date">
            {offer.created_at
              ? new Date(offer.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
              : 'Récemment publiée'}
          </span>
        )})()}
        <button className="co-btn-apply"
          style={{ background: meta.color }}
          onClick={e => { e.stopPropagation(); onOpen(offer.id) }}>
          Voir & Postuler →
        </button>
      </div>
    </article>
  )
}

function OfferRow({ offer, onOpen }) {
  const meta = contractMeta(offer.type_contrat)
  const skills = (offer.competences_requises || []).slice(0, 5)

  return (
    <article className="co-row" onClick={() => onOpen(offer.id)}>
      <div className="co-row-accent" style={{ background: meta.color }} />
      <div className="co-row-main">
        <div className="co-row-top">
          <h3 className="co-row-title">{offer.titre}</h3>
          <div className="co-row-badges">
            {offer.type_contrat && (
              <span className="co-badge"
                style={{ color: meta.color, background: meta.bg, borderColor: meta.border }}>
                {offer.type_contrat}
              </span>
            )}
            {offer.localisation && (
              <span className="co-badge co-badge-loc">📍 {offer.localisation}</span>
            )}
          </div>
        </div>
        {offer.description && (
          <p className="co-row-desc">{offer.description}</p>
        )}
        <div className="co-skills" style={{ marginTop: 8 }}>
          {skills.map((s, i) => <span key={i} className="co-skill-chip">{s}</span>)}
        </div>
      </div>
      <div className="co-row-action">
        {(() => { const dl = deadlineBadge(offer.date_limite); return dl ? (
          <span className="co-deadline-badge" style={{ color: dl.color, background: dl.bg, marginBottom: 6 }}>
            {dl.label}
          </span>
        ) : null })()}
        <button className="co-btn-apply"
          style={{ background: meta.color }}
          onClick={e => { e.stopPropagation(); onOpen(offer.id) }}>
          Postuler →
        </button>
      </div>
    </article>
  )
}

export default function CandidateOffers() {
  const navigate = useNavigate()
  const [offers, setOffers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')
  const [filterType, setFilterType] = useState('Tous')
  const [viewMode, setViewMode]     = useState('grid')

  useEffect(() => {
    setLoading(true)
    api.get('/offers/public')
      .then(res => setOffers(res.data.offers || []))
      .catch(() => setError('Impossible de charger les offres.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return offers.filter(o => {
      const matchType = filterType === 'Tous' ||
        (o.type_contrat || '').toLowerCase().includes(filterType.toLowerCase())
      const matchSearch = !q || [o.titre, o.description, o.localisation, o.type_contrat,
        ...(o.competences_requises || [])].filter(Boolean).join(' ').toLowerCase().includes(q)
      return matchType && matchSearch
    })
  }, [offers, search, filterType])

  const openOffer = (id) => navigate(`/jobs/${id}`)

  return (
    <div className="co-page">

      {/* ── Hero ─────────────────────────────────────────────── */}
      <div className="co-hero">
        <div className="co-hero-orb co-hero-orb-1" />
        <div className="co-hero-orb co-hero-orb-2" />
        <div className="co-hero-inner">
          <p className="co-hero-eyebrow">🎯 Votre prochaine opportunité</p>
          <h1 className="co-hero-title">Offres d'emploi</h1>
          <p className="co-hero-sub">
            Uploadez votre CV une seule fois et découvrez les offres qui correspondent à votre profil.
          </p>
          <div className="co-hero-search">
            <span className="co-search-icon">🔍</span>
            <input
              className="co-search-input"
              placeholder="Titre, compétence, localisation…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button className="co-search-clear" onClick={() => setSearch('')}>✕</button>
            )}
          </div>
          <div className="co-hero-stats">
            <span className="co-stat-pill">{offers.length} offres disponibles</span>
            <span className="co-stat-dot">·</span>
            <span className="co-stat-note">Analyse automatique de compatibilité</span>
          </div>
        </div>
      </div>

      {/* ── Toolbar ──────────────────────────────────────────── */}
      <div className="co-toolbar">
        {/* Filtres contrat */}
        <div className="co-filter-pills">
          {CONTRACT_TYPES.map(t => (
            <button key={t}
              className={`co-filter-pill ${filterType === t ? 'active' : ''}`}
              onClick={() => setFilterType(t)}>
              {t}
            </button>
          ))}
        </div>

        {/* Résultats + toggle vue */}
        <div className="co-toolbar-right">
          <span className="co-results-count">
            <strong>{filtered.length}</strong> résultat{filtered.length !== 1 ? 's' : ''}
          </span>
          <div className="co-view-toggle">
            <button className={`co-view-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')} title="Vue grille">⊞</button>
            <button className={`co-view-btn ${viewMode === 'list' ? 'active' : ''}`}
              onClick={() => setViewMode('list')} title="Vue liste">☰</button>
          </div>
        </div>
      </div>

      {/* ── Contenu ──────────────────────────────────────────── */}
      {error && (
        <div className="co-error">⚠ {error}</div>
      )}

      {loading ? (
        <div className="co-loading">
          <div className="co-spinner" />
          <span>Chargement des offres…</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="co-empty">
          <div className="co-empty-icon">📭</div>
          <p>Aucune offre ne correspond à votre recherche.</p>
          {(search || filterType !== 'Tous') && (
            <button className="co-btn-reset"
              onClick={() => { setSearch(''); setFilterType('Tous') }}>
              Réinitialiser les filtres
            </button>
          )}
        </div>
      ) : viewMode === 'grid' ? (
        <div className="co-grid">
          {filtered.map(o => <OfferCard key={o.id} offer={o} onOpen={openOffer} />)}
        </div>
      ) : (
        <div className="co-list">
          {filtered.map(o => <OfferRow key={o.id} offer={o} onOpen={openOffer} />)}
        </div>
      )}
    </div>
  )
}
