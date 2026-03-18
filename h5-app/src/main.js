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
import Home from './views/Home.vue'
import Tasks from './views/Tasks.vue'
import TaskDetail from './views/TaskDetail.vue'
import InspectionExecution from './views/InspectionExecution.vue'
import InspectList from './views/InspectList.vue'
import InspectItem from './views/InspectItem.vue'
import Profile from './views/Profile.vue'
import Records from './views/Records.vue'
import RecordDetail from './views/RecordDetail.vue'
import SelectEnterprise from './views/SelectEnterprise.vue'
import SelectTemplate from './views/SelectTemplate.vue'
import Statistics from './views/Statistics.vue'
import Settings from './views/Settings.vue'
import About from './views/About.vue'
import ReportPreview from './views/ReportPreview.vue'
// 审核项目模块
import AuditTasks from './views/AuditTasks.vue'
import AuditTaskDetail from './views/AuditTaskDetail.vue'

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
  { path: '/audit-tasks', component: AuditTasks },
  { path: '/audit-task/:id', component: AuditTaskDetail, name: 'AuditTaskDetail' },
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
