import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import UploadCV from './pages/UploadCV'
import Candidates from './pages/Candidates'
import './App.css'

function App() {
  return (
    <div className="app">
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<UploadCV />} />
          <Route path="/candidates" element={<Candidates />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
