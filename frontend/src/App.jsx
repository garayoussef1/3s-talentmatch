import { Routes, Route, useLocation } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import Home from './pages/Home'
import UploadCV from './pages/UploadCV'
import AssessmentCandidate from './pages/AssessmentCandidate'
import Candidates from './pages/Candidates'
import CandidateDetail from './pages/CandidateDetail'
import MyApplications from './pages/MyApplications'
import MyAssessments from './pages/MyAssessments'
import MesDonnees from './pages/MesDonnees'
import AdminUsers from './pages/AdminUsers'
import OffersList  from './pages/OffersList'
import OfferNew    from './pages/OfferNew'
import OfferDetail from './pages/OfferDetail'
import CandidateOffers from './pages/CandidateOffers'
import Dashboard from './pages/Dashboard'
import CandidateOfferDetail from './pages/CandidateOfferDetail'
import Login from './pages/Login'
import Register from './pages/Register'
import OAuthCallback from './pages/OAuthCallback'
import VerifyEmail from './pages/VerifyEmail'
import ForgotPassword from './pages/ForgotPassword'
import './App.css'

function App() {
  const location = useLocation()

  return (
    <AuthProvider>
      <div className="app">
        {location.pathname !== '/login' && <Navbar />}
        <main className={`main-content ${location.pathname === '/login' ? 'main-content--full' : ''}`}>
          <ErrorBoundary>
            <Routes>
              {/* Public */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/evaluation/:token" element={<AssessmentCandidate />} />
              <Route path="/auth/callback/google" element={<OAuthCallback provider="google" />} />
              <Route path="/auth/callback/linkedin" element={<OAuthCallback provider="linkedin" />} />

              {/* Vérification email — authentifié mais pas forcément vérifié */}
              <Route path="/verify-email" element={<ProtectedRoute skipEmailCheck><VerifyEmail /></ProtectedRoute>} />

              {/* Protected — tous les rôles */}
              <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
              <Route path="/upload" element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><UploadCV /></ProtectedRoute>} />

              {/* Recruteur / Admin uniquement */}
              <Route path="/candidates" element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><Candidates /></ProtectedRoute>} />
              <Route path="/candidates/:cvId" element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><CandidateDetail /></ProtectedRoute>} />
              <Route path="/offers"      element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><OffersList  /></ProtectedRoute>} />
              <Route path="/offers/new"  element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><OfferNew    /></ProtectedRoute>} />
              <Route path="/offers/:id"  element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><OfferDetail /></ProtectedRoute>} />

              <Route path="/dashboard" element={<ProtectedRoute allowedRoles={["recruteur","admin"]}><Dashboard /></ProtectedRoute>} />

              {/* Admin uniquement */}
              <Route path="/admin/users" element={<ProtectedRoute adminOnly><AdminUsers /></ProtectedRoute>} />

              {/* Candidat uniquement */}
              <Route path="/jobs" element={<ProtectedRoute allowedRoles={["candidat"]}><CandidateOffers /></ProtectedRoute>} />
              <Route path="/jobs/:id" element={<ProtectedRoute allowedRoles={["candidat"]}><CandidateOfferDetail /></ProtectedRoute>} />
              <Route path="/my-applications" element={<ProtectedRoute allowedRoles={["candidat"]}><MyApplications /></ProtectedRoute>} />
              <Route path="/my-assessments" element={<ProtectedRoute allowedRoles={["candidat"]}><MyAssessments /></ProtectedRoute>} />
              <Route path="/mes-donnees" element={<ProtectedRoute allowedRoles={["candidat"]}><MesDonnees /></ProtectedRoute>} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </AuthProvider>
  )
}

export default App
