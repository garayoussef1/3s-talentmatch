import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import "./Login.css"; /* shared styles */

function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const skipEmailVerification =
    String(import.meta.env.VITE_SKIP_EMAIL_VERIFICATION || "false").toLowerCase() === "true";
  const [form, setForm] = useState({
    nom: "",
    prenom: "",
    email: "",
    password: "",
    password2: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (form.password !== form.password2) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }
    setLoading(true);
    try {
      const { password2, ...payload } = form;
      const res = await api.post("/auth/register", payload);
      login(res.data.access_token, res.data.user);
      navigate(skipEmailVerification ? "/" : "/verify-email");
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'inscription");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>Créer un compte</h2>
        <p className="auth-subtitle">
          Rejoignez 3S TalentMatch en quelques secondes
        </p>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form" autoComplete="off">
          <div className="form-row">
            <label>
              Nom
              <input
                name="nom"
                value={form.nom}
                onChange={handleChange}
                required
                placeholder="Dupont"
                autoComplete="family-name"
              />
            </label>
            <label>
              Prénom
              <input
                name="prenom"
                value={form.prenom}
                onChange={handleChange}
                required
                placeholder="Marie"
                autoComplete="given-name"
              />
            </label>
          </div>
          <label>
            Email
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
              placeholder="nom@exemple.com"
              autoComplete="email"
            />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              required
              placeholder="Min. 6 caractères"
              minLength={6}
              autoComplete="new-password"
            />
          </label>
          <label>
            Confirmer le mot de passe
            <input
              type="password"
              name="password2"
              value={form.password2}
              onChange={handleChange}
              required
              placeholder="••••••••"
              minLength={6}
              autoComplete="new-password"
            />
          </label>
          <button type="submit" className="btn-primary auth-btn" disabled={loading}>
            {loading ? "Création…" : "Créer mon compte"}
          </button>
        </form>

        <p className="auth-footer">
          Déjà un compte ?{" "}
          <Link to="/login">Se connecter</Link>
        </p>
      </div>
    </div>
  );
}

export default Register;
