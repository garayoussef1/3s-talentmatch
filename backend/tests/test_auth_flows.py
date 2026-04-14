"""Tests ciblés sur les flows Auth (OTP email + reset mot de passe).

Objectif: valider les endpoints FastAPI sans dépendre d'une vraie DB PostgreSQL.
On patch les fonctions de service (auth_service) appelées par les routes.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserRole, AuthProvider


@pytest.fixture()
def client():
    """TestClient avec dépendances override + cleanup après."""

    def override_get_db():
        db = MagicMock()
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app)

    app.dependency_overrides.clear()


def _fake_user(*, role: UserRole = UserRole.candidat, verified: bool = False) -> User:
    u = User()
    u.id = "00000000-0000-0000-0000-000000000001"
    u.nom = "Dupont"
    u.prenom = "Marie"
    u.email = "marie.dupont@local.test"
    u.role = role
    u.is_active = True
    u.is_email_verified = verified
    u.auth_provider = AuthProvider.local
    return u


class TestEmailVerificationOTP:
    def test_register_sends_code_and_returns_token(self, client):
        fake = _fake_user(role=UserRole.candidat, verified=False)

        with patch("app.routes.auth.get_user_by_email", return_value=None), \
             patch("app.routes.auth.create_user", return_value=fake), \
             patch("app.routes.auth.send_verification_code", return_value=True), \
             patch(
                 "app.routes.auth.user_to_token_response",
                 return_value={
                     "access_token": "token",
                     "token_type": "bearer",
                     "user": {
                         "id": str(fake.id),
                         "nom": fake.nom,
                         "prenom": fake.prenom,
                         "email": fake.email,
                         "role": fake.role.value,
                         "auth_provider": fake.auth_provider.value,
                         "avatar_url": None,
                         "is_active": True,
                         "is_email_verified": False,
                     },
                 },
             ):
            res = client.post(
                "/api/auth/register",
                json={
                    "nom": "Dupont",
                    "prenom": "Marie",
                    "email": "marie.dupont@local.test",
                    "password": "secret123",
                    "role": "candidat",
                },
            )

        assert res.status_code == 201
        payload = res.json()
        assert payload["access_token"] == "token"
        assert payload["user"]["email"] == "marie.dupont@local.test"

    def test_verify_email_ok(self, client):
        fake = _fake_user(role=UserRole.candidat, verified=False)

        async def override_current_user():
            return fake

        app.dependency_overrides[get_current_user] = override_current_user

        with patch("app.routes.auth.verify_email_code", return_value=True):
            res = client.post("/api/auth/verify-email", json={"code": "123456"})

        assert res.status_code == 200
        data = res.json()
        assert data["verified"] is True

    def test_verify_email_invalid_code_returns_400(self, client):
        fake = _fake_user(role=UserRole.candidat, verified=False)

        async def override_current_user():
            return fake

        app.dependency_overrides[get_current_user] = override_current_user

        with patch("app.routes.auth.verify_email_code", return_value=False):
            res = client.post("/api/auth/verify-email", json={"code": "000000"})

        assert res.status_code == 400
        assert "Code" in res.json().get("detail", "")


class TestForgotResetPassword:
    def test_forgot_password_returns_200_even_if_unknown_email(self, client):
        with patch("app.routes.auth.get_user_by_email", return_value=None):
            res = client.post("/api/auth/forgot-password", json={"email": "unknown@local.test"})

        assert res.status_code == 200
        assert "message" in res.json()

    def test_forgot_password_oauth_account_returns_200(self, client):
        fake = _fake_user(role=UserRole.candidat)
        fake.auth_provider = AuthProvider.google

        with patch("app.routes.auth.get_user_by_email", return_value=fake):
            res = client.post("/api/auth/forgot-password", json={"email": fake.email})

        assert res.status_code == 200
        assert "OAuth" in res.json().get("message", "")

    def test_reset_password_ok(self, client):
        fake = _fake_user(role=UserRole.candidat)

        with patch("app.routes.auth.get_user_by_email", return_value=fake), \
             patch("app.routes.auth.verify_reset_code_and_change_password", return_value=True):
            res = client.post(
                "/api/auth/reset-password",
                json={
                    "email": fake.email,
                    "code": "123456",
                    "new_password": "newsecret123",
                },
            )

        assert res.status_code == 200
        assert "réinitialisé" in res.json().get("message", "").lower()


class TestAdminCreateRecruiter:
    def test_admin_create_recruteur_requires_admin_dependency(self, client):
        # Pas d'override get_current_admin -> devrait retourner 403/401.
        res = client.post(
            "/api/auth/admin/create-recruteur",
            json={
                "nom": "HR",
                "prenom": "Admin",
                "email": "hr@local.test",
                "password": "secret123",
                "telephone": "0600000000",
            },
        )
        assert res.status_code in (401, 403)

    def test_admin_create_recruteur_ok(self, client):
        fake_admin = _fake_user(role=UserRole.admin, verified=True)
        fake_recruteur = _fake_user(role=UserRole.recruteur, verified=True)
        fake_recruteur.email = "recruteur@local.test"

        async def override_admin():
            return fake_admin

        app.dependency_overrides[get_current_admin] = override_admin

        with patch("app.routes.auth.get_user_by_email", return_value=None), patch(
            "app.routes.auth.create_user", return_value=fake_recruteur
        ):
            res = client.post(
                "/api/auth/admin/create-recruteur",
                json={
                    "nom": "Doe",
                    "prenom": "Recruiter",
                    "email": fake_recruteur.email,
                    "password": "secret123",
                    "telephone": "0600000000",
                },
            )

        assert res.status_code == 201
        data = res.json()
        assert data["email"] == fake_recruteur.email
        assert data["role"] == "recruteur"
