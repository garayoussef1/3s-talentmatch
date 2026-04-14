import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import api from '../services/api'
import './Home.css'

function Home() {
  const { user } = useAuth()
  const role = (user?.role ?? '').toString().trim().toLowerCase()
  const isCandidat = role === 'candidat'
  const [stats, setStats] = useState({ cvs: '…', offres: '—', matchings: '—', myApps: '…' })

  useEffect(() => {
    if (isCandidat) {
      // Candidat : afficher nombre de ses candidatures
      api.get('/my-applications')
        .then(res => setStats(s => ({ ...s, myApps: res.data.total })))
        .catch(() => setStats(s => ({ ...s, myApps: '?' })))
    } else {
      // Recruteur/admin
      api.get('/candidates')
        .then(res => setStats(s => ({ ...s, cvs: res.data.total })))
        .catch(() => setStats(s => ({ ...s, cvs: '?' })))
    }
  }, [isCandidat])

  return (
    <div className="home-page">
      <div className="hero">
        <h1>Bienvenue, <span className="accent">{user?.prenom || 'Utilisateur'}</span></h1>
        <p>
          {isCandidat
            ? 'Uploadez votre CV et suivez l\'état de vos candidatures.'
            : 'Plateforme intelligente de matching CV ↔ Offres d\'emploi'}
        </p>
      </div>

      <div className="cards-grid">
        {isCandidat ? (
          <>
            <div className="stat-card">
              <span className="stat-icon">📄</span>
              <h3>Mes CVs soumis</h3>
              <p className="stat-value">{stats.myApps}</p>
            </div>
            <div className="stat-card">
              <span className="stat-icon">⏳</span>
              <h3>Statut</h3>
              <p className="stat-value-sm">Consultez vos candidatures</p>
            </div>
          </>
        ) : (
          <>
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
          </>
        )}
      </div>

      <div className="actions">
        <Link to="/upload" className="btn-primary">
          📤 Uploader un CV
        </Link>
        {isCandidat ? (
          <Link to="/my-applications" className="btn-secondary">
            📋 Mes Candidatures
          </Link>
        ) : (
          <Link to="/candidates" className="btn-secondary">
            👥 Voir les candidats
          </Link>
        )}
      </div>
    </div>
  )
}

export default Home
