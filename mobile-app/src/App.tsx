import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/auth'
import Login from './pages/Login'
import TaskList from './pages/TaskList'
import Inspection from './pages/Inspection'
import QuickCheck from './pages/QuickCheck'
import Profile from './pages/Profile'
import BottomNav from './components/BottomNav'
import './styles/app.css'

function AppContent() {
  const { token } = useAuthStore()

  if (!token) {
    return <Login />
  }

  return (
    <div className="app-container">
      <div className="page-content">
        <Routes>
          <Route path="/" element={<Navigate to="/tasks" replace />} />
          <Route path="/tasks" element={<TaskList />} />
          <Route path="/inspection/:taskId" element={<Inspection />} />
          <Route path="/quick-check" element={<QuickCheck />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </div>
      <BottomNav />
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}

export default App
