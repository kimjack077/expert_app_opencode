import { DocCategory, DocArticle } from '../types'

export const DOCS_CATEGORIES: DocCategory[] = [
  {
    id: 'get-started',
    title: '🚀 快速上手',
    icon: 'RocketOutlined',
    description: '快速认识易审通平台，掌握核心操作路径与角色职责分工',
    articles: [],
  },
  {
    id: 'audit-lifecycle',
    title: '📋 审核项目全流程',
    icon: 'AuditOutlined',
    description: '从项目立项、计划排期、团队分工到首末次会议与不符合项跟踪',
    articles: [],
  },
  {
    id: 'field-inspection',
    title: '📝 现场检查与记录采集',
    icon: 'FormOutlined',
    description: '现场检查表填写、条款判定、客观证据上传与审核员个人任务',
    articles: [],
  },
  {
    id: 'ai-assistant',
    title: '🤖 AI 智审助手协同',
    icon: 'RobotOutlined',
    description: 'RAG 标准规范检索、AI 辅助撰写计划与润色事实依据、人在回路机制',
    articles: [],
  },
  {
    id: 'mobile-app',
    title: '📱 H5 移动端现场实操',
    icon: 'MobileOutlined',
    description: '审核员手机端现场核查、AI 现场会话、证据拍照与弱网离线全攻略',
    articles: [],
  },
  {
    id: 'reports-archive',
    title: '📑 报告生成与归档',
    icon: 'FileDoneOutlined',
    description: '自动化审核报告汇总、在线预览、整改单追踪及 PDF/Word 导出',
    articles: [],
  },
  {
    id: 'analytics-dashboard',
    title: '📊 统计分析与看板',
    icon: 'BarChartOutlined',
    description: '工作台待办中心、不符合项分布、行业认证趋势与质量看板',
    articles: [],
  },
  {
    id: 'base-config',
    title: '⚙️ 基础配置与知识库',
    icon: 'SettingOutlined',
    description: '检查模板编制、认证标准规范库、受审核企业档案及用户权限',
    articles: [],
  },
  {
    id: 'faq-guide',
    title: '💡 常见问题与操作技巧',
    icon: 'QuestionCircleOutlined',
    description: '高频问题速查、网络疑难排查、操作最佳实践与快捷键指南',
    articles: [],
  },
]

