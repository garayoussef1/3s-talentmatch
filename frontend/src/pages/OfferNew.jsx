import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'
import './Offers.css'

const today = () => new Date().toISOString().slice(0, 10)

const CONTRACT_TYPES = ['CDI', 'CDD', 'Stage', 'Alternance', 'Freelance']

const DOMAINES_METIER = [
  'IT / Développement',
  'Data / IA',
  'Cybersécurité',
  'Infrastructure / DevOps',
  'Santé / Médical',
  'Paramédical / Soins',
  'Finance / Comptabilité',
  'Ressources Humaines',
  'Marketing / Communication',
  'Commercial / Vente',
  'Juridique / Droit',
  'Enseignement / Formation',
  'Ingénierie / BTP',
  'Design / Création',
  'Logistique / Supply Chain',
  'Agriculture / Environnement',
  'Artisanat / Industrie',
  'Autre',
]

const NIVEAUX_SENIORITE = [
  { value: 'Stage',     label: 'Stage (étudiant)' },
  { value: 'Alternance', label: 'Alternance' },
  { value: 'Junior',    label: 'Junior (0–2 ans)' },
  { value: 'Confirmé',  label: 'Confirmé (2–5 ans)' },
  { value: 'Senior',    label: 'Senior (5–10 ans)' },
  { value: 'Expert',    label: 'Expert (10+ ans)' },
]

const FORMATION_LEVELS = [
  { value: '',   niveau: null, label: 'Non spécifié' },
  { value: 'Bac',   niveau: 0,  label: 'Bac (Bac+0)' },
  { value: 'Bac+2', niveau: 2,  label: 'Bac+2 (BTS, DUT)' },
  { value: 'Bac+3', niveau: 3,  label: 'Bac+3 (Licence)' },
  { value: 'Bac+4', niveau: 4,  label: 'Bac+4 (Master 1)' },
  { value: 'Bac+5', niveau: 5,  label: 'Bac+5 (Master, Ingénieur)' },
  { value: 'Bac+8', niveau: 8,  label: 'Bac+8 (Doctorat)' },
]

