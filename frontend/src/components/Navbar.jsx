import { Link, useLocation } from 'react-router-dom'
import './Navbar.css'

function Navbar() {
  const location = useLocation()

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="brand-icon">🎯</span>
        <span className="brand-name">3S TalentMatch</span>
      </div>
      <ul className="navbar-links">
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
      </ul>
    </nav>
  )
}

export default Navbar
