import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Protège une route :
 * - redirige vers /login si non authentifié.
 * - redirige vers /verify-email si email non vérifié (sauf si skipEmailCheck).
 * - allowedRoles (optionnel) : tableau de rôles autorisés (ex: ["recruteur","admin"])
 * - adminOnly : raccourci pour n'autoriser que les admins
 * - skipEmailCheck : ne pas vérifier is_email_verified (pour la page /verify-email)
 */
function ProtectedRoute({ children, adminOnly = false, allowedRoles = null, skipEmailCheck = false }) {
  const { isAuthenticated, isAdmin, user, loading } = useAuth();
  const userRole = (user?.role ?? "").toString().trim().toLowerCase();

  // En DEV, on désactive le blocage "email non vérifié" pour éviter de dépendre du SMTP.
  // En build prod, import.meta.env.DEV = false, donc la vérification reste active.
  const skipEmailVerificationInDev = import.meta.env.DEV;

  if (loading) return <div className="py-12 text-center text-gray-500">⏳ Chargement...</div>;

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  // Rediriger vers la vérification email si non vérifié
  // (sauf pour la page de vérification elle-même et les comptes OAuth)
  if (
    !skipEmailCheck &&
    !skipEmailVerificationInDev &&
    user &&
    !user.is_email_verified &&
    user.auth_provider === "local"
  ) {
    return <Navigate to="/verify-email" replace />;
  }

  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;

  if (allowedRoles) {
    const allowed = allowedRoles.map((r) => (r ?? "").toString().trim().toLowerCase());
    if (!allowed.includes(userRole)) {
      return <Navigate to="/" replace />;
    }
  }

  return children;
}

export default ProtectedRoute;
