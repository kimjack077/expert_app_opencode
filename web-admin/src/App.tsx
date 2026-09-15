import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/components/MainLayout'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Templates from '@/pages/Templates'
import Tasks from '@/pages/Tasks'
import TaskDetail from '@/pages/TaskDetail'
import InspectionForm from '@/components/InspectionForm'
import Analytics from '@/pages/Analytics'
import Enterprises from '@/pages/Enterprises'
import Knowledge from '@/pages/Knowledge'
import Records from '@/pages/Records'
import NewInspection from '@/pages/NewInspection'
import Users from '@/pages/Users'
import Industries from '@/pages/Industries'
// 审核项目模块
import AuditProjects from '@/pages/AuditProjects'
import CreateAuditProject from '@/pages/AuditProjects/Create'
import AuditProjectDetail from '@/pages/AuditProjects/Detail'
// 审核统计模块
import AuditStatistics from '@/pages/AuditStatistics'
// 我的审核任务
import MyAuditTasks from '@/pages/MyAuditTasks'
// 检查项详情
import AuditItemDetail from '@/pages/AuditItemDetail'
// 审核记录编辑
import AuditRecordEdit from '@/pages/AuditRecordEdit'

// 在线使用文档模块
import DocsPage from '@/pages/Docs'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        {/* 在线文档中心 (全屏独立现代技术文档布局) */}
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/docs/:docId" element={<DocsPage />} />
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
          <Route path="inspection/:id" element={<InspectionForm backPath="/tasks" />} />
          <Route path="inspection/new" element={<NewInspection />} />
          <Route path="record/:id" element={<InspectionForm backPath="/records" />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="enterprises" element={<Enterprises />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="records" element={<Records />} />
          <Route path="users" element={<Users />} />
          <Route path="industries" element={<Industries />} />
          {/* 审核项目模块 */}
          <Route path="audit-projects" element={<AuditProjects />} />
          <Route path="audit-projects/create" element={<CreateAuditProject />} />
          <Route path="audit-projects/:id" element={<AuditProjectDetail />} />
          <Route path="audit-projects/:id/edit" element={<CreateAuditProject />} />
          <Route path="audit-projects/:projectId/records/:recordId" element={<AuditRecordEdit />} />
          {/* 审核统计模块 */}
          <Route path="audit-statistics" element={<AuditStatistics />} />
          {/* 我的审核任务 */}
          <Route path="my-audit-tasks" element={<MyAuditTasks />} />
          {/* 检查项详情 */}
          <Route path="audit-item/:recordId/:itemId" element={<AuditItemDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
