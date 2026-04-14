import { useEffect, useRef, useState } from 'react'
import api from '../services/api'
import './CandidateOffers.css'

function CandidateOffers() {
  const [offers, setOffers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(null)
  const [success, setSuccess] = useState('')
  const fileInputRef = useRef(null)
  const [selectedOffer, setSelectedOffer] = useState(null)

  const fetchOffers = () => {
    setLoading(true)
    setError(null)
    api.get('/offers/public')
      .then(res => setOffers(res.data.offers || []))
      .catch(() => setError("Impossible de charger les offres."))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchOffers()
  }, [])

  const triggerApply = (offerId) => {
    setSelectedOffer(offerId)
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file || !selectedOffer) return
    setUploading(selectedOffer)
    setSuccess('')
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    api.post(`/upload-cv?offer_id=${selectedOffer}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // OCR/NLP peut dépasser le timeout global (8s).
      timeout: 120000,
    })
      .then(() => {
        setSuccess("Candidature envoyee avec succes.")
      })
      .catch(() => setError("Erreur lors de l'envoi de la candidature."))
      .finally(() => {
        setUploading(null)
        setSelectedOffer(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
      })
  }

  return (
    <div className="candidate-offers-page">
      <header className="page-hero">
        <div>
          <span className="eyebrow">Offres</span>
          <h1>Offres disponibles</h1>
          <p>Choisissez une offre et postulez avec votre CV.</p>
        </div>
        <div className="hero-chip">{offers.length} offres actives</div>
      </header>

      {error && <div className="alert error">❌ {error}</div>}
      {success && <div className="alert success">✅ {success}</div>}

      {loading ? (
        <div className="loading">⏳ Chargement...</div>
      ) : (
        <div className="offers-grid">
          {offers.map(offer => (
            <article key={offer.id} className="offer-card">
              <div className="offer-head">
                <h3>{offer.titre}</h3>
                <span className="status-pill status-active">Active</span>
              </div>
              <p className="offer-meta">{offer.localisation || '—'} • {offer.type_contrat || '—'}</p>
              {offer.description && <p className="offer-desc">{offer.description}</p>}
              {offer.competences_requises?.length ? (
                <div className="chips">
                  {offer.competences_requises.map((c, idx) => (
                    <span key={idx} className="chip">{c}</span>
                  ))}
                </div>
              ) : null}
              <button
                className="btn-primary"
                onClick={() => triggerApply(offer.id)}
                disabled={uploading === offer.id}
              >
                {uploading === offer.id ? 'Envoi...' : 'Postuler'}
              </button>
            </article>
          ))}
        </div>
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

export default CandidateOffers
