import os
import sys

import pytest


# Setup import path (repo backend)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.nlp.entity_extractor import EntityExtractor  # noqa: E402
from app.services.nlp.nlp_parser import NLPParser  # noqa: E402


def test_is_plausible_name_rejects_broken_section_word():
    assert EntityExtractor._is_plausible_name("Form ation") is False


def test_is_plausible_name_rejects_broken_devops():
    assert EntityExtractor._is_plausible_name("Dev Ops") is False


def test_is_plausible_name_rejects_section_title_experiences_professionnelles():
    assert EntityExtractor._is_plausible_name("Expériences Professionnelles") is False


def test_is_plausible_name_accepts_normal_name():
    assert EntityExtractor._is_plausible_name("Jean Dupont") is True


@pytest.mark.parametrize(
    "email,expected",
    [
        ("jean.dupont@example.com", "Jean Dupont"),
        ("jean_dupont@example.com", "Jean Dupont"),
        ("jean-dupont@example.com", "Jean Dupont"),
        ("inesbensaad95@gmail.com", "Ines Ben Saad"),
    ],
)
def test_derive_name_from_email(email, expected):
    assert NLPParser._derive_name_from_email(email) == expected


@pytest.mark.parametrize(
    "email",
    [
        None,
        "",
        "not-an-email",
        "a.b@example.com",  # initiales
        "contact.hr@example.com",  # role mailbox
        "jean@example.com",  # pas de separateur
    ],
)
def test_derive_name_from_email_returns_none_when_ambiguous(email):
    assert NLPParser._derive_name_from_email(email) is None


def test_derive_name_from_email_does_not_overfit_ben_substring():
    # "rubenstein" contient "ben" mais ce n'est pas une particule de nom.
    assert NLPParser._derive_name_from_email("rubenstein@example.com") is None


@pytest.mark.parametrize(
    "name",
    [
        None,
        "",
        "Formation",
        "DevOps",
        "Compétences",
        "Profil",
        "Contact",
        "Dev Ops",
        "Form ation",
    ],
)
def test_is_name_suspicious_true_for_headers_or_job_titles(name):
    assert NLPParser._is_name_suspicious(name) is True
