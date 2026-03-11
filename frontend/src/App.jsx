import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import Home from './pages/Home'
import UploadCV from './pages/UploadCV'
import Candidates from './pages/Candidates'
import MyApplications from './pages/MyApplications'
import Login from './pages/Login'
import Register from './pages/Register'
import OAuthCallback from './pages/OAuthCallback'
import './App.css'

function App() {
  return (
    <AuthProvider>
      <div className="app">
        <Navbar />
        <main className="main-content">
          <Routes>
            {/* Public */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/auth/callback/google" element={<OAuthCallback provider="google" />} />
            <Route path="/auth/callback/linkedin" element={<OAuthCallback provider="linkedin" />} />

            {/* Protected — tous les rôles */}
            <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
            <Route path="/upload" element={<ProtectedRoute><UploadCV /></ProtectedRoute>} />

            {/* Recruteur / Admin uniquement */}
            <Route path="/candidates" element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><Candidates /></ProtectedRoute>} />

            {/* Candidat uniquement */}
            <Route path="/my-applications" element={<ProtectedRoute allowedRoles={["candidat"]}><MyApplications /></ProtectedRoute>} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  )
}

export default App
