import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/components/MainLayout'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Templates from '@/pages/Templates'
import Tasks from '@/pages/Tasks'
import TaskDetail from '@/pages/TaskDetail'
import Inspection from '@/pages/Inspection'
import Analytics from '@/pages/Analytics'
import Enterprises from '@/pages/Enterprises'
import Knowledge from '@/pages/Knowledge'
import Records from '@/pages/Records'
import NewInspection from '@/pages/NewInspection'
import RecordInspection from '@/pages/RecordInspection'
import Users from '@/pages/Users'
import Industries from '@/pages/Industries'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <MainLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="templates" element={<Templates />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="tasks/:id" element={<TaskDetail />} />
          <Route path="inspection/:id" element={<Inspection />} />
          <Route path="inspection/new" element={<NewInspection />} />
          <Route path="record/:id" element={<RecordInspection />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="enterprises" element={<Enterprises />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="records" element={<Records />} />
          <Route path="users" element={<Users />} />
          <Route path="industries" element={<Industries />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
