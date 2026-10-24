"""
审核 AI Agent 服务
Audit AI Agent Service

支持多个 AI 模型：
1. 阿里云通义千问 (Qwen3.5-Plus) - 默认
2. NVIDIA Mistral Large
3. OpenAI GPT-4 (如果配置)
"""
import logging
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.llm_fallback import create_main_llm_client
from app.utils.llm_json import extract_json
from app.models.audit_project import (
    AuditProject,
    AuditAreaRecord,
    Nonconformity,
)
from app.models.record import InspectionRecordItem
from app.models.enterprise import Enterprise


logger = logging.getLogger(__name__)

# 主 LLM 客户端（1 主 + 多备）在进程内共享：便捷包装函数每次调用都新建
# AuditAgent，若每次都重建整条 fallback 链（每个 OpenAI 客户端构造约
# 数百毫秒），AI 端点会白付约 1~2s 的固定开销。LLMClientWithFallback
# 只持有不可变配置，跨协程共享安全（其余服务均为模块级单例，同此口径）。
_shared_llm_client: Optional["object"] = None


def _get_shared_llm_client():
    global _shared_llm_client
    if _shared_llm_client is None:
        _shared_llm_client = create_main_llm_client()
    return _shared_llm_client


class AuditAgent:
    """审核 AI Agent - 支持多模型"""

    def __init__(self, db: AsyncSession, user_id: Optional[str] = None):
        """
        初始化 AI Agent

        Args:
            db: 数据库会话
            user_id: 触发本次调用的用户，用于 LLMCallLog 归属

        注：原先接受 model_provider 参数但在函数体内被无条件覆盖为
        "sensenova"，是个会误导调用方的死参数，已移除。模型统一取配置值。
        """
        self.db = db
        self.user_id = user_id
        # Audit preparation, evidence evaluation, report writing and NC
        # drafting are text tasks.  Keep them on the configured primary text
        # model; the separate vision model is reserved for photo analysis.
        self.model_provider = settings.LLM_PROVIDER
        self.client = _get_shared_llm_client()
        self.model = settings.LLM_MODEL

    async def _chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        call_type: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """统一的 JSON 调用入口，负责记账。

        这四个能力此前每处各写一遍 create() 且完全不写 LLMCallLog，
        导致审核准备/报告撰写这条链路的成本与失败率不可见。
        """
        started = time.monotonic()
        content = ""
        tokens_used = 0
        error_text: Optional[str] = None
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            tokens_used = getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
            return content
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                from app.models.audit import LLMCallLog

                self.db.add(
                    LLMCallLog(
                        user_id=self.user_id,
                        call_type=call_type,
                        prompt=user_prompt,
                        response=content,
                        model=self.model,
                        tokens_used=tokens_used or None,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        is_success="false" if error_text else "true",
                        error_msg=error_text,
                    )
                )
                await self.db.flush()
            except Exception as log_err:
                logger.warning("[AuditAgent] failed to write LLMCallLog: %s", log_err)

    async def _chat_stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        call_type: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[dict, None]:
        """流式调用 LLM 并逐 chunk 生成 SSE 事件。"""
        started = time.monotonic()
        content = ""
        tokens_used = 0
        error_text: Optional[str] = None
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in response:
                if not chunk.choices:
                    if getattr(chunk, "usage", None):
                        tokens_used += chunk.usage.total_tokens or 0
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    content += delta.content
                    yield {"type": "content", "content": delta.content}

            yield {"type": "done", "full_content": content}
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            yield {"type": "error", "content": f"AI 服务异常: {exc}"}
            raise
        finally:
            try:
                from app.models.audit import LLMCallLog

                self.db.add(
                    LLMCallLog(
                        user_id=self.user_id,
                        call_type=call_type,
                        prompt=user_prompt,
                        response=content,
                        model=self.model,
                        tokens_used=tokens_used or None,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        is_success="false" if error_text else "true",
                        error_msg=error_text,
                    )
                )
                await self.db.flush()
            except Exception as log_err:
                logger.warning("[AuditAgent] failed to write LLMCallLog: %s", log_err)

    async def stream_prepare_audit(
        self, project_id: UUID
    ) -> AsyncGenerator[dict, None]:
        """流式生成审核准备建议。"""
        project_result = await self.db.execute(
            select(AuditProject).where(AuditProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            yield {"type": "error", "content": "审核项目不存在"}
            return

        enterprise_result = await self.db.execute(
            select(Enterprise).where(Enterprise.id == project.enterprise_id)
        )
        enterprise = enterprise_result.scalar_one_or_none()

        historical_nc = []
        if enterprise:
            historical_result = await self.db.execute(
                select(Nonconformity, AuditProject)
                .join(AuditProject, Nonconformity.project_id == AuditProject.id)
                .where(AuditProject.enterprise_id == enterprise.id)
                .where(AuditProject.id != project.id)
                .order_by(Nonconformity.created_at.desc())
                .limit(20)
            )
            historical_nc = [
                {
                    "project_no": historical_project.project_no,
                    "severity": nc.severity,
                    "clause_no": nc.clause_no,
                    "description": nc.description,
                    "status": nc.status,
                }
                for nc, historical_project in historical_result.all()
            ]

        prompt = f"""
你是一位资深的认证审核专家。请基于以下企业信息与本次审核要求，为即将进行的现场审核提供专业、详尽的审核准备建议与风险评估方案：

企业信息：
- 企业名称：{enterprise.name if enterprise else '未知'}
- 行业类型：{enterprise.enterprise_type if enterprise else '未知'}
- 员工人数：{enterprise.employee_count if enterprise else '未知'}
- 上次审核时间：{enterprise.last_audit_date if enterprise else '首次审核'}
- 上次审核类型：{enterprise.last_audit_type if enterprise else '无'}

本次审核信息：
- 项目名称：{project.title}
- 审核类型：{project.audit_type}
- 认证体系：{', '.join(project.certification_systems)}
- 审核准则：{', '.join(project.audit_criteria)}
- 计划审核人天：{project.audit_days or '待定'} 天

历史不符合项：
{historical_nc if historical_nc else '无历史不符合项记录'}

请按照以下 Markdown 格式结构输出专业建议：
### 一、 审核人天与资源评估
（评估计划人天数是否合理，给出依据）

### 二、 高风险区域与重点工序预判
（列出需要重点抽查的生产车间、职能部门、危险化学品/特种设备等关键区域，并说明原因）

### 三、 重点审核条款及核查要点
（基于行业特点与体系标准，列出 3-5 个核心标准条款及其现场核查要点）

### 四、 现场审核注意事项与取证建议
（列出审核员在现场取证、交谈、抽样、安全防护等方面的特别注意事项）

### 五、 总体准备建议
（给出审核组进驻前的一揽子准备建议）
"""
        async for chunk in self._chat_stream(
            system_prompt="你是一位资深的认证审核专家，擅长审核准备、风险评估与现场策略制定。",
            user_prompt=prompt,
            call_type="audit_prepare_stream",
            max_tokens=3000,
            temperature=0.7,
        ):
            yield chunk

    async def stream_generate_report(
        self, project_id: UUID
    ) -> AsyncGenerator[dict, None]:
        """流式生成审核报告叙述性评价。"""
        project_result = await self.db.execute(
            select(AuditProject).where(AuditProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            yield {"type": "error", "content": "审核项目不存在"}
            return

        records_result = await self.db.execute(
            select(AuditAreaRecord).where(AuditAreaRecord.project_id == project_id)
        )
        records = records_result.scalars().all()

        nc_result = await self.db.execute(
            select(Nonconformity).where(Nonconformity.project_id == project_id)
        )
        nonconformities = nc_result.scalars().all()

        findings_summary = []
        for record in records:
            if record.conclusion:
                findings_summary.append(f"【{record.area_id or '区域'}】{record.conclusion}")

        nc_summary = []
        for nc in nonconformities:
            nc_summary.append(f"[{nc.severity}] {nc.clause_no}: {nc.description}")

        prompt = f"""
你是一位资深的认证审核专家。请基于以下现场审核信息，生成审核报告第二章中的叙述性综合评价：

审核项目信息：
- 项目名称：{project.title}
- 认证体系：{', '.join(project.certification_systems)}
- 审核类型：{project.audit_type}

现场审核发现摘要：
{chr(10).join(findings_summary[:15]) if findings_summary else '暂无异常发现记录'}

不符合项摘要：
{chr(10).join(nc_summary) if nc_summary else '本次审核未开具不符合项'}

请按照以下 Markdown 格式结构输出审核报告评价内容（每节150-250字，用词严谨专业）：
### 3.1 文件化信息与管理体系构建
### 3.2 质量/环境/安全目标与指标达成
### 3.3 风险和机遇的应对措施
### 3.4 资源配置与支持过程控制
### 3.5 现场运行控制与过程绩效
### 3.6 监测、测量与绩效评价
### 3.7 持续改进与纠正措施
### 3.8 管理评审与内部审核实施
### 3.9 总体审核结论与推荐意见
"""
        async for chunk in self._chat_stream(
            system_prompt="你是一位资深的认证审核专家，擅长撰写规范、客观、严谨的认证审核报告。",
            user_prompt=prompt,
            call_type="audit_report_stream",
            max_tokens=4000,
            temperature=0.7,
        ):
            yield chunk

    async def prepare_audit(self, project_id: UUID) -> Dict[str, Any]:
        """
        审核准备 Agent
        基于企业信息和历史审核记录，预判高风险区域和重点关注事项
        """
        # 获取项目和企业信息
        project_result = await self.db.execute(
            select(AuditProject).where(AuditProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        enterprise_result = await self.db.execute(
            select(Enterprise).where(Enterprise.id == project.enterprise_id)
        )
        enterprise = enterprise_result.scalar_one_or_none()

        # 获取历史不符合项
        historical_nc = []
        if enterprise:
            historical_result = await self.db.execute(
                select(Nonconformity, AuditProject)
                .join(AuditProject, Nonconformity.project_id == AuditProject.id)
                .where(AuditProject.enterprise_id == enterprise.id)
                .where(AuditProject.id != project.id)
                .order_by(Nonconformity.created_at.desc())
                .limit(20)
            )
            historical_nc = [
                {
                    "project_no": historical_project.project_no,
                    "severity": nc.severity,
                    "clause_no": nc.clause_no,
                    "description": nc.description,
                    "status": nc.status,
                }
                for nc, historical_project in historical_result.all()
            ]

        # 构建提示词
        prompt = f"""
你是一位资深的认证审核专家。请基于以下信息，为即将进行的审核提供准备建议：

企业信息：
- 企业名称：{enterprise.name if enterprise else '未知'}
- 行业类型：{enterprise.enterprise_type if enterprise else '未知'}
- 员工人数：{enterprise.employee_count if enterprise else '未知'}
- 上次审核时间：{enterprise.last_audit_date if enterprise else '首次审核'}
- 上次审核类型：{enterprise.last_audit_type if enterprise else '无'}

本次审核信息：
- 审核类型：{project.audit_type}
- 认证体系：{', '.join(project.certification_systems)}
- 审核准则：{', '.join(project.audit_criteria)}
- 审核人天：{project.audit_days}

历史不符合项：
{historical_nc if historical_nc else '无历史不符合项'}

请提供以下内容：
1. 建议的审核人天数是否合理（基于企业规模和风险）
2. 高风险区域预判（哪些部门/区域需要重点关注）
3. 重点审核条款（基于行业特点和历史问题）
4. 审核注意事项（需要特别关注的方面）

请以 JSON 格式返回，包含以下字段：
{{
  "audit_days_assessment": "审核人天评估",
  "high_risk_areas": ["高风险区域1", "高风险区域2"],
  "key_clauses": ["重点条款1", "重点条款2"],
  "attention_points": ["注意事项1", "注意事项2"],
  "overall_suggestion": "总体建议"
}}
"""

        try:
            content = await self._chat_json(
                system_prompt="你是一位资深的认证审核专家，擅长审核准备和风险评估。",
                user_prompt=prompt,
                call_type="audit_prepare",
                max_tokens=2048,
                temperature=0.7,
            )

            result = extract_json(content)
            return result

        except Exception as e:
            return {
                "error": str(e),
                "audit_days_assessment": "无法评估",
                "high_risk_areas": [],
                "key_clauses": [],
                "attention_points": [],
                "overall_suggestion": f"AI 服务暂时不可用 ({self.model_provider})"
            }

    async def evaluate_evidence(
        self,
        evidence: str,
        clause_no: str,
        certification_system: str
    ) -> Dict[str, Any]:
        """
        证据充分性评估 Agent
        评估审核证据是否满足标准条款要求
        """
        prompt = f"""
你是一位资深的认证审核专家。请评估以下审核证据是否满足标准要求：

认证体系：{certification_system}
标准条款：{clause_no}
审核证据：{evidence}

请评估：
1. 证据是否充分（是否足以证明符合要求）
2. 建议的评估等级（1-符合、2-基本符合、3-不符合）
3. 评估理由
4. 如果证据不足，建议补充什么证据

请以 JSON 格式返回：
{{
  "is_sufficient": true/false,
  "suggested_evaluation": "1/2/3",
  "reasoning": "评估理由",
  "additional_evidence_needed": "需要补充的证据（如果有）"
}}
"""

        try:
            content = await self._chat_json(
                system_prompt="你是一位资深的认证审核专家，擅长证据评估和标准解读。",
                user_prompt=prompt,
                call_type="audit_evidence_eval",
                max_tokens=2048,
                temperature=0.3,
            )

            result = extract_json(content)
            return result

        except Exception as e:
            return {
                "error": str(e),
                "is_sufficient": None,
                "suggested_evaluation": "1",
                "reasoning": f"AI 服务暂时不可用 ({self.model_provider})",
                "additional_evidence_needed": ""
            }

    async def generate_report_narrative(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        报告生成 Agent
        基于审核记录自动生成叙述性综合评价
        """
        # 获取项目信息
        project_result = await self.db.execute(
            select(AuditProject).where(AuditProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        # 获取审核记录
        records_result = await self.db.execute(
            select(AuditAreaRecord).where(AuditAreaRecord.project_id == project_id)
        )
        records = records_result.scalars().all()

        # 获取不符合项
        nc_result = await self.db.execute(
            select(Nonconformity).where(Nonconformity.project_id == project_id)
        )
        nonconformities = nc_result.scalars().all()

        # 构建审核发现摘要
        findings_summary = []
        for record in records:
            if record.conclusion:
                findings_summary.append(f"{record.area_id}: {record.conclusion}")

        nc_summary = []
        for nc in nonconformities:
            nc_summary.append(f"[{nc.severity}] {nc.clause_no}: {nc.description}")

        prompt = f"""
你是一位资深的认证审核专家。请基于以下审核信息，生成审核报告的叙述性综合评价（第二章第二节）。

审核项目信息：
- 认证体系：{', '.join(project.certification_systems)}
- 审核类型：{project.audit_type}

审核发现摘要：
{chr(10).join(findings_summary[:10])}  # 限制前10条

不符合项摘要：
{chr(10).join(nc_summary)}

请按照以下结构生成评价（每节100-200字）：
3.1 文件化信息
3.2 目标和指标
3.3 风险和机遇
3.4 支持过程
3.5 运行控制
3.6 绩效评价
3.7 改进
3.8 管理评审
3.9 总体评价

请以 JSON 格式返回：
{{
  "section_3_1": "文件化信息评价",
  "section_3_2": "目标和指标评价",
  "section_3_3": "风险和机遇评价",
  "section_3_4": "支持过程评价",
  "section_3_5": "运行控制评价",
  "section_3_6": "绩效评价评价",
  "section_3_7": "改进评价",
  "section_3_8": "管理评审评价",
  "section_3_9": "总体评价"
}}
"""

        try:
            content = await self._chat_json(
                system_prompt="你是一位资深的认证审核专家，擅长撰写审核报告。",
                user_prompt=prompt,
                call_type="audit_report_narrative",
                max_tokens=4096,
                temperature=0.7,
            )

            result = extract_json(content)
            return result

        except Exception as e:
            return {
                "error": str(e),
                "section_3_1": f"AI 服务暂时不可用 ({self.model_provider})",
                "section_3_2": "",
                "section_3_3": "",
                "section_3_4": "",
                "section_3_5": "",
                "section_3_6": "",
                "section_3_7": "",
                "section_3_8": "",
                "section_3_9": ""
            }

    async def suggest_nonconformity(
        self,
        evidence: str,
        clause_no: str,
        certification_system: str
    ) -> Dict[str, Any]:
        """
        不符合项建议 Agent
        当评估为不符合时，自动起草不符合项描述
        """
        prompt = f"""
你是一位资深的认证审核专家。基于以下信息，请起草一份不符合项报告：

认证体系：{certification_system}
涉及条款：{clause_no}
审核证据：{evidence}

请提供：
1. 不符合项描述（客观、具体、可验证）
2. 建议的严重程度（major/minor/observation）
3. 整改要求
4. 整改期限建议（天数）

请以 JSON 格式返回：
{{
  "description": "不符合项描述",
  "severity": "major/minor/observation",
  "corrective_action_required": "整改要求",
  "suggested_due_days": 30
}}
"""

        try:
            content = await self._chat_json(
                system_prompt="你是一位资深的认证审核专家，擅长不符合项管理。",
                user_prompt=prompt,
                call_type="audit_nc_suggest",
                max_tokens=2048,
                temperature=0.5,
            )

            result = extract_json(content)
            return result

        except Exception as e:
            return {
                "error": str(e),
                "description": f"AI 服务暂时不可用 ({self.model_provider})",
                "severity": "minor",
                "corrective_action_required": "",
                "suggested_due_days": 30
            }


# 便捷函数
async def prepare_audit_with_ai(
    db: AsyncSession, 
    project_id: UUID,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """使用 AI 准备审核"""
    agent = AuditAgent(db, user_id=user_id)
    return await agent.prepare_audit(project_id)


async def evaluate_evidence_with_ai(
    db: AsyncSession,
    evidence: str,
    clause_no: str,
    certification_system: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """使用 AI 评估证据"""
    agent = AuditAgent(db, user_id=user_id)
    return await agent.evaluate_evidence(evidence, clause_no, certification_system)


async def generate_report_with_ai(
    db: AsyncSession, 
    project_id: UUID,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """使用 AI 生成报告"""
    agent = AuditAgent(db, user_id=user_id)
    return await agent.generate_report_narrative(project_id)


async def suggest_nc_with_ai(
    db: AsyncSession,
    evidence: str,
    clause_no: str,
    certification_system: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """使用 AI 建议不符合项"""
    agent = AuditAgent(db, user_id=user_id)
    return await agent.suggest_nonconformity(evidence, clause_no, certification_system)


def stream_prepare_audit_with_ai(
    db: AsyncSession,
    project_id: UUID,
    user_id: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """使用 AI 流式准备审核"""
    agent = AuditAgent(db, user_id=user_id)
    return agent.stream_prepare_audit(project_id)


def stream_generate_report_with_ai(
    db: AsyncSession,
    project_id: UUID,
    user_id: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """使用 AI 流式生成报告"""
    agent = AuditAgent(db, user_id=user_id)
    return agent.stream_generate_report(project_id)

