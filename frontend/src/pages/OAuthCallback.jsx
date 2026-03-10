import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import "./Login.css";

/**
 * Page de callback OAuth.
 * URL attendue : /auth/callback/:provider?code=xxx
 */
function OAuthCallback({ provider }) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setError("Code d'autorisation manquant");
      return;
    }

    const redirect_uri = `${window.location.origin}/auth/callback/${provider}`;

    api
      .post(`/auth/oauth/${provider}`, { code, redirect_uri })
      .then((res) => {
        login(res.data.access_token, res.data.user);
        navigate("/");
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail ||
            `Erreur d'authentification ${provider}`
        );
      });
  }, [provider, searchParams, login, navigate]);

  if (error) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-error">{error}</div>
          <p className="auth-footer">
            <a href="/login">Retour à la connexion</a>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card auth-loading">
        <div className="spinner" />
        <p>Connexion via {provider === "google" ? "Google" : "LinkedIn"}…</p>
      </div>
    </div>
  );
}

export default OAuthCallback;
