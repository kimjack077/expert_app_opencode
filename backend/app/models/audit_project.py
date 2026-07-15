"""
审核项目相关模型
Audit Project Related Models

根据 EFIS 系统需求修改建议文档 v2.0 和 PRD-系统重构方案
"""
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Date,
    Integer,
    Numeric,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class AuditProject(Base):
    """审核项目 - 顶层容器，替代原有 InspectionTask 用于认证审核场景"""
    __tablename__ = "audit_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 项目基本信息
    project_no = Column(String(50), unique=True, nullable=False, comment="项目编号，如 LYEC-2025-1058")
    title = Column(String(300), nullable=False, comment="项目名称")
    
    # 企业信息
    enterprise_id = Column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id"),
        nullable=False,
        comment="受审核企业 ID"
    )
    
    # 审核类型
    audit_type = Column(
        String(50),
        nullable=False,
        comment="审核类型：initial(初审)/surveillance(监督)/recertification(再认证)/expansion(扩项)"
    )
    
    # 认证体系（可多选）
    certification_systems = Column(
        ARRAY(String),
        default=list,
        comment="认证体系列表：Q(质量)/E(环境)/S(职业健康安全)/En(能源)"
    )
    
    # 审核准则
    audit_criteria = Column(
        JSON,
        default=list,
        comment="审核准则列表，如 ['GB/T 19001-2016', 'ISO 14001:2015']"
    )
    
    # 审核范围
    audit_scope = Column(
        JSON,
        comment="审核范围：{activities: '活动和过程', units: '组织单元', locations: '场所', period: '覆盖时期'}"
    )
    
    # 时间安排
    scheduled_start = Column(DateTime(timezone=True), comment="计划开始时间")
    scheduled_end = Column(DateTime(timezone=True), comment="计划结束时间")
    actual_start = Column(DateTime(timezone=True), comment="实际开始时间")
    actual_end = Column(DateTime(timezone=True), comment="实际结束时间")
    audit_days = Column(Numeric(4, 1), comment="审核人天数")
    
    # 审核组
    team_leader_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        comment="审核组长 ID"
    )
    
    # 状态
    status = Column(
        String(20),
        default="planning",
        comment="状态：planning(策划中)/in_progress(进行中)/completed(已完成)/cancelled(已取消)"
    )
    
    # 备注
    remarks = Column(Text, comment="备注")
    
    # 创建信息
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    enterprise = relationship("Enterprise", foreign_keys=[enterprise_id])
    team_leader = relationship("User", foreign_keys=[team_leader_id])
    creator = relationship("User", foreign_keys=[created_by])
    
    team_members = relationship(
        "AuditTeamMember",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    plan_items = relationship(
        "AuditPlanItem",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    areas = relationship(
        "AuditArea",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    records = relationship(
        "AuditAreaRecord",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    nonconformities = relationship(
        "Nonconformity",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    reports = relationship(
        "AuditReport",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    meetings = relationship(
        "CommunicationMeeting",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    project_documents = relationship(
        "ProjectDocument",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    ai_audit_sessions = relationship(
        "AiAuditSession",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    evidence_submissions = relationship(
        "EvidenceSubmission",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    ai_draft_records = relationship(
        "AiDraftRecord",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    artifacts = relationship(
        "ProjectArtifact",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AuditProject {self.project_no}: {self.title}>"


class AuditTeamMember(Base):
    """审核工作组成员"""
    __tablename__ = "audit_team_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属项目
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属审核项目 ID"
    )
    
    # 成员信息
    member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="审核员 ID"
    )
    
    # 角色
    role = Column(
        String(20),
        default="member",
        comment="角色：leader(组长)/member(组员)/trainee(被验证审核员)/observer(观察员)/expert(技术专家)"
    )
    
    # 负责体系
    responsible_systems = Column(
        ARRAY(String),
        default=list,
        comment="负责的认证体系：Q/E/S/En"
    )
    
    # 资质信息（快照，从 User 表复制）
    qualification_codes = Column(
        JSON,
        default=list,
        comment="专业代码列表，如 ['10.01', '12.01']"
    )
    registration_no = Column(String(100), comment="注册审核员编号快照")
    registration_level = Column(String(50), comment="注册级别快照")
    
    # 分工信息
    assigned_areas = Column(
        JSON,
        default=list,
        comment="负责审核的区域/部门列表"
    )
    assigned_clauses = Column(
        JSON,
        default=list,
        comment="负责审核的标准条款列表"
    )
    
    # 状态
    status = Column(
        String(20),
        default="assigned",
        comment="状态：assigned(已分配)/in_progress(进行中)/completed(已完成)"
    )
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    project = relationship("AuditProject", back_populates="team_members")
    member = relationship("User")

    def __repr__(self):
        return f"<AuditTeamMember {self.member_id} in {self.project_id}>"


class AuditPlanItem(Base):
    """
    审核计划项 = 工作任务单元
    这是核心实体：既是计划矩阵中的一个格子，也是审核员的工作任务
    """
    __tablename__ = "audit_plan_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属项目
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属审核项目 ID"
    )
    
    # 时间安排
    plan_date = Column(Date, nullable=False, comment="审核日期")
    time_start = Column(String(10), comment="开始时间，如 '09:00'")
    time_end = Column(String(10), comment="结束时间，如 '12:00'")
    
    # 工作组
    group_no = Column(
        String(20),
        comment="工作组编号：A/B/C/D/E/ABCDE(全员)"
    )
    
    # 审核区域
    area_name = Column(String(200), nullable=False, comment="区域/部门名称，如'煤焦车间'")
    area_type = Column(
        String(50),
        comment="区域类型：department(职能部门)/workshop(车间)/office(办公室)/site(现场)/leadership(高层领导)"
    )
    
    # 分配的审核员（支持多人）
    assigned_member_ids = Column(
        ARRAY(UUID),
        default=list,
        comment="分配的审核员 ID 列表（支持多人协作）"
    )
    
    # 审核内容
    certification_systems = Column(
        ARRAY(String),
        default=list,
        comment="本次任务审核的体系：Q/E/S/En"
    )
    clauses = Column(
        JSON,
        default=list,
        comment="具体条款列表，如 ['8.5.1', '7.1.3']"
    )
    
    # 关联模板
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_templates.id"),
        comment="关联的检查模板 ID（可后期绑定）"
    )
    
    # 关联检查任务（自动创建）
    inspection_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_tasks.id", ondelete="SET NULL"),
        comment="关联的检查任务 ID（创建计划项时自动生成）"
    )
    
    # 联合审核标识
    is_joint = Column(Boolean, default=False, comment="是否为联合审核（如AB共同审核S）")
    joint_group_ids = Column(
        JSON,
        default=list,
        comment="联合的其他组标识列表"
    )
    
    # 活动类型
    activity_type = Column(
        String(50),
        default="normal",
        comment="活动类型：normal(正常审核)/opening_meeting(首次会议)/closing_meeting(末次会议)/night_inspection(夜间巡视)/internal_meeting(内部沟通)"
    )
    
    # 状态
    status = Column(
        String(20),
        default="pending",
        comment="状态：pending(待开始)/in_progress(进行中)/completed(已完成)"
    )
    
    # 备注
    remarks = Column(Text, comment="备注")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    project = relationship("AuditProject", back_populates="plan_items")
    template = relationship("InspectionTemplate")
    area_records = relationship(
        "AuditAreaRecord",
        back_populates="plan_item",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AuditPlanItem {self.area_name} on {self.plan_date}>"


class AuditArea(Base):
    """审核区域/部门 - 用于组织和跟踪各区域审核进度"""
    __tablename__ = "audit_areas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属项目
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属审核项目 ID"
    )
    
    # 区域信息
    area_name = Column(String(200), nullable=False, comment="区域名称，如'煤焦车间'")
    area_type = Column(
        String(50),
        comment="区域类型：department/workshop/office/site/leadership"
    )
    
    # 关联信息
    responsible_team_member_ids = Column(
        ARRAY(UUID),
        default=list,
        comment="负责的审核员 ID 列表"
    )
    audit_clauses = Column(
        JSON,
        default=list,
        comment="审核条款列表"
    )
    
    # 状态
    status = Column(
        String(20),
        default="pending",
        comment="状态：pending/in_progress/completed"
    )
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    project = relationship("AuditProject", back_populates="areas")
    records = relationship(
        "AuditAreaRecord",
        back_populates="area",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AuditArea {self.area_name}>"


class AuditAreaRecord(Base):
    """
    审核区域记录 - 支持协作填写
    对应真实审核材料中的"现场审核记录"
    """
    __tablename__ = "audit_area_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属项目和区域
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属审核项目 ID"
    )
    area_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_areas.id"),
        comment="审核区域 ID"
    )
    plan_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_plan_items.id"),
        comment="关联的审核计划项 ID"
    )
    
    # 记录信息
    record_no = Column(String(50), comment="记录编号")
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_templates.id"),
        comment="使用的模板 ID"
    )
    
    # 审核体系
    certification_systems = Column(
        ARRAY(String),
        default=list,
        comment="本记录涉及的体系：Q/E/S/En"
    )
    
    # 填写人（支持协作）
    recorded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="主填写人 ID"
    )
    co_recorders = Column(
        ARRAY(UUID),
        default=list,
        comment="协作填写人 ID 列表"
    )
    
    # 审核时间
    audit_date = Column(Date, comment="审核日期")
    audit_time_start = Column(String(10), comment="审核开始时间")
    audit_time_end = Column(String(10), comment="审核结束时间")
    
    # 审核结论
    conclusion = Column(Text, comment="审核结论")
    
    # 状态
    status = Column(
        String(20),
        default="draft",
        comment="状态：draft(草稿)/submitted(已提交)/reviewed(已审核)"
    )
    
    # 模板快照
    template_snapshot = Column(JSON, comment="模板快照 JSON")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    project = relationship("AuditProject", back_populates="records")
    area = relationship("AuditArea", back_populates="records")
    plan_item = relationship("AuditPlanItem", back_populates="area_records")
    template = relationship("InspectionTemplate")
    recorder = relationship("User", foreign_keys=[recorded_by])
    
    items = relationship(
        "InspectionRecordItem",
        foreign_keys="InspectionRecordItem.audit_area_record_id",
        back_populates="audit_area_record",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AuditAreaRecord {self.record_no}>"


class Nonconformity(Base):
    """不符合项"""
    __tablename__ = "nonconformities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属项目
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属审核项目 ID"
    )
    
    # 来源
    plan_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_plan_items.id"),
        comment="来源于哪个审核计划项"
    )
    area_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_area_records.id"),
        comment="来源于哪个区域记录"
    )
    record_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_record_items.id"),
        comment="来源于哪个检查记录项"
    )
    
    # 不符合项信息
    nc_no = Column(String(50), unique=True, nullable=False, comment="不符合项编号（自动生成）")
    severity = Column(
        String(20),
        nullable=False,
        comment="严重程度：major(严重)/minor(一般)/observation(观察项)"
    )
    
    # 涉及体系和条款
    certification_system = Column(
        String(10),
        comment="涉及的认证体系：Q/E/S/En"
    )
    clause_no = Column(String(50), comment="涉及的标准条款号")
    
    # 描述
    description = Column(Text, nullable=False, comment="不符合描述")
    evidence = Column(Text, comment="客观证据")
    
    # 整改要求
    corrective_action_required = Column(Text, comment="整改要求")
    due_date = Column(Date, comment="整改期限")
    
    # 整改情况
    corrective_action = Column(Text, comment="整改措施")
    correction_date = Column(Date, comment="整改日期")
    verification_result = Column(Text, comment="验证结果")
    verification_photos = Column(JSON, default=list, comment="验证照片 URL 列表")
    
    # 状态
    status = Column(
        String(20),
        default="open",
        comment="状态：open(待整改)/corrected(已整改)/verified(已验证)/closed(已关闭)"
    )
    
    # 关联人员
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        comment="开具人 ID"
    )
    source_draft_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_draft_records.id", ondelete="SET NULL"),
        comment="AI draft that produced this nonconformity"
    )
    confirmed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="Team leader or administrator who confirmed the draft"
    )
    confirmed_at = Column(
        DateTime(timezone=True),
        comment="Time the draft nonconformity became confirmed"
    )
    verified_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        comment="验证人 ID"
    )
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    project = relationship("AuditProject", back_populates="nonconformities")
    plan_item = relationship("AuditPlanItem")
    area_record = relationship("AuditAreaRecord")
    record_item = relationship("InspectionRecordItem")
    creator = relationship("User", foreign_keys=[created_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    confirmer = relationship("User", foreign_keys=[confirmed_by])
    source_draft = relationship("AiDraftRecord", back_populates="nonconformities")

    def __repr__(self):
        return f"<Nonconformity {self.nc_no}: {self.severity}>"


class AuditReport(Base):
    """审核报告"""
    __tablename__ = "audit_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属项目
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属审核项目 ID"
    )
    
    # 报告类型
    report_type = Column(
        String(20),
        nullable=False,
        comment="报告类型：QES(质量环境职业健康安全)/EnMS(能源管理)/combined(综合)"
    )
    
    # 报告编号
    report_no = Column(String(50), unique=True, comment="报告编号")
    
    # 审核概况（对应报告第一章）
    audit_summary = Column(
        JSON,
        comment="审核过程综述：{audit_dates, audit_team, audit_scope, audit_criteria}"
    )
    
    # 综合评价（对应报告第二章(一)）
    system_evaluation = Column(
        JSON,
        comment="管理体系综合评价打勾表：{management_system_docs, objectives, risk_opportunity, ...}"
    )
    
    # 叙述性评价（对应报告第二章(二)）
    narrative_text = Column(
        Text,
        comment="叙述性综合评价（3.1-3.9各节）"
    )
    
    # 审核发现汇总（对应报告第二章(三)）
    findings_summary = Column(
        JSON,
        comment="审核发现统计：{total_items, compliant, minor_nc, major_nc, observations}"
    )
    
    # 不符合项清单
    nonconformity_ids = Column(
        ARRAY(UUID),
        default=list,
        comment="不符合项 ID 列表"
    )
    
    # 改进机会
    improvement_opportunities = Column(
        Text,
        comment="改进机会列表"
    )
    
    # 审核结论（对应报告第三章）
    conclusion = Column(
        String(50),
        comment="审核结论：recommend(推荐认证)/conditional(有条件推荐)/not_recommend(不推荐)"
    )
    conclusion_notes = Column(Text, comment="结论说明")
    
    # 签署
    prepared_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        comment="编制人 ID"
    )
    reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        comment="审核人 ID"
    )
    # Reproducible report snapshot and pre-publication validation results.
    consistency_check = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    completeness_check = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    source_snapshot = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    version = Column(
        Integer, nullable=False, default=1, server_default=text("1")
    )

    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        comment="批准人 ID"
    )
    
    # 签署时间
    prepared_at = Column(DateTime(timezone=True), comment="编制时间")
    reviewed_at = Column(DateTime(timezone=True), comment="审核时间")
    approved_at = Column(DateTime(timezone=True), comment="批准时间")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    project = relationship("AuditProject", back_populates="reports")
    preparer = relationship("User", foreign_keys=[prepared_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    approver = relationship("User", foreign_keys=[approved_by])

    def __repr__(self):
        return f"<AuditReport {self.report_no}: {self.report_type}>"


class CommunicationMeeting(Base):
    """沟通会议记录"""
    __tablename__ = "communication_meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属项目
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属审核项目 ID"
    )
    
    # 会议类型
    meeting_type = Column(
        String(20),
        nullable=False,
        comment="会议类型：opening(首次会议)/interim(阶段沟通)/closing(末次会议)/internal(内部会议)"
    )
    
    # 会议时间
    meeting_time = Column(DateTime(timezone=True), nullable=False, comment="会议时间")
    
    # 参会人员
    participants_enterprise = Column(
        Text,
        comment="企业参会人员（文本描述）"
    )
    participants_audit_team = Column(
        ARRAY(UUID),
        default=list,
        comment="审核组参会人员 ID 列表"
    )
    
    # 会议内容
    key_points = Column(Text, comment="会议要点")
    meeting_minutes = Column(Text, comment="会议纪要")
    
    # 签到表
    sign_in_sheet = Column(JSON, comment="签到表 JSON")
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    project = relationship("AuditProject", back_populates="meetings")
    creator = relationship("User")

    def __repr__(self):
        return f"<CommunicationMeeting {self.meeting_type} at {self.meeting_time}>"
