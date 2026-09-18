"""
审核报告生成服务
Audit Report Generator Service
"""
import logging
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any
from uuid import UUID

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_project import (
    AuditProject,
    AuditTeamMember,
    AuditAreaRecord,
    Nonconformity,
    AuditReport,
)
from app.models.user import User
from app.models.enterprise import Enterprise


logger = logging.getLogger(__name__)

_CJK_FONT_NAME = "Helvetica"


def _ensure_cjk_font() -> str:
    """注册仓库自带中文字体，返回供 reportlab 使用的字体名。

    BUG-02：项目报告 PDF 原先全程使用内置 Helvetica，中文字形被静默丢弃，
    导出文件只有 3.2KB 且无正文。字体注册策略与 report_service 保持一致：
    仓库字体优先（随部署分发），系统字体兜底；进程内只注册一次。
    """
    global _CJK_FONT_NAME
    if _CJK_FONT_NAME != "Helvetica":
        return _CJK_FONT_NAME
    if "ChineseFont" in pdfmetrics.getRegisteredFontNames():
        _CJK_FONT_NAME = "ChineseFont"
        return _CJK_FONT_NAME

    repo_fonts = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    candidates = [
        repo_fonts / "NotoSansSC-Regular.ttf",
        repo_fonts / "SourceHanSansSC-Regular.otf",
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("ChineseFont", str(path), subfontIndex=0))
            _CJK_FONT_NAME = "ChineseFont"
            logger.info("项目报告 PDF 使用中文字体：%s", path)
            return _CJK_FONT_NAME
        except Exception as exc:
            logger.warning("注册中文字体失败，继续尝试下一个：%s (%s)", path, exc)

    logger.error("项目报告 PDF 未找到可用中文字体，中文将无法正常显示：%s", repo_fonts)
    return _CJK_FONT_NAME


def _p(text: Any) -> str:
    """动态文本转 Paragraph 安全 HTML：转义特殊字符并把换行转为 <br/>。"""
    return escape(str(text if text is not None else "")).replace("\n", "<br/>")


