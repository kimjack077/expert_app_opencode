import { DocCategory, DocArticle } from '../types'

export const DOCS_CATEGORIES: DocCategory[] = [
  {
    id: 'core-principles',
    title: '🎯 核心原则与智能工作台',
    icon: 'DashboardOutlined',
    description: '业务双轨分离、人在回路原则、智能工作台待办对账与合规率口径（第一幕）',
    articles: [],
  },
  {
    id: 'template-design',
    title: '📐 检查模板设计与防呆机制',
    icon: 'FormOutlined',
    description: '根节点分类目录治理、父节点防呆锁定、表单域隐藏与精准对账（第二幕）',
    articles: [],
  },
  {
    id: 'knowledge-regulations',
    title: '📚 全局法规知识库 (Markdown模式)',
    icon: 'BookOutlined',
    description: 'Markdown 结构化解析、在线校对预览、流式向量索引与 RAG 检索（第三幕）',
    articles: [],
  },
  {
    id: 'enterprise-projects',
    title: '🏢 企业档案与审核项目策划',
    icon: 'AuditOutlined',
    description: '受审核企业全景、「审核工作量（人天）」释义 Tooltip、体系与排期（第四幕）',
    articles: [],
  },
  {
    id: 'project-materials-agent',
    title: '🤖 项目资料与智审 Agent 协同',
    icon: 'RobotOutlined',
    description: '项目资料受控强隔离（project_id）、Agent 自然语言生成首末次会议卡片（第五幕）',
    articles: [],
  },
  {
    id: 'h5-field-inspection',
    title: '📱 H5 移动端现场实操 (核心体验)',
    icon: 'MobileOutlined',
    description: '自适应纵向滚动、大类横幅树形分组、彻底无 na 业务释义、叶子进度（第六/七幕）',
    articles: [],
  },
  {
    id: 'h5-ai-offline',
    title: '⚡ 现场 AI 会话与离线弱网保障',
    icon: 'ThunderboltOutlined',
    description: '现场口述/拍照提交、多条款智能研判、确认卡写入、NC草稿、离线缓存（第八幕）',
    articles: [],
  },
  {
    id: 'records-reports-gate',
    title: '📑 树形记录追溯与合规报告生成',
    icon: 'FileDoneOutlined',
    description: '记录抽屉分类卡片高亮（彻底消灭未填写）、表三明细横幅、字符清洁（第八幕）',
    articles: [],
  },
  {
    id: 'quality-gate-delivery',
    title: '🔒 多重要素质量门禁与交付归档包',
    icon: 'SafetyCertificateOutlined',
    description: '多重要素质量门禁防线阻断、带 SHA-256 防伪清单的 ZIP 归档成果包（第九幕）',
    articles: [],
  },
  {
    id: 'faq-troubleshoot',
    title: '💡 常见问题与应急预案 (FAQ)',
    icon: 'QuestionCircleOutlined',
    description: '现场断网弱网应急、分类目录不打分答疑、LLM 双通道容灾热备与快捷键速查',
    articles: [],
  },
]

