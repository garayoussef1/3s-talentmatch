import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import './MesDonnees.css'

function MesDonnees() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [applications, setApplications] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    api.get('/my-applications/offers')
      .then(res => setApplications(res.data.applications || []))
      .catch(() => setApplications([]))
  }, [])

  const downloadData = () => {
    const data = {
      utilisateur: {
        nom: user?.nom,
        prenom: user?.prenom,
        email: user?.email,
        role: user?.role,
      },
      candidatures: applications || [],
      export_date: new Date().toISOString(),
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mes-donnees-3s-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDelete = async (cvId) => {
    if (!window.confirm('Supprimer ce CV et toutes vos données associées ? Cette action est irréversible.')) return
    setDeleting(cvId)
    try {
      await api.delete(`/my-cv/${cvId}`)
      setApplications(prev => prev.filter(a => a.cv_id !== cvId))
      setMsg('CV supprimé avec succès.')
    } catch {
      setMsg('Erreur lors de la suppression.')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="mes-donnees-page">
      <div className="md-header">
        <h1>Mes données personnelles</h1>
        <p className="md-subtitle">
          Conformément au RGPD, vous pouvez consulter, exporter ou supprimer vos données à tout moment.
        </p>
      </div>

      {/* ── Informations du compte ───────────────────── */}
      <section className="md-section">
        <h2>Mon compte</h2>
        <div className="md-info-grid">
          <div className="md-info-row"><span>Prénom</span><strong>{user?.prenom || '—'}</strong></div>
          <div className="md-info-row"><span>Nom</span><strong>{user?.nom || '—'}</strong></div>
          <div className="md-info-row"><span>Email</span><strong>{user?.email || '—'}</strong></div>
          <div className="md-info-row"><span>Rôle</span><strong>{user?.role || '—'}</strong></div>
        </div>
      </section>

      {/* ── Export ───────────────────────────────────── */}
      <section className="md-section">
        <h2>Exporter mes données</h2>
        <p className="md-hint">Téléchargez l'ensemble de vos données au format JSON.</p>
        <button className="md-btn md-btn-export" onClick={downloadData}>
          Télécharger mes données (JSON)
        </button>
      </section>

      {/* ── Mes CVs / Suppression ────────────────────── */}
      <section className="md-section">
        <h2>Mes CVs</h2>
        <p className="md-hint">
          Vous pouvez supprimer un CV et toutes les données associées à tout moment.
          Cette action est définitive.
        </p>

        {msg && <div className="md-alert">{msg}</div>}

        {applications === null ? (
          <div className="md-loading">Chargement…</div>
        ) : applications.length === 0 ? (
          <p className="md-empty">Aucune candidature enregistrée.</p>
        ) : (
          <div className="md-cv-list">
            {applications.map((app, i) => (
              <div key={app.application_id || i} className="md-cv-item">
                <div className="md-cv-info">
                  <strong>{app.offer_title || 'Offre'}</strong>
                  <span className="md-cv-meta">
                    {app.cv_id && `CV : ${app.cv_id.slice(0, 8)}…`}
                    {app.created_at && ` • ${new Date(app.created_at).toLocaleDateString('fr-FR')}`}
                  </span>
                  <span className={`md-cv-status md-status-${app.status}`}>
                    {app.status === 'accepted' ? 'Accepté' : app.status === 'rejected' ? 'Refusé' : 'En attente'}
                  </span>
                </div>
                {app.cv_id && (
                  <button
                    className="md-btn md-btn-delete"
                    disabled={deleting === app.cv_id}
                    onClick={() => handleDelete(app.cv_id)}
                  >
                    {deleting === app.cv_id ? 'Suppression…' : 'Supprimer ce CV'}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="md-section md-section-info">
        <h2>Vos droits</h2>
        <ul>
          <li><strong>Droit d'accès</strong> — consultez vos données ci-dessus.</li>
          <li><strong>Droit à la portabilité</strong> — exportez vos données en JSON.</li>
          <li><strong>Droit à l'effacement</strong> — supprimez vos CVs à tout moment.</li>
          <li><strong>Contact DPO</strong> — pour toute demande : <a href="mailto:dpo@3s.tn">dpo@3s.tn</a></li>
        </ul>
      </section>

      <button className="md-btn md-btn-back" onClick={() => navigate('/')}>
        ← Retour à l'accueil
      </button>
    </div>
  )
}

export default MesDonnees
