import { useState, useRef } from 'react'
import api from '../services/api'
import './UploadCV.css'

function UploadCV() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('resume')
  const fileInputRef = useRef()

  const handleFileChange = (e) => {
    const selected = e.target.files[0]
    setFile(selected)
    setResult(null)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped) {
      setFile(dropped)
      setResult(null)
      setError(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return

    setLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await api.post('/upload-cv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        // L'extraction (OCR/NLP) peut prendre > 8s. On évite un faux échec client.
        timeout: 120000,
      })
      setResult(response.data)
      setActiveTab('resume')
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de l\'upload')
    } finally {
      setLoading(false)
    }
  }

  const parsed = result?.parsed_data
  const meta = parsed?.metadata

  return (
    <div className="upload-page">
      <h1>Uploader un CV</h1>
      <p className="subtitle">Formats acceptés : PDF, DOCX, PNG, JPG (max 10 Mo)</p>

      <form onSubmit={handleSubmit} className="upload-form">
        <div
          className="drop-zone"
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current.click()}
        >
          {file ? (
            <div className="file-selected">
              <span className="file-icon">📄</span>
              <span>{file.name}</span>
              <span className="file-size">({(file.size / 1024 / 1024).toFixed(2)} Mo)</span>
            </div>
          ) : (
            <div className="drop-hint">
              <span className="drop-icon">📂</span>
              <p>Glissez un fichier ici ou <strong>cliquez pour parcourir</strong></p>
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

        <button type="submit" className="btn-upload" disabled={!file || loading}>
          {loading ? (
            <span className="spinner-wrapper">
              <span className="spinner"></span>
              Traitement en cours...
            </span>
          ) : '🚀 Envoyer le CV'}
        </button>
      </form>

      {error && (
        <div className="alert error">
          ❌ {error}
        </div>
      )}

      {result && (
        <div className="result-card">
          <h2>✅ CV traité avec succès</h2>
          <div className="result-grid">
            <div className="result-item">
              <span className="label">Fichier</span>
              <span className="value">{result.filename}</span>
            </div>
            <div className="result-item">
              <span className="label">Méthode</span>
              <span className="value">{result.method}</span>
            </div>
            <div className="result-item">
              <span className="label">ID</span>
              <span className="value mono">{result.cv_id}</span>
            </div>
          </div>

          {/* ── Onglets de données parsées ───────────────── */}
          {parsed && (
            <>
              {meta && (
                <div className="meta-bar">
                  <span className="meta-chip">🎯 Confiance : {Math.round(meta.confidence_score * 100)}%</span>
                  <span className="meta-chip">💼 {meta.total_experiences || 0} expériences</span>
                  <span className="meta-chip">🎓 {meta.total_formations || 0} formations</span>
                  <span className="meta-chip">⚡ {meta.total_competences || 0} compétences</span>
                  <span className="meta-chip">🌐 {parsed.langues?.length || 0} langues</span>
                  <span className="meta-chip">📊 {meta.annees_experience_totales || 0} ans exp.</span>
                  <span className="meta-chip">🏷️ {meta.niveau_seniorite}</span>
                </div>
              )}

              <div className="tabs">
                {['resume', 'competences', 'experiences', 'formations', 'langues', 'texte'].map(tab => (
                  <button
                    key={tab}
                    className={`tab ${activeTab === tab ? 'active' : ''}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === 'resume' ? '📋 Résumé' :
                     tab === 'competences' ? '⚡ Compétences' :
                     tab === 'experiences' ? '💼 Expériences' :
                     tab === 'formations' ? '🎓 Formations' :
                     tab === 'langues' ? '🌐 Langues' : '📝 Texte brut'}
                  </button>
                ))}
              </div>

              <div className="tab-content">
                {/* ── RÉSUMÉ ── */}
                {activeTab === 'resume' && (
                  <div className="tab-resume">
                    {parsed.identite?.nom_complet && (
                      <div className="info-block">
                        <h3>👤 Identité</h3>
                        <p className="big-name">{parsed.identite.nom_complet}</p>
                      </div>
                    )}
                    {(parsed.contacts?.email || parsed.contacts?.telephone) && (
                      <div className="info-block">
                        <h3>📬 Contact</h3>
                        {parsed.contacts.email && <p>📧 {parsed.contacts.email}</p>}
                        {parsed.contacts.telephone && <p>📱 {parsed.contacts.telephone}</p>}
                        {parsed.contacts.linkedin && (
                          <p>💼 <a href={parsed.contacts.linkedin} target="_blank" rel="noreferrer">{parsed.contacts.linkedin}</a></p>
                        )}
                        {parsed.contacts.github && (
                          <p>🐙 <a href={parsed.contacts.github} target="_blank" rel="noreferrer">{parsed.contacts.github}</a></p>
                        )}
                        {parsed.contacts.website && (
                          <p>🌐 <a href={parsed.contacts.website} target="_blank" rel="noreferrer">{parsed.contacts.website}</a></p>
                        )}
                        {parsed.contacts.address && <p>📍 {parsed.contacts.address}</p>}
                      </div>
                    )}
                    {parsed.langues?.length > 0 && (
                      <div className="info-block">
                        <h3>🌐 Langues</h3>
                        <div className="tag-list">
                          {parsed.langues.map((l, i) => (
                            <span key={i} className="tag tag-lang">{l.langue}{l.niveau ? ` — ${l.niveau}` : ''}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* ── COMPÉTENCES ── */}
                {activeTab === 'competences' && (
                  <div className="tab-skills">
                    {parsed.competences_par_categorie && Object.keys(parsed.competences_par_categorie).length > 0 ? (
                      Object.entries(parsed.competences_par_categorie).map(([cat, skills]) => (
                        <div key={cat} className="skill-category">
                          <h4>{cat.replace(/_/g, ' ')}</h4>
                          <div className="tag-list">
                            {skills.map((s, i) => (
                              <span key={i} className="tag tag-skill">{s}</span>
                            ))}
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="empty-tab">Aucune compétence détectée</p>
                    )}
                  </div>
                )}

                {/* ── EXPÉRIENCES ── */}
                {activeTab === 'experiences' && (
                  <div className="tab-experiences">
                    {parsed.experiences?.length > 0 ? (
                      parsed.experiences.map((exp, i) => (
                        <div key={i} className="exp-card">
                          <div className="exp-header">
                            <h4>{exp.poste || 'Poste non détecté'}</h4>
                            {exp.en_cours && <span className="badge-ongoing">En cours</span>}
                          </div>
                          <div className="exp-meta">
                            {exp.entreprise && <span>🏢 {exp.entreprise}</span>}
                            {exp.date_debut && <span>📅 {exp.date_debut} → {exp.date_fin || 'Présent'}</span>}
                            {exp.duree_mois > 0 && <span>⏱️ {exp.duree_mois} mois</span>}
                            {exp.localisation && <span>📍 {exp.localisation}</span>}
                          </div>
                          {exp.missions?.length > 0 && (
                            <ul className="exp-missions">
                              {exp.missions.map((m, j) => <li key={j}>{m}</li>)}
                            </ul>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="empty-tab">Aucune expérience détectée</p>
                    )}
                  </div>
                )}

                {/* ── FORMATIONS ── */}
                {activeTab === 'formations' && (
                  <div className="tab-formations">
                    {parsed.formations?.length > 0 ? (
                      parsed.formations.map((f, i) => (
                        <div key={i} className="formation-card">
                          <h4>
                            {f.diplome || 'Formation'}
                            {f.niveau_bac_plus !== undefined && f.niveau_bac_plus !== null && (
                              <span className="bac-plus"> Bac+{f.niveau_bac_plus}</span>
                            )}
                          </h4>
                          <div className="formation-meta">
                            {f.specialite && <span>📚 {f.specialite}</span>}
                            {f.etablissement && <span>🏫 {f.etablissement}</span>}
                            {f.annee && <span>📅 {f.annee}</span>}
                            {f.mention && <span>🏅 {f.mention}</span>}
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="empty-tab">Aucune formation détectée</p>
                    )}
                  </div>
                )}

                {/* ── LANGUES ── */}
                {activeTab === 'langues' && (
                  <div className="tab-langues">
                    {parsed.langues?.length > 0 ? (
                      <div className="langues-grid">
                        {parsed.langues.map((l, i) => (
                          <div key={i} className="langue-card">
                            <h4>{l.langue}</h4>
                            <span className="langue-niveau">{l.niveau || 'Non précisé'}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-tab">Aucune langue détectée</p>
                    )}
                  </div>
                )}

                {/* ── TEXTE BRUT ── */}
                {activeTab === 'texte' && (
                  <div className="text-preview">
                    <pre>{result.text_preview}</pre>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Fallback si pas de parsed_data */}
          {!parsed && result.text_preview && (
            <div className="text-preview">
              <span className="label">Aperçu du texte extrait</span>
              <pre>{result.text_preview}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default UploadCV
