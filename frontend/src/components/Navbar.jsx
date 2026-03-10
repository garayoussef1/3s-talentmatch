import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './Navbar.css'

function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isAuthenticated, user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="brand-icon">🎯</span>
        <span className="brand-name">3S TalentMatch</span>
      </div>

      <ul className="navbar-links">
        {isAuthenticated ? (
          <>
            <li>
              <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
                Tableau de bord
              </Link>
            </li>
            <li>
              <Link to="/upload" className={location.pathname === '/upload' ? 'active' : ''}>
                Uploader un CV
              </Link>
            </li>
            <li>
              <Link to="/candidates" className={location.pathname === '/candidates' ? 'active' : ''}>
                Candidats
              </Link>
            </li>
          </>
        ) : null}
      </ul>

      <div className="navbar-auth">
        {isAuthenticated ? (
          <div className="user-menu">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" className="user-avatar" />
            ) : (
              <span className="user-avatar-placeholder">
                {(user?.prenom?.[0] || '') + (user?.nom?.[0] || '')}
              </span>
            )}
            <span className="user-name">{user?.prenom} {user?.nom}</span>
            <span className="user-role">{user?.role}</span>
            <button className="btn-logout" onClick={handleLogout}>
              Déconnexion
            </button>
          </div>
        ) : (
          <div className="auth-links">
            <Link to="/login" className={location.pathname === '/login' ? 'active' : ''}>
              Connexion
            </Link>
            <Link to="/register" className="btn-register">
              Inscription
            </Link>
          </div>
        )}
      </div>
    </nav>
  )
}

export default Navbar