export default function OfferNew() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    titre: '', entreprise: '', description: '', competences: '', competences_apr: '',
    localisation: '', type_contrat: '', nb_postes: 1, experience_requise: '',
    formation_requise: '', domaine_metier: '', niveau_seniorite: '',
    status: 'active', date_limite: '',
  })
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState(null)
  const [loading, setLoading] = useState(false)

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
    const skills = form.competences.split(',').map(s => s.trim()).filter(Boolean)
    if (skills.length === 0) e.competences = 'Au moins une compétence requise pour un bon matching.'
    if (!form.type_contrat) e.type_contrat = 'Le type de contrat est obligatoire.'
    return e
  }

  const buildDescription = () => form.description || null

  const handleSubmit = (e) => {
    e.preventDefault()
    setApiError(null)
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setLoading(true)
    const payload = {
      titre: form.titre.trim(),
      entreprise: form.entreprise.trim() || null,
      description: buildDescription(),
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
      formation_requise_niveau: (() => {
        const found = FORMATION_LEVELS.find(f => f.value === form.formation_requise)
        return found ? found.niveau : null
      })(),
      domaine_metier: form.domaine_metier || null,
      niveau_seniorite: form.niveau_seniorite || null,
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

      {/* Bandeau qualité matching */}
      <div style={{
        background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10,
        padding: '12px 18px', marginBottom: 20, fontSize: '0.85rem', color: '#1e40af',
      }}>
        <strong>Qualité du matching IA :</strong> plus les champs ci-dessous sont remplis avec précision,
        meilleur sera le score calculé par BGE-M3 + Cross-Encoder.
        Les compétences requises et le type de contrat sont particulièrement critiques.
      </div>

      {apiError && <div className="alert error">{apiError}</div>}

      <div className="offer-form-card">
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-grid">

            {/* Titre */}
            <div className="form-group form-full">
              <label>
                Titre du poste *
                <span style={{ color: '#6b7280', fontWeight: 400, fontSize: '0.8rem', marginLeft: 8 }}>
                  — utilisé pour la détection du niveau (junior/senior) et le scoring sémantique
                </span>
              </label>
              <input
                placeholder="ex: Développeur React Native Senior"
                value={form.titre}
                onChange={e => set('titre', e.target.value)}
                className={errors.titre ? 'input-error' : ''}
              />
              {errors.titre && <span className="field-error">{errors.titre}</span>}
            </div>

            {/* Entreprise */}
            <div className="form-group form-full">
              <label>Entreprise <span style={{ color: '#9ca3af', fontWeight: 400 }}>(optionnel)</span></label>
              <input
                placeholder="ex: Clinique Internationale de Tunis"
                value={form.entreprise}
                onChange={e => set('entreprise', e.target.value)}
              />
            </div>

            {/* Localisation */}
            <div className="form-group">
              <label>Localisation</label>
              <input placeholder="ex: Tunis" value={form.localisation} onChange={e => set('localisation', e.target.value)} />
            </div>

            {/* Type de contrat — SELECT obligatoire */}
            <div className="form-group">
              <label>
                Type de contrat *
                <span style={{ color: '#6b7280', fontWeight: 400, fontSize: '0.8rem', marginLeft: 8 }}>
                  — adapte les poids du modèle (Stage → moins d'expérience requise)
                </span>
              </label>
              <select
                value={form.type_contrat}
                onChange={e => set('type_contrat', e.target.value)}
                className={errors.type_contrat ? 'input-error' : ''}
              >
                <option value="">-- Choisir --</option>
                {CONTRACT_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              {errors.type_contrat && <span className="field-error">{errors.type_contrat}</span>}
            </div>

            {/* Domaine métier */}
            <div className="form-group">
              <label>
                Domaine métier
                <span style={{ color: '#dc2626', fontWeight: 400, fontSize: '0.8rem', marginLeft: 8 }}>
                  — utilisé par l'IA pour la détection ESCO
                </span>
              </label>
              <select value={form.domaine_metier} onChange={e => set('domaine_metier', e.target.value)}>
                <option value="">-- Non spécifié --</option>
                {DOMAINES_METIER.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            {/* Niveau séniorité */}
            <div className="form-group">
              <label>
                Niveau séniorité
                <span style={{ color: '#dc2626', fontWeight: 400, fontSize: '0.8rem', marginLeft: 8 }}>
                  — adapte les poids expérience/formation
                </span>
              </label>
              <select value={form.niveau_seniorite} onChange={e => set('niveau_seniorite', e.target.value)}>
                <option value="">-- Non spécifié --</option>
                {NIVEAUX_SENIORITE.map(n => (
                  <option key={n.value} value={n.value}>{n.label}</option>
                ))}
              </select>
            </div>

            {/* Expérience requise */}
            <div className="form-group">
              <label>
                Expérience requise
                <span style={{ color: '#9ca3af', fontWeight: 400 }}> (années minimum)</span>
              </label>
              <input
                type="number" min="0" max="30"
                placeholder="ex: 3"
                value={form.experience_requise}
                onChange={e => set('experience_requise', e.target.value)}
                style={{ width: 120 }}
              />
              <span style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: 4, display: 'block' }}>
                0 = junior, 3-5 = intermédiaire, 5+ = senior
              </span>
            </div>

            {/* Niveau de formation requis */}
            <div className="form-group">
              <label>
                Niveau de formation requis
                <span style={{ color: '#6b7280', fontWeight: 400, fontSize: '0.8rem', marginLeft: 8 }}>
                  — injecté automatiquement dans la description
                </span>
              </label>
              <select value={form.formation_requise} onChange={e => set('formation_requise', e.target.value)}>
                {FORMATION_LEVELS.map(l => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>

            {/* Nombre de postes */}
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

            {/* Statut */}
            <div className="form-group">
              <label>Statut</label>
              <select value={form.status} onChange={e => set('status', e.target.value)}>
                <option value="active">Active</option>
                <option value="draft">Brouillon</option>
                <option value="closed">Clôturée</option>
              </select>
            </div>

            {/* Description */}
            <div className="form-group form-full">
              <label>
                Description
                <span style={{ color: '#6b7280', fontWeight: 400, fontSize: '0.8rem', marginLeft: 8 }}>
                  — le cross-encoder BGE-M3 lit ce texte pour le scoring sémantique
                </span>
              </label>
              <textarea
                placeholder={`Décrivez le poste, les missions et le profil recherché.\n\nExemple : "Nous recherchons un développeur backend pour rejoindre notre équipe produit. Vous serez responsable de la conception des APIs REST, de l'optimisation des requêtes SQL et de la mise en place de tests automatisés..."`}
                value={form.description}
                onChange={e => set('description', e.target.value)}
                style={{ minHeight: 140 }}
              />
              <span style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: 4, display: 'block' }}>
                Plus la description est précise (contexte métier, missions, technologies), plus le scoring sémantique sera juste.
              </span>
            </div>

            {/* Compétences requises */}
            <div className="form-group form-full">
              <label>
                Compétences obligatoires *
                <span style={{ color: '#dc2626', fontWeight: 400, fontSize: '0.8rem', marginLeft: 8 }}>
                  — dimension principale du scoring (40% du score total)
                </span>
              </label>
              <textarea
                placeholder="ex: Python, FastAPI, PostgreSQL, Docker, Git"
                value={form.competences}
                onChange={e => set('competences', e.target.value)}
                className={errors.competences ? 'input-error' : ''}
              />
              {errors.competences
                ? <span className="field-error">{errors.competences}</span>
                : <span style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: 4, display: 'block' }}>
                    Séparez par des virgules. Soyez précis : "React" plutôt que "développement web".
                  </span>
              }
            </div>

            {/* Compétences appréciées */}
            <div className="form-group form-full">
              <label>
                Compétences appréciées
                <span style={{ color: '#9ca3af', fontWeight: 400 }}> — bonus non bloquant (séparées par des virgules)</span>
              </label>
              <textarea
                placeholder="ex: GraphQL, TypeScript, Redis, Kubernetes"
                value={form.competences_apr}
                onChange={e => set('competences_apr', e.target.value)}
                style={{ borderColor: '#a78bfa' }}
              />
              <span style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: 4, display: 'block' }}>
                Ces compétences augmentent le score mais ne pénalisent pas si absentes.
              </span>
            </div>

            {/* Date limite */}
            <div className="form-group">
              <label>Date limite de candidature <span style={{ color: '#9ca3af', fontWeight: 400 }}>(optionnel)</span></label>
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
