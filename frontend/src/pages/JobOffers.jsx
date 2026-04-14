import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './JobOffers.css'

function JobOffers() {
  const [offers, setOffers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState('')
  const [openOffer, setOpenOffer] = useState(null)
  const [applications, setApplications] = useState({})
  const [loadingApps, setLoadingApps] = useState(null)
  const [form, setForm] = useState({
    titre: '',
    description: '',
    competences: '',
    localisation: '',
    type_contrat: '',
    status: 'active',
  })

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
    }
    api.post('/offers', payload)
      .then(() => {
        setForm({ titre: '', description: '', competences: '', localisation: '', type_contrat: '', status: 'active' })
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
      <header className="offers-header">
        <h1>Offres d'emploi</h1>
        <p>Créez et gérez vos offres.</p>
      </header>

      {error && <div className="alert error">❌ {error}</div>}
      {success && <div className="alert success">✅ {success}</div>}

      <section className="offers-card">
        <h2>Nouvelle offre</h2>
        <form className="offers-form" onSubmit={handleCreate}>
          <input placeholder="Titre" value={form.titre} onChange={e => setForm(f => ({ ...f, titre: e.target.value }))} required />
          <input placeholder="Localisation" value={form.localisation} onChange={e => setForm(f => ({ ...f, localisation: e.target.value }))} />
          <input placeholder="Type de contrat" value={form.type_contrat} onChange={e => setForm(f => ({ ...f, type_contrat: e.target.value }))} />
          <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
            <option value="active">Active</option>
            <option value="draft">Brouillon</option>
            <option value="closed">Clôturée</option>
          </select>
          <textarea placeholder="Description" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          <textarea placeholder="Compétences (séparées par virgules)" value={form.competences} onChange={e => setForm(f => ({ ...f, competences: e.target.value }))} />
          <button className="btn-primary" type="submit">Créer l'offre</button>
        </form>
      </section>

      <section className="offers-card">
        <h2>Mes offres</h2>
        {loading ? (
          <div className="loading">⏳ Chargement...</div>
        ) : (
          <div className="offers-list">
            {offers.length === 0 ? (
              <div className="empty-state">Aucune offre pour le moment.</div>
            ) : (
              offers.map(o => (
                <div key={o.id} className="offer-item">
                  <div>
                    <h3>{o.titre}</h3>
                    <p className="muted">{o.localisation || '—'} • {o.type_contrat || '—'}</p>
                    {o.competences_requises?.length ? (
                      <div className="chips">
                        {o.competences_requises.map((c, idx) => (
                          <span key={idx} className="chip">{c}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className="offer-actions">
                    <select value={o.status} onChange={e => handleStatus(o.id, e.target.value)}>
                      <option value="active">Active</option>
                      <option value="draft">Brouillon</option>
                      <option value="closed">Clôturée</option>
                    </select>
                    <button className="btn-light" onClick={() => toggleApplications(o.id)}>
                      {openOffer === o.id ? 'Masquer candidatures' : 'Voir candidatures'}
                    </button>
                    <button className="danger" onClick={() => handleDelete(o.id)}>Supprimer</button>
                  </div>

                  {openOffer === o.id && (
                    <div className="offer-applications">
                      {loadingApps === o.id ? (
                        <div className="loading">⏳ Chargement...</div>
                      ) : (
                        (applications[o.id] || []).length === 0 ? (
                          <div className="empty-state">Aucune candidature pour cette offre.</div>
                        ) : (
                          <div className="applications-list">
                            {(applications[o.id] || []).map(app => (
                              <div key={app.id} className="application-row">
                                <div>
                                  <div className="app-name">{app.candidate_name || 'Candidat'}</div>
                                  <div className="app-email">{app.candidate_email || '—'}</div>
                                </div>
                                <div className="app-actions">
                                  {app.cv_id ? (
                                    <Link
                                      className="btn-light"
                                      to={`/candidates/${app.cv_id}`}
                                      title="Voir les extractions du CV"
                                    >
                                      👁 CV
                                    </Link>
                                  ) : null}
                                  <select
                                    value={app.status}
                                    onChange={e => updateApplicationStatus(o.id, app.id, e.target.value)}
                                  >
                                    <option value="pending">En attente</option>
                                    <option value="accepted">Accepté</option>
                                    <option value="rejected">Refusé</option>
                                  </select>
                                </div>
                              </div>
                            ))}
                          </div>
                        )
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </section>
    </div>
  )
}

export default JobOffers
