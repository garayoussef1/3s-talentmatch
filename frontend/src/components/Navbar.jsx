import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import NotificationBell from './NotificationBell'
import logo3s from '../assets/logo_3s.png'
import './Navbar.css'

function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isAuthenticated, user, logout } = useAuth()
  const role = (user?.role ?? '').toString().trim().toLowerCase()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand" onClick={() => navigate('/')}
        role="button" tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter') navigate('/') }}>
        <img src={logo3s} alt="3S" className="brand-logo" />
        <div className="brand-text">
          <span className="brand-name">3S TalentMatch</span>
          <span className="brand-slogan">L'intelligence au service du recrutement</span>
        </div>
      </div>

      <ul className="navbar-links">
        {isAuthenticated ? (
          <>
            <li>
              <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
                Accueil
              </Link>
            </li>
            <li>
              {role !== 'candidat' && (
                <Link to="/upload" className={location.pathname === '/upload' ? 'active' : ''}>
                  Uploader un CV
                </Link>
              )}
            </li>
            {/* Candidats et extractions : recruteur/admin uniquement */}
            {role !== 'candidat' && (
              <li>
                <Link to="/candidates" className={location.pathname === '/candidates' ? 'active' : ''}>
                  Candidats
                </Link>
              </li>
            )}
            {role !== 'candidat' && (
              <li>
                <Link to="/offers" className={location.pathname === '/offers' ? 'active' : ''}>
                  Offres
                </Link>
              </li>
            )}
            {role !== 'candidat' && (
              <li>
                <Link to="/dashboard" className={location.pathname === '/dashboard' ? 'active' : ''}>
                  Dashboard
                </Link>
              </li>
            )}
            {role === 'admin' && (
              <li>
                <Link to="/admin/users" className={location.pathname === '/admin/users' ? 'active' : ''}>
                  Admin
                </Link>
              </li>
            )}
            {/* Mes candidatures : candidat uniquement */}
            {role === 'candidat' && (
              <li>
                <Link to="/jobs" className={location.pathname === '/jobs' ? 'active' : ''}>
                  Offres
                </Link>
              </li>
            )}
            {role === 'candidat' && (
              <li>
                <Link to="/my-applications" className={location.pathname === '/my-applications' ? 'active' : ''}>
                  Mes Candidatures
                </Link>
              </li>
            )}
            {role === 'candidat' && (
              <li>
                <Link to="/mes-donnees" className={location.pathname === '/mes-donnees' ? 'active' : ''}>
                  Mes Données
                </Link>
              </li>
            )}
          </>
        ) : null}
      </ul>

      <div className="navbar-auth">
        {isAuthenticated ? (
          <div className="user-menu">
            {role !== 'admin' && <NotificationBell />}
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
