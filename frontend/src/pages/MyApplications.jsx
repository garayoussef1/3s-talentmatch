import { useEffect, useState } from 'react'
import api from '../services/api'
import './MyApplications.css'

const STATUS_MAP = {
  pending: { label: 'En attente', icon: '⏳', className: 'status-pending' },
  reviewed: { label: 'En cours', icon: '📝', className: 'status-pending' },
  accepted: { label: 'Accepté', icon: '✅', className: 'status-accepted' },
  rejected: { label: 'Refusé', icon: '❌', className: 'status-rejected' },
}

function MyApplications() {
  const [applications, setApplications] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .get('/my-applications/offers')
      .then((res) => {
        setApplications(res.data.applications)
        setTotal(res.data.total)
      })
      .catch(() => setError('Impossible de charger vos candidatures.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="my-applications-page">
      <div className="page-header">
        <h1>Mes Candidatures</h1>
        <span className="badge">{total} au total</span>
      </div>
      <p className="subtitle">
        Suivez l'état de vos CVs soumis. Un recruteur mettra à jour votre statut.
      </p>

      {loading && <div className="loading">⏳ Chargement…</div>}
      {error && <div className="alert error">❌ {error}</div>}

      {!loading && !error && applications.length === 0 && (
        <div className="empty-state">
          <span>📂</span>
          <p>
            Aucune candidature pour l'instant.
            <br />
            <a href="/jobs">Postulez a une offre</a> pour commencer.
          </p>
        </div>
      )}

      {applications.length > 0 && (
        <div className="applications-grid">
          {applications.map((app) => {
            const st = STATUS_MAP[app.status] || STATUS_MAP.pending
            return (
              <div key={app.application_id} className="application-card">
                <div className="card-top">
                  <span className="file-icon">📄</span>
                  <div className="card-info">
                    <h3>{app.offer_title || 'Offre'}</h3>
                    <p className="card-date">
                      {app.created_at
                        ? new Date(app.created_at).toLocaleDateString('fr-FR', {
                            day: 'numeric',
                            month: 'long',
                            year: 'numeric',
                          })
                        : '—'}
                    </p>
                  </div>
                </div>
                <p className="card-nom">📍 {app.offer_location || '—'} • {app.offer_type || '—'}</p>
                <div className={`status-badge ${st.className}`}>
                  {st.icon} {st.label}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default MyApplications
