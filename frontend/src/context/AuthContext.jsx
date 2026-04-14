/**
 * Context d'authentification React — gère le state user/token globalement.
 */
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import api from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("user");
    if (!saved) return null;
    try {
      return JSON.parse(saved);
    } catch {
      // Évite écran blanc si le storage est corrompu (ex: 'undefined')
      localStorage.removeItem("user");
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  // Vérifier le profil au démarrage si un token existe
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      let timedOut = false;
      const timeoutId = window.setTimeout(() => {
        timedOut = true;
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setUser(null);
        setLoading(false);
      }, 8000);

      api
        .get("/auth/me")
        .then((res) => {
          if (timedOut) return;
          setUser(res.data);
          localStorage.setItem("user", JSON.stringify(res.data));
        })
        .catch(() => {
          if (timedOut) return;
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          setUser(null);
        })
        .finally(() => {
          if (timedOut) return;
          window.clearTimeout(timeoutId);
          setLoading(false);
        });

      return () => window.clearTimeout(timeoutId);
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback((token, userData) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(userData));
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  }, []);

  const isAuthenticated = !!user;
  const normalizedRole = (user?.role ?? "").toString().trim().toLowerCase();
  const isAdmin = normalizedRole === "admin";

  return (
    <AuthContext.Provider
      value={{ user, loading, login, logout, isAuthenticated, isAdmin }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
