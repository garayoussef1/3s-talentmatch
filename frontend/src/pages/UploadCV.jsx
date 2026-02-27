import { useState, useRef } from 'react'
import axios from 'axios'
import './UploadCV.css'

function UploadCV() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
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
      const response = await axios.post('/api/upload-cv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de l\'upload')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="upload-page">
      <h1>Uploader un CV</h1>
      <p className="subtitle">Formats acceptés : PDF, DOCX (max 10 Mo)</p>

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
            accept=".pdf,.docx"
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
          {result.text_preview && (
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
