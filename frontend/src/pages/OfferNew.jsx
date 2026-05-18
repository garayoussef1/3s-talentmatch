import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'
import './Offers.css'

const today = () => new Date().toISOString().slice(0, 10)

export default function OfferNew() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    titre: '', entreprise: '', description: '', competences: '', competences_apr: '',
    localisation: '', type_contrat: '', nb_postes: 1, experience_requise: '', status: 'active', date_limite: '',
  })
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState(null)
  const [loading, setLoading]   = useState(false)

  const set = (k, v) => {
    setForm(f => ({ ...f, [k]: v }))
    setErrors(e => ({ ...e, [k]: null }))
  }

  const validate = () => {
    const e = {}
    if (!form.titre.trim()) e.titre = 'Le titre est obligatoire.'
    if (form.titre.trim().length < 3) e.titre = 'Le titre doit contenir au moins 3 caractères.'
    const nb = parseInt(form.nb_postes)
    if (isNaN(nb) || nb < 1) e.nb_postes = 'Minimum 1 poste.'
    if (nb > 20) e.nb_postes = 'Maximum 20 postes.'
    if (form.date_limite && form.date_limite < today()) {
      e.date_limite = 'La date limite ne peut pas être dans le passé.'
    }
    return e
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setApiError(null)
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setLoading(true)
    const payload = {
      titre: form.titre.trim(),
      entreprise: form.entreprise.trim() || null,
      description: form.description || null,
      competences_requises: form.competences
        ? form.competences.split(',').map(s => s.trim()).filter(Boolean)
        : [],
      competences_appreciees: form.competences_apr
        ? form.competences_apr.split(',').map(s => s.trim()).filter(Boolean)
        : [],
      localisation: form.localisation || null,
      type_contrat: form.type_contrat || null,
      nb_postes: parseInt(form.nb_postes) || 1,
      experience_requise: form.experience_requise ? parseInt(form.experience_requise) : null,
      status: form.status,
      date_limite: form.date_limite ? new Date(form.date_limite).toISOString() : null,
    }
    api.post('/offers', payload)
      .then(res => navigate(`/offers/${res.data.id}`))
      .catch(() => setApiError("Erreur lors de la création. Vérifiez votre connexion."))
      .finally(() => setLoading(false))
  }

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <div>
          <Link to="/offers" className="btn-back">← Retour aux offres</Link>
          <h1 style={{ marginTop: 10 }}>Nouvelle offre</h1>
        </div>
      </div>

      {apiError && <div className="alert error">{apiError}</div>}

      <div className="offer-form-card">
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-grid">

            <div className="form-group form-full">
              <label>Titre du poste *</label>
              <input
                placeholder="ex: Développeur React Native"
                value={form.titre}
                onChange={e => set('titre', e.target.value)}
                className={errors.titre ? 'input-error' : ''}
              />
              {errors.titre && <span className="field-error">{errors.titre}</span>}
            </div>

            <div className="form-group form-full">
              <label>Entreprise <span style={{color:'#9ca3af', fontWeight:400}}>(optionnel)</span></label>
              <input
                placeholder="ex: Clinique Internationale de Tunis"
                value={form.entreprise}
                onChange={e => set('entreprise', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label>Localisation</label>
              <input placeholder="ex: Tunis" value={form.localisation} onChange={e => set('localisation', e.target.value)} />
            </div>

            <div className="form-group">
              <label>Type de contrat</label>
              <input placeholder="ex: CDI, Stage, Freelance" value={form.type_contrat} onChange={e => set('type_contrat', e.target.value)} />
            </div>

            <div className="form-group">
              <label>Expérience requise <span style={{color:'#9ca3af', fontWeight:400}}>(années minimum)</span></label>
              <input
                type="number" min="0" max="30"
                placeholder="ex: 3"
                value={form.experience_requise}
                onChange={e => set('experience_requise', e.target.value)}
                style={{ width: 120 }}
              />
            </div>

            <div className="form-group">
              <label>Nombre de postes</label>
              <input
                type="number" min="1" max="20"
                value={form.nb_postes}
                onChange={e => set('nb_postes', e.target.value)}
                className={errors.nb_postes ? 'input-error' : ''}
                style={{ width: 100 }}
              />
              {errors.nb_postes && <span className="field-error">{errors.nb_postes}</span>}
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
              <textarea
                placeholder="Décrivez le poste, les missions, le profil recherché…"
                value={form.description}
                onChange={e => set('description', e.target.value)}
                style={{ minHeight: 120 }}
              />
            </div>

            <div className="form-group form-full">
              <label>
                Compétences obligatoires
                <span style={{color:'#9ca3af', fontWeight:400}}> — requises pour le poste (séparées par des virgules)</span>
              </label>
              <textarea
                placeholder="ex: React, Node.js, Python, SQL"
                value={form.competences}
                onChange={e => set('competences', e.target.value)}
              />
            </div>

            <div className="form-group form-full">
              <label>
                Compétences appréciées
                <span style={{color:'#9ca3af', fontWeight:400}}> — un plus, non bloquant (séparées par des virgules)</span>
              </label>
              <textarea
                placeholder="ex: Docker, GraphQL, TypeScript"
                value={form.competences_apr}
                onChange={e => set('competences_apr', e.target.value)}
                style={{ borderColor: '#a78bfa' }}
              />
            </div>

            <div className="form-group">
              <label>Date limite de candidature <span style={{color:'#9ca3af', fontWeight:400}}>(optionnel)</span></label>
              <input
                type="date"
                min={today()}
                value={form.date_limite}
                onChange={e => set('date_limite', e.target.value)}
                className={errors.date_limite ? 'input-error' : ''}
              />
              {errors.date_limite && <span className="field-error">{errors.date_limite}</span>}
            </div>

          </div>
          <div className="form-actions" style={{ marginTop: 20 }}>
            <button className="btn-primary" type="submit" disabled={loading}>
              {loading ? 'Création…' : "Créer l'offre"}
            </button>
            <Link to="/offers" className="btn-secondary">Annuler</Link>
          </div>
        </form>
      </div>
    </div>
  )
}
