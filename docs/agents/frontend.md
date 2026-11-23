# 前端约定

两个客户端（2026-11-23 起 `mobile-app` 与 Flutter `inspection_app` 停止维护，已移出项目）。

| 客户端 | 技术栈 | 开发端口 | 说明 |
|--------|--------|----------|------|
| `web-admin/` | React 18 + TS + Ant Design + Vite | 3000 | 管理后台（主战场） |
| `h5-app/` | Vue 3 + Vant + Vite | 5174 | 现场审核员移动端，base path `/h5/` |

两个客户端的 Vite dev server 都把 `/api` 和 `/uploads` 代理到
`http://localhost:8000`，`@` 别名指向 `src/`。API 地址由 `VITE_API_URL` 控制
（`.env.development` / `.env.production`）。
生产构建用 `esbuild.pure` 去掉 `console.log/debug`（`console.error/warn` 保留）。

## 命令

```bash
# web-admin
cd web-admin && npm install
npm run dev          # :3000
npm run build        # tsc && vite build
npx tsc --noEmit     # 仅类型检查（没有 lint/test 脚本）

# h5-app（Node ^20.19.0 || >=22.12.0）
cd h5-app && npm install
npm run dev          # :5174
npm run build        # run-p type-check build-only
npm run type-check   # vue-tsc --build
npm run format       # oxfmt src/
```

## web-admin 结构

```
web-admin/src/
├── pages/          # 按路由组织，每个目录一个页面
│   ├── AuditProjects/  # 审核项目管理（核心页面）
│   │                   # Detail.tsx 支持 ?tab=（team/plan/records/meetings/nonconformities/documents/artifacts），地址栏随页签同步
│   ├── AuditStatistics/ AuditItemDetail/ AuditRecordEdit/ MyAuditTasks/
│   ├── Templates/ Records/ Tasks/ TaskDetail/ NewInspection/
│   ├── Enterprises/    # index.tsx + EnterpriseSubResources.tsx（资质 / 产品 / 整改单）
│   ├── Knowledge/ Industries/ Users/ Analytics/ Dashboard/ Login/ Docs/ NotFound/
├── components/
│   ├── MainLayout.tsx      # 侧边栏 + 顶栏骨架（顶栏"?"打开 /docs）
│   ├── NotificationBell.tsx # 智审提醒铃铛：未读角标、2 分钟轮询、按类型跳转
│   ├── agent/              # Agent 侧边栏与对话组件
│   ├── brand/              # EasyAuditLogo.tsx 等品牌资产
│   ├── common/ InspectionForm/
│   ├── EnterpriseRiskProfile/  # 读真实 /enterprises/{id}/risk-profile
├── stores/         # Zustand：auth.ts、app.ts
├── services/       # api.ts（通用）、auditProjectApi.ts（审核项目域）
└── utils/          # display.ts / roles.ts / completion.ts / resultOptions.ts
                    # sessionGuard.ts：main.tsx 第一个 import；未勾"记住登录状态"时关浏览器即退出
```

路由在 `App.tsx`（没有 `router/` 目录）。未登录访问受保护页面会跳 `/login`，登录后回到原页面；未知路径显示 404。

日常检查任务**没有优先级字段**（`inspection_tasks` 表无此列），列表只按状态和关键词筛选。

**风格**：导入顺序 React → 第三方库 → `@/` 本地。组件用函数式 + hooks，
`export default` 且组件名 PascalCase；变量/函数 camelCase；类型 PascalCase。
状态 `const [s, setS] = useState<Type>()`，props 解构。
Ant Design 表单用 `Form` + `form.submit()`，提示用 `message.success()` / `message.error()`。
新增 API 调用放进 `services/` 的对应文件，不要在页面里直接写 axios。

## h5-app 结构

```
h5-app/src/
├── views/          # 页面组件
│   ├── AiAuditSession.vue / AuditSessionResult.vue   # AI 审核会话（Agent 主路径）
│   ├── TodayAudit.vue / AuditTasks.vue / AuditTaskDetail.vue（旧链接跳转页）
│   ├── InspectionExecution.vue / InspectItem.vue
│   ├── Records.vue / RecordDetail.vue / ReportPreview.vue / Statistics.vue
│   ├── Messages.vue  # 智审提醒（左滑标已读 / 忽略）
│   └── Home.vue / Login.vue / Profile.vue / Settings.vue / About.vue / NotFound.vue
│       SelectEnterprise.vue / SelectTemplate.vue / Tasks.vue / TaskDetail.vue
├── api/            # JavaScript 模块：request.js(拦截器) auth tasks records agent auditProjects
├── components/     # BottomNav / OfflineBanner / RiskAlertPopup / TreeItem
│                   # agent/（AgentChatPanel、AgentMessage、AgentActionCard、AgentFab）、brand/
├── utils/          # display.js / photoUtils.js / offlineCache.js / appSettings.js（通知开关等本机设置）
├── styles/
└── main.js         # 实际入口（index.html 引用 main.js；同目录的 main.ts 未被使用）
```

底部导航：今日审核 / 检查任务 / 记录 / 我的。根路径按登录状态跳 `/today-audit` 或 `/login`，
登录后按 `redirect` 参数回跳；未知路径显示 NotFound。
可选环境变量（`.env.production`）：`VITE_APP_VERSION`、`VITE_SUPPORT_CONTACT`、`VITE_DOCS_URL`。

**风格**：oxfmt——无分号、单引号。变量 camelCase，组件文件 PascalCase。
`<script setup>` + `ref()`。Vant 组件用 `van-` 前缀，无限滚动用
`van-pull-refresh` + `van-list`。样式一律 `scoped`，颜色走 CSS 变量
（`--primary-color`、`--bg-white`）。

```vue
<script setup>
import { ref, onMounted } from 'vue'
const items = ref([])
const loading = ref(false)
</script>
```

## 离线能力（当前状态：几乎没有，别照文档假设）

- **没有离线写队列，也没有本地记录持久化**。早期文档提到的
  `offlineStorage.js` / `uploadQueue.js` 已不存在。
- `utils/offlineCache.js` 只做读缓存；`components/OfflineBanner.vue` 监听
  `navigator.onLine` 弹提示条——都不缓冲、不重试写请求。
- Agent 路径依赖 SSE + 远端 LLM，**纯在线**，断网即不可用。
- `api/request.js` 拦截器遇 401 先用 `refresh_token` **单飞刷新并重试原请求**
  （两端均实现：web-admin 见 `services/api.ts`，h5 见 `api/request.js`；
  refresh_token 存 localStorage，由 Login 时写入）；刷新失败才清 token 跳 `/login`。
- `utils/display.js` 的 `formatTaskDisplay` 按 `-` 拆分"名称-区域"展示，
  但仅当首段 ≥4 字符才拆（防"QA-xxx"这类短前缀被割裂）；3 段以上按"项目-区域-日期"解析。
