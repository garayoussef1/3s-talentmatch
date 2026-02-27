import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import axios from 'axios'
import './Home.css'

function Home() {
  const [stats, setStats] = useState({ cvs: '…', offres: '—', matchings: '—' })

  useEffect(() => {
    axios.get('/api/candidates')
      .then(res => setStats(s => ({ ...s, cvs: res.data.total })))
      .catch(() => setStats(s => ({ ...s, cvs: '?' })))
  }, [])

  return (
    <div className="home-page">
      <div className="hero">
        <h1>Bienvenue sur <span className="accent">3S TalentMatch</span></h1>
        <p>Plateforme intelligente de matching CV ↔ Offres d'emploi</p>
      </div>

      <div className="cards-grid">
        <div className="stat-card">
          <span className="stat-icon">📄</span>
          <h3>CVs uploadés</h3>
          <p className="stat-value">{stats.cvs}</p>
        </div>
        <div className="stat-card">
          <span className="stat-icon">💼</span>
          <h3>Offres actives</h3>
          <p className="stat-value">{stats.offres}</p>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🎯</span>
          <h3>Matchings</h3>
          <p className="stat-value">{stats.matchings}</p>
        </div>
      </div>

      <div className="actions">
        <Link to="/upload" className="btn-primary">
          📤 Uploader un CV
        </Link>
        <Link to="/candidates" className="btn-secondary">
          👥 Voir les candidats
        </Link>
      </div>
    </div>
  )
}

export default Home
