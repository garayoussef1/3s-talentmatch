from __future__ import annotations

from app.services.nlp.formation_extractor import FormationExtractor


def test_score_establishment_penalizes_specialty_only_name() -> None:
    extractor = FormationExtractor(nlp_model=None)

    # "Data Science" seul est une spécialité, pas un établissement.
    score_specialty = extractor._score_establishment("Data Science")
    score_real_school = extractor._score_establishment("ESPRIT")

    assert score_specialty < score_real_school


def test_score_establishment_does_not_penalize_institution_with_field() -> None:
    extractor = FormationExtractor(nlp_model=None)

    # Un vrai établissement peut contenir une spécialité.
    score_institut_info = extractor._score_establishment("Institut Supérieur d'Informatique")
    score_field_only = extractor._score_establishment("Informatique")

    assert score_institut_info > score_field_only


def test_score_establishment_data_science_institute_is_not_over_penalized() -> None:
    extractor = FormationExtractor(nlp_model=None)

    score_dsi = extractor._score_establishment("Data Science Institute")
    score_ds = extractor._score_establishment("Data Science")

    assert score_dsi > score_ds
