import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './Candidates.css'

const STATUS_LABELS = {
  en_attente: { label: 'En attente', icon: '⏳' },
  accepte: { label: 'Accepté', icon: '✅' },
  refuse: { label: 'Refusé', icon: '❌' },
}

function Candidates() {
  const [candidates, setCandidates] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const fetchCandidates = () => {
    setLoading(true)
    setError(null)
    api.get('/candidates')
      .then(res => {
        setCandidates(res.data.candidates)
        setTotal(res.data.total)
      })
      .catch(() => setError('Impossible de charger les candidats.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchCandidates()

    const onFocus = () => fetchCandidates()
    const onVisibility = () => {
      if (document.visibilityState === 'visible') fetchCandidates()
    }

    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  const handleDelete = (cvId) => {
    if (!window.confirm('Supprimer ce candidat ?')) return
    setDeleting(cvId)
    api.delete(`/candidates/${cvId}`)
      .then(() => fetchCandidates())
      .catch(() => setError('Erreur lors de la suppression.'))
      .finally(() => setDeleting(null))
  }

  const handleDeleteAll = () => {
    if (!window.confirm(`Supprimer les ${total} candidat(s) ? Cette action est irréversible.`)) return
    setDeleting('all')
    api.delete('/candidates')
      .then(() => fetchCandidates())
      .catch(() => setError('Erreur lors de la suppression.'))
      .finally(() => setDeleting(null))
  }

  const renderStatus = (statusValue) => {
    const normalized = statusValue || 'en_attente'
    const meta = STATUS_LABELS[normalized] || STATUS_LABELS.en_attente
    return (
      <span className={`status-badge status-${normalized}`}>{meta.icon} {meta.label}</span>
    )
  }

  return (
    <div className="candidates-page">
      <div className="page-header">
        <h1>Candidats</h1>
        <span className="badge">{total} au total</span>
        {total > 0 && (
          <button
            className="btn-delete-all"
            onClick={handleDeleteAll}
            disabled={deleting === 'all'}
          >
            {deleting === 'all' ? '⏳ Suppression...' : '🗑 Supprimer tout'}
          </button>
        )}
      </div>
      <p className="subtitle">Liste des candidats extraits depuis les CVs uploadés.</p>

      {loading && <div className="loading">⏳ Chargement...</div>}
      {error && <div className="alert error">❌ {error}</div>}

      {!loading && !error && candidates.length === 0 && (
        <div className="empty-state">
          <span>📂</span>
          <p>Aucun candidat pour l'instant.<br />Uploadez un CV pour commencer.</p>
        </div>
      )}

      {candidates.length > 0 && (
        <div className="candidates-table-wrap">
          <table className="candidates-table">
            <thead>
              <tr>
                <th>Fichier</th>
                <th>Nom</th>
                <th>Email</th>
                <th>Offre</th>
                <th>Méthode</th>
                <th>Statut</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map(c => (
                <tr key={c.cv_id}>
                  <td className="filename">📄 {c.filename}</td>
                  <td>{c.nom || <span className="empty">—</span>}</td>
                  <td>{c.email || <span className="empty">—</span>}</td>
                  <td>
                    {c.offer_titles?.length ? (
                      <div className="offer-badges">
                        {c.offer_titles.map((title, idx) => (
                          <span key={`${c.cv_id}-${idx}`} className="offer-badge">
                            {title}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="empty">—</span>
                    )}
                  </td>
                  <td><span className="method-badge">{c.extraction_method}</span></td>
                  <td>
                    {renderStatus(c.candidature_status)}
                  </td>
                  <td className="date">{c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : '—'}</td>
                  <td>
                    <Link
                      className="btn-view"
                      to={`/candidates/${c.cv_id}`}
                      title="Voir les extractions"
                    >
                      👁
                    </Link>
                    <button
                      className="btn-delete"
                      onClick={() => handleDelete(c.cv_id)}
                      disabled={deleting === c.cv_id}
                      title="Supprimer ce candidat"
                    >
                      {deleting === c.cv_id ? '⏳' : '🗑'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default Candidates
