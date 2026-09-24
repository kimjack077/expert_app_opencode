import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

// Vant UI
import { Button, Cell, CellGroup, Field, Form, NavBar, Tabbar, TabbarItem, List, PullRefresh, Card, Tag, Toast, Dialog, ActionSheet, Uploader, Icon, Search, Empty, Loading, Skeleton, Checkbox, CheckboxGroup, Radio, RadioGroup, NoticeBar, SubmitBar, Popup, SwipeCell, Badge, Divider, Image as VanImage, Progress, Stepper, Collapse, CollapseItem } from 'vant'
import 'vant/lib/index.css'

// Global Styles
import './styles/global.css'

// 路由
import Login from './views/Login.vue'

const Home = () => import('./views/Home.vue')
const Tasks = () => import('./views/Tasks.vue')
const TaskDetail = () => import('./views/TaskDetail.vue')
const InspectionExecution = () => import('./views/InspectionExecution.vue')
const InspectItem = () => import('./views/InspectItem.vue')
const Profile = () => import('./views/Profile.vue')
const Records = () => import('./views/Records.vue')
const RecordDetail = () => import('./views/RecordDetail.vue')
const SelectEnterprise = () => import('./views/SelectEnterprise.vue')
const SelectTemplate = () => import('./views/SelectTemplate.vue')
const Statistics = () => import('./views/Statistics.vue')
const Settings = () => import('./views/Settings.vue')
const About = () => import('./views/About.vue')
const ReportPreview = () => import('./views/ReportPreview.vue')
const AuditTasks = () => import('./views/AuditTasks.vue')
const AuditTaskDetail = () => import('./views/AuditTaskDetail.vue')
const TodayAudit = () => import('./views/TodayAudit.vue')
const AiAuditSession = () => import('./views/AiAuditSession.vue')
const AuditSessionResult = () => import('./views/AuditSessionResult.vue')

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/home', component: Home },
  { path: '/select-enterprise', component: SelectEnterprise },
  { path: '/select-template', component: SelectTemplate },
  { path: '/tasks', component: Tasks },
  { path: '/task/:id', component: TaskDetail },
  { path: '/task/:id/execute', component: InspectionExecution },
  { path: '/inspection/:id', component: InspectionExecution },
  { path: '/inspection/:id/item/:itemId', component: InspectItem },
  { path: '/records', component: Records },
  { path: '/record/:id', component: RecordDetail },
  { path: '/record/:id/report', component: ReportPreview },
  { path: '/profile', component: Profile },
  { path: '/statistics', component: Statistics },
  { path: '/settings', component: Settings },
  { path: '/about', component: About },
  // 审核项目模块
  { path: '/today-audit', component: TodayAudit, name: 'TodayAudit' },
  { path: '/audit-tasks', component: AuditTasks },
  { path: '/audit-task/:id', component: AuditTaskDetail, name: 'AuditTaskDetail' },
  { path: '/audit-session/:sessionId', component: AiAuditSession, name: 'AiAuditSession' },
  // 已完成审核：只读结果页（非现场录入界面）
  { path: '/audit-result/:sessionId', component: AuditSessionResult, name: 'AuditSessionResult' },
]

const router = createRouter({
  history: createWebHistory('/h5/'),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else {
    next()
  }
})

const app = createApp(App)

// 注册 Vant 组件
app.use(Button)
app.use(Cell)
app.use(CellGroup)
app.use(Field)
app.use(Form)
app.use(NavBar)
app.use(Tabbar)
app.use(TabbarItem)
app.use(List)
app.use(PullRefresh)
app.use(Card)
app.use(Tag)
app.use(Toast)
app.use(Dialog)
app.use(ActionSheet)
app.use(Uploader)
app.use(Icon)
app.use(Search)
app.use(Empty)
app.use(Loading)
app.use(Skeleton)
app.use(Checkbox)
app.use(CheckboxGroup)
app.use(Radio)
app.use(RadioGroup)
app.use(NoticeBar)
app.use(SubmitBar)
app.use(Popup)
app.use(SwipeCell)
app.use(Badge)
app.use(Divider)
app.use(VanImage)
app.use(Progress)
app.use(Stepper)
app.use(Collapse)
app.use(CollapseItem)

app.use(router)
app.mount('#app')
