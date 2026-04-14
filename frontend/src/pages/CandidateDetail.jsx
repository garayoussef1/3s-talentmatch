import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '../services/api'
import './CandidateDetail.css'

function _asArray(value) {
  if (!value) return []
  return Array.isArray(value) ? value : [value]
}

function _asString(value) {
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

function _asText(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(_asText).filter(Boolean).join(', ')
  if (typeof value === 'object') {
    const langue = _asString(value.langue || value.language || value.name)
    const niveau = _asString(value.niveau || value.level)
    if (langue && niveau) return `${langue} (${niveau})`
    if (langue) return langue
    if (niveau) return niveau
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

function _formatPeriod(start, end, enCours) {
  const s = _asString(start)
  const e = _asString(end)
  if (!s && !e && !enCours) return '—'
  if (enCours) return `${s || '—'} → En cours`
  return `${s || '—'} → ${e || '—'}`
}

function _formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleDateString('fr-FR')
}

function _initials(fullName) {
  const parts = _asString(fullName).split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  const a = parts[0]?.[0] || ''
  const b = parts.length > 1 ? (parts[parts.length - 1]?.[0] || '') : ''
  return (a + b).toUpperCase() || '—'
}

function _downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

function CandidateDetail() {
  const { cvId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyAction, setBusyAction] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)

    api.get(`/candidates/${cvId}`)
      .then((res) => {
        const payload = res?.data
        if (!payload || typeof payload !== 'object') {
          setError('Réponse invalide du serveur pour ce candidat.')
          setData(null)
          return
        }

        let parsedData = payload.parsed_data
        if (typeof parsedData === 'string') {
          try {
            parsedData = JSON.parse(parsedData)
          } catch {
            // Keep original string if parsing fails.
          }
        }

        setData({
          ...payload,
          parsed_data: parsedData,
        })
      })
      .catch(() => setError('Impossible de charger les extractions de ce candidat.'))
      .finally(() => setLoading(false))
  }, [cvId])

  const parsed = data?.parsed_data || null
  const identite = parsed?.identite || null
  const contacts = parsed?.contacts || null
  const metadata = parsed?.metadata || null
  const errors = _asArray(parsed?.errors)

  const competences = _asArray(parsed?.competences)
  const competencesParCategorie = parsed?.competences_par_categorie || null
  const langues = _asArray(parsed?.langues)
  const experiences = _asArray(parsed?.experiences)
  const formations = _asArray(parsed?.formations)

  const normalizedEmail = _asString(data?.email || contacts?.email)
  const normalizedName = _asString(data?.nom || identite?.nom_complet) || '—'
  const normalizedPhone = _asString(data?.telephone || contacts?.telephone)

  const headline = useMemo(() => {
    const topExp = experiences[0]
    const title = _asString(topExp?.poste || topExp?.title)
    return title || '—'
  }, [experiences])

  const stats = {
    totalSkills: metadata?.total_competences ?? competences.length,
    totalExp: metadata?.total_experiences ?? experiences.length,
    totalEdu: metadata?.total_formations ?? formations.length,
    seniorite: metadata?.niveau_seniorite || '—',
    years: metadata?.annees_experience_totales,
    confidence: metadata?.confidence_score,
  }

  const categoryEntries = (() => {
    if (competencesParCategorie && typeof competencesParCategorie === 'object') {
      return Object.entries(competencesParCategorie)
        .map(([cat, items]) => [cat, _asArray(items)])
        .filter(([, items]) => items.length > 0)
    }

    const grouped = {}
    competences.forEach((s) => {
      const obj = (typeof s === 'string') ? { name: s } : (s || {})
      const cat = obj.category || obj.categorie || 'Autres'
      const name = obj.name || obj.label || (typeof s === 'string' ? s : '')
      if (!name) return
      grouped[cat] = grouped[cat] || []
      grouped[cat].push({ name })
    })

    return Object.entries(grouped)
      .map(([cat, items]) => [cat, items])
      .filter(([, items]) => items.length > 0)
  })()

  const fileName = data?.filename || 'CV'
  const originalAvailable = !!data?.original_file_available

  const handleContact = () => {
    if (normalizedEmail) {
      window.location.href = `mailto:${normalizedEmail}`
      return
    }
    if (normalizedPhone) {
      window.location.href = `tel:${normalizedPhone}`
    }
  }

  const handleExport = () => {
    if (!data) return
    const payload = {
      cv_id: data.cv_id,
      filename: data.filename,
      created_at: data.created_at,
      extraction_method: data.extraction_method,
      candidature_status: data.candidature_status,
      parsed_data: data.parsed_data,
      raw_text_preview: data.raw_text_preview,
      raw_text_length: data.raw_text_length,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    _downloadBlob(blob, `extractions_${cvId}.json`)
  }

  const handleDownloadOriginal = async (mode) => {
    if (!originalAvailable) return
    try {
      setBusyAction(mode)
      const res = await api.get(`/candidates/${cvId}/original`, { responseType: 'blob' })
      const blob = res.data
      const safeName = fileName || `cv_${cvId}`
      if (mode === 'view') {
        const url = window.URL.createObjectURL(blob)
        window.open(url, '_blank', 'noopener,noreferrer')
        window.setTimeout(() => window.URL.revokeObjectURL(url), 15000)
      } else {
        _downloadBlob(blob, safeName)
      }
    } catch {
      setError('Impossible de récupérer le CV original pour le moment.')
    } finally {
      setBusyAction(null)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm('Supprimer ce candidat ?')) return
    try {
      setBusyAction('delete')
      await api.delete(`/candidates/${cvId}`)
      navigate('/candidates')
    } catch {
      setError('Erreur lors de la suppression.')
    } finally {
      setBusyAction(null)
    }
  }

  return (
    <div className="candidate-detail">
      <section className="cd-hero">
        <div className="cd-hero-main">
          <div className="cd-avatar">{_initials(normalizedName)}</div>
          <div>
            <h1 className="cd-title text-2xl font-bold">{normalizedName}</h1>
            <div className="cd-subtitle">{headline}</div>
            <div className="cd-meta">
              <span className="cd-chip">CV #{cvId}</span>
              <span className="cd-chip">{stats.seniorite}{stats.years === undefined ? '' : ` • ${stats.years} ans`}</span>
              <span className="cd-chip">{_formatDate(data?.created_at)}</span>
              <span className="cd-chip">{_asString(data?.extraction_method) || '—'}</span>
            </div>
          </div>
        </div>
        <div className="cd-actions">
          <button type="button" className="cd-btn" onClick={() => navigate('/candidates')}>← Retour</button>
          <button
            type="button"
            className="cd-btn cd-btn-primary"
            onClick={handleContact}
            disabled={!normalizedEmail && !normalizedPhone}
          >
            Contacter
          </button>
          <button type="button" className="cd-btn" onClick={handleExport} disabled={!data}>Exporter</button>
          <button type="button" className="cd-btn" onClick={handleDelete} disabled={busyAction === 'delete' || !data}>
            {busyAction === 'delete' ? 'Suppression…' : 'Supprimer'}
          </button>
        </div>
      </section>

      {loading ? (
        <div className="cd-card cd-muted">⏳ Chargement…</div>
      ) : null}
      {error ? (
        <div className="cd-card" style={{ borderColor: '#fecaca', background: '#fef2f2', color: '#991b1b' }}>❌ {error}</div>
      ) : null}

      {!loading && !error && !data ? (
        <div className="cd-card" style={{ borderColor: '#fde68a', background: '#fffbeb', color: '#92400e' }}>
          ⚠️ Aucune extraction disponible pour ce candidat pour le moment.
        </div>
      ) : null}

      {!loading && !error && data ? (
        <div className="cd-grid">
          <aside className="cd-col cd-col-left">
            <div className="cd-card">
              <details className="cd-details" open>
                <summary className="cd-summary">Contact</summary>
                <div className="cd-stat-list">
                  <div className="cd-stat"><span className="cd-muted">Email</span><span>{normalizedEmail || '—'}</span></div>
                  <div className="cd-stat"><span className="cd-muted">Téléphone</span><span>{normalizedPhone || '—'}</span></div>
                  <div className="cd-stat"><span className="cd-muted">LinkedIn</span><span>{_asString(data.linkedin || contacts?.linkedin) || '—'}</span></div>
                  <div className="cd-stat"><span className="cd-muted">GitHub</span><span>{_asString(data.github || contacts?.github) || '—'}</span></div>
                </div>
              </details>
            </div>

            <div className="cd-card">
              <div className="cd-card-title">Tags</div>
              <div className="cd-tag-cloud">
                <span className="cd-pill">{stats.seniorite}</span>
                {categoryEntries.slice(0, 4).map(([cat]) => (
                  <span key={cat} className="cd-pill">{cat}</span>
                ))}
              </div>
            </div>
          </aside>

          <main className="cd-col cd-col-main">
            <section className="cd-card">
              <details className="cd-details">
                <summary className="cd-summary">Experiences</summary>
                {experiences.length === 0 ? (
                  <div className="cd-muted">—</div>
                ) : (
                  <div className="cd-timeline">
                    {experiences.map((e, idx) => {
                      const poste = _asString(e?.poste || e?.title) || '—'
                      const entreprise = _asString(e?.entreprise || e?.company) || '—'
                      const debut = e?.date_debut || e?.start_date || null
                      const fin = e?.date_fin || e?.end_date || null
                      const enCours = !!(e?.en_cours)
                      const duree = (e?.duree_mois ?? e?.duration_months)
                      const localisation = _asString(e?.localisation || e?.location)
                      const missions = _asArray(e?.missions)
                      return (
                        <div key={idx} className="cd-timeline-item">
                          <div className="font-semibold">{poste}</div>
                          <div className="cd-muted">{entreprise}{localisation ? ` • ${localisation}` : ''}</div>
                          <div className="cd-muted">
                            {_formatPeriod(debut, fin, enCours)}{duree === null || duree === undefined ? '' : ` • ${duree} mois`}
                          </div>
                          {missions.length > 0 ? (
                            <ul className="mt-2 list-disc pl-5 text-sm">
                              {missions.map((m, j) => <li key={j}>{_asText(m) || '—'}</li>)}
                            </ul>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                )}
              </details>
            </section>

            <section className="cd-card">
              <details className="cd-details">
                <summary className="cd-summary">Competences</summary>
                {categoryEntries.length === 0 ? (
                  <div className="cd-muted">—</div>
                ) : (
                  <div className="cd-timeline">
                    {categoryEntries.map(([cat, items]) => (
                      <div key={cat}>
                        <div className="cd-muted" style={{ fontWeight: 700 }}>{cat}</div>
                        <div className="cd-tag-cloud">
                          {items.map((s, idx) => {
                            const label = typeof s === 'string' ? s : (s?.name || s?.label || JSON.stringify(s))
                            return (
                              <span key={`${cat}-${idx}`} className="cd-pill">{label}</span>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="cd-card-title" style={{ marginTop: '16px' }}>Langues</div>
                {langues.length === 0 ? (
                  <div className="cd-muted">—</div>
                ) : (
                  <div className="cd-tag-cloud">
                    {langues.map((l, idx) => (
                      <span key={idx} className="cd-pill">{_asText(l) || '—'}</span>
                    ))}
                  </div>
                )}
              </details>
            </section>

            <section className="cd-card">
              <details className="cd-details">
                <summary className="cd-summary">Formations</summary>
                {formations.length === 0 ? (
                  <div className="cd-muted">—</div>
                ) : (
                  <div className="cd-timeline">
                    {formations.map((f, idx) => {
                      const diplome = _asString(f?.diplome || f?.degree) || '—'
                      const specialite = _asString(f?.specialite || f?.specialty)
                      const etab = _asString(f?.etablissement || f?.school) || '—'
                      const annee = f?.annee || f?.year || null
                      const mention = _asString(f?.mention)
                      const niveau = f?.niveau_bac_plus
                      const enCours = !!(f?.en_cours)
                      return (
                        <div key={idx} className="cd-timeline-item">
                          <div className="font-semibold">{diplome}</div>
                          <div className="cd-muted">{etab}{specialite ? ` • ${specialite}` : ''}</div>
                          <div className="cd-tag-cloud">
                            <span className="cd-pill">{enCours ? 'En cours' : (annee ? `Annee: ${annee}` : 'Annee: —')}</span>
                            <span className="cd-pill">{niveau === undefined || niveau === null ? 'Bac+—' : `Bac+${niveau}`}</span>
                            <span className="cd-pill">{mention ? `Mention: ${mention}` : 'Mention: —'}</span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </details>
            </section>

            {data?.raw_text_preview ? (
              <section className="cd-card">
                <details className="cd-details">
                  <summary className="cd-summary">Extrait texte</summary>
                  <div className="cd-raw">{data.raw_text_preview}</div>
                </details>
              </section>
            ) : null}

            {errors.length > 0 ? (
              <section className="cd-card" style={{ borderColor: '#fed7aa', background: '#fff7ed' }}>
                <details className="cd-details">
                  <summary className="cd-summary" style={{ color: '#9a3412' }}>Avertissements NLP</summary>
                  <ul className="mt-2 list-disc pl-5 text-sm" style={{ color: '#9a3412' }}>
                    {errors.map((e, idx) => <li key={idx}>{typeof e === 'string' ? e : JSON.stringify(e)}</li>)}
                  </ul>
                </details>
              </section>
            ) : null}
          </main>

          <aside className="cd-col cd-col-right">
            <section className="cd-card">
              <div className="cd-card-title">Fichier CV</div>
              <div className="cd-muted" style={{ marginTop: '8px', wordBreak: 'break-word' }}>{fileName}</div>
              <div className="cd-stat-list">
                <button
                  type="button"
                  className="cd-btn"
                  onClick={() => handleDownloadOriginal('download')}
                  disabled={!originalAvailable || busyAction === 'download'}
                >
                  {busyAction === 'download' ? 'Telechargement…' : 'Telecharger'}
                </button>
                <button
                  type="button"
                  className="cd-btn"
                  onClick={() => handleDownloadOriginal('view')}
                  disabled={!originalAvailable || busyAction === 'view'}
                >
                  {busyAction === 'view' ? 'Ouverture…' : 'Voir original'}
                </button>
              </div>
              {!originalAvailable ? (
                <div className="cd-muted" style={{ marginTop: '8px' }}>
                  CV original indisponible (anciens uploads).
                </div>
              ) : null}
            </section>

            <section className="cd-card">
              <div className="cd-card-title">Metriques NLP</div>
              <div className="cd-stat-list">
                <div className="cd-stat"><span className="cd-muted">Confiance</span><span>{stats.confidence === undefined ? '—' : `${Math.round(stats.confidence * 100)}%`}</span></div>
                <div className="cd-stat"><span className="cd-muted">Competences</span><span>{stats.totalSkills}</span></div>
                <div className="cd-stat"><span className="cd-muted">Experiences</span><span>{stats.totalExp}</span></div>
                <div className="cd-stat"><span className="cd-muted">Formations</span><span>{stats.totalEdu}</span></div>
              </div>
            </section>

            <section className="cd-card">
              <div className="cd-card-title">Traitement</div>
              <div className="cd-stat-list">
                <div className="cd-stat"><span className="cd-muted">Date upload</span><span>{_formatDate(data.created_at)}</span></div>
                <div className="cd-stat"><span className="cd-muted">Methode</span><span>{_asString(data.extraction_method) || '—'}</span></div>
                <div className="cd-stat"><span className="cd-muted">Duree extraction</span><span>—</span></div>
              </div>
            </section>
          </aside>
        </div>
      ) : null}
    </div>
  )
}

export default CandidateDetail
