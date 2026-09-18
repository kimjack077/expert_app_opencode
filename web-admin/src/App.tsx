import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/components/MainLayout'

const PageLoading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '360px' }}>
    <Spin size="large" tip="页面加载中..." />
  </div>
)

const Login = lazy(() => import('@/pages/Login'))
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Templates = lazy(() => import('@/pages/Templates'))
const Tasks = lazy(() => import('@/pages/Tasks'))
const TaskDetail = lazy(() => import('@/pages/TaskDetail'))
const InspectionForm = lazy(() => import('@/components/InspectionForm'))
const Analytics = lazy(() => import('@/pages/Analytics'))
const Enterprises = lazy(() => import('@/pages/Enterprises'))
const Knowledge = lazy(() => import('@/pages/Knowledge'))
const Records = lazy(() => import('@/pages/Records'))
const NewInspection = lazy(() => import('@/pages/NewInspection'))
const Users = lazy(() => import('@/pages/Users'))
const Industries = lazy(() => import('@/pages/Industries'))
// 审核项目模块
const AuditProjects = lazy(() => import('@/pages/AuditProjects'))
const CreateAuditProject = lazy(() => import('@/pages/AuditProjects/Create'))
const AuditProjectDetail = lazy(() => import('@/pages/AuditProjects/Detail'))
// 审核统计模块
const AuditStatistics = lazy(() => import('@/pages/AuditStatistics'))
// 我的审核任务
const MyAuditTasks = lazy(() => import('@/pages/MyAuditTasks'))
// 检查项详情
const AuditItemDetail = lazy(() => import('@/pages/AuditItemDetail'))
// 审核记录编辑
const AuditRecordEdit = lazy(() => import('@/pages/AuditRecordEdit'))
// 在线使用文档模块
const DocsPage = lazy(() => import('@/pages/Docs'))

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoading />}>
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
      </Suspense>
    </BrowserRouter>
  )
}

export default App
