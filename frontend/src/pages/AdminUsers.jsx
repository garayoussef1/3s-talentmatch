import { useEffect, useMemo, useState } from 'react'
import api from '../services/api'
import './AdminUsers.css'

function AdminUsers() {
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({ q: '', role: '', is_active: '' })
  const [form, setForm] = useState({ nom: '', prenom: '', email: '', password: '', telephone: '' })
  const [busy, setBusy] = useState(false)

  const stats = useMemo(() => {
    const counts = { admin: 0, recruteur: 0, candidat: 0, active: 0 }
    users.forEach(u => {
      if (u.role in counts) counts[u.role] += 1
      if (u.is_active) counts.active += 1
    })
    return counts
  }, [users])

  const queryString = useMemo(() => {
    const params = new URLSearchParams()
    if (filters.q) params.set('q', filters.q)
    if (filters.role) params.set('role', filters.role)
    if (filters.is_active !== '') params.set('is_active', filters.is_active)
    return params.toString()
  }, [filters])

  const fetchUsers = () => {
    setLoading(true)
    setError(null)
    api.get(`/admin/users${queryString ? `?${queryString}` : ''}`)
      .then(res => {
        setUsers(res.data.users || [])
        setTotal(res.data.total || 0)
      })
      .catch(() => setError("Impossible de charger les utilisateurs."))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchUsers()
  }, [queryString])

  const handleToggleActive = (id, current) => {
    api.patch(`/admin/users/${id}`, { is_active: !current })
      .then(() => fetchUsers())
      .catch(() => setError("Erreur lors de la mise à jour du statut."))
  }

  const handleDelete = (id) => {
    if (!window.confirm('Supprimer cet utilisateur ?')) return
    api.delete(`/admin/users/${id}`)
      .then(() => fetchUsers())
      .catch(() => setError("Erreur lors de la suppression."))
  }

  const handleResetPassword = (id) => {
    if (!window.confirm('Envoyer un code de reset mot de passe ?')) return
    api.post(`/admin/users/${id}/reset-password`)
      .then(() => alert('Code de reset envoyé.'))
      .catch(() => setError("Erreur lors de l'envoi du reset."))
  }

  const handleCreateRecruiter = (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    api.post('/auth/admin/create-recruteur', {
      nom: form.nom,
      prenom: form.prenom,
      email: form.email,
      password: form.password,
      telephone: form.telephone || undefined,
    })
      .then(() => {
        setForm({ nom: '', prenom: '', email: '', password: '', telephone: '' })
        fetchUsers()
      })
      .catch(() => setError("Impossible de créer le recruteur."))
      .finally(() => setBusy(false))
  }

  return (
    <div className="admin-users-page">
      <header className="admin-hero">
        <div>
          <span className="eyebrow">Backoffice</span>
          <h1>Administration utilisateurs</h1>
          <p>Gérez les comptes, rôles et accès en un seul endroit.</p>
        </div>
        <div className="hero-badge">
          <span className="hero-number">{total}</span>
          <span className="hero-label">utilisateurs</span>
        </div>
      </header>

      <section className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">Actifs</span>
          <strong className="stat-value">{stats.active}</strong>
        </div>
        <div className="stat-card">
          <span className="stat-label">Admins</span>
          <strong className="stat-value">{stats.admin}</strong>
        </div>
        <div className="stat-card">
          <span className="stat-label">Recruteurs</span>
          <strong className="stat-value">{stats.recruteur}</strong>
        </div>
        <div className="stat-card">
          <span className="stat-label">Candidats</span>
          <strong className="stat-value">{stats.candidat}</strong>
        </div>
      </section>

      {error && <div className="alert error">❌ {error}</div>}

      <div className="admin-layout">
        <section className="admin-card admin-card--form">
          <div className="card-title">
            <h2>Créer un recruteur</h2>
            <span className="pill">Admin only</span>
          </div>
          <p className="card-subtitle">Créez un compte recruteur et activez-le immédiatement.</p>
          <form className="admin-form" onSubmit={handleCreateRecruiter}>
            <label className="field">
              <span>Nom</span>
              <input value={form.nom} onChange={e => setForm(f => ({ ...f, nom: e.target.value }))} required />
            </label>
            <label className="field">
              <span>Prénom</span>
              <input value={form.prenom} onChange={e => setForm(f => ({ ...f, prenom: e.target.value }))} required />
            </label>
            <label className="field">
              <span>Email</span>
              <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
            </label>
            <label className="field">
              <span>Mot de passe</span>
              <input type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
            </label>
            <label className="field">
              <span>Téléphone (optionnel)</span>
              <input value={form.telephone} onChange={e => setForm(f => ({ ...f, telephone: e.target.value }))} />
            </label>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Création...' : 'Créer recruteur'}
            </button>
          </form>
        </section>

        <section className="admin-card admin-card--table">
          <div className="card-title">
            <h2>Utilisateurs</h2>
            <span className="pill">{total} comptes</span>
          </div>
          <div className="legend-row">
            <span className="legend-item"><span className="role-badge role-admin">admin</span> Administrateur</span>
            <span className="legend-item"><span className="role-badge role-recruteur">recruteur</span> Recruteur</span>
            <span className="legend-item"><span className="role-badge role-candidat">candidat</span> Candidat</span>
            <span className="legend-item"><span className="status-pill status-active">Actif</span></span>
            <span className="legend-item"><span className="status-pill status-off">Inactif</span></span>
          </div>
          <div className="admin-filters">
            <label className="field">
              <span>Recherche</span>
              <input
                placeholder="Nom ou email"
                value={filters.q}
                onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
              />
            </label>
            <label className="field">
              <span>Rôle</span>
              <select value={filters.role} onChange={e => setFilters(f => ({ ...f, role: e.target.value }))}>
                <option value="">Tous les rôles</option>
                <option value="admin">Admin</option>
                <option value="recruteur">Recruteur</option>
                <option value="candidat">Candidat</option>
              </select>
            </label>
            <label className="field">
              <span>Statut</span>
              <select value={filters.is_active} onChange={e => setFilters(f => ({ ...f, is_active: e.target.value }))}>
                <option value="">Tous les statuts</option>
                <option value="true">Actifs</option>
                <option value="false">Inactifs</option>
              </select>
            </label>
          </div>

          {loading ? (
            <div className="loading">⏳ Chargement...</div>
          ) : (
            <div className="user-grid">
              {users.length === 0 && (
                <div className="empty-state">Aucun utilisateur trouvé.</div>
              )}
              {users.map(u => (
                <article key={u.id} className="user-card">
                  <header className="user-card-header">
                    <div className="user-name">
                      <span className="avatar">{(u.prenom || 'U')[0]}</span>
                      <div>
                        <div className="user-title">{u.prenom} {u.nom}</div>
                        <div className="muted">ID: {u.id.slice(0, 8)}</div>
                      </div>
                    </div>
                    <span className={`status-pill ${u.is_active ? 'status-active' : 'status-off'}`}>
                      {u.is_active ? 'Actif' : 'Inactif'}
                    </span>
                  </header>

                  <div className="user-meta">
                    <div className="user-row">
                      <span className="meta-label">Email</span>
                      <span className="meta-value">{u.email}</span>
                    </div>
                    <div className="user-row">
                      <span className="meta-label">Role</span>
                      <span className={`role-badge role-${u.role}`}>{u.role}</span>
                    </div>
                  </div>

                  <div className="action-bar">
                    <details className="action-menu">
                      <summary>⋯</summary>
                      <div className="action-panel">
                        <button onClick={() => handleToggleActive(u.id, u.is_active)}>
                          {u.is_active ? 'Désactiver' : 'Activer'}
                        </button>
                        <button onClick={() => handleResetPassword(u.id)}>Reset MDP</button>
                        <button className="danger" onClick={() => handleDelete(u.id)}>Supprimer</button>
                      </div>
                    </details>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

export default AdminUsers
