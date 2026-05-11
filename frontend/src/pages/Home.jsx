import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import api from '../services/api'
import logo3s from '../assets/logo_3s.png'
import './Home.css'

function Home() {
  const { user } = useAuth()
  const role = (user?.role ?? '').toString().trim().toLowerCase()
  const isCandidat = role === 'candidat'

  const [recruiterStats, setRecruiterStats] = useState({ cvs: '…', offres: '—', matchings: '—' })
  const [applications, setApplications]     = useState(null)   // null = loading
  const [activeOffers, setActiveOffers]     = useState('…')

  useEffect(() => {
    if (isCandidat) {
      api.get('/my-applications/offers')
        .then(res => setApplications(res.data.applications || []))
        .catch(() => setApplications([]))

      api.get('/offers/public')
        .then(res => setActiveOffers(res.data.total))
        .catch(() => setActiveOffers('?'))
    } else {
      api.get('/candidates')
        .then(res => setRecruiterStats(s => ({ ...s, cvs: res.data.total })))
        .catch(() => setRecruiterStats(s => ({ ...s, cvs: '?' })))
    }
  }, [isCandidat])

  const accepted = (applications || []).filter(a => a.status === 'accepted')
  const refused  = (applications || []).filter(a => a.status === 'rejected')
  const pending  = (applications || []).filter(a => a.status === 'pending')

  const firstName = user?.prenom || user?.nom?.split(' ')[0] || ''

  return (
    <div className="home-page">
      <div className="home-bg" aria-hidden="true">
        <span className="home-orb orb-1" />
        <span className="home-orb orb-2" />
        <span className="home-orb orb-3" />
        <div className="home-grid" />
      </div>

      {/* ── Hero ─────────────────────────────────────── */}
      <section className="home-hero">
        <div className="hero-copy">
          <div className="hero-badge">
            <img src={logo3s} alt="3S" />
            <span>3S TalentMatch</span>
          </div>

          {isCandidat ? (
            <>
              <h1>
                {firstName ? `Bonjour, ${firstName} 👋` : 'Bienvenue'}
                <span className="hero-accent"> Votre prochain poste vous attend.</span>
              </h1>
              <p className="hero-lead">
                Déposez votre CV, laissez notre système évaluer votre profil et suivez
                votre progression en temps réel.
              </p>
            </>
          ) : (
            <>
              <h1>
                Pilotez le recrutement avec une
                <span className="hero-accent"> intelligence sémantique</span>
              </h1>
              <p className="hero-lead">
                Analysez les CV, évaluez la pertinence et priorisez les meilleurs profils
                en quelques secondes.
              </p>
            </>
          )}

          <div className="hero-actions">
            <Link to={isCandidat ? '/jobs' : '/offers'} className="btn-primary">
              {isCandidat ? 'Voir les offres' : 'Voir les offres actives'}
            </Link>
            <Link to={isCandidat ? '/my-applications' : '/candidates'} className="btn-secondary">
              {isCandidat ? 'Mes candidatures' : 'Voir les candidats'}
            </Link>
          </div>
          <div className="hero-slogan">
            3S Group — L'intelligence au service du recrutement.
          </div>
        </div>

        <div className="hero-visual">
          {isCandidat ? (
            <div className="cand-hero-card">
              {/* Header */}
              <div className="chc-header">
                <div className="chc-avatar">
                  {firstName ? firstName[0].toUpperCase() : '?'}
                </div>
                <div>
                  <div className="chc-name">{user?.prenom} {user?.nom}</div>
                  <div className="chc-role">Candidat</div>
                </div>
                <div className="chc-pulse" />
              </div>

              {/* Mini KPIs — total + offres actives uniquement */}
              <div className="chc-kpis">
                <div className="chc-kpi">
                  <div className="chc-kpi-val">{applications === null ? '…' : applications.length}</div>
                  <div className="chc-kpi-lbl">Candidature{applications?.length !== 1 ? 's' : ''}</div>
                </div>
                <div className="chc-kpi-sep" />
                <div className="chc-kpi">
                  <div className="chc-kpi-val" style={{ color: '#22c55e' }}>{accepted.length}</div>
                  <div className="chc-kpi-lbl">Acceptée{accepted.length !== 1 ? 's' : ''}</div>
                </div>
                <div className="chc-kpi-sep" />
                <div className="chc-kpi">
                  <div className="chc-kpi-val">{activeOffers}</div>
                  <div className="chc-kpi-lbl">Offres actives</div>
                </div>
              </div>

              {/* Liste candidatures avec statuts */}
              <div className="chc-apps">
                <div className="chc-apps-title">Mes candidatures</div>

                {applications === null ? (
                  <div className="chc-apps-loading">Chargement…</div>
                ) : applications.length === 0 ? (
                  <div className="chc-apps-empty">
                    Aucune candidature pour l'instant.{' '}
                    <Link to="/jobs" className="chc-apps-link">Voir les offres →</Link>
                  </div>
                ) : (
                  <div className="chc-apps-list">
                    {applications.slice(0, 4).map((app, i) => {
                      const isAccepted = app.status === 'accepted'
                      const isRefused  = app.status === 'rejected'
                      return (
                        <div
                          key={app.id || i}
                          className={`chc-app-item ${isAccepted ? 'app-accepted' : isRefused ? 'app-refused' : 'app-pending'}`}
                        >
                          <div className="chc-app-dot" />
                          <div className="chc-app-info">
                            <span className="chc-app-offer">
                              {isAccepted ? (
                                <Link to={`/jobs/${app.offer_id}`} className="chc-offer-link">
                                  {app.offer_title}
                                </Link>
                              ) : (
                                app.offer_title
                              )}
                            </span>
                            <span className="chc-app-badge">
                              {isAccepted ? '✓ Accepté' : isRefused ? '✗ Refusé' : '⏳ En attente'}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                    {applications.length > 4 && (
                      <Link to="/my-applications" className="chc-apps-more">
                        +{applications.length - 4} autres candidatures →
                      </Link>
                    )}
                  </div>
                )}
              </div>

              <div className="chc-tip">
                Votre profil est analysé avec transparence et équité.
              </div>
            </div>
          ) : (
            <>
              <div className="visual-card">
                <div className="visual-title">Aperçu matching</div>
                <div className="visual-row">
                  <span>TalentMatch-BERT</span>
                  <div className="visual-bar">
                    <span style={{ width: '86%' }} />
                  </div>
                  <strong>86%</strong>
                </div>
                <div className="visual-row">
                  <span>Compétences</span>
                  <div className="visual-bar alt">
                    <span style={{ width: '78%' }} />
                  </div>
                  <strong>78%</strong>
                </div>
                <div className="visual-row">
                  <span>Heuristique</span>
                  <div className="visual-bar muted">
                    <span style={{ width: '64%' }} />
                  </div>
                  <strong>64%</strong>
                </div>
                <div className="visual-note">Priorité : profil data</div>
              </div>
              <div className="visual-tag">
                <span>Decision score</span>
                <strong>Appris + explicable</strong>
              </div>
            </>
          )}
        </div>
      </section>

      {/* ── Section candidat : Comment ça marche ─── */}
      {isCandidat && (
        <section className="home-how">
          <div className="how-title">Comment ça marche ?</div>
          <div className="how-steps">
            <div className="how-step">
              <div className="how-icon">📄</div>
              <div className="how-step-num">1</div>
              <h4>Parcourez les offres</h4>
              <p>Consultez les postes ouverts par 3S et trouvez celui qui correspond à votre profil.</p>
              <Link to="/jobs" className="how-link">Voir les offres →</Link>
            </div>
            <div className="how-arrow">→</div>
            <div className="how-step">
              <div className="how-icon">🚀</div>
              <div className="how-step-num">2</div>
              <h4>Déposez votre CV</h4>
              <p>Uploadez votre CV (PDF, Word ou image) et notre pipeline NLP extrait vos compétences automatiquement.</p>
            </div>
            <div className="how-arrow">→</div>
            <div className="how-step">
              <div className="how-icon">🎯</div>
              <div className="how-step-num">3</div>
              <h4>Suivez votre évaluation</h4>
              <p>Votre profil est scoré en 4 dimensions par TalentMatch-BERT. Suivez votre statut en temps réel.</p>
              <Link to="/my-applications" className="how-link">Mes candidatures →</Link>
            </div>
          </div>
        </section>
      )}

      {/* ── Stats ────────────────────────────────────── */}
      <section className="home-stats">
        {isCandidat ? (
          <>
            <div className="stat-card stat-card-green">
              <span className="stat-kicker">Acceptées</span>
              <p className="stat-value">{applications === null ? '…' : accepted.length}</p>
              <span className="stat-label">{accepted.length > 0 ? 'Félicitations !' : 'En cours d\'évaluation'}</span>
            </div>
            <div className="stat-card">
              <span className="stat-kicker">En attente</span>
              <p className="stat-value">{applications === null ? '…' : pending.length}</p>
              <span className="stat-label">Réponse prochainement</span>
            </div>
            <div className="stat-card stat-card-danger">
              <span className="stat-kicker">Non retenues</span>
              <p className="stat-value">{applications === null ? '…' : refused.length}</p>
              <span className="stat-label">{refused.length > 0 ? 'Continuez à postuler' : 'Aucune pour l\'instant'}</span>
            </div>
          </>
        ) : (
          <>
            <div className="stat-card">
              <span className="stat-kicker">CV analysés</span>
              <p className="stat-value">{recruiterStats.cvs}</p>
              <span className="stat-label">Données structurées</span>
            </div>
            <div className="stat-card">
              <span className="stat-kicker">Offres</span>
              <p className="stat-value">{recruiterStats.offres}</p>
              <span className="stat-label">Actives</span>
            </div>
            <div className="stat-card">
              <span className="stat-kicker">Matchings</span>
              <p className="stat-value">{recruiterStats.matchings}</p>
              <span className="stat-label">Tri intelligent</span>
            </div>
          </>
        )}
      </section>

      {/* ── Features ─────────────────────────────────── */}
      <section className="home-features">
        {isCandidat ? (
          <>
            <div className="feature-card">
              <div className="feature-icon">🔍</div>
              <h3>Matching 4 dimensions</h3>
              <p>Votre profil est évalué sur les compétences, l'expérience, la formation et la sémantique globale.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">⚡</div>
              <h3>Résultats en secondes</h3>
              <p>L'extraction et le scoring de votre CV sont effectués automatiquement dès le dépôt.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">🔒</div>
              <h3>Données protégées</h3>
              <p>Vos informations restent confidentielles. Aucune donnée n'est transmise à des serveurs externes.</p>
            </div>
          </>
        ) : (
          <>
            <div className="feature-card">
              <div className="feature-icon">📊</div>
              <h3>Parsing CV haute précision</h3>
              <p>Extraction multi-format (PDF, image, Word) avec normalisation automatique des compétences.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">🧠</div>
              <h3>Matching sémantique + règles</h3>
              <p>Combine le sens du CV avec les exigences métiers pour un score fiable et explicable.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">✅</div>
              <h3>Décision transparente</h3>
              <p>Score détaillé, incohérences visibles et recommandations concrètes pour chaque profil.</p>
            </div>
          </>
        )}
      </section>

      {/* ── Mission ──────────────────────────────────── */}
      <section className="home-mission">
        <div className="mission-card">
          <h3>Mission 3S</h3>
          <p>
            Accompagner les organisations dans l'intégration d'infrastructures IT
            fiables, évolutives et sécurisées, en mettant l'innovation au service
            de la performance.
          </p>
        </div>
        <div className="mission-card alt">
          <h3>Valeurs clé</h3>
          <ul>
            <li>Excellence technique et qualité de service</li>
            <li>Innovation utile et orientée résultat</li>
            <li>Proximité et accompagnement des clients</li>
          </ul>
        </div>
      </section>
    </div>
  )
}

export default Home
