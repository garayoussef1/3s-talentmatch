import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Protège une route : redirige vers /login si non authentifié.
 * Optionnel : adminOnly=true  → accessible uniquement aux admins.
 */
function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) return null; // évite le flash de redirection

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;

  return children;
}

export default ProtectedRoute;
