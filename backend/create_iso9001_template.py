"""
ISO 9001:2015 质量管理体系审核模板录入脚本
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.template import InspectionTemplate, TemplateItem
from app.models.user import User


AUDIT_RESULT_OPTIONS = [
    {"label": "合格", "value": "pass", "color": "green"},
    {"label": "不合格", "value": "fail", "color": "red"},
    {"label": "待整改", "value": "pending_rectification", "color": "orange"},
    {"label": "未涉及", "value": "not_applicable", "color": "gray"},
]


ISO_9001_TEMPLATE = {
    "name": "ISO 9001:2015 质量管理体系审核",
    "code": "ISO9001-2015-QMS",
    "description": "依据 ISO 9001:2015 标准进行质量管理体系审核，覆盖第4-10章全部条款要求。",
    "category": "质量管理体系",
    "certification_system": "Q",
    "applicable_area_type": "通用",
    "version": "1.0",
}


TEMPLATE_ITEMS = [
    {
        "clause_no": "4",
        "title": "第4章 组织环境",
        "description": "理解组织及其环境、相关方需求、确定QMS范围",
        "is_category": True,
        "sort_order": 1,
        "children": [
            {
                "clause_no": "4.1",
                "title": "理解组织及其环境",
                "description": "组织是否确定与其宗旨和战略方向相关并影响其实现质量管理体系预期结果的能力的各种外部和内部因素？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅组织环境分析报告、战略规划文件；访谈高层领导了解环境分析过程",
                "sort_order": 1,
            },
            {
                "clause_no": "4.2",
                "title": "理解相关方的需求和期望",
                "description": "组织是否确定与质量管理体系有关的相关方及其要求？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅相关方清单及要求识别记录；访谈了解相关方需求收集方式",
                "sort_order": 2,
            },
            {
                "clause_no": "4.3",
                "title": "确定质量管理体系的范围",
                "description": "组织是否确定质量管理体系的边界和适用性？范围是否形成文件并保持？",
                "check_method": "文件审查",
                "evidence_hint": "查阅质量手册中的范围声明；确认是否明确说明适用的产品和服务、不适用条款及理由",
                "sort_order": 3,
            },
            {
                "clause_no": "4.4",
                "title": "质量管理体系及其过程",
                "description": "组织是否按照本标准的要求建立、实施、保持和持续改进质量管理体系？",
                "check_method": "文件审查+现场观察",
                "evidence_hint": "查阅质量手册、程序文件；确认过程识别、顺序和相互作用是否明确",
                "sort_order": 4,
            },
        ],
    },
    {
        "clause_no": "5",
        "title": "第5章 领导作用",
        "description": "领导作用和承诺、质量方针、组织角色职责",
        "is_category": True,
        "sort_order": 2,
        "children": [
            {
                "clause_no": "5.1",
                "title": "领导作用和承诺",
                "description": "最高管理者是否证实对质量管理体系的领导作用和承诺？",
                "check_method": "访谈+文件审查",
                "evidence_hint": "访谈最高管理者；查阅管理评审记录、资源提供证据、质量方针制定和传达记录",
                "sort_order": 1,
            },
            {
                "clause_no": "5.2",
                "title": "质量方针",
                "description": "最高管理者是否制定、实施和保持质量方针？方针是否适应组织宗旨？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅质量方针文件；确认方针是否包含适用要求承诺、持续改进框架；访谈员工是否理解方针",
                "sort_order": 2,
            },
            {
                "clause_no": "5.3",
                "title": "组织的角色、职责和权限",
                "description": "最高管理者是否确保组织内相关角色的职责和权限得到分配、沟通和理解？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅组织架构图、岗位职责说明书；访谈关键岗位人员了解职责权限",
                "sort_order": 3,
            },
        ],
    },
    {
        "clause_no": "6",
        "title": "第6章 策划",
        "description": "应对风险和机遇、质量目标及其实现策划、变更策划",
        "is_category": True,
        "sort_order": 3,
        "children": [
            {
                "clause_no": "6.1",
                "title": "应对风险和机遇的措施",
                "description": "组织是否策划并确定需要应对的风险和机遇？是否制定相应措施？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅风险和机遇识别清单、评估记录、措施计划；确认措施是否实施并评价有效性",
                "sort_order": 1,
            },
            {
                "clause_no": "6.2",
                "title": "质量目标及其实现策划",
                "description": "组织是否在相关职能、层次和过程上建立质量目标？目标是否可测量？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅质量目标文件；确认目标是否与方针一致、可测量、包含产品和服务要求；查阅目标达成情况统计",
                "sort_order": 2,
            },
            {
                "clause_no": "6.3",
                "title": "变更的策划",
                "description": "当组织确定需要对质量管理体系进行变更时，是否以策划的方式进行？",
                "check_method": "文件审查",
                "evidence_hint": "查阅变更记录、变更评审记录；确认变更是否考虑目的、完整性、资源分配、职责权限",
                "sort_order": 3,
            },
        ],
    },
    {
        "clause_no": "7",
        "title": "第7章 支持",
        "description": "资源、能力、意识、沟通、成文信息",
        "is_category": True,
        "sort_order": 4,
        "children": [
            {
                "clause_no": "7.1.1",
                "title": "总则（资源）",
                "description": "组织是否确定并提供所需的资源？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅资源配置计划、预算文件；访谈了解资源需求识别和提供过程",
                "sort_order": 1,
            },
            {
                "clause_no": "7.1.2",
                "title": "人员",
                "description": "组织是否确定并配备所需的人员？",
                "check_method": "文件审查",
                "evidence_hint": "查阅人员配置计划、招聘记录、人员清单；确认关键岗位人员是否到位",
                "sort_order": 2,
            },
            {
                "clause_no": "7.1.3",
                "title": "基础设施",
                "description": "组织是否确定、提供和维护所需的基础设施？",
                "check_method": "现场观察+文件审查",
                "evidence_hint": "现场查看设备、设施状况；查阅设备台账、维护保养记录、校准记录",
                "sort_order": 3,
            },
            {
                "clause_no": "7.1.4",
                "title": "过程运行环境",
                "description": "组织是否确定、提供和维护运行过程所需的环境？",
                "check_method": "现场观察",
                "evidence_hint": "现场查看生产环境、温湿度控制、照明、通风、卫生状况等",
                "sort_order": 4,
            },
            {
                "clause_no": "7.1.5",
                "title": "监视和测量资源",
                "description": "组织是否确定并提供所需的监视和测量资源？是否确保测量溯源？",
                "check_method": "现场观察+文件审查",
                "evidence_hint": "查看测量设备台账、校准证书、校准计划；确认测量不确定度是否考虑",
                "sort_order": 5,
            },
            {
                "clause_no": "7.1.6",
                "title": "组织的知识",
                "description": "组织是否确定和管理运行过程所需的知识？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅知识管理制度、知识库、培训教材、经验总结记录；访谈了解知识传递方式",
                "sort_order": 6,
            },
            {
                "clause_no": "7.2",
                "title": "能力",
                "description": "组织是否确定在其控制下工作的人员所需具备的能力？是否确保人员胜任？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅岗位能力要求、培训记录、考核记录、上岗证；抽查人员培训档案",
                "sort_order": 7,
            },
            {
                "clause_no": "7.3",
                "title": "意识",
                "description": "组织是否确保在其控制下工作的人员知晓质量方针、质量目标、自身贡献？",
                "check_method": "访谈",
                "evidence_hint": "访谈各层级员工，了解其对质量方针、目标、职责的认知程度",
                "sort_order": 8,
            },
            {
                "clause_no": "7.4",
                "title": "沟通",
                "description": "组织是否确定与质量管理体系相关的内部和外部沟通？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅沟通制度、会议记录、信息传递记录；访谈了解沟通方式和效果",
                "sort_order": 9,
            },
            {
                "clause_no": "7.5.1",
                "title": "总则（成文信息）",
                "description": "组织的质量管理体系是否包括本标准要求的成文信息？",
                "check_method": "文件审查",
                "evidence_hint": "查阅文件清单，确认是否包含标准要求的程序文件、记录",
                "sort_order": 10,
            },
            {
                "clause_no": "7.5.2",
                "title": "创建和更新",
                "description": "组织是否控制成文信息的创建和更新？",
                "check_method": "文件审查",
                "evidence_hint": "查阅文件编制审批流程、格式要求、版本控制、修订记录",
                "sort_order": 11,
            },
            {
                "clause_no": "7.5.3",
                "title": "成文信息的控制",
                "description": "组织是否控制质量管理体系和本标准要求的成文信息？",
                "check_method": "文件审查+现场观察",
                "evidence_hint": "查阅文件发放回收记录、现场使用的文件版本；确认文件是否易于获取、防止非预期使用",
                "sort_order": 12,
            },
        ],
    },
    {
        "clause_no": "8",
        "title": "第8章 运行",
        "description": "运行策划和控制、产品和服务要求、设计开发、外部提供控制、生产服务提供、放行、不合格控制",
        "is_category": True,
        "sort_order": 5,
        "children": [
            {
                "clause_no": "8.1",
                "title": "运行策划和控制",
                "description": "组织是否策划、实施和控制满足产品和服务要求所需的过程？",
                "check_method": "文件审查+现场观察",
                "evidence_hint": "查阅过程策划文件、工艺文件、作业指导书；现场确认策划实施情况",
                "sort_order": 1,
            },
            {
                "clause_no": "8.2.1",
                "title": "顾客沟通",
                "description": "组织是否与顾客进行沟通？沟通内容是否包括产品信息、问询、合同、反馈？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅顾客沟通记录、合同评审记录、顾客反馈处理记录；访谈销售人员",
                "sort_order": 2,
            },
            {
                "clause_no": "8.2.2",
                "title": "产品和服务要求的确定",
                "description": "组织是否确定产品和服务的要求？",
                "check_method": "文件审查",
                "evidence_hint": "查阅合同、订单、技术协议、法律法规要求识别记录",
                "sort_order": 3,
            },
            {
                "clause_no": "8.2.3",
                "title": "产品和服务要求的评审",
                "description": "组织是否确保有能力满足向顾客提供的产品和服务的要求？",
                "check_method": "文件审查",
                "evidence_hint": "查阅合同评审记录、订单确认记录；确认评审是否在承诺前进行",
                "sort_order": 4,
            },
            {
                "clause_no": "8.2.4",
                "title": "产品和服务要求的更改",
                "description": "组织是否确保相关文件得到修改、相关人员获知变更的要求？",
                "check_method": "文件审查",
                "evidence_hint": "查阅合同变更记录、变更通知记录；确认变更是否正确传递",
                "sort_order": 5,
            },
            {
                "clause_no": "8.3.1",
                "title": "总则（设计和开发）",
                "description": "组织是否建立、实施和保持设计和开发过程？",
                "check_method": "文件审查",
                "evidence_hint": "查阅设计开发控制程序；确认设计开发流程是否建立",
                "sort_order": 6,
            },
            {
                "clause_no": "8.3.2",
                "title": "设计和开发策划",
                "description": "组织是否对设计和开发进行策划？",
                "check_method": "文件审查",
                "evidence_hint": "查阅设计开发计划、任务书；确认阶段划分、评审验证确认安排、职责分工",
                "sort_order": 7,
            },
            {
                "clause_no": "8.3.3",
                "title": "设计和开发输入",
                "description": "组织是否确定设计和开发输入？",
                "check_method": "文件审查",
                "evidence_hint": "查阅设计输入清单、技术要求、法律法规要求；确认输入是否完整、充分",
                "sort_order": 8,
            },
            {
                "clause_no": "8.3.4",
                "title": "设计和开发控制",
                "description": "组织是否对设计和开发过程进行控制？",
                "check_method": "文件审查",
                "evidence_hint": "查阅设计评审记录、设计验证记录、设计确认记录；确认评审验证确认是否按计划执行",
                "sort_order": 9,
            },
            {
                "clause_no": "8.3.5",
                "title": "设计和开发输出",
                "description": "组织是否确保设计和开发输出满足输入要求？",
                "check_method": "文件审查",
                "evidence_hint": "查阅设计输出文件、图纸、规范、采购要求；确认输出是否满足输入、放行前得到批准",
                "sort_order": 10,
            },
            {
                "clause_no": "8.3.6",
                "title": "设计和开发更改",
                "description": "组织是否识别、评审和控制设计和开发期间及后续的更改？",
                "check_method": "文件审查",
                "evidence_hint": "查阅设计变更记录、变更评审记录；确认变更是否受控",
                "sort_order": 11,
            },
            {
                "clause_no": "8.4.1",
                "title": "总则（外部提供的过程、产品和服务的控制）",
                "description": "组织是否确保外部提供的过程、产品和服务符合要求？",
                "check_method": "文件审查",
                "evidence_hint": "查阅供应商管理制度、供应商清单、外包过程识别",
                "sort_order": 12,
            },
            {
                "clause_no": "8.4.2",
                "title": "控制类型和程度",
                "description": "组织是否确保外部提供的过程、产品和服务不会对组织稳定地向顾客交付合格产品和服务的能力产生不利影响？",
                "check_method": "文件审查+现场观察",
                "evidence_hint": "查阅供应商评价记录、供应商监控记录、进货检验记录；确认控制措施是否有效",
                "sort_order": 13,
            },
            {
                "clause_no": "8.4.3",
                "title": "提供给外部供方的信息",
                "description": "组织是否确保在与外部供方沟通之前所确定的要求是充分和适宜的？",
                "check_method": "文件审查",
                "evidence_hint": "查阅采购合同、技术协议、质量协议；确认要求是否明确传达",
                "sort_order": 14,
            },
            {
                "clause_no": "8.5.1",
                "title": "生产和服务提供的控制",
                "description": "组织是否在受控条件下进行生产和服务提供？",
                "check_method": "现场观察+文件审查",
                "evidence_hint": "现场查看作业指导书、过程参数监控、设备状态、人员操作；查阅生产记录",
                "sort_order": 15,
            },
            {
                "clause_no": "8.5.2",
                "title": "标识和可追溯性",
                "description": "组织是否需要使用适宜的方法识别输出？是否需要在产品实现的全过程中识别监视和测量状态？",
                "check_method": "现场观察",
                "evidence_hint": "现场查看产品标识、状态标识、追溯记录；确认标识是否清晰、可追溯",
                "sort_order": 16,
            },
            {
                "clause_no": "8.5.3",
                "title": "顾客或外部供方的财产",
                "description": "组织是否爱护在其控制下或使用的顾客或外部供方的财产？",
                "check_method": "现场观察+文件审查",
                "evidence_hint": "现场查看顾客财产存放区域；查阅顾客财产登记、维护记录、异常报告",
                "sort_order": 17,
            },
            {
                "clause_no": "8.5.4",
                "title": "防护",
                "description": "组织是否在生产和服务提供期间对输出进行必要的防护？",
                "check_method": "现场观察",
                "evidence_hint": "现场查看产品包装、搬运、储存条件；确认防护措施是否到位",
                "sort_order": 18,
            },
            {
                "clause_no": "8.5.5",
                "title": "交付后的活动",
                "description": "组织是否满足与产品和服务相关的交付后活动的要求？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅售后服务制度、维修记录、顾客反馈处理记录；访谈售后服务人员",
                "sort_order": 19,
            },
            {
                "clause_no": "8.5.6",
                "title": "更改控制",
                "description": "组织是否对生产和服务提供的更改进行必要的评审和控制？",
                "check_method": "文件审查",
                "evidence_hint": "查阅生产变更记录、变更评审记录；确认变更是否受控、保留成文信息",
                "sort_order": 20,
            },
            {
                "clause_no": "8.6",
                "title": "产品和服务的放行",
                "description": "组织是否在适当阶段实施策划的安排，以验证产品和服务的要求已得到满足？",
                "check_method": "文件审查+现场观察",
                "evidence_hint": "查阅检验记录、放行记录；确认是否按策划安排检验、合格后放行",
                "sort_order": 21,
            },
            {
                "clause_no": "8.7",
                "title": "不合格输出的控制",
                "description": "组织是否确保对不符合要求的输出进行识别和控制？",
                "check_method": "现场观察+文件审查",
                "evidence_hint": "现场查看不合格品区域、标识；查阅不合格品处理记录、纠正措施记录",
                "sort_order": 22,
            },
        ],
    },
    {
        "clause_no": "9",
        "title": "第9章 绩效评价",
        "description": "监视测量分析和评价、内部审核、管理评审",
        "is_category": True,
        "sort_order": 6,
        "children": [
            {
                "clause_no": "9.1.1",
                "title": "总则（监视、测量、分析和评价）",
                "description": "组织是否确定需要监视和测量什么？是否确定监视、测量、分析和评价的方法？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅监视测量清单、方法规定、数据分析报告；访谈了解数据分析应用情况",
                "sort_order": 1,
            },
            {
                "clause_no": "9.1.2",
                "title": "顾客满意",
                "description": "组织是否监视顾客对其需求和期望已得到满足的程度的感受？",
                "check_method": "文件审查",
                "evidence_hint": "查阅顾客满意度调查记录、调查结果分析、改进措施",
                "sort_order": 2,
            },
            {
                "clause_no": "9.1.3",
                "title": "分析与评价",
                "description": "组织是否分析和评价通过监视和测量获得的适宜数据？",
                "check_method": "文件审查",
                "evidence_hint": "查阅数据分析报告、绩效评价报告、趋势分析；确认评价结果是否用于改进",
                "sort_order": 3,
            },
            {
                "clause_no": "9.2.1",
                "title": "总则（内部审核）",
                "description": "组织是否按照策划的时间间隔进行内部审核？",
                "check_method": "文件审查",
                "evidence_hint": "查阅内审计划、内审报告、内审记录；确认内审是否按计划执行",
                "sort_order": 4,
            },
            {
                "clause_no": "9.2.2",
                "title": "内部审核方案",
                "description": "组织是否策划、建立、实施和保持审核方案？",
                "check_method": "文件审查",
                "evidence_hint": "查阅年度内审计划、审核方案、检查表、不符合报告、纠正措施记录",
                "sort_order": 5,
            },
            {
                "clause_no": "9.3.1",
                "title": "总则（管理评审）",
                "description": "最高管理者是否按照策划的时间间隔对组织的质量管理体系进行评审？",
                "check_method": "文件审查",
                "evidence_hint": "查阅管理评审计划、管理评审报告；确认评审是否按计划执行",
                "sort_order": 6,
            },
            {
                "clause_no": "9.3.2",
                "title": "管理评审输入",
                "description": "管理评审输入是否包括本标准要求的信息？",
                "check_method": "文件审查",
                "evidence_hint": "查阅管理评审输入材料：审核结果、顾客反馈、过程绩效、不合格处置、改进机会等",
                "sort_order": 7,
            },
            {
                "clause_no": "9.3.3",
                "title": "管理评审输出",
                "description": "管理评审输出是否包括与持续改进机会相关的决定和措施？",
                "check_method": "文件审查",
                "evidence_hint": "查阅管理评审报告、改进决定、资源需求、跟踪验证记录",
                "sort_order": 8,
            },
        ],
    },
    {
        "clause_no": "10",
        "title": "第10章 改进",
        "description": "总则、不合格和纠正措施、持续改进",
        "is_category": True,
        "sort_order": 7,
        "children": [
            {
                "clause_no": "10.1",
                "title": "总则（改进）",
                "description": "组织是否确定并选择改进机会？是否采取必要措施实现预期结果？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅改进项目清单、改进措施记录；访谈了解改进机会识别方式",
                "sort_order": 1,
            },
            {
                "clause_no": "10.2",
                "title": "不合格和纠正措施",
                "description": "组织是否对不合格做出应对？是否评价是否需要采取措施消除不合格原因？",
                "check_method": "文件审查",
                "evidence_hint": "查阅不合格台账、纠正措施报告、原因分析、措施实施记录、有效性验证记录",
                "sort_order": 2,
            },
            {
                "clause_no": "10.3",
                "title": "持续改进",
                "description": "组织是否持续改进质量管理体系的适宜性、充分性和有效性？",
                "check_method": "文件审查+访谈",
                "evidence_hint": "查阅持续改进记录、PDCA循环证据、改进效果评价；访谈了解持续改进机制",
                "sort_order": 3,
            },
        ],
    },
]


async def create_template():
    """创建ISO 9001审核模板"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(InspectionTemplate).where(
                InspectionTemplate.code == ISO_9001_TEMPLATE["code"]
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"模板已存在: {existing.name} (ID: {existing.id})")
            return existing

        result = await db.execute(select(User).limit(1))
        admin_user = result.scalar_one_or_none()
        if not admin_user:
            print("错误: 未找到用户，请先创建用户")
            return None

        template = InspectionTemplate(
            **ISO_9001_TEMPLATE,
            is_published=True,
            is_public=True,
            created_by=admin_user.id,
        )
        db.add(template)
        await db.flush()

        print(f"创建模板: {template.name}")

        total_items = 0

        for chapter_data in TEMPLATE_ITEMS:
            chapter_item = TemplateItem(
                template_id=template.id,
                clause_no=chapter_data["clause_no"],
                title=chapter_data["title"],
                description=chapter_data.get("description"),
                is_category=True,
                sort_order=chapter_data["sort_order"],
                check_type="radio",
                result_options=AUDIT_RESULT_OPTIONS,
                created_by=admin_user.id,
            )
            db.add(chapter_item)
            await db.flush()
            total_items += 1
            print(f"  创建章节: {chapter_data['clause_no']} {chapter_data['title']}")

            for item_data in chapter_data.get("children", []):
                item = TemplateItem(
                    template_id=template.id,
                    parent_id=chapter_item.id,
                    clause_no=item_data["clause_no"],
                    title=item_data["title"],
                    description=item_data.get("description"),
                    check_method=item_data.get("check_method"),
                    evidence_hint=item_data.get("evidence_hint"),
                    sort_order=item_data["sort_order"],
                    check_type="radio",
                    result_options=AUDIT_RESULT_OPTIONS,
                    is_required=True,
                    allow_attachment=True,
                    created_by=admin_user.id,
                )
                db.add(item)
                total_items += 1
                print(f"    创建检查项: {item_data['clause_no']} {item_data['title']}")

        await db.commit()
        print(f"\n模板创建完成!")
        print(f"  模板ID: {template.id}")
        print(f"  检查项总数: {total_items}")

        return template


if __name__ == "__main__":
    print("=" * 60)
    print("ISO 9001:2015 质量管理体系审核模板录入")
    print("=" * 60)
    asyncio.run(create_template())
