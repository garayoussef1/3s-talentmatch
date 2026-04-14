import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../services/api";
import "./ForgotPassword.css";

function ForgotPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1); // 1=email, 2=code+nouveau mdp
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSendCode = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post("/auth/forgot-password", { email });
      setSuccess(res.data.message);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'envoi");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setError("");
    if (newPassword !== newPassword2) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }
    if (newPassword.length < 6) {
      setError("Le mot de passe doit contenir au moins 6 caractères");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/auth/reset-password", {
        email,
        code,
        new_password: newPassword,
      });
      setSuccess(res.data.message);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || "Code invalide ou expiré");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="forgot-page">
      <div className="forgot-card">
        <div className="forgot-icon">{step === 1 ? "🔑" : "🔐"}</div>
        <h2>{step === 1 ? "Mot de passe oublié" : "Réinitialiser le mot de passe"}</h2>
        <p className="forgot-subtitle">
          {step === 1
            ? "Entrez votre adresse email pour recevoir un code de réinitialisation."
            : `Un code a été envoyé à ${email}`}
        </p>

        {error && <div className="forgot-error">{error}</div>}
        {success && <div className="forgot-success">{success}</div>}

        {step === 1 ? (
          <form onSubmit={handleSendCode} className="forgot-form">
            <label>
              Adresse email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="nom@exemple.com"
                autoFocus
              />
            </label>
            <button type="submit" className="btn-primary forgot-btn" disabled={loading}>
              {loading ? "Envoi…" : "Envoyer le code"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleReset} className="forgot-form">
            <label>
              Code de vérification (6 chiffres)
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                required
                placeholder="000000"
                maxLength={6}
                inputMode="numeric"
                autoFocus
                className="code-input"
              />
            </label>
            <label>
              Nouveau mot de passe
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                placeholder="Min. 6 caractères"
                minLength={6}
              />
            </label>
            <label>
              Confirmer le nouveau mot de passe
              <input
                type="password"
                value={newPassword2}
                onChange={(e) => setNewPassword2(e.target.value)}
                required
                placeholder="••••••••"
                minLength={6}
              />
            </label>
            <button type="submit" className="btn-primary forgot-btn" disabled={loading}>
              {loading ? "Réinitialisation…" : "Réinitialiser mon mot de passe"}
            </button>
            <button
              type="button"
              className="back-btn"
              onClick={() => { setStep(1); setError(""); setSuccess(""); }}
            >
              ← Changer l'adresse email
            </button>
          </form>
        )}

        <p className="forgot-footer">
          <Link to="/login">← Retour à la connexion</Link>
        </p>
      </div>
    </div>
  );
}

export default ForgotPassword;
