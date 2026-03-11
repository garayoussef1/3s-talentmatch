import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Protège une route :
 * - redirige vers /login si non authentifié.
 * - allowedRoles (optionnel) : tableau de rôles autorisés (ex: ["recruteur","admin"])
 * - adminOnly : raccourci pour n'autoriser que les admins
 */
function ProtectedRoute({ children, adminOnly = false, allowedRoles = null }) {
  const { isAuthenticated, isAdmin, user, loading } = useAuth();

  if (loading) return null;

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;

  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
}

export default ProtectedRoute;