class AuditReportGenerator:
    """审核报告生成器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_word_report(self, project_id: UUID) -> BytesIO:
        """生成 Word 格式审核报告"""
        # 获取项目数据
        project_data = await self._fetch_project_data(project_id)
        
        # 创建 Word 文档
        doc = Document()
        
        # 设置文档样式
        self._setup_word_styles(doc)
        
        # 添加标题
        title = doc.add_heading('审核报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 第一章：审核过程综述
        self._add_chapter_1(doc, project_data)
        
        # 第二章：管理体系综合评价
        self._add_chapter_2(doc, project_data)
        
        # 第三章：审核结论
        self._add_chapter_3(doc, project_data)
        
        # 保存到内存
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    async def generate_pdf_report(self, project_id: UUID) -> BytesIO:
        """生成 PDF 格式审核报告"""
        # 获取项目数据
        project_data = await self._fetch_project_data(project_id)

        font_name = _ensure_cjk_font()

        # 创建 PDF 文档
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        # 构建内容（所有样式显式绑定中文字体，避免回退 Helvetica 丢字形）
        story = []
        base = getSampleStyleSheet()
        styles = {
            'Title': ParagraphStyle(
                'PdfTitle', parent=base['Heading1'], fontName=font_name,
                fontSize=22, leading=30, alignment=TA_CENTER, spaceAfter=10 * mm,
            ),
            'H1': ParagraphStyle(
                'PdfH1', parent=base['Heading1'], fontName=font_name,
                fontSize=15, leading=22, textColor=colors.HexColor('#1e40af'),
                spaceBefore=6 * mm, spaceAfter=4 * mm,
            ),
            'H2': ParagraphStyle(
                'PdfH2', parent=base['Heading2'], fontName=font_name,
                fontSize=12, leading=18, spaceBefore=4 * mm, spaceAfter=2 * mm,
            ),
            'Normal': ParagraphStyle(
                'PdfNormal', parent=base['Normal'], fontName=font_name,
                fontSize=10.5, leading=18,
            ),
            'Cell': ParagraphStyle(
                'PdfCell', parent=base['Normal'], fontName=font_name,
                fontSize=9, leading=14,
            ),
            'Right': ParagraphStyle(
                'PdfRight', parent=base['Normal'], fontName=font_name,
                fontSize=10.5, leading=18, alignment=TA_RIGHT,
            ),
        }

        # 添加标题
        story.append(Paragraph('审核报告', styles['Title']))
        story.append(Spacer(1, 0.2 * inch))

        # 第一章：审核过程综述
        self._add_pdf_chapter_1(story, styles, project_data)

        # 第二章：管理体系综合评价
        self._add_pdf_chapter_2(story, styles, project_data)

        # 第三章：审核结论
        self._add_pdf_chapter_3(story, styles, project_data)

        # 生成 PDF
        doc.build(story)
        buffer.seek(0)
        return buffer

    async def _fetch_project_data(self, project_id: UUID) -> Dict[str, Any]:
        """获取项目完整数据"""
        # 获取项目基本信息
        project_result = await self.db.execute(
            select(AuditProject).where(AuditProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")
        
        # 获取企业信息
        enterprise_result = await self.db.execute(
            select(Enterprise).where(Enterprise.id == project.enterprise_id)
        )
        enterprise = enterprise_result.scalar_one_or_none()
        
        # 获取审核组成员
        team_result = await self.db.execute(
            select(AuditTeamMember, User)
            .join(User, AuditTeamMember.member_id == User.id)
            .where(AuditTeamMember.project_id == project_id)
        )
        team_members = team_result.all()
        
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

        report_result = await self.db.execute(
            select(AuditReport)
            .where(AuditReport.project_id == project_id)
            .order_by(AuditReport.version.desc(), AuditReport.created_at.desc())
        )
        report = report_result.scalars().first()
        
        # 统计数据
        total_records = len(records)
        completed_records = sum(
            1 for r in records if r.status in {'submitted', 'reviewed'}
        )
        major_nc = sum(1 for nc in nonconformities if nc.severity == 'major')
        minor_nc = sum(1 for nc in nonconformities if nc.severity == 'minor')
        observations = sum(1 for nc in nonconformities if nc.severity == 'observation')
        
        return {
            'project': project,
            'enterprise': enterprise,
            'team_members': team_members,
            'records': records,
            'nonconformities': nonconformities,
            'report': report,
            'statistics': {
                'total_records': total_records,
                'completed_records': completed_records,
                'major_nc': major_nc,
                'minor_nc': minor_nc,
                'observations': observations,
            }
        }

    def _setup_word_styles(self, doc: Document):
        """设置 Word 文档样式"""
        # 设置默认字体
        style = doc.styles['Normal']
        style.font.name = 'SimSun'
        style.font.size = Pt(12)

    def _add_chapter_1(self, doc: Document, data: Dict[str, Any]):
        """添加第一章：审核过程综述"""
        doc.add_heading('一、审核过程综述', 1)
        
        project = data['project']
        enterprise = data['enterprise']
        team_members = data['team_members']
        
        # 1.1 受审核方基本信息
        doc.add_heading('1.1 受审核方基本信息', 2)
        p = doc.add_paragraph()
        p.add_run(f"企业名称：{enterprise.name if enterprise else '未知'}\n")
        p.add_run(f"统一社会信用代码：{enterprise.credit_code if enterprise else '未知'}\n")
        p.add_run(f"地址：{enterprise.address if enterprise else '未知'}\n")
        
        # 1.2 审核类型和准则
        doc.add_heading('1.2 审核类型和准则', 2)
        audit_type_map = {
            'initial': '初审',
            'surveillance': '监督审核',
            'recertification': '再认证审核',
            'expansion': '扩项审核'
        }
        p = doc.add_paragraph()
        p.add_run(f"审核类型：{audit_type_map.get(project.audit_type, project.audit_type)}\n")
        p.add_run(f"认证体系：{', '.join(project.certification_systems)}\n")
        p.add_run(f"审核准则：{', '.join(project.audit_criteria)}\n")
        
        # 1.3 审核组成员
        doc.add_heading('1.3 审核组成员', 2)
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Light Grid Accent 1'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = '姓名'
        hdr_cells[1].text = '角色'
        hdr_cells[2].text = '注册编号'
        hdr_cells[3].text = '注册级别'
        hdr_cells[4].text = '负责体系'
        
        for member, user in team_members:
            row_cells = table.add_row().cells
            row_cells[0].text = user.full_name or user.username
            row_cells[1].text = member.role
            row_cells[2].text = member.registration_no or '-'
            row_cells[3].text = member.registration_level or '-'
            row_cells[4].text = ', '.join(member.responsible_systems)
        
        # 1.4 审核日期
        doc.add_heading('1.4 审核日期', 2)
        p = doc.add_paragraph()
        if project.actual_start:
            start = project.actual_start.strftime('%Y年%m月%d日')
            end = project.actual_end.strftime('%Y年%m月%d日') if project.actual_end else '进行中'
            p.add_run(f"审核时间：{start} 至 {end}\n")
        p.add_run(f"审核人天：{project.audit_days or 0} 天\n")

    def _add_chapter_2(self, doc: Document, data: Dict[str, Any]):
        """添加第二章：管理体系综合评价"""
        doc.add_heading('二、管理体系综合评价', 1)
        
        stats = data['statistics']
        
        # 2.1 审核基本情况
        doc.add_heading('2.1 审核基本情况', 2)
        p = doc.add_paragraph()
        p.add_run(f"本次审核共完成 {stats['total_records']} 个区域的审核，")
        p.add_run(f"其中已审核完成 {stats['completed_records']} 个区域。\n\n")
        
        # 2.2 不符合项统计
        doc.add_heading('2.2 不符合项统计', 2)
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Light Grid Accent 1'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = '严重不符合'
        hdr_cells[1].text = '一般不符合'
        hdr_cells[2].text = '观察项'
        hdr_cells[3].text = '合计'
        
        row_cells = table.add_row().cells
        row_cells[0].text = str(stats['major_nc'])
        row_cells[1].text = str(stats['minor_nc'])
        row_cells[2].text = str(stats['observations'])
        row_cells[3].text = str(stats['major_nc'] + stats['minor_nc'] + stats['observations'])
        
        # 2.3 不符合项详情
        if data['nonconformities']:
            doc.add_heading('2.3 不符合项详情', 2)
            for nc in data['nonconformities']:
                p = doc.add_paragraph(style='List Bullet')
                severity_map = {'major': '严重', 'minor': '一般', 'observation': '观察项'}
                p.add_run(f"【{severity_map.get(nc.severity, nc.severity)}】")
                p.add_run(f"条款 {nc.clause_no}：{nc.description}\n")
                if nc.evidence:
                    p.add_run(f"证据：{nc.evidence}\n")

    def _add_chapter_3(self, doc: Document, data: Dict[str, Any]):
        """添加第三章：审核结论"""
        doc.add_heading('三、审核结论', 1)
        
        # 3.1 综合评价
        doc.add_heading('3.1 综合评价', 2)
        p = doc.add_paragraph()

        p.add_run(self._conclusion_text(data))
        
        # 3.2 审核组长签字
        doc.add_paragraph()
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.add_run('审核组长签字：________________    日期：________________')
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    def _add_pdf_chapter_1(self, story: List, styles: Any, data: Dict[str, Any]):
        """添加 PDF 第一章（内容与 Word 版保持一致）"""
        font_name = _ensure_cjk_font()
        story.append(Paragraph('一、审核过程综述', styles['H1']))

        project = data['project']
        enterprise = data['enterprise']
        team_members = data['team_members']

        # 1.1 受审核方基本信息
        story.append(Paragraph('1.1 受审核方基本信息', styles['H2']))
        ent_name = enterprise.name if enterprise else '未知'
        credit_code = enterprise.credit_code if enterprise else '未知'
        address = enterprise.address if enterprise else '未知'
        info_rows = [
            ['企业名称', _p(ent_name)],
            ['统一社会信用代码', _p(credit_code)],
            ['地址', _p(address)],
        ]
        info_table = Table(
            [[Paragraph(k, styles['Cell']), Paragraph(v, styles['Cell'])] for k, v in info_rows],
            colWidths=[40 * mm, 120 * mm],
        )
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f4ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(info_table)

        # 1.2 审核类型和准则
        story.append(Paragraph('1.2 审核类型和准则', styles['H2']))
        audit_type_map = {
            'initial': '初审',
            'surveillance': '监督审核',
            'recertification': '再认证审核',
            'expansion': '扩项审核',
        }
        audit_type = audit_type_map.get(project.audit_type, project.audit_type)
        systems = ', '.join(project.certification_systems or []) or '-'
        criteria = ', '.join(project.audit_criteria or []) or '-'
        story.append(Paragraph(f"审核类型：{_p(audit_type)}", styles['Normal']))
        story.append(Paragraph(f"认证体系：{_p(systems)}", styles['Normal']))
        story.append(Paragraph(f"审核准则：{_p(criteria)}", styles['Normal']))

        # 1.3 审核组成员
        story.append(Paragraph('1.3 审核组成员', styles['H2']))
        member_rows = [['姓名', '角色', '注册编号', '注册级别', '负责体系']]
        role_map = {'leader': '组长', 'member': '审核员', 'expert': '技术专家'}
        for member, user in team_members:
            member_rows.append([
                _p(user.full_name or user.username),
                _p(role_map.get(member.role, member.role or '-')),
                _p(member.registration_no or '-'),
                _p(member.registration_level or '-'),
                _p(', '.join(member.responsible_systems or []) or '-'),
            ])
        if len(member_rows) == 1:
            member_rows.append(['-', '-', '-', '-', '-'])
        member_table = Table(
            [[Paragraph(str(c), styles['Cell']) for c in row] for row in member_rows],
            colWidths=[28 * mm, 24 * mm, 36 * mm, 32 * mm, 40 * mm],
        )
        member_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(member_table)

        # 1.4 审核日期
        story.append(Paragraph('1.4 审核日期', styles['H2']))
        if project.actual_start:
            start = project.actual_start.strftime('%Y年%m月%d日')
            end = project.actual_end.strftime('%Y年%m月%d日') if project.actual_end else '进行中'
            story.append(Paragraph(f"审核时间：{start} 至 {end}", styles['Normal']))
        elif project.scheduled_start:
            start = project.scheduled_start.strftime('%Y年%m月%d日')
            end = project.scheduled_end.strftime('%Y年%m月%d日') if project.scheduled_end else '待定'
            story.append(Paragraph(f"计划审核时间：{start} 至 {end}", styles['Normal']))
        story.append(Paragraph(f"审核工作量（人天）：{project.audit_days or 0}", styles['Normal']))

    def _add_pdf_chapter_2(self, story: List, styles: Any, data: Dict[str, Any]):
        """添加 PDF 第二章（内容与 Word 版保持一致）"""
        font_name = _ensure_cjk_font()
        story.append(PageBreak())
        story.append(Paragraph('二、管理体系综合评价', styles['H1']))

        stats = data['statistics']

        # 2.1 审核基本情况
        story.append(Paragraph('2.1 审核基本情况', styles['H2']))
        story.append(Paragraph(
            f"本次审核共完成 {stats['total_records']} 个区域的审核，"
            f"其中已审核完成 {stats['completed_records']} 个区域。",
            styles['Normal'],
        ))

        # 2.2 不符合项统计
        story.append(Paragraph('2.2 不符合项统计', styles['H2']))
        total_nc = stats['major_nc'] + stats['minor_nc'] + stats['observations']
        table_data = [
            ['严重不符合', '一般不符合', '观察项', '合计'],
            [
                str(stats['major_nc']),
                str(stats['minor_nc']),
                str(stats['observations']),
                str(total_nc),
            ],
        ]
        t = Table(
            [[Paragraph(c, styles['Cell']) for c in row] for row in table_data],
            colWidths=[40 * mm, 40 * mm, 40 * mm, 40 * mm],
        )
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

        # 2.3 不符合项详情
        nonconformities = data['nonconformities']
        if nonconformities:
            story.append(Paragraph('2.3 不符合项详情', styles['H2']))
            severity_map = {'major': '严重', 'minor': '一般', 'observation': '观察项'}
            for nc in nonconformities:
                severity = severity_map.get(nc.severity, nc.severity)
                line = f"【{severity}】条款 {nc.clause_no or '-'}：{nc.description or ''}"
                story.append(Paragraph(_p(line), styles['Normal']))
                if nc.evidence:
                    story.append(Paragraph(f"证据：{_p(nc.evidence)}", styles['Normal']))
                story.append(Spacer(1, 2 * mm))

    def _add_pdf_chapter_3(self, story: List, styles: Any, data: Dict[str, Any]):
        """添加 PDF 第三章"""
        story.append(PageBreak())
        story.append(Paragraph('三、审核结论', styles['H1']))

        story.append(Paragraph('3.1 综合评价', styles['H2']))
        # _conclusion_text 内含换行，Paragraph 需转成 <br/> 才能正确分段
        story.append(Paragraph(_p(self._conclusion_text(data)), styles['Normal']))
        story.append(Spacer(1, 0.5 * inch))

        # 签字栏
        signature_text = "审核组长签字：________________    日期：________________"
        story.append(Paragraph(signature_text, styles['Right']))

    @staticmethod
    def _conclusion_text(data: Dict[str, Any]) -> str:
        """Only render a certification opinion explicitly confirmed in a report.

        Counts of findings are not a certification decision.  An unfinished NC
        always takes precedence over a previously selected recommendation.
        """
        nonconformities = data.get('nonconformities') or []
        open_ncs = [
            item for item in nonconformities
            if getattr(item, 'severity', None) != 'observation'
            and getattr(item, 'status', None) not in {'verified', 'closed', 'rejected'}
        ]
        if open_ncs:
            return (
                f"本项目仍有 {len(open_ncs)} 条不符合项未完成整改验证和关闭，"
                "当前不得形成推荐认证结论。"
            )

        report = data.get('report')
        conclusion_code = getattr(report, 'conclusion', None) if report else None
        conclusion_map = {
            'recommend': '经审核组长确认，建议推荐认证。',
            'conditional': '经审核组长确认，整改验证完成后可有条件推荐认证。',
            'not_recommend': '经审核组长确认，本次不建议推荐认证。',
        }
        conclusion = conclusion_map.get(
            conclusion_code,
            '审核结论尚未由审核组长确认。本文件为审核记录汇总草稿，不构成认证推荐意见。',
        )
        notes = str(getattr(report, 'conclusion_notes', '') or '').strip() if report else ''
        return f"{conclusion}\n结论说明：{notes}" if notes else conclusion


async def generate_audit_report_word(db: AsyncSession, project_id: UUID) -> BytesIO:
    """生成 Word 格式审核报告"""
    generator = AuditReportGenerator(db)
    return await generator.generate_word_report(project_id)


async def generate_audit_report_pdf(db: AsyncSession, project_id: UUID) -> BytesIO:
    """生成 PDF 格式审核报告"""
    generator = AuditReportGenerator(db)
    return await generator.generate_pdf_report(project_id)
