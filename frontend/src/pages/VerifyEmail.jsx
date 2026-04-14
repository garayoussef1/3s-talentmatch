import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import "./VerifyEmail.css";

function VerifyEmail() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const inputRefs = useRef([]);

  // Redirect si déjà vérifié
  useEffect(() => {
    if (user?.is_email_verified) {
      navigate("/");
    }
  }, [user, navigate]);

  // Cooldown timer
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown((c) => c - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  const handleChange = (index, value) => {
    if (value.length > 1) value = value.slice(-1);
    if (value && !/^\d$/.test(value)) return;

    const newCode = [...code];
    newCode[index] = value;
    setCode(newCode);
    setError("");

    // Auto-focus next
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit quand tous les chiffres sont remplis
    if (newCode.every((d) => d !== "")) {
      submitCode(newCode.join(""));
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const paste = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (paste.length === 6) {
      const newCode = paste.split("");
      setCode(newCode);
      inputRefs.current[5]?.focus();
      submitCode(paste);
    }
  };

  const submitCode = async (codeStr) => {
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/verify-email", { code: codeStr });
      setSuccess("Email vérifié avec succès !");
      // Rafraîchir le profil
      const me = await api.get("/auth/me");
      login(localStorage.getItem("token"), me.data);
      setTimeout(() => navigate("/"), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Code invalide ou expiré");
      setCode(["", "", "", "", "", ""]);
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  const resendCode = async () => {
    if (resendCooldown > 0) return;
    try {
      await api.post("/auth/resend-code");
      setResendCooldown(60);
      setError("");
      setSuccess("Nouveau code envoyé !");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors du renvoi");
    }
  };

  return (
    <div className="verify-page">
      <div className="verify-card">
        <header className="verify-header">
          <div className="verify-hero">
            <div className="verify-icon">📬</div>
            <div>
              <span className="verify-eyebrow">Sécurité</span>
              <h2>Vérifiez votre email</h2>
              <p className="verify-subtitle">
                Un code à 6 chiffres a été envoyé à<br />
                <strong>{user?.email || "votre adresse email"}</strong>
              </p>
            </div>
          </div>
          <div className="verify-steps">
            <div className="verify-step">
              <span>1</span> Ouvrir l'email
            </div>
            <div className="verify-step">
              <span>2</span> Copier le code
            </div>
            <div className="verify-step">
              <span>3</span> Confirmer ici
            </div>
          </div>
        </header>

        {error && <div className="verify-error">{error}</div>}
        {success && <div className="verify-success">{success}</div>}

        <div className="otp-inputs" onPaste={handlePaste}>
          {code.map((digit, i) => (
            <input
              key={i}
              ref={(el) => (inputRefs.current[i] = el)}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              className={`otp-input ${digit ? "filled" : ""}`}
              disabled={loading}
              autoFocus={i === 0}
            />
          ))}
        </div>

        {loading && <div className="verify-loading">Vérification…</div>}

        <div className="verify-actions">
          <button
            className="resend-btn"
            onClick={resendCode}
            disabled={resendCooldown > 0}
          >
            {resendCooldown > 0
              ? `Renvoyer dans ${resendCooldown}s`
              : "Renvoyer le code"}
          </button>
        </div>

        <p className="verify-hint">
          💡 Vérifiez vos spams si vous ne trouvez pas l'email.
          <br />
          Le code expire dans 15 minutes.
        </p>
      </div>
    </div>
  );
}

export default VerifyEmail;
