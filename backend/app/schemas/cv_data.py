"""
Schéma de validation Pydantic pour CVs structurés.
Sprint 2 - US-208

Structure JSON cible pour le parsing NLP complet.
Classes : Identite, Contacts, Competence, Formation, Experience, Langue,
          Metadata, CVDataStructured (principale).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ================================================================
# Sous-modèles
# ================================================================


class Identite(BaseModel):
    """Informations d'identité du candidat."""
    nom_complet: Optional[str] = Field(None, description="Nom complet du candidat")
    prenom: Optional[str] = None
    nom: Optional[str] = None

    @model_validator(mode="after")
    def split_name(self) -> "Identite":
        """Déduit prénom / nom depuis nom_complet si nécessaire."""
        if self.nom_complet and not self.prenom:
            parts = self.nom_complet.strip().split()
            if len(parts) >= 2:
                self.prenom = parts[0]
                self.nom = " ".join(parts[1:])
            elif len(parts) == 1:
                self.nom = parts[0]
        return self


class Contacts(BaseModel):
    """Informations de contact."""
    email: Optional[str] = None
    telephone: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    linkedin: Optional[str] = None
    github: Optional[str] = None
    site_web: Optional[str] = None


class Competence(BaseModel):
    """Compétence technique détectée."""
    name: str = Field(..., description="Nom de la compétence")
    category: str = Field("autre", description="Catégorie (langages, frameworks_web, ...)")
    years: Optional[int] = Field(None, description="Années d'expérience")
    level: str = Field("Non spécifié", description="Débutant / Intermédiaire / Avancé / Expert")


class Formation(BaseModel):
    """Formation académique."""
    diplome: Optional[str] = None
    specialite: Optional[str] = None
    etablissement: Optional[str] = None
    annee: Optional[int] = None
    niveau_bac_plus: Optional[int] = Field(None, description="Niveau Bac+X (0=Bac, 2,3,5,8)")


class Experience(BaseModel):
    """Expérience professionnelle."""
    entreprise: Optional[str] = None
    poste: Optional[str] = None
    date_debut: Optional[str] = Field(None, description="Format YYYY-MM")
    date_fin: Optional[str] = Field(None, description="Format YYYY-MM ou null si en cours")
    en_cours: bool = False
    duree_mois: int = 0
    lieu: Optional[str] = None
    missions: List[str] = Field(default_factory=list)


class Langue(BaseModel):
    """Langue parlée."""
    langue: str
    niveau: Optional[str] = Field(None, description="Natif / Courant / Intermédiaire / Débutant")


class Metadata(BaseModel):
    """Métadonnées de parsing."""
    parser_version: str = "2.0.0"
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    parsed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Traces runtime (debug/qualité) — optionnelles pour rester rétro-compatibles
    spacy_model: Optional[str] = Field(None, description="Nom du modèle spaCy chargé")
    spacy_version: Optional[str] = Field(None, description="Version de spaCy")
    spacy_has_ner: Optional[bool] = Field(None, description="Indique si le pipeline spaCy contient le composant NER")
    spacy_fallback: Optional[bool] = Field(None, description="True si fallback vers spacy.blank('fr') a été utilisé")
    spacy_pipes: List[str] = Field(default_factory=list, description="Liste des composants du pipeline spaCy")

    # Trace "nom" (debug/qualité)
    name_source: Optional[str] = Field(
        None,
        description="Source du nom final (ex: entity_extractor, hf_camembert, email, etc.)",
    )
    name_candidates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Candidats de nom proposés par chaque méthode (debug)",
    )
    name_conflict: Optional[bool] = Field(
        None,
        description="True si conflit entre sources de nom (ex: entity vs hf)",
    )

    # Trace CamemBERT (HF) — optionnel
    hf_camembert_enabled: Optional[bool] = Field(
        None,
        description="True si CamemBERT est activé par config (HF_TOKEN/HF_ENABLE_CAMEMBERT_NAME)",
    )
    hf_camembert_attempted: Optional[bool] = Field(
        None,
        description="True si une requête CamemBERT a été tentée pendant ce parsing",
    )
    hf_camembert_used: Optional[bool] = Field(
        None,
        description="True si la sortie CamemBERT a été retenue comme nom final",
    )
    hf_camembert_model: Optional[str] = Field(
        None,
        description="Nom du modèle HF utilisé (ex: Jean-Baptiste/camembert-ner)",
    )
    hf_camembert_timeout_seconds: Optional[float] = Field(
        None,
        description="Timeout (secondes) configuré pour l'appel HF",
    )

    annees_experience_totales: float = 0.0
    niveau_formation_max: int = 0
    niveau_seniorite: str = "Non déterminé"
    total_competences: int = 0


# ================================================================
# Modèle principal
# ================================================================


class CVDataStructured(BaseModel):
    """
    Structure JSON complète pour un CV parsé.

    Exemple :
    {
      "identite": {"nom_complet": "Jean Dupont", "prenom": "Jean", "nom": "Dupont"},
      "contacts": {"email": "jean@mail.com", "telephone": "+33 6 12 34 56 78"},
      "competences": [{"name": "Python", "category": "langages", "years": 7, "level": "Avancé"}],
      "formations": [{"diplome": "Master", "specialite": "Informatique", "annee": 2020, "niveau_bac_plus": 5}],
      "experiences": [{"entreprise": "Airbus", "poste": "Dev Python", "date_debut": "2020-01", ...}],
      "langues": [{"langue": "Français", "niveau": "Natif"}],
      "competences_par_categorie": {"langages": ["Python", "Java"]},
      "metadata": {...}
    }
    """

    identite: Identite = Field(default_factory=Identite)
    contacts: Contacts = Field(default_factory=Contacts)
    competences: List[Competence] = Field(default_factory=list)
    formations: List[Formation] = Field(default_factory=list)
    experiences: List[Experience] = Field(default_factory=list)
    langues: List[Langue] = Field(default_factory=list)
    competences_par_categorie: dict = Field(default_factory=dict)
    metadata: Metadata = Field(default_factory=Metadata)

    @model_validator(mode="after")
    def compute_metadata(self) -> "CVDataStructured":
        """Calcule les métadonnées dérivées automatiquement."""
        # Années d'expérience totales
        total_months = sum(e.duree_mois for e in self.experiences)
        self.metadata.annees_experience_totales = round(total_months / 12, 1)

        # Niveau formation max
        self.metadata.niveau_formation_max = max(
            (f.niveau_bac_plus or 0 for f in self.formations), default=0
        )

        # Total compétences
        self.metadata.total_competences = len(self.competences)

        # Niveau séniorité
        years = self.metadata.annees_experience_totales
        if years == 0:
            self.metadata.niveau_seniorite = "Junior"
        elif years <= 2:
            self.metadata.niveau_seniorite = "Junior"
        elif years <= 5:
            self.metadata.niveau_seniorite = "Confirmé"
        elif years <= 10:
            self.metadata.niveau_seniorite = "Senior"
        else:
            self.metadata.niveau_seniorite = "Expert"

        return self

    def to_json(self) -> str:
        """Sérialise en JSON indenté."""
        return self.model_dump_json(indent=2, exclude_none=False)

    def to_dict(self) -> dict:
        """Sérialise en dictionnaire Python."""
        return self.model_dump(exclude_none=False)