export const DOCS_ARTICLES: DocArticle[] = [
  // =========================================================================
  // 1. 快速上手
  // =========================================================================
  {
    id: 'overview',
    title: '平台概览与核心架构',
    category: 'get-started',
    order: 1,
    description: '全面了解易审通（EasyAudit）平台定位、业务闭环与技术架构',
    badge: '必读',
    routeLink: '/dashboard',
    actionText: '进入系统工作台',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['平台概览', '架构', '功能总览', '工作流', '认证评审'],
    intro: '易审通 (EasyAudit) 是专为认证机构、现场评审专家与专职审核员打造的新一代认证审核智能协同云平台。平台打通「项目立项 ➔ 审核计划 ➔ 现场检查 ➔ 证据采集 ➔ 不符合项跟踪 ➔ 报告生成 ➔ 统计归档」全生命周期，并深度整合大语言模型（LLM）与 RAG 标准知识库，实现人机协同的高效智审模式。',
    sections: [
      {
        id: 'core-values',
        title: '平台三大核心价值',
        level: 2,
        content: '传统认证审核面临标准繁多查找慢、现场纸质记录录入繁琐、报告编写耗时易错、跨端数据不互通等痛点。易审通通过数字化与智能化双轮驱动：',
        keyPoints: [
          '⚡ 现场全流程无纸化：支持 PC 管理端与手机 H5 移动端双向实时同步，现场拍摄照片、录入事实一键直达云端。',
          '🤖 AI Agent 深度赋能：基于知识库检索增强（RAG），随时查询国标行标、自动匹配适用条款、辅助润色判定事实。',
          '🔒 严谨的合规与留痕：严格遵循人在回路（Human-in-the-Loop）机制，所有审核判定与修改全程留痕、可溯源。',
        ],
        image: {
          src: '/docs-assets/web_02_dashboard.png',
          caption: '图 1-1：易审通管理后台工作台全局全景（含 KPI 看板与待办流水线）',
        },
      },
      {
        id: 'system-architecture',
        title: '系统功能模块架构',
        level: 2,
        content: '系统围绕认证机构三大日常工作场景展开，分为以下核心业务板块：',
        steps: [
          {
            title: '1. 现场工作域 (PC + H5 手机端)',
            desc: '包括个人工作台、我的审核任务、日常检查任务执行以及检查记录与报告归档。手机端支持单手核查、拍照取证与 AI 现场会话。',
          },
          {
            title: '2. 项目管理域 (PC 管理后台)',
            desc: '包括审核项目库（多阶段状态机）、受审核企业档案管理与审核质量大屏统计，满足审核部主任与项目经理把控全局。',
          },
          {
            title: '3. 基础配置与知识域',
            desc: '沉淀检查模板库、法律法规与认证准则知识库、多维度统计分析报表以及系统用户与角色权限管理。',
          },
        ],
      },
      {
        id: 'tech-highlights',
        title: '双端协同与离线支持',
        level: 2,
        content: '审核员在车间、厂房等可能存在网络盲区的现场，可使用手机端快速查看当日检查清单，拍照取证支持本地缓存，网络恢复后一键同步至云端数据库。',
        callout: {
          type: 'tip',
          title: '推荐使用环境',
          content: '管理端推荐使用 Google Chrome 110+、Edge 等现代浏览器；现场检查端支持手机微信、钉钉或自带浏览器直接扫码进入。',
        },
      },
    ],
  },
  {
    id: 'quickstart',
    title: '3分钟快速上手指南',
    category: 'get-started',
    order: 2,
    description: '通过一个标准审核项目，带您在 3 分钟内走通核心操作链路',
    badge: '快速入门',
    routeLink: '/audit-projects/create',
    actionText: '立即创建审核项目',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['快速开始', '新手引导', '3步完成', '登录', '创建项目'],
    intro: '如果您是第一次使用易审通，本篇指南将指导您从登录系统、创建第一个审核项目，到完成现场检查表录入与报告查看。',
    sections: [
      {
        id: 'step1-login',
        title: '第 1 步：登录系统与角色选择',
        level: 2,
        content: '打开系统登录入口，输入账号密码。系统支持管理员（admin）、专职审核员/评审专家（expert）等多种身份，提供快捷登录卡片：',
        image: {
          src: '/docs-assets/web_01_login.png',
          caption: '图 1-2：系统登录界面与快捷身份选择卡片',
        },
        steps: [
          {
            title: '访问登录页面',
            desc: '输入用户名和密码，或在体验环境点击「admin / admin123」或「expert / expert123」一键填入。',
          },
          {
            title: '点击登录进入系统',
            desc: '验证成功后将直接进入「工作台 (Dashboard)」，显示您的待办项目与核心数据指标。',
          },
        ],
      },
      {
        id: 'step2-create-project',
        title: '第 2 步：创建审核项目与配置计划',
        level: 2,
        content: '在左侧菜单点击「项目管理」➔「审核项目」，点击页面右上角「新建审核项目」：',
        image: {
          src: '/docs-assets/web_04_audit_projects.png',
          caption: '图 1-3：审核项目中心与多状态项目列表',
        },
        steps: [
          {
            title: '选择受审核企业',
            desc: '从下拉列表中选择已有企业，或直接现场录入新的企业基本信息及统一社会信用代码。',
          },
          {
            title: '设置审核基本参数',
            desc: '选择审核类型（初审、监督审核、再认证或专项审查）、拟定审核起始日期与结束日期、填写审核工作量（人天）。',
          },
          {
            title: '指派审核组与检查模板',
            desc: '指定审核组长（Lead Auditor）与审核员，并绑定适用的检查模板（如 ISO9001 质量管理体系检查表）。',
          },
        ],
      },
      {
        id: 'step3-field-audit',
        title: '第 3 步：现场检查与一键生成报告',
        level: 2,
        content: '项目创建后，进入项目详情页，即可开启现场检查任务：',
        image: {
          src: '/docs-assets/web_06_project_overview.png',
          caption: '图 1-4：审核项目详情全景总览看板',
        },
        steps: [
          {
            title: '填报检查项',
            desc: '点击「现场检查记录」，依次对检查要点进行「符合 / 不符合 / 观察项」判定，输入现场客观事实陈述。',
          },
          {
            title: '上传实物取证',
            desc: '点击证据栏的「上传证据」，上传现场拍摄的设备标牌、台账照片、检验记录等凭证文件。',
          },
          {
            title: '生成并导出报告',
            desc: '所有检查项完成后，点击「生成审核报告」，系统自动汇总不符合项并支持导出为标准 Word/PDF 格式。',
          },
        ],
      },
    ],
  },
  {
    id: 'roles-permissions',
    title: '角色划分与权限体系',
    category: 'get-started',
    order: 3,
    description: '详细说明超级管理员、审核组长、专职审核员与评审专家的职责权限',
    badge: '权限指南',
    routeLink: '/users',
    actionText: '查看用户管理',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['角色', '权限', '管理员', '审核员', '组长', '专家'],
    intro: '易审通采用严密的角色访问控制（RBAC），确保认证审核数据的保密性、公正性与完整性。以下是系统主要角色的职责与可访问范围说明。',
    sections: [
      {
        id: 'roles-matrix',
        title: '四级角色矩阵与职责对照',
        level: 2,
        content: '系统内置四类标准工作角色，各角色权限界定如下：',
        keyPoints: [
          '👑 系统超级管理员 (super_admin)：拥有全局最高权限，负责机构账号初始化、系统字典、行业分类、全局审计日志查询及底层配置。',
          '🛡️ 机构管理员 (admin)：负责受审核企业维护、检查模板审批、审核项目立项与人员指派、全机构统计报表查看。',
          '📋 审核组长 (Lead Auditor)：全面负责指定审核项目的日程编制、审核组成员分工、首末次会议主持、不符合项最终签发与审核报告编制。',
          '🔍 专职审核员 / 评审专家 (auditor / expert)：负责分配给自己的专业条款现场检查、事实采集、证据拍照上传、录入判定意见初稿。',
        ],
        image: {
          src: '/docs-assets/web_18_users.png',
          caption: '图 1-5：系统用户角色体系与账号权限管理',
        },
      },
    ],
  },

  // =========================================================================
  // 2. 审核项目全流程
  // =========================================================================
  {
    id: 'audit-projects',
    title: '审核项目全流程管理',
    category: 'audit-lifecycle',
    order: 1,
    description: '从项目立项、状态机流转到全景看板监控的完整指南',
    badge: '核心业务',
    routeLink: '/audit-projects',
    actionText: '进入审核项目中心',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['审核项目', '立项', '状态机', '项目总览', '生命周期'],
    intro: '审核项目是易审通最核心的业务单元。一个项目完整承载了一次针对特定企业的认证审核或现场评审活动。系统提供了状态机全流程追踪能力。',
    sections: [
      {
        id: 'project-lifecycle-states',
        title: '项目生命周期与状态流转',
        level: 2,
        content: '每个审核项目包含严谨的状态机流转过程，各阶段流转节点如下：',
        steps: [
          {
            title: '1. 准备中 (Preparing)',
            desc: '完成项目基本信息录入、确定审核范围、配置审核组长与组员、绑定检查模板。',
          },
          {
            title: '2. 计划中 (Planning)',
            desc: '编制日程安排、召开准备会，下发具体任务清单至审核员个人终端。',
          },
          {
            title: '3. 现场审核中 (In Progress)',
            desc: '现场实地核查、逐项判定检查项、拍照取证、记录客观事实与不符合项。',
          },
          {
            title: '4. 报告编制 (Reporting)',
            desc: '审核组长汇总各组员记录，召开末次会议，自动合成审核报告并进行技术评审。',
          },
          {
            title: '5. 整改追踪 (Rectification)',
            desc: '开具不符合项报告，受审核企业提交纠正措施与证据，组长审核闭环。',
          },
          {
            title: '6. 已归档 (Closed)',
            desc: '所有整改项验证通过，项目档案入库，全量数据归档只读存证。',
          },
        ],
        image: {
          src: '/docs-assets/web_06_project_overview.png',
          caption: '图 2-1：项目详情总览页与全生命周期各模块导航',
        },
      },
      {
        id: 'create-project-guide',
        title: '新建审核项目详细操作步骤',
        level: 2,
        content: '点击页面右上角「新建审核项目」按钮，进入项目创建表单：',
        image: {
          src: '/docs-assets/web_05_project_create.png',
          caption: '图 2-2：新建审核项目表单与人天排期配置',
        },
        steps: [
          {
            title: '填写基本信息',
            desc: '输入项目名称（如“2026年XX实业有限公司质量体系再认证现场审核”）。',
          },
          {
            title: '选择受审核企业',
            desc: '选择受审核企业，系统自动回填该企业统一社会信用代码与法定代表人。',
          },
          {
            title: '设定审核工作量与排期',
            desc: '填写审核工作量（人天）、现场起止日期。系统严格校验起止时间的合理性。',
          },
        ],
      },
    ],
  },
  {
    id: 'audit-plan',
    title: '审核计划制定与日程排期',
    category: 'audit-lifecycle',
    order: 2,
    description: '科学编制现场审核日程、分工分配与检查表关联',
    badge: '计划编制',
    routeLink: '/audit-projects',
    actionText: '前往项目管理',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['审核计划', '日程排期', '审核组分工', '部门覆盖', '检查表分配'],
    intro: '规范的现场审核计划是确保现场评审有条不紊、不漏项的关键文件。易审通支持精细化到小时级的时间分段排期与责任审核员分配。',
    sections: [
      {
        id: 'plan-structure',
        title: '计划结构与排期要点',
        level: 2,
        content: '审核计划支持按天、按时间段进行网格化拆解，包括首末次会议、最高管理层访谈、车间现场巡视及各职能部门审核：',
        image: {
          src: '/docs-assets/web_08_project_plan.png',
          caption: '图 2-3：审核计划编制与日程排期视图',
        },
        steps: [
          {
            title: '添加日程时间段',
            desc: '设定日期与时段（如 09:00 - 11:30），选择受审核部门（如生产部、质保部、技术部）。',
          },
          {
            title: '明确审核内容与适用条款',
            desc: '选择该时间段核查的标准条款（如 8.5 生产和服务提供、7.1.5 监视和测量资源）。',
          },
          {
            title: '指定执行审核员',
            desc: '将日程分配给对应专业的审核员，被指派审核员在手机端及个人工作台将即时收到任务。',
          },
        ],
      },
    ],
  },
  {
    id: 'audit-team-meeting',
    title: '团队分工与首末次会议',
    category: 'audit-lifecycle',
    order: 3,
    description: '审核团队资格把控、首次会议与末次会议规范化留痕',
    badge: '会议管理',
    routeLink: '/audit-projects',
    actionText: '查看项目团队',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['审核组', '首末次会议', '签到表', '会议纪要', '专家分工'],
    intro: '首次会议与末次会议是认证审核现场的重要法定与规范程序。易审通实现了会议签到、议程记录与纪要文档的一键归档。',
    sections: [
      {
        id: 'team-management',
        title: '审核组团队配置与资质确认',
        level: 2,
        content: '进入项目「团队配置」标签页，可查看与维护审核组长、专职审核员、技术专家及实习审核员名单：',
        image: {
          src: '/docs-assets/web_07_project_team.png',
          caption: '图 2-4：审核组成员名单与专业分工',
        },
      },
      {
        id: 'meetings-management',
        title: '首次会议与末次会议管理',
        level: 2,
        content: '进入「会议管理」板块，系统为首次会议与末次会议分别设立标准化卡片：',
        image: {
          src: '/docs-assets/web_09_project_meetings.png',
          caption: '图 2-5：首末次会议记录、参会名单与签到表存证',
        },
        steps: [
          {
            title: '录入会议基本信息',
            desc: '包括开会时间、地点、主持人（组长）、受审核方负责人及参会部门代表名单。',
          },
          {
            title: '确认会议标准议程',
            desc: '勾选已宣读的合规议程（保密承诺、审核范围确认、抽样局限性声明、末次会议沟通机制等）。',
          },
          {
            title: '上传现场签到表与照片',
            desc: '拍照上传双方亲笔签字的纸质签到表原件与会议全景照片，生成数字存证档案。',
          },
        ],
      },
    ],
  },
  {
    id: 'nonconformities',
    title: '不符合项与整改闭环',
    category: 'audit-lifecycle',
    order: 4,
    description: '严谨开具不符合项报告、纠正措施要求与整改闭环验证',
    badge: '质量闭环',
    routeLink: '/audit-projects',
    actionText: '不符合项管理',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['不符合项', '严重不符合', '轻微不符合', '观察项', '整改闭环', 'CAPA'],
    intro: '发现不符合项是推动受审核企业持续改进的核心抓手。易审通提供从现场开具、企业原因分析、制定纠正措施到审核员验证关闭的闭环工作流。',
    sections: [
      {
        id: 'nc-create',
        title: '开具不符合项报告的规范要素',
        level: 2,
        content: '每一份合规的不符合项报告都必须包含「三段论」原则：明确的不符合事实、违反的标准条款以及证据支撑。',
        image: {
          src: '/docs-assets/web_12_nonconformities.png',
          caption: '图 2-6：不符合项列表、严重等级与整改关闭进度',
        },
        steps: [
          {
            title: '判定不符合级别',
            desc: '根据缺陷性质选择：严重不符合（Major NC）、轻微不符合（Minor NC）或建议改进项（Observation）。',
          },
          {
            title: '规范陈述客观事实',
            desc: '客观描述抽查时间、地点、抽样样本编号、具体偏差事实，避免主观推测。',
          },
          {
            title: '绑定判定标准条款',
            desc: '精准关联违规的标准条款（如 GB/T 19001-2016 8.5.1 条款）。支持通过 AI 智能助手进行润色核实。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 3. 现场检查与记录采集 (Web端视角)
  // =========================================================================
  {
    id: 'field-records',
    title: '现场检查表填写与记录采集',
    category: 'field-inspection',
    order: 1,
    description: '现场逐项核查、证据关联、客观事实陈述与判定全攻略',
    badge: '操作核心',
    routeLink: '/records',
    actionText: '查看检查记录',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['现场检查', '检查表', '客观事实', '判定准则', '证据采集'],
    intro: '现场检查表是审核员在现场评审时的执行指南。易审通将纸质检查表数字化，支持条款展开、一键判定、事实即时录入与多媒体证据挂接。',
    sections: [
      {
        id: 'inspection-interface',
        title: '现场检查表交互界面',
        level: 2,
        content: '进入项目的「现场检查记录」界面，左侧展示章节条款大纲树，右侧展示当前条款的具体检查要点与记录卡片：',
        image: {
          src: '/docs-assets/web_10_field_records.png',
          caption: '图 3-1：现场检查记录填报与多媒体凭据库',
        },
        steps: [
          {
            title: '选择检查条款',
            desc: '在左侧目录或搜索栏快速定位到当前正在审核的章节（如 7.2 能力、8.4 外部提供过程的控制）。',
          },
          {
            title: '执行合规判定',
            desc: '点击单选按钮选择判定结果：「符合」、「轻微不符合」、「严重不符合」或「不适用 (N/A)」。',
          },
          {
            title: '录入事实依据与抽样记录',
            desc: '在文本框中输入抽查的具体记录编号、人员姓名、设备编号与现场实际状况。',
          },
          {
            title: '挂接现场照片与证据',
            desc: '点击证据栏的「上传证据」，上传拍摄的照片或扫描件，支持添加文字说明。',
          },
        ],
      },
    ],
  },
  {
    id: 'my-audit-tasks',
    title: '我的审核任务与个人中心',
    category: 'field-inspection',
    order: 2,
    description: '专职审核员与评审专家的个人专属任务视图',
    badge: '个人视角',
    routeLink: '/my-audit-tasks',
    actionText: '进入我的任务',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['我的任务', '待办清单', '现场执行', '审核员工作台'],
    intro: '为减轻专职审核员的界面认知负担，系统专门设计了「我的审核任务」页面。该页面只汇总当前登录人员被指派的、待现场执行的检查任务。',
    sections: [
      {
        id: 'tasks-list',
        title: '个人任务列表与快速进入',
        level: 2,
        content: '登录系统后，点击左侧菜单「现场工作」➔「我的审核任务」：',
        image: {
          src: '/docs-assets/web_03_my_tasks.png',
          caption: '图 3-2：审核员个人工作台与分配检查任务清单',
        },
        steps: [
          {
            title: '查看任务卡片',
            desc: '清晰显示项目名称、受审核企业、审核日期区间、本人在项目中的角色及待检查项进度。',
          },
          {
            title: '一键「继续执行」',
            desc: '点击卡片上的操作按钮，直接穿透定位到上次填写的检查项位置。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 4. AI 智审助手
  // =========================================================================
  {
    id: 'ai-agent',
    title: 'AI Agent 智审助手与智能协同',
    category: 'ai-assistant',
    order: 1,
    description: '深度利用大模型与 RAG 知识库，赋能审核全链路智能升级',
    badge: '核心黑科技',
    routeLink: '/audit-projects',
    actionText: '体验 AI 助手',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['AI Agent', '大模型', 'RAG', '智能问答', '人在回路', '条款匹配'],
    intro: '易审通内置了基于最新大模型与检索增强生成（RAG）技术的 AI 审核助手。AI 助手不仅能精准解答标准规范疑问，更能深度嵌入审核业务流，辅助编写计划、分析违规事实及生成初稿报告。',
    sections: [
      {
        id: 'agent-capabilities',
        title: 'AI 智审助手的核心能力',
        level: 2,
        content: '点击系统右上角或右侧悬浮的「智审 Agent」展开侧边会话面板，支持全方位交互协同：',
        image: {
          src: '/docs-assets/web_11_ai_agent.png',
          caption: '图 4-1：智审 Agent 侧边栏交互面板与 Action Proposal 确认卡',
        },
        steps: [
          {
            title: '1. 标准与法规精准 RAG 检索',
            desc: '输入自然语言问题，AI 基于底层知识库秒级定位标准原文条款（带文档出处标注）。',
          },
          {
            title: '2. 现场事实智能润色与判词生成',
            desc: '审核员输入口语化的现场记录，AI 自动重构为符合认证认可机构规范的合规陈述语言。',
          },
          {
            title: '3. 现场异常一键生成不符合项草稿',
            desc: '智能提取事实与依据，生成标准的不符合项卡片，供组长确认签发。',
          },
        ],
        callout: {
          type: 'warning',
          title: '人在回路（Human-in-the-Loop）安全原则',
          content: 'AI 生成的所有写入数据库建议均以「操作确认卡 (Action Proposal)」呈现，必须经现场审核人员点击确认后才落库，杜绝大模型幻觉风险。',
        },
      },
    ],
  },

  // =========================================================================
  // 5. H5 移动端现场实操 (重点扩充！回应用户痛点)
  // =========================================================================
  {
    id: 'h5-overview',
    title: 'H5 移动端定位与登录指引',
    category: 'mobile-app',
    order: 1,
    description: '专为车间生产线穿梭打造的极简移动作业端',
    badge: '移动入门',
    routeLink: '/my-audit-tasks',
    actionText: '查看我的任务',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['H5', '移动端', '手机登录', '车间巡检', '单手操作'],
    intro: '现场审核往往需要在嘈杂、无电脑桌的车间生产线穿梭，携带笨重笔记本极为不便。易审通提供极致轻便的 H5 移动应用，审核员直接使用手机即可完成当天的所有现场检查任务。',
    sections: [
      {
        id: 'h5-login-steps',
        title: '手机端扫码与登录',
        level: 2,
        content: '使用手机浏览器或微信扫描系统二维码，进入移动端登录页面：',
        image: {
          src: '/docs-assets/h5_01_login.png',
          caption: '图 5-1：H5 移动端登录界面（支持一键选择角色）',
        },
        steps: [
          {
            title: '进入移动端首页',
            desc: '访问系统 H5 地址，界面专为手机竖屏比例深度定制，按钮尺寸适合大拇指触控。',
          },
          {
            title: '选择专家身份登录',
            desc: '输入审核员/专家账号密码，或点击「专家」卡片一键快速填入凭据，点击「登录」。',
          },
        ],
      },
    ],
  },
  {
    id: 'h5-today-audit',
    title: '今日现场审核与待办看板',
    category: 'mobile-app',
    order: 2,
    description: '手机端首页实时呈现当天现场审核任务卡片与项目信息',
    badge: '每日现场',
    routeLink: '/my-audit-tasks',
    actionText: '查看今日任务',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['今日审核', '现场签到', '待办卡片', '审核进度'],
    intro: '登录成功后，移动端首先呈现「今日审核」专属主页。该页面直观展示审核员当天需要实地奔赴的企业与审核任务。',
    sections: [
      {
        id: 'today-card-breakdown',
        title: '今日任务卡片要素详解',
        level: 2,
        content: '登录进入后的真实「今日现场审核」主页：',
        image: {
          src: '/docs-assets/h5_02_today_audit.png',
          caption: '图 5-2：登录后真实的「今日现场审核」主页卡片',
        },
        keyPoints: [
          '🏢 企业信息：醒目展示受审核企业全称（如“山东盛发焦化有限公司”）、所属行业与厂区位置。',
          '⏱️ 审核排期：显示审核起始与结束日期、审核人日数以及当前项目状态。',
          '📊 现场完成率：直观进度环呈现本人负责检查项的填报百分比（已评/总项）。',
          '🚀 快捷进入：点击卡片底部的「开始现场检查」或「进入 AI 智审会话」，一键直达作业界面。',
        ],
      },
    ],
  },
  {
    id: 'h5-tasks-detail',
    title: '任务列表与条款大纲查看',
    category: 'mobile-app',
    order: 3,
    description: '多状态任务切换、企业概况核对与检查条款大纲',
    badge: '任务导航',
    routeLink: '/my-audit-tasks',
    actionText: '任务清单',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['任务列表', '进行中', '已完成', '任务详情', '大纲'],
    intro: '审核员可能同时参与多个审核项目。移动端「任务」列表支持按阶段分类筛选，并可穿透查看任务详细信息。',
    sections: [
      {
        id: 'tasks-tab-filter',
        title: '任务列表多状态切换',
        level: 2,
        content: '点击底部导航栏「任务」，进入审核任务列表界面：',
        image: {
          src: '/docs-assets/h5_03_tasks_list.png',
          caption: '图 5-3：移动端审核任务列表（支持全部/进行中/已完成筛选）',
        },
        steps: [
          {
            title: '查看任务卡片状态',
            desc: '每个卡片清晰标明项目编号、企业名称、指派给本人的区域（如“焦化车间审核单”）与检查项数。',
          },
          {
            title: '点击进入任务详情',
            desc: '点击卡片即可展开该任务的详细信息视图。',
          },
        ],
      },
      {
        id: 'task-detail-view',
        title: '现场审核任务详情视图',
        level: 2,
        content: '任务详情页汇总了本次现场审查的核心信息：',
        image: {
          src: '/docs-assets/h5_04_task_detail.png',
          caption: '图 5-4：现场审核任务详情页（含基本信息与快速执行入口）',
        },
        steps: [
          {
            title: '核对检查范围与要求',
            desc: '确认受审核部门、适用体系标准、审核组长姓名及联系方式。',
          },
          {
            title: '一键开始现场检查',
            desc: '点击屏幕底部的蓝色「开始现场检查」大号按钮，直接进入逐项填报页。',
          },
        ],
      },
    ],
  },
  {
    id: 'h5-ai-session',
    title: 'H5 现场 AI 智审会话 (重磅核心功能)',
    category: 'mobile-app',
    order: 4,
    description: '现场语音/文字/拍照提交证据、AI 多条款分析、置信度展示与确认卡写入',
    badge: '现场黑科技',
    routeLink: '/my-audit-tasks',
    actionText: '体验现场 AI 审核',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['AI 审核会话', '现场语音', '拍照取证', '置信度', '确认卡', 'NC草稿'],
    intro: '这是易审通最具革命性的现场核查工具！审核员在车间无需手动翻阅几百页的标准规范，直接通过语音口述、输入现场情况或拍摄设备照片发给 AI，智审 Agent 现场完成多条款研判！',
    sections: [
      {
        id: 'ai-session-interface',
        title: '现场 AI 智审会话界面详解',
        level: 2,
        content: '在今日任务或任务详情点击「现场 AI 审核」进入会话交互界面：',
        image: {
          src: '/docs-assets/h5_07_ai_audit_session.png',
          caption: '图 5-5：H5 现场 AI 智审会话（多条款分析、置信度、确认卡与 NC 生成）',
        },
        steps: [
          {
            title: '1. 提交现场证据 (语音 / 文字 / 照片)',
            desc: '在底部输入框口述现场发现（如“抽查了配电室，发现 3 具干粉灭火器压力表处于红区，巡检记录未及时更新”），或直接拍照上传。',
          },
          {
            title: '2. AI Agent 多条款智能拆解',
            desc: 'AI 瞬间检索知识库与标准条款，列出候选条款（如 7.1.3 基础设施、8.1 运行策划和控制），展示证据充分性与置信度百分比（如“置信度 92%”）。',
          },
          {
            title: '3. 审核员查看「人工确认卡」',
            desc: 'AI 绝不擅自落库。AI 将整理出合规的事实陈述草稿，生成「操作确认卡」。审核员核实无误后点击「确认采纳并写入记录」。',
          },
          {
            title: '4. 现场异常一键生成 NC 草稿',
            desc: '如果判定为不符合项，点击卡片上的「生成 NC 草稿」，系统自动填写事实与依据，直接推送至审核组长待办中！',
          },
        ],
        callout: {
          type: 'tip',
          title: '现场提效秘籍',
          content: '在噪音较大的车间环境，可使用手机输入法的语音转文字功能快速输入，AI Agent 会自动去除口语杂词，润色为极其严谨专业的标准审核判词！',
        },
      },
    ],
  },
  {
    id: 'h5-records-offline',
    title: '已填记录追溯与离线弱网指南',
    category: 'mobile-app',
    order: 5,
    description: '审核记录历史版本追溯、离线本地缓存机制与个人中心',
    badge: '弱网保障',
    routeLink: '/my-audit-tasks',
    actionText: '查看记录',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['审核记录', '历史版本', '只读保护', '离线存储', '断网可用', '个人中心'],
    intro: '现场审查结束后，数据需要可靠归档存证。同时，针对钢厂、矿山、密闭车间等信号不良区域，移动端具备完备的弱网离线缓存保障。',
    sections: [
      {
        id: 'records-archive-view',
        title: '现场审核记录追溯与只读存证',
        level: 2,
        content: '点击底部导航栏「记录」，可查阅已完成的现场检查记录单：',
        image: {
          src: '/docs-assets/h5_09_records_list.png',
          caption: '图 5-6：移动端现场检查记录列表与历史版本查询',
        },
        steps: [
          {
            title: '只读防篡改视图',
            desc: '已提交的记录进入正式只读保护状态，完整保留当时的填报人、提交时间、客观证据与照片附件。',
          },
          {
            title: '版本演进追溯',
            desc: '若组长提出复核修改意见，系统保留 V1、V2 演进历史，符合认证认可监督评审要求。',
          },
        ],
      },
      {
        id: 'profile-offline-settings',
        title: '个人中心与离线缓存管理',
        level: 2,
        content: '点击底部导航「我的」，进入个人中心：',
        image: {
          src: '/docs-assets/h5_12_profile_offline.png',
          caption: '图 5-7：移动端个人中心与离线缓存/账号设置',
        },
        keyPoints: [
          '📴 离线本地缓存：现场断网时，您填写的客观事实会自动安全保存在手机 LocalStorage 中，页面顶部显示“离线暂存”黄色警示灯。',
          '🔄 一键批量同步：走出厂房网络恢复后，页面提示“检测到网络，是否同步本地草稿”，点击即可一次性全部同步至云端。',
          '👤 账号与资质信息：查看当前登录审核员姓名、工号、持证体系与所属认证机构。',
        ],
      },
    ],
  },

  // =========================================================================
  // 6. 报告生成与归档
  // =========================================================================
  {
    id: 'records-reports',
    title: '检查记录汇总与报告导出',
    category: 'reports-archive',
    order: 1,
    description: '报告自动聚合、格式化排版、整改追踪单及 PDF/Word 导出',
    badge: '成果归档',
    routeLink: '/records',
    actionText: '进入检查记录与报告',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['审核报告', '报告导出', 'PDF下载', 'Word导出', '归档存证'],
    intro: '在传统模式下，审核组长需要花费数小时拼凑各组员的记录表格。易审通能够将分散的现场数据一键聚合成规范的《现场审核报告》与《不符合项纠正措施表》。',
    sections: [
      {
        id: 'generate-report',
        title: '一键自动生成审核报告',
        level: 2,
        content: '当所有审核员完成各自的检查条款并提交后，审核组长在「检查记录与报告」模块进行审查：',
        image: {
          src: '/docs-assets/web_13_records_reports.png',
          caption: '图 6-1：检查记录汇总、报告编制与多格式导出',
        },
        steps: [
          {
            title: '查看检查记录汇总',
            desc: '系统自动核算总检查项数、符合项数、轻微不符合项数、严重不符合项数及体系符合度综合得分。',
          },
          {
            title: '填写审核结论与建议',
            desc: '审核组长填写综合评价意见，选择推荐结论：「推荐通过认证注册」、「整改验证后推荐」或「不予推荐」。',
          },
          {
            title: '预览与多格式导出',
            desc: '支持一键导出为精美排版的 PDF 文件或可二次编辑的 DOCX Word 文件，内置标准公文版头与签章区域。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 7. 统计分析与看板
  // =========================================================================
  {
    id: 'dashboard-guide',
    title: '工作台操作指南与待办中心',
    category: 'analytics-dashboard',
    order: 1,
    description: '掌握综合工作台核心指标看板、待办提醒与快捷导航',
    badge: '每日工作台',
    routeLink: '/dashboard',
    actionText: '返回系统工作台',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['工作台', '待办中心', '仪表盘', '指标看板', '审核日历'],
    intro: '工作台是用户每天登录系统后的第一站。它聚合了与当前用户最紧密相关的数据指标、待办提醒、项目日历与高频入口。',
    sections: [
      {
        id: 'dashboard-layout',
        title: '工作台四大功能区域',
        level: 2,
        content: '工作台采用卡片化自适应设计，清晰划分四大视觉区：',
        image: {
          src: '/docs-assets/web_02_dashboard.png',
          caption: '图 7-1：易审通管理后台工作台全局布局与待办流水线',
        },
        steps: [
          {
            title: '顶部核心 KPI 指标卡',
            desc: '实时统计「进行中项目数」、「本月待审核任务」、「待处理不符合项」及「已归档项目累计」。',
          },
          {
            title: '待办事项流水线',
            desc: '列出急需当前用户处理的节点（如待确认的检查表、待批复的整改报告），点击直接穿透处理。',
          },
          {
            title: '严格合规率口径说明',
            desc: '界面显式标注合规率对账口径（已填报合格项 / 已填报项），分子分母剔除不适用与未评项。',
          },
        ],
      },
    ],
  },
  {
    id: 'analytics-guide',
    title: '审核质量大数据与多维分析',
    category: 'analytics-dashboard',
    order: 2,
    description: '不符合项高发条款雷达、行业分布、审核员绩效与质量趋势',
    badge: '数据赋能',
    routeLink: '/analytics',
    actionText: '查看数据分析',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['数据分析', '质量看板', '不符合项趋势', '行业分布', '统计大屏'],
    intro: '认证机构管理层需要深入掌握审核质量规律。易审通提供丰富的大数据分析图表，支持从行业门类、受审核企业规模、标准条款及审核员维度进行深度下钻。',
    sections: [
      {
        id: 'analytics-charts',
        title: '关键统计图表解读',
        level: 2,
        content: '进入左侧菜单「基础配置」➔「数据分析」：',
        image: {
          src: '/docs-assets/web_19_analytics.png',
          caption: '图 7-2：审核大数据多维统计看板与不符合项雷达图',
        },
        steps: [
          {
            title: '不符合项高发条款分布雷达',
            desc: '清晰发现企业普遍薄弱的管理环节（如质量控制、文件记录、应急准备等条款的不符合占比）。',
          },
          {
            title: '行业分类与审核通过率统计',
            desc: '对比化工、机械、食品、信息技术等不同行业的首次通过率与整改平均周期。',
          },
          {
            title: '审核员工作量与绩效矩阵',
            desc: '统计每位审核员承担的现场人日数、查出不符合项数量分布，辅助机构进行绩效评价与业务排单。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 8. 基础配置与知识库
  // =========================================================================
  {
    id: 'templates-guide',
    title: '检查模板设计中心',
    category: 'base-config',
    order: 1,
    description: '灵活定制多级树状检查表、评分规则与分类目录防呆机制',
    badge: '标准利器',
    routeLink: '/templates',
    actionText: '前往检查模板',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['检查模板', '模板库', '条款配置', '分类目录', '防呆编辑器'],
    intro: '检查模板是现场检查的规范基石。机构管理员可在模板中心创建并维护通用的质量、环境、职业健康体系模板，也可针对特殊行业定制专项评审表。',
    sections: [
      {
        id: 'templates-list',
        title: '模板库管理与条目对账',
        level: 2,
        content: '进入「基础配置」➔「检查模板」，可查看系统内所有通用模板与自定义模板：',
        image: {
          src: '/docs-assets/web_14_templates.png',
          caption: '图 8-1：检查模板管理库与条目统计对账列',
        },
        steps: [
          {
            title: '新建或克隆现有模板',
            desc: '点击「新建模板」或基于既有成熟模板点击「复制克隆」，输入模板名称与适用行业代码。',
          },
          {
            title: '分级编制章节与条款',
            desc: '支持无限级目录树结构（如第一章：管理职责 ➔ 1.1 方针目标 ➔ 1.1.1 考核落实）。',
          },
          {
            title: '分类目录防呆锁定',
            desc: '有子项的节点在编辑器中强制锁定为分类目录，隐藏打分项，确保只为活跃叶子项生成填报单。',
          },
        ],
      },
    ],
  },
  {
    id: 'knowledge-guide',
    title: '知识库与标准规范智能检索',
    category: 'base-config',
    order: 2,
    description: '国家标准、行业规范、认证准则与法规文献的智能语义检索',
    badge: '智审大脑',
    routeLink: '/knowledge',
    actionText: '进入知识库',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['知识库', '国家标准', '行业法规', 'RAG检索', '智能文档'],
    intro: '知识库是易审通 RAG 智能助手的底层数据源。机构可上传最新的国家标准（GB/T）、国际标准（ISO）、法律法规及内部审核指南，系统自动完成文本解析与向量化。',
    sections: [
      {
        id: 'knowledge-search',
        title: '标准文献检索与查阅',
        level: 2,
        content: '进入「基础配置」➔「知识库」，界面支持关键词全文检索与分类筛选：',
        image: {
          src: '/docs-assets/web_16_knowledge.png',
          caption: '图 8-2：知识库标准法规检索与多维度分类筛选',
        },
        steps: [
          {
            title: '快速搜索标准条文',
            desc: '输入标准号（如“GB/T 19001-2016”）或业务关键词，秒级列出对应条文原文。',
          },
          {
            title: '上传机构专属规范',
            desc: '支持上传 PDF、Word、TXT 格式文件，系统后台智能切片并提取关键词索引。',
          },
        ],
      },
    ],
  },
  {
    id: 'enterprises-guide',
    title: '受审核企业档案库管理',
    category: 'base-config',
    order: 3,
    description: '受审核客户统一社会信用代码、资质证照、历史审核档案全记录',
    badge: '客户档案',
    routeLink: '/enterprises',
    actionText: '管理企业库',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['企业管理', '统一信用代码', '资质管理', '受审客户', '历史档案'],
    intro: '企业库维护了所有受审核客户的档案资料。包括企业名称、统一社会信用代码、法定代表人、注册地址、实际生产地址、联系人方式及历年在本机构的审核历史记录。',
    sections: [
      {
        id: 'enterprises-list',
        title: '企业列表与详细档案维护',
        level: 2,
        content: '进入「项目管理」➔「企业管理」，支持搜索、筛选与维护企业数据：',
        image: {
          src: '/docs-assets/web_17_enterprises.png',
          caption: '图 8-3：受审核企业数据库与客户档案库',
        },
        steps: [
          {
            title: '录入新企业基本信息',
            desc: '输入统一社会信用代码（系统自动校验 18 位格式）、所属行业门类及人员规模。',
          },
          {
            title: '维护生产经营场所信息',
            desc: '若企业存在多个分支厂区或多场所（Multi-site），可在档案中逐一添加多场所地址。',
          },
        ],
      },
    ],
  },
  {
    id: 'users-roles-guide',
    title: '用户管理与账号权限配置',
    category: 'base-config',
    order: 4,
    description: '审核员账号维护、密码重置、角色权限下发与安全控制',
    badge: '安全运维',
    routeLink: '/users',
    actionText: '管理用户账号',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['用户管理', '账号管理', '角色分配', '重置密码', '权限控制'],
    intro: '机构管理员可通过用户管理模块维护全机构的人员账号体系，包括专职审核员、兼职专家、实习人员及各部门负责人的账号启停与角色赋权。',
    sections: [
      {
        id: 'user-add-edit',
        title: '用户账号的新建与维护',
        level: 2,
        content: '进入「基础配置」➔「用户管理」，列表支持按姓名、手机号、角色分类检索：',
        image: {
          src: '/docs-assets/web_18_users.png',
          caption: '图 8-4：用户账号管理列表与操作弹窗',
        },
        steps: [
          {
            title: '新建用户',
            desc: '点击「添加用户」，填写姓名、登录手机号/账号、电子邮箱及初始密码。',
          },
          {
            title: '指派系统角色',
            desc: '选择用户角色（管理员、审核组长、专职审核员或技术专家）。',
          },
        ],
      },
    ],
  },

  // =========================================================================
  // 9. 常见问题与操作技巧
  // =========================================================================
  {
    id: 'faq',
    title: '常见问题答疑与高效使用技巧',
    category: 'faq-guide',
    order: 1,
    description: '账号登录、现场网络异常应对、报告导出乱码与系统快捷键速查',
    badge: '答疑技巧',
    routeLink: '/dashboard',
    actionText: '返回系统首页',
    updatedAt: '2026-09-15',
    author: '易审通产品团队',
    keywords: ['常见问题', 'FAQ', '排错', '快捷键', '使用技巧', '断网解决'],
    intro: '汇集审核员与管理专家在使用易审通时最常遇到的疑问与高效操作秘籍，助您快速成为系统熟手。',
    sections: [
      {
        id: 'online-docs-guide',
        title: '关于系统内置在线文档的使用',
        level: 2,
        content: '随时在系统右上角点击「?」帮助图标或访问 /docs 即可进入本中心：',
        image: {
          src: '/docs-assets/web_20_online_docs.png',
          caption: '图 9-1：系统内置在线文档与操作指南中心全景',
        },
      },
      {
        id: 'faq-troubleshoot',
        title: '高频操作疑难排查',
        level: 2,
        steps: [
          {
            title: 'Q1: 现场网络信号弱或断网，填写的检查数据会丢失吗？',
            desc: '答：绝对不会。易审通前端具备完善的本地缓存机制。在无网环境下，系统会自动将您填写的客观事实和判定暂存在浏览器本地存储中，并提示“离线暂存中”；网络恢复后点击同步即可无缝上传云端。',
          },
          {
            title: 'Q2: 审核报告导出为 Word 或 PDF 格式时出现排版错乱怎么办？',
            desc: '答：请确认您的检查记录中未包含非法特殊 Unicode 控制字符。建议在导出前点击「报告预览」，检查文本是否完整。如仍有问题，请联系机构系统管理员刷新模板样式表。',
          },
          {
            title: 'Q3: 为什么审核员在检查表中看不到某些特定的章节？',
            desc: '答：这是因为审核组长在制定审核计划和分工时，将不同专业章节分配给了不同组员。若需核查其他章节，可请审核组长在「团队分工」中增加您的条款权限。',
          },
          {
            title: 'Q4: 上传现场证据照片有文件大小或格式限制吗？',
            desc: '答：单张照片建议在 10MB 以内，支持 JPG、PNG、JPEG 及常见 PDF 扫描件。移动端拍照时系统已内置适度图片压缩算法，在保留关键细节的同时加快传输速度。',
          },
        ],
      },
      {
        id: 'pro-tips',
        title: '键盘快捷键与高效使用技巧',
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
