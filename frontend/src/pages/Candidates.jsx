function Candidates() {
  return (
    <div className="candidates-page">
      <h1>Candidats</h1>
      <p className="subtitle">Liste des candidats extraits depuis les CVs uploadés.</p>
      <div className="empty-state">
        <span>📂</span>
        <p>Aucun candidat pour l'instant.<br />Uploadez un CV pour commencer.</p>
      </div>
    </div>
  )
}

export default Candidates
