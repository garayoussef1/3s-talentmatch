import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import logo3S from "../assets/logo_3s.jpg";
import "./Login.css";

const GOOGLE_CLIENT_ID   = import.meta.env.VITE_GOOGLE_CLIENT_ID   || "";
const LINKEDIN_CLIENT_ID = import.meta.env.VITE_LINKEDIN_CLIENT_ID || "";

function generateOAuthState() {
  try {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
  } catch { return String(Date.now()); }
}

const PARTICLES = Array.from({ length: 22 }, (_, i) => ({
  id: i,
  size: Math.random() * 3 + 1.5,
  x: Math.random() * 100,
  y: Math.random() * 100,
  delay: Math.random() * 8,
  duration: 10 + Math.random() * 14,
  opacity: 0.15 + Math.random() * 0.35,
}));

const FEATURES = [
  { icon: "🧠", label: "Analyse avancée", sub: "Modèle spécialisé recrutement" },
  { icon: "📄", label: "Multi-formats", sub: "PDF · DOCX · Image · LaTeX" },
  { icon: "🌍", label: "FR + EN", sub: "Bilingue natif" },
  { icon: "⚡", label: "Temps réel", sub: "Analyse en quelques secondes" },
];

export default function Login() {
  const { login }    = useAuth();
  const navigate     = useNavigate();
  const [form, setForm]       = useState({ email: "", password: "" });
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const [typed, setTyped]     = useState("");
  const HEADLINE = "Recrutez les meilleurs talents avec une analyse automatisée des profils";

  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      setTyped(HEADLINE.slice(0, i + 1));
      i++;
      if (i >= HEADLINE.length) clearInterval(timer);
    }, 38);
    return () => clearInterval(timer);
  }, []);

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post("/auth/login", form);
      login(res.data.access_token, res.data.user);
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur de connexion");
    } finally {
      setLoading(false);
    }
  };

  const oauthGoogle = () => {
    if (!GOOGLE_CLIENT_ID) { setError("Google OAuth non configuré"); return; }
    const redirect = `${window.location.origin}/auth/callback/google`;
    const state    = generateOAuthState();
    sessionStorage.setItem("oauth_state_google", state);
    window.location.href =
      `https://accounts.google.com/o/oauth2/v2/auth?` +
      `client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${encodeURIComponent(redirect)}` +
      `&response_type=code&scope=openid%20email%20profile` +
      `&state=${encodeURIComponent(state)}&access_type=offline&prompt=consent`;
  };

  const oauthLinkedin = () => {
    if (!LINKEDIN_CLIENT_ID) { setError("LinkedIn OAuth non configuré"); return; }
    const redirect = `${window.location.origin}/auth/callback/linkedin`;
    const state    = generateOAuthState();
    sessionStorage.setItem("oauth_state_linkedin", state);
    window.location.href =
      `https://www.linkedin.com/oauth/v2/authorization?` +
      `response_type=code&client_id=${LINKEDIN_CLIENT_ID}` +
      `&redirect_uri=${encodeURIComponent(redirect)}` +
      `&state=${encodeURIComponent(state)}&scope=openid%20profile%20email`;
  };

  return (
    <div className="lp-root">

      {/* ── Fond animé ── */}
      <div className="lp-bg">
        <div className="lp-orb lp-orb-1" />
        <div className="lp-orb lp-orb-2" />
        <div className="lp-orb lp-orb-3" />
        <div className="lp-grid" />
        {PARTICLES.map((p) => (
          <span
            key={p.id}
            className="lp-particle"
            style={{
              width: p.size, height: p.size,
              left: `${p.x}%`, top: `${p.y}%`,
              opacity: p.opacity,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
            }}
          />
        ))}
      </div>

      {/* ── Contenu ── */}
      <div className="lp-content">

        {/* ══ Panneau gauche ══ */}
        <div className="lp-left">

          <div className="lp-brand">
            <img src={logo3S} alt="3S Informatique" className="lp-logo" />
            <div>
              <div className="lp-product">TalentMatch</div>
              <div className="lp-tagline">Powered by AI · 3S Informatique</div>
            </div>
          </div>

          <h1 className="lp-headline">
            {typed}
            <span className="lp-cursor">|</span>
          </h1>

          <p className="lp-desc">
            Plateforme RH intelligente qui analyse vos CVs, classe vos candidats
            et génère des rapports explicatifs grâce au deep learning.
          </p>

          <div className="lp-features">
            {FEATURES.map((f) => (
              <div key={f.label} className="lp-feat">
                <span className="lp-feat-icon">{f.icon}</span>
                <div>
                  <div className="lp-feat-label">{f.label}</div>
                  <div className="lp-feat-sub">{f.sub}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="lp-badge">
            <span className="lp-badge-dot" />
            Standard Sharing Software — 3S Informatique
          </div>
        </div>

        {/* ══ Panneau droit — carte ══ */}
        <div className="lp-right">
          <div className="lp-card">

            <div className="lp-card-header">
              <div className="lp-card-icon">🔐</div>
              <h2 className="lp-card-title">Connexion</h2>
              <p className="lp-card-sub">Accédez à votre espace TalentMatch</p>
            </div>

            {error && <div className="lp-error">{error}</div>}

            <form onSubmit={handleSubmit} className="lp-form">
              <label className="lp-label">
                Email
                <input
                  type="email" name="email" value={form.email}
                  onChange={handleChange} required
                  placeholder="nom@exemple.com"
                  className="lp-input"
                />
              </label>
              <label className="lp-label">
                Mot de passe
                <input
                  type="password" name="password" value={form.password}
                  onChange={handleChange} required minLength={6}
                  placeholder="••••••••"
                  className="lp-input"
                />
              </label>

              <div className="lp-row">
                <label className="lp-remember">
                  <input type="checkbox" defaultChecked />
                  Se souvenir
                </label>
                <Link to="/forgot-password" className="lp-forgot">
                  Mot de passe oublié ?
                </Link>
              </div>

              <button type="submit" className="lp-btn" disabled={loading}>
                {loading ? (
                  <><span className="lp-spinner" /> Connexion…</>
                ) : "Se connecter →"}
              </button>
            </form>

            <div className="lp-divider"><span>ou continuer avec</span></div>

            <div className="lp-oauth">
              <button className="lp-oauth-btn lp-oauth-btn--full" onClick={oauthGoogle} type="button">
                <svg viewBox="0 0 24 24" width="17" height="17">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Continuer avec Google
              </button>
            </div>

            <p className="lp-footer">
              Pas encore de compte ?{" "}
              <Link to="/register">Créer un compte</Link>
            </p>

            <div className="lp-secure">
              <span className="lp-secure-dot" />
              Connexion sécurisée · 3S Informatique
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
