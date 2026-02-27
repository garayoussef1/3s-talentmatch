import { useEffect, useState } from 'react'
import axios from 'axios'
import './Candidates.css'

function Candidates() {
  const [candidates, setCandidates] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchCandidates = () => {
    setLoading(true)
    axios.get('/api/candidates')
      .then(res => {
        setCandidates(res.data.candidates)
        setTotal(res.data.total)
      })
      .catch(() => setError('Impossible de charger les candidats.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchCandidates() }, [])

  return (
    <div className="candidates-page">
      <div className="page-header">
        <h1>Candidats</h1>
        <span className="badge">{total} au total</span>
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
                <th>Méthode</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map(c => (
                <tr key={c.cv_id}>
                  <td className="filename">📄 {c.filename}</td>
                  <td>{c.nom || <span className="empty">—</span>}</td>
                  <td>{c.email || <span className="empty">—</span>}</td>
                  <td><span className="method-badge">{c.extraction_method}</span></td>
                  <td className="date">{c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : '—'}</td>
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
