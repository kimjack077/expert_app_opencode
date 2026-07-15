"""
审核报告生成服务
Audit Report Generator Service
"""
from datetime import datetime
from io import BytesIO
from typing import List, Dict, Any
from uuid import UUID

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
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
        
        # 创建 PDF 文档
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # 构建内容
        story = []
        styles = getSampleStyleSheet()
        
        # 添加标题
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=1  # 居中
        )
        story.append(Paragraph('审核报告', title_style))
        story.append(Spacer(1, 0.3 * inch))
        
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
        
        stats = data['statistics']
        project = data['project']
        
        # 3.1 综合评价
        doc.add_heading('3.1 综合评价', 2)
        p = doc.add_paragraph()
        
        if stats['major_nc'] == 0 and stats['minor_nc'] <= 3:
            conclusion = "经审核，受审核方的管理体系运行有效，符合认证要求，建议推荐认证。"
        elif stats['major_nc'] > 0:
            conclusion = "经审核，受审核方存在严重不符合项，需要整改后重新审核。"
        else:
            conclusion = "经审核，受审核方存在一般不符合项，需要整改验证后方可推荐认证。"
        
        p.add_run(conclusion)
        
        # 3.2 审核组长签字
        doc.add_paragraph()
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.add_run('审核组长签字：________________    日期：________________')
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    def _add_pdf_chapter_1(self, story: List, styles: Any, data: Dict[str, Any]):
        """添加 PDF 第一章"""
        story.append(Paragraph('一、审核过程综述', styles['Heading1']))
        story.append(Spacer(1, 0.2 * inch))
        
        project = data['project']
        enterprise = data['enterprise']
        
        # 基本信息
        story.append(Paragraph('1.1 受审核方基本信息', styles['Heading2']))
        info_text = f"""
        企业名称：{enterprise.name if enterprise else '未知'}<br/>
        统一社会信用代码：{enterprise.credit_code if enterprise else '未知'}<br/>
        地址：{enterprise.address if enterprise else '未知'}
        """
        story.append(Paragraph(info_text, styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

    def _add_pdf_chapter_2(self, story: List, styles: Any, data: Dict[str, Any]):
        """添加 PDF 第二章"""
        story.append(PageBreak())
        story.append(Paragraph('二、管理体系综合评价', styles['Heading1']))
        story.append(Spacer(1, 0.2 * inch))
        
        stats = data['statistics']
        
        # 统计表格
        table_data = [
            ['严重不符合', '一般不符合', '观察项', '合计'],
            [
                str(stats['major_nc']),
                str(stats['minor_nc']),
                str(stats['observations']),
                str(stats['major_nc'] + stats['minor_nc'] + stats['observations'])
            ]
        ]
        
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

    def _add_pdf_chapter_3(self, story: List, styles: Any, data: Dict[str, Any]):
        """添加 PDF 第三章"""
        story.append(PageBreak())
        story.append(Paragraph('三、审核结论', styles['Heading1']))
        story.append(Spacer(1, 0.2 * inch))
        
        stats = data['statistics']
        
        if stats['major_nc'] == 0 and stats['minor_nc'] <= 3:
            conclusion = "经审核，受审核方的管理体系运行有效，符合认证要求，建议推荐认证。"
        elif stats['major_nc'] > 0:
            conclusion = "经审核，受审核方存在严重不符合项，需要整改后重新审核。"
        else:
            conclusion = "经审核，受审核方存在一般不符合项，需要整改验证后方可推荐认证。"
        
        story.append(Paragraph(conclusion, styles['Normal']))
        story.append(Spacer(1, 0.5 * inch))
        
        # 签字栏
        signature_text = "审核组长签字：________________    日期：________________"
        story.append(Paragraph(signature_text, styles['Normal']))


async def generate_audit_report_word(db: AsyncSession, project_id: UUID) -> BytesIO:
    """生成 Word 格式审核报告"""
    generator = AuditReportGenerator(db)
    return await generator.generate_word_report(project_id)


async def generate_audit_report_pdf(db: AsyncSession, project_id: UUID) -> BytesIO:
    """生成 PDF 格式审核报告"""
    generator = AuditReportGenerator(db)
    return await generator.generate_pdf_report(project_id)
