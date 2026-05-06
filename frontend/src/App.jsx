import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Home from './pages/Home'
import CoachRegister from './pages/CoachRegister'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <nav className="navbar">
        <Link to="/">Inicio</Link>
        <Link to="/coach/register">Registro Coach</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/coach/register" element={<CoachRegister />} />
      </Routes>
    </BrowserRouter>
  )
}
