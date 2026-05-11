import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '../services/api'
import './CandidateOfferDetail.css'

function CandidateOfferDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [offer, setOffer] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [success, setSuccess] = useState('')
  const [consentChecked, setConsentChecked] = useState(false)
  const [showApply, setShowApply] = useState(false)
  const fileInputRef = useRef(null)


  useEffect(() => {
    const loadOffer = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await api.get(`/offers/public/${id}`)
        setOffer(res.data)
      } catch {
        try {
          const res = await api.get('/offers/public')
          const found = (res.data.offers || []).find(o => o.id === id)
          if (found) {
            setOffer(found)
            setError(null)
          } else {
            setError("Offre introuvable ou inactive.")
          }
        } catch {
          setError("Impossible de charger l'offre.")
        }
      } finally {
        setLoading(false)
      }
    }

    loadOffer()
  }, [id])

  const triggerApply = () => {
    if (!consentChecked) return
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setSuccess('')
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    api.post(`/upload-cv?offer_id=${id}&information_acknowledged=true`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
      .then(() => {
        setSuccess('Candidature envoyée avec succès.')
        setShowApply(false)
      })
      .catch(() => setError("Erreur lors de l'envoi de la candidature."))
      .finally(() => {
        setUploading(false)
        if (fileInputRef.current) fileInputRef.current.value = ''
      })
  }

  return (
    <div className="candidate-offer-detail">
      <button className="btn-back" onClick={() => navigate('/jobs')}>
        ← Retour aux offres
      </button>

      {loading ? (
        <div className="loading">⏳ Chargement...</div>
      ) : error ? (
        <div className="alert error">❌ {error}</div>
      ) : !offer ? (
        <div className="empty-state">Offre introuvable.</div>
      ) : (
        <>
          <header className="detail-hero">
            <div>
              <span className="detail-tag">Offre active</span>
              <h1>{offer.titre}</h1>
              <p className="detail-meta">{offer.localisation || '—'} • {offer.type_contrat || '—'}</p>
              <div className="detail-actions">
                <button className="btn-primary" onClick={() => setShowApply(v => !v)} disabled={uploading}>
                  {uploading ? 'Envoi...' : 'Postuler maintenant'}
                </button>
                <button className="btn-secondary" onClick={() => navigate('/jobs')}>
                  Voir toutes les offres
                </button>
              </div>

              {showApply && (
                <div className="apply-consent-box">
                  <label className="consent-label">
                    <input
                      type="checkbox"
                      checked={consentChecked}
                      onChange={e => setConsentChecked(e.target.checked)}
                    />
                    <span>
                      J'ai pris connaissance que mes données personnelles (nom, email, téléphone, compétences)
                      seront traitées par 3S uniquement dans le cadre du processus de recrutement,
                      conformément à la politique de protection des données.
                    </span>
                  </label>
                  <button
                    className="btn-primary"
                    onClick={triggerApply}
                    disabled={!consentChecked || uploading}
                  >
                    {uploading ? 'Envoi...' : 'Choisir mon CV et postuler'}
                  </button>
                </div>
              )}
            </div>
          </header>

          <section className="detail-section info-cards">
            <div className="info-card">
              <div className="info-label">Statut</div>
              <div className="info-value">{offer.status || 'active'}</div>
            </div>
            <div className="info-card">
              <div className="info-label">Type de contrat</div>
              <div className="info-value">{offer.type_contrat || '—'}</div>
            </div>
            <div className="info-card">
              <div className="info-label">Localisation</div>
              <div className="info-value">{offer.localisation || '—'}</div>
            </div>
            <div className="info-card">
              <div className="info-label">Competences</div>
              <div className="info-value">{offer.competences_requises?.length || 0}</div>
            </div>
          </section>

          <section className="detail-section">
            <h2>Description</h2>
            <p>{offer.description || '—'}</p>
          </section>


          <section className="detail-section">
            <h2>Competences requises</h2>
            {offer.competences_requises?.length ? (
              <div className="chips">
                {offer.competences_requises.map((c, idx) => (
                  <span key={idx} className="chip">{c}</span>
                ))}
              </div>
            ) : (
              <p>—</p>
            )}
          </section>


          {success && <div className="alert success">✅ {success}</div>}
        </>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.png,.jpg,.jpeg"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
    </div>
  )
}

export default CandidateOfferDetail