export const DOCS_ARTICLES: DocArticle[] = [
  // =========================================================================
  // 第一幕：系统登录与智能工作台
  // =========================================================================
  {
    id: 'platform-principles',
    title: '平台定位与三大核心原则',
    category: 'core-principles',
    order: 1,
    description: '业务双轨分离、人在回路原则与项目数据强隔离机制',
    badge: '最高纲领',
    routeLink: '/dashboard',
    actionText: '进入工作台',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['核心原则', '业务双轨分离', '人在回路', '项目隔离', '认证审核'],
    intro: '易审通 (EasyAudit / EFIS) 是面向认证机构、审核员与评审专家的认证审核与现场评审智能云平台。为保证系统的合规性、权威性与严谨性，平台在架构设计上严格贯彻三大核心原则。',
    sections: [
      {
        id: 'principle-1',
        title: '1. 业务双轨分离原则',
        level: 2,
        content: '系统严格区分两大工作流，两套流程职责分明、不可混淆：',
        keyPoints: [
          '📋 正式认证审核主流程：走“审核项目 ➔ 我的审核任务 / 今日审核 ➔ 现场审核”，支持多体系 (QMS/EMS/OHSMS/EnMS)、首末次会议、完整多媒体证据链、多重要素质量门禁与交付级资料包。',
          '🔍 日常检查巡查流程：走“日常检查任务 ➔ 现场检查执行 ➔ 检查记录”，专供车间日常巡查、单点专项飞检，轻便灵活。',
        ],
      },
      {
        id: 'principle-2',
        title: '2. AI 辅助原则（人在回路 Human-in-the-Loop）',
        level: 2,
        content: 'AI 是专业审核员的“超级副驾驶”，绝非最终裁决者。所有 AI 生成的模板项、判定意见、不符合项草稿必须经由持证审核员人工采纳、修改或驳回后方可落库；无论 AI 是否在线，审核员均可通过纯手工模式完成 100% 审核工作。',
        callout: {
          type: 'warning',
          title: '人在回路法定责任',
          content: '审核结论与不符合项的法律与规范责任始终由持证审核组长及专业审核员签署承担。',
        },
      },
      {
        id: 'principle-3',
        title: '3. 项目资料强隔离与隐私保护',
        level: 2,
        content: '所有上传的企业项目资料均强制绑定 project_id 进行物理与向量隔离，绝不允许跨企业、跨项目交叉检索或引用，确保商业机密与企业专有技术 100% 安全。',
      },
    ],
  },
  {
    id: 'dashboard-guide',
    title: '智能工作台与精准对账（第一幕）',
    category: 'core-principles',
    order: 2,
    description: '待办任务精准对账、合规率严谨口径说明与多维态势看板',
    badge: '第一幕',
    routeLink: '/dashboard',
    actionText: '进入工作台',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['工作台', '待办对账', '合规率口径', '不适用剔除', 'KPI'],
    intro: '演示第一幕重点：展示现代化专业 UI、工作台多维态势、精准对账的待办任务流水线与规范严谨的合规率统计口径。',
    sections: [
      {
        id: 'dashboard-login',
        title: '快捷角色登录',
        level: 2,
        content: '登录页面展示动态流光背景，并提供「管理员 admin/admin123」与「审核专家 expert/expert123」一键快捷体验卡片：',
        image: {
          src: '/docs-assets/web_01_login.png',
          caption: '图 1-1：Web 管理端登录界面与快捷身份卡片',
        },
      },
      {
        id: 'dashboard-overview',
        title: '工作台待办对账与合规率口径详解',
        level: 2,
        content: '登录进入工作台后，核心区域直观展示全生命周期关键指标：',
        image: {
          src: '/docs-assets/web_02_dashboard.png',
          caption: '图 1-2：工作台待办任务精准对账与合规率严格口径看板',
        },
        steps: [
          {
            title: '待办任务精准对账',
            desc: '卡片明确展示“进行中”与“待开始”任务数量，数字满足「待办 = 进行中 + 待开始」，与下方的待办流水线完全对齐。',
          },
          {
            title: '合规率口径显式呈现',
            desc: '副标题清晰标注：“全生命周期协同 · 优先处理待办事项（合规率口径 = 已填报合格项 / 已填报项）”。分子分母科学地将「不适用项」与「未填报项」严格排除，体现认证评审的专业严密性。',
          },
          {
            title: '可视化走势分析',
            desc: '展示 14 日审核任务推进走势、综合合规率柱状图与企业风险等级分布饼图，项目瓶颈一览无余。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 第二幕：检查模板设计与层级规范化
  // =========================================================================
  {
    id: 'template-editor-v2',
    title: '检查模板设计与层级防呆（第二幕 · 核心看点）',
    category: 'template-design',
    order: 1,
    description: '根节点与分类目录治理、父节点防呆锁定、表单域隐藏与条目精准对账',
    badge: '第二幕重磅',
    routeLink: '/templates',
    actionText: '前往检查模板',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['模板设计', '根节点重构', '分类目录', '防呆锁定', '条目对账', 'TemplateEditorV2'],
    intro: '演示第二幕核心：展示系统重大的“根节点与层级关系重构”，证明系统彻底杜绝了“根节点既当分类目录又当检查项打分”的行业通病，实现分类目录与活跃叶子项的严格分离！',
    sections: [
      {
        id: 'template-list-stat',
        title: '模板列表精准统计对账（P0-03 根治）',
        level: 2,
        content: '进入「检查模板」模块，关注表格中的“条目统计”列：',
        image: {
          src: '/docs-assets/web_14_templates.png',
          caption: '图 2-1：检查模板列表与条目统计列（如 5条 · 3目录 · 2检查项）',
        },
        keyPoints: [
          '📊 统计对账恒等式：系统已全面自动剔除软删除历史条目，并严格按照“活跃叶子项”统计检查项，三者恒满足：total_items = categories + check_items（如 5 = 3 + 2）。',
          '🚫 彻底消除失真：从源头上杜绝了以往“检查项数字对不上”的行业顽疾。',
        ],
      },
      {
        id: 'parent-node-lock',
        title: '选中有子项父节点：防呆锁定演示',
        level: 2,
        content: '点击“编辑检查项”进入 TemplateEditorV2，在左侧树形结构选中任意包含子项的父节点：',
        image: {
          src: '/docs-assets/w_editor_parent.png',
          caption: '图 2-2：选中有子项父节点时，顶部弹出防呆 Alert 且输入域彻底隐藏',
        },
        steps: [
          {
            title: '1. 醒目 Alert 提示立即生效',
            desc: '右侧表单顶部弹出蓝色警示：“当前节点包含下级子项，系统已将其规范为「分类目录」，仅作为层级分组容器，不可录入打分、判定等检查项内容。”',
          },
          {
            title: '2. Switch 强行置灰禁用',
            desc: '“条目属性：分类目录 / 检查项”开关强制锁定开启并置灰禁用，杜绝用户误操作将父节点设为检查项。',
          },
          {
            title: '3. 16 项检查项表单域瞬间隐藏',
            desc: '采集结果类型、风险等级、合格阈值、检查方法、法律依据、AI 提示词等全部表单项瞬间隐藏，界面干净清爽。保存时后端数据库父节点属性被彻底洗净！',
          },
        ],
      },
      {
        id: 'leaf-node-config',
        title: '选中活跃叶子项：完整指标配置',
        level: 2,
        content: '展开左侧节点，选中底部的活跃叶子项：',
        image: {
          src: '/docs-assets/w_editor_leaf.png',
          caption: '图 2-3：选中叶子检查项时，Alert 消失并恢复完整的采集指标表单',
        },
        steps: [
          {
            title: 'Alert 消失与开关解锁',
            desc: '右侧 Alert 自动消失，Switch 恢复为可选状态。',
          },
          {
            title: '全要素检查项配置',
            desc: '采集类型（单选/数值/文本）、异常风险等级、标准编号、操作指导、必要附件配置等完整检查项表单恢复呈现。',
          },
          {
            title: 'AI 智审提示词配置',
            desc: '可为该叶子项开启“是否允许 AI 智能判断”，并定制专属的“AI 研判提示词模板”。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 第三幕：全局法规知识库
  // =========================================================================
  {
    id: 'knowledge-markdown',
    title: '全局法规知识库与 Markdown 流式索引（第三幕）',
    category: 'knowledge-regulations',
    order: 1,
    description: 'Markdown 结构化解析、在线校对预览、流式向量切块与 RAG 检索',
    badge: '第三幕',
    routeLink: '/knowledge',
    actionText: '进入知识库',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['知识库', 'Markdown解析', '流式切块', 'SSE进度', 'RAG检索'],
    intro: '演示第三幕：展示行业领先的非结构化标准文档结构化入库与 SSE 流式向量切块能力，支持在线校对预览与带文档出处的精准检索。',
    sections: [
      {
        id: 'two-phase-parse',
        title: '两阶段智能解析与在线校对',
        level: 2,
        content: '进入「知识库 ➔ 政策法规」，支持上传标准文档（如 GB/T 19001-2016 质量管理体系要求）：',
        image: {
          src: '/docs-assets/web_16_knowledge.png',
          caption: '图 3-1：知识库政策法规列表与分类检索',
        },
        steps: [
          {
            title: '结构化转换为 Markdown',
            desc: '调用结构化解析引擎，将 PDF 自动转换为保留标题层级与二维 Markdown 表格的高质量正文。',
          },
          {
            title: '在线预览与人工校对',
            desc: '在入库前通过在线编辑器审阅解析出的 Markdown，确认表格与条款编号无误。',
          },
          {
            title: 'SSE 流式建立向量索引',
            desc: '点击确认入库后，界面展示实时流式进度（15% 切块 ➔ 25% 生成 Embedding ➔ 100% 完成），生成带 <Markdown> 标识的高质量知识条目。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 第四幕：企业档案与审核项目策划
  // =========================================================================
  {
    id: 'enterprises-projects',
    title: '企业档案与审核项目策划（第四幕）',
    category: 'enterprise-projects',
    order: 1,
    description: '企业全景画像、「审核工作量（人天）」业务释义 Tooltip、体系与排期',
    badge: '第四幕',
    routeLink: '/audit-projects/create',
    actionText: '新建审核项目',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['企业管理', '审核工作量', '人天释义', '多体系立项', '审核计划'],
    intro: '演示第四幕：展示多体系项目立项、「审核工作量（人天）」严谨业务定义与审核计划自动派发。',
    sections: [
      {
        id: 'enterprise-profile',
        title: '示范受审企业档案画像',
        level: 2,
        content: '在「企业管理」中查看示范企业（如“山东盛发焦化有限公司”）：',
        image: {
          src: '/docs-assets/web_17_enterprises.png',
          caption: '图 4-1：受审核企业数据库与客户全景画像',
        },
      },
      {
        id: 'project-create-manday',
        title: '立项与「审核工作量（人天）」释义 Tooltip',
        level: 2,
        content: '进入「创建审核项目」，输入项目名称并勾选认证体系（Q/E/S/En 四体系）：',
        image: {
          src: '/docs-assets/web_05_project_create.png',
          caption: '图 4-2：新建审核项目表单与工作量人天释义',
        },
        steps: [
          {
            title: '字段严谨重命名（P2-08 重点）',
            desc: '系统已将以往产生歧义的“审核人天数”规范重命名为「审核工作量（人天）」。',
          },
          {
            title: '悬浮查看官方 Tooltip',
            desc: '鼠标悬浮字段旁的 (?) 图标，弹出清晰释义：“指全体审核员现场工作天数之和（例如：2 名审核员现场工作 3 天即为 6 人天）”。',
          },
          {
            title: '起止日期合理性校验',
            desc: '系统智能校验审核工作量与现场起始日期的匹配关系，防止非理性排单。',
          },
        ],
      },
      {
        id: 'project-plan-schedule',
        title: '审核组分工与计划日程排期',
        level: 2,
        content: '在项目详情的“审核计划”中创建各部门核查日程，关联已发布的演示模板，系统底层自动为活跃叶子项生成审核记录单：',
        image: {
          src: '/docs-assets/web_08_project_plan.png',
          caption: '图 4-3：审核计划日程排期与部门分工',
        },
      },
    ],
  },

  // =========================================================================
  // 第五幕：项目资料接入与智审 Agent 会议管理
  // =========================================================================
  {
    id: 'project-agent-meetings',
    title: '项目资料受控隔离与智审 Agent 会议管理（第五幕）',
    category: 'project-materials-agent',
    order: 1,
    description: '项目资料 project_id 强隔离、智审 Agent 自然语言一键生成首末次会议纪要',
    badge: '第五幕',
    routeLink: '/audit-projects',
    actionText: '查看项目协同',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['项目资料隔离', '智审Agent', '首末次会议', 'CommunicationMeeting', '人在回路卡片'],
    intro: '演示第五幕：展示项目资料带 project_id 的强安全隔离检索，以及智审 Agent 自然语言生成首末次会议纪要并受控落库的高效体验。',
    sections: [
      {
        id: 'materials-isolation',
        title: '受控项目资料强隔离',
        level: 2,
        content: '在项目详情的「项目资料」选项卡上传企业体系文件，系统强制绑定 project_id 切块。该资料仅在本项目审核时被调用，杜绝跨企业数据穿透。',
      },
      {
        id: 'agent-meeting-gen',
        title: '智审 Agent 自然语言生成首次会议纪要',
        level: 2,
        content: '点击右下角“智审 Agent”展开侧边协同抽屉，直接下达自然语言指令：',
        image: {
          src: '/docs-assets/web_11_ai_agent.png',
          caption: '图 5-1：智审 Agent 交互抽屉与会议生成 Action Proposal 确认卡',
        },
        steps: [
          {
            title: '输入自然语言诉求',
            desc: '输入：“请为本项目生成首次会议纪要，参会人员包括企业总经理、质量负责人、审核组全体成员，会议确认了审核范围与现场安全注意事项。”',
          },
          {
            title: 'Agent 产出格式化确认卡片',
            desc: 'Agent 检索项目元数据，输出会议时间、地点、参会人员与标准化议程的「操作确认卡」。',
          },
          {
            title: '人工确认受控写入数据库',
            desc: '审核员核对无误后点击卡片上的“确认并写入数据库”，数据瞬间落库至 CommunicationMeeting 表并在会议面板实时呈现！',
          },
        ],
      },
      {
        id: 'meeting-panel-display',
        title: '会议管理面板即时沉淀',
        level: 2,
        content: '确认写入后，在项目详情的「会议管理」板块即刻呈现标准的首末次会议记录与签到证明：',
        image: {
          src: '/docs-assets/web_09_project_meetings.png',
          caption: '图 5-2：会议管理板块中沉淀的首末次会议卡片与签到存证',
        },
      },
    ],
  },

  // =========================================================================
  // 第六幕 & 第七幕：H5 移动端现场实操全景 (用户最关注核心！)
  // =========================================================================
  {
    id: 'h5-field-inspection',
    title: 'H5 移动端现场检查实操全攻略（第六幕 · 核心体验）',
    category: 'h5-field-inspection',
    order: 1,
    description: '自适应顺畅滚动、大类横幅树形分组、彻底无 na 业务释义、叶子项实时进度',
    badge: '第六幕核心',
    routeLink: '/my-audit-tasks',
    actionText: '查看我的任务',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['H5现场检查', '自适应滚动', '树形大类横幅', '合格不合格不适用', '叶子项进度', '无na'],
    intro: '演示第六幕重点：展示移动端流畅滚动、大类分类树形横幅分组、业务枚举规范化（彻底告别 na）与精准叶子进度计算！',
    sections: [
      {
        id: 'h5-login-tasks',
        title: '移动端登录与任务列表对账（P0-03 验证）',
        level: 2,
        content: '手机打开 H5 端，选择“审核专家”快捷登录，点击底部“任务”Tab：',
        image: {
          src: '/docs-assets/h5_03_tasks_list.png',
          caption: '图 6-1：H5 任务列表与状态对账（待处理 + 进行中 + 已完成 = 总数）',
        },
        keyPoints: [
          '📱 任务对账严格满足：页面顶部统计徽章清晰展示：“0 待处理 · 1 进行中 · 34 已完成 · 共 35 个任务”，三项之和严格等于总任务数。',
          '🏢 项目信息清晰：卡片标明项目编号、企业名称、分管车间区域及检查项数。',
        ],
      },
      {
        id: 'h5-task-detail-enter',
        title: '任务详情与进入检查执行',
        level: 2,
        content: '点击任务卡片进入详情页，点击绿色大按钮“执行检查”进入现场长表格：',
        image: {
          src: '/docs-assets/h5_04_task_detail.png',
          caption: '图 6-2：H5 任务详情页（含基本参数核对与开始检查按钮）',
        },
      },
      {
        id: 'h5-inspection-details',
        title: '现场检查执行页三大核心看点（P0-01 / P0-05 验证）',
        level: 2,
        content: '进入检查执行页，体现本次重大升级的交互细节：',
        steps: [
          {
            title: '1. 纵向长页面滚动丝滑顺畅',
            desc: '针对移动端与各类小屏幕深度优化，手指任意上下滑动，全表单顺畅自如，无任何卡顿或白屏。',
          },
          {
            title: '2. 大类分类树形横幅分组（彻底无未填写干扰）',
            desc: '顶部呈现大类横幅「📂 测试难度 (0/1)」，下级呈现「📂 难度高 (0/1)」，真正的叶子项缩进并标有「必填」红签。分类目录行绝不显示任何“未填写”Tag！',
          },
          {
            title: '3. 彻底无 na！三级单选与常驻业务释义（P0-05 闭环）',
            desc: '每个检查项提供规范的三项选择：[合格]、[不合格]、[不适用]。并在选项下方常驻展示释义说明小字：“「不适用」= 该条款不涉及本次受审对象，不计入不合格、不触发整改、不纳入合规率”，业务逻辑清清楚楚！',
          },
          {
            title: '4. 进度精准基于真实叶子项计算',
            desc: '顶部进度条展示为 0/2（仅计算系统内真正的 2 个叶子项，绝不将父目录算进总数）。评定第 1 项后动态变为 1/2，大类胶囊联动更新为 1/1；评完第 2 项后变为 2/2，提示“必填项已全完成，请在下方填写最终判定”。',
          },
        ],
      },
    ],
  },
  {
    id: 'h5-final-judgment',
    title: 'H5 最终判定与提交二次确认（第七幕）',
    category: 'h5-field-inspection',
    order: 2,
    description: '判定结论卡片自动展开、汇总统计清单、全要素确认提交防呆弹窗',
    badge: '第七幕',
    routeLink: '/my-audit-tasks',
    actionText: '查看我的任务',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['最终判定', '全要素确认弹窗', '二次确认', '防呆', '状态流转'],
    intro: '演示第七幕：展示现场检查执行闭环、最终判定说明录入与安全提交二次确认机制。',
    sections: [
      {
        id: 'judgment-auto-expand',
        title: '最终判定结论区自动展开',
        level: 2,
        content: '当所有叶子检查项评定完毕后，页面底部自动平滑延伸显现“最终判定结论”卡片：',
        steps: [
          {
            title: '汇总统计清晰罗列',
            desc: '自动汇总：符合项 2 · 不符合项 0 · 不适用项 0 · 总检查项 2。',
          },
          {
            title: '录入判定结论与陈述',
            desc: '选择判定结果 [合格]，输入说明：“现场检查全部符合标准要求，体系运行受控”，亦支持点击“AI 生成最终判定”自动提炼摘要。',
          },
        ],
      },
      {
        id: 'submit-confirm-dialog',
        title: '全要素提交二次确认弹窗（核心防呆看点）',
        level: 2,
        content: '点击启用的“提交检查结果”按钮，屏幕居中弹出严肃的确认对话框：',
        image: {
          src: '/docs-assets/h5_submit_confirm_dialog.png',
          caption: '图 7-1：H5 现场检查提交前的全要素二次确认弹窗',
        },
        keyPoints: [
          '📋 全要素统计复核：弹窗明确列出“检查项目统计：✅ 合格：2 项 ━━━━ 共计：2 项”。',
          '🔒 不可逆警示：明确提示“确定要提交本次检查结果吗？提交后将无法修改。”',
          '✅ 状态无缝联动：点击确认后，轻提示“检查已完成”，页面平滑返回任务列表，任务列表中的“已完成”数量即时自增刷新！',
        ],
      },
    ],
  },

  // =========================================================================
  // 第八幕：现场 AI 会话与离线弱网保障
  // =========================================================================
  {
    id: 'h5-ai-session-guide',
    title: '现场 AI 智审会话深度实操（第八幕）',
    category: 'h5-ai-offline',
    order: 1,
    description: '现场语音/文字/拍照提交证据、AI 多条款分析、置信度展示与确认卡写入',
    badge: '现场黑科技',
    routeLink: '/my-audit-tasks',
    actionText: '体验现场 AI 审核',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['AI审核会话', '现场语音', '拍照取证', '置信度', '确认卡', 'NC草稿'],
    intro: '审核员在车间无需手动翻阅几百页的标准规范，直接通过语音口述、输入现场情况或拍摄设备照片发给 AI，智审 Agent 现场完成多条款研判！',
    sections: [
      {
        id: 'ai-session-workflow',
        title: '现场 AI 审核四大实操步骤',
        level: 2,
        content: '在今日审核卡片点击进入现场 AI 审核会话界面：',
        image: {
          src: '/docs-assets/h5_07_ai_audit_session.png',
          caption: '图 8-1：H5 现场 AI 智审会话交互与多条款候选草稿',
        },
        steps: [
          {
            title: '1. 提交现场多模态证据',
            desc: '在底部输入框口述现场发现（如“抽查了配电室，发现 3 具灭火器压力表处于红区，巡检记录未及时更新”），或直接拍照上传设备表盘。',
          },
          {
            title: '2. AI Agent 多候选条款拆解',
            desc: 'AI 秒级检索知识库与标准条款，列出候选条款（如 7.1.3 基础设施、8.1 运行策划），展示证据充分性与置信度百分比（如“置信度 92%”）。',
          },
          {
            title: '3. 审核员查看「人工确认卡」',
            desc: 'AI 整理出合规的事实陈述草稿，生成操作确认卡。审核员核实无误后点击“确认采纳并写入记录”。',
          },
          {
            title: '4. 现场异常一键生成 NC 草稿',
            desc: '若判定为不符合项，点击“生成 NC 草稿”，直接推送到审核组长待办中！',
          },
        ],
      },
    ],
  },
  {
    id: 'h5-offline-guide',
    title: '车间弱网应对与离线本地缓存保障',
    category: 'h5-ai-offline',
    order: 2,
    description: '深井/防爆区/无网车间 localStorage 自动缓存与网络恢复批量同步',
    badge: '弱网保障',
    routeLink: '/my-audit-tasks',
    actionText: '个人中心',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['弱网离线', 'localStorage缓存', '断网可用', '自动同步', '车间巡检'],
    intro: '现场审查经常深入密闭车间、防爆区或地下室等无网络信号环境。易审通移动端具备出色的弱网离线缓存保障机制。',
    sections: [
      {
        id: 'offline-mechanism',
        title: '离线存储与自愈同步机制',
        level: 2,
        content: '在个人中心与现场检查中深度整合的离线保障：',
        image: {
          src: '/docs-assets/h5_12_profile_offline.png',
          caption: '图 8-2：移动端个人中心与离线缓存管理',
        },
        keyPoints: [
          '📴 出发前一键预缓存：在有网环境下进入任务详情，点击“缓存到本地”，系统将任务、检查模板与企业信息安全落盘到 localStorage（键前缀 efis:offline:v1:）。',
          '📝 断网流畅填报：在无信号区域，审核员仍可流畅进行单选判定、客观事实输入与本地拍照存证，页面顶部显示“离线暂存”黄色警示灯。',
          '🔄 网络自愈批量同步：走出厂房网络恢复后，系统自动检测联机状态，弹出“检测到网络，是否同步本地草稿”，点击即可一键批量回传云端！',
        ],
      },
    ],
  },

  // =========================================================================
  // 第九幕：树形检查记录追溯与合规报告生成
  // =========================================================================
  {
    id: 'records-trace-reports',
    title: '树形检查记录追溯与规范报告生成（第八幕 · 核心看点）',
    category: 'records-reports-gate',
    order: 1,
    description: '记录抽屉分类卡片高亮（彻底消除未填写）、表三明细横幅、字符清洁',
    badge: '第八幕看点',
    routeLink: '/records',
    actionText: '查看检查记录',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['检查记录抽屉', '消除未填写', '分类卡片高亮', '报告分类横幅', '字符清洁'],
    intro: '演示第八幕：展示检查记录的树形层次还原、彻底消除“未填写”假象与无代码字符的规范报告预览。',
    sections: [
      {
        id: 'record-drawer-tree',
        title: '检查记录详情抽屉（树形高亮卡片演示）',
        level: 2,
        content: '在「检查记录与报告」点击已提交记录的“详情”，右侧滑出抽屉：',
        image: {
          src: '/docs-assets/w_record_drawer.png',
          caption: '图 9-1：检查记录详情抽屉树形折叠展开与分类浅蓝高亮卡片（彻底消除“未填写”）',
        },
        steps: [
          {
            title: '分类目录高亮卡片（P0-01 根治）',
            desc: '分类节点呈现为浅蓝灰优雅卡片，带有 Folder 图标、蓝色「大类分类」标签及子项统计胶囊，完全不显示任何灰色的“未填写”Tag！彻底消除了客户以往的误解。',
          },
          {
            title: '层级平滑折叠展开',
            desc: '点击分类卡片右上角箭头，下级检查项平滑收起或展开；叶子项显示真实的测试数据与照片缩略图。',
          },
        ],
      },
      {
        id: 'report-preview-clean',
        title: '合规检查报告预览两大规范看点（P1-08 验证）',
        level: 2,
        content: '在记录列表点击“生成报告”预览模态框：',
        image: {
          src: '/docs-assets/web_13_records_reports.png',
          caption: '图 9-2：合规现场检查报告生成预览与导出',
        },
        steps: [
          {
            title: '表三明细按分类横幅分组',
            desc: '在“各检查项明细”表格中，清晰展示「📂 分类：XXXX」横幅分割条，下方只罗列属于该分类的叶子项，分类本身绝不占用序号行。',
          },
          {
            title: '实体字符彻底洗净（无 &nbsp; 乱码）',
            desc: '在报告底部的签名与签收日期区域，均规整呈现为标准下划线「————」，彻底清除了以往暴露给客户的 &nbsp; 原始 HTML 代码字符！',
          },
          {
            title: '一键下载 PDF / Word',
            desc: '点击顶部下载按钮，即刻输出规范的交付级现场检查报告单。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 第十幕：质量门禁验证与交付资料包归档
  // =========================================================================
  {
    id: 'quality-gate-delivery',
    title: '多重要素质量门禁与交付归档包（第九幕 · 核心看点）',
    category: 'quality-gate-delivery',
    order: 1,
    description: '多重要素质量门禁防线、带 SHA-256 防伪清单的 ZIP 归档成果包',
    badge: '第九幕压轴',
    routeLink: '/audit-projects',
    actionText: '查看审核项目',
    updatedAt: '2026-09-19',
    author: '易审通产品专家团队',
    keywords: ['质量门禁', '多重防线', '归档资料包', 'SHA-256', 'manifest.json', '合规审计'],
    intro: '演示第九幕：展示企业级多重要素质量门禁防线阻断机制，以及一键自动化生成符合认监委规范的交付归档包 (ZIP) 与 SHA-256 防篡改清单。',
    sections: [
      {
        id: 'quality-gates',
        title: '多重要素质量门禁把关防线',
        level: 2,
        content: '在审核项目详情页点击“生成审核报告”或“项目归档”，系统自动触发多重要素刚性检验，结论分为「阻断项」与「提醒项」两类。下列为核心防线举例：',
        image: {
          src: '/docs-assets/web_06_project_overview.png',
          caption: '图 10-1：项目详情看板与全生命周期质量门禁状态',
        },
        steps: [
          {
            title: '门禁 · 审核组成员资质与排期覆盖性校验',
            desc: '核验审核组长与组员资质专业代码是否覆盖本项目所有认证体系，排期无重叠冲突。',
          },
          {
            title: '门禁 · 首末次会议签到与纪要完整性校验',
            desc: '必须完整录入首次会议与末次会议纪要，并上传双方签收的现场签到表。',
          },
          {
            title: '门禁 · 现场检查项 100% 覆盖校验',
            desc: '所有计划内活跃叶子检查项必须全部给出判定，严禁存在“未填报项”。',
          },
          {
            title: '门禁 · 高风险检查项必要证据校验',
            desc: '高风险关键条款必须上传现场实物照片或抽样单据扫描件。',
          },
          {
            title: '门禁 · 不符合项 (NC) 全闭环整改验证',
            desc: '所有开具的轻微/严重不符合项必须经企业整改、上传凭证并由组长验证关闭！',
          },
          {
            title: '门禁 · 审核结论与快照版本一致性校验',
            desc: '自动比对报告草稿与现场记录数据一致性。若存在任何缺陷，精准弹出阻断警告与跳转补全链接。',
          },
        ],
      },
      {
        id: 'archive-zip-package',
        title: '一键成果包交付与 SHA-256 防篡改清单',
        level: 2,
        content: '门禁全部通过后，点击“下载交付归档包 (ZIP)”，解压后呈现国家认证认可监管级的规范目录结构：',
        keyPoints: [
          '📁 01_审核报告/：包含排版精美、带防伪水印与页码的 Word/PDF 完整审核报告。',
          '📁 02_现场审核记录/：按任务分区的结构化现场检查记录单。',
          '📁 03_会议记录与签到/：首末次会议纪要与现场签到扫描证明。',
          '📁 04_不符合项整改卷宗/：包含原因分析、纠正措施与验证证据的 NC 闭环表。',
          '📁 05_现场影像证据库/：以条款命名的现场高清取证照片。',
          '🔒 manifest.json：列出包内所有文件的相对路径、大小与 SHA-256 哈希防伪指纹，完全满足 CNAS/认证机构合规归档审计要求！',
        ],
      },
    ],
  },

  // =========================================================================
  // 第十一幕：常见问题与应急预案 (FAQ)
  // =========================================================================
  {
    id: 'faq-troubleshoot',
    title: '常见问题答疑与备用预案 (FAQ)',
    category: 'faq-guide',
    order: 1,
    description: '现场断网应急、分类目录不打分答疑、LLM 双通道容灾热备与快捷键速查',
    badge: '应急预案',
    routeLink: '/dashboard',
    actionText: '返回系统首页',
    updatedAt: '2026-09-15',
    author: '易审通产品专家团队',
    keywords: ['常见问题', 'FAQ', '断网应急', '分类目录答疑', 'LLM容灾热备', '快捷键'],
    intro: '收录《EFIS 客户全功能演示说明》官方推荐的答疑口径与系统级应急保障方案。',
    sections: [
      {
        id: 'faq-q1-network',
        title: 'Q1：现场断网或网络信号极差怎么办？',
        level: 2,
        content: '系统具备出色的离线现场填报能力：出发前在有网环境下进入 H5 任务详情，点击“缓存到本地”，系统将任务、模板与企业信息落盘到手机 localStorage（键前缀 efis:offline:v1:）；在无网防爆区或深井车间，审核员仍可流畅单选判定、文字输入与本地拍照留存；走出厂房网络恢复后，系统自动检测联机状态，一键同步回传云端。',
      },
      {
        id: 'faq-q2-category',
        title: 'Q2：为什么分类目录行不显示打分和“未填写”？',
        level: 2,
        content: '这正是易审通新版的核心优势所在！认证审核与现场检查必须严格遵循“层级结构与执行对象分离”原则。根节点和中间目录是用来归集条款的逻辑容器（如“运行控制”），具体由下属条款（如“烟气监测”、“危废贮存”）落实填报。旧系统把目录误当成检查项暴露，才会导致刺眼的“未填写”假象；新版通过“父节点一律为分类目录，仅统计真实叶子项”的设计，彻底解决了数据失真问题！',
      },
      {
        id: 'faq-q3-llm-fallback',
        title: 'Q3：大模型调用超时或出现异常怎么办？',
        level: 2,
        content: '系统配备了 LLM 双重容灾热备（主通道深度调优模型 deepseek-v4-flash + 备份通道 DeepSeek-V3.2），发生异常时后台毫秒级平滑切换；且智审 Agent 采用严格的“人在回路”设计，AI 仅用于生成建议卡片，审核员完全可以手动输入结论并保存，业务主流程绝不受模型可用性影响。',
      },
      {
        id: 'pro-shortcuts',
        title: '键盘快捷键速查表',
        level: 2,
        content: '熟练使用以下快捷键可大幅提升审核记录填报效率：',
        keyPoints: [
          '⌨️ 全局搜索在线文档：随时按下 Ctrl + K（Mac: Cmd + K）唤起在线帮助检索弹窗。',
          '⌨️ 快速保存草稿：在检查表填报页按下 Ctrl + S 即可强制同步保存当前项。',
          '⌨️ 快速唤起 AI 助手：在任意审核页面按下 Alt + A 快速展开 AI 智审侧边栏。',
          '⌨️ 上下条款切换：在检查表填报时，使用 Alt + 方向键 上/下 可快速切换前后检查条款。',
        ],
      },
    ],
  },
]

// 将文章组织进分类目录
DOCS_CATEGORIES.forEach((cat) => {
  cat.articles = DOCS_ARTICLES.filter((art) => art.category === cat.id).sort((a, b) => a.order - b.order)
})

// 根据 ID 查找文章
export function getDocArticleById(articleId: string): DocArticle | undefined {
  return DOCS_ARTICLES.find((art) => art.id === articleId)
}

// 扁平化所有文章列表（用于前一篇/后一篇导航）
export const ALL_FLATTEN_ARTICLES: DocArticle[] = DOCS_CATEGORIES.flatMap((c) => c.articles)
