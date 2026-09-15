import os
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.template import InspectionTemplate, TemplateItem
from app.models.enterprise import Enterprise
from app.models.user import User


logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self):
        self._init_fonts()
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _init_fonts(self):
        """注册中文字体。

        排查提示：线上「报告 PDF 中文变方块」的根因就是这里找不到中文字体，
        静默回退到 reportlab 内置 Helvetica（没有中文字形）。
        因此候选顺序把「仓库自带字体」放在第一位，随部署一起走，不依赖服务器环境；
        并且加载失败时打 error 日志而不是 warning，避免再次被当成「报告乱码」查不出来。
        """
        repo_fonts = Path(__file__).resolve().parents[2] / "assets" / "fonts"
        candidates = [
            # 仓库自带（推荐：把字体文件提交进 backend/assets/fonts/）
            repo_fonts / "NotoSansSC-Regular.ttf",
            repo_fonts / "SourceHanSansSC-Regular.otf",
            # Windows 开发机
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            # Linux 服务器
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            # macOS
            Path("/System/Library/Fonts/PingFang.ttc"),
        ]
        self.font_name = "Helvetica"
        self.font_name_cn = "Helvetica"
        self.cjk_font_ready = False
        for path in candidates:
            if not path.exists():
                continue
            try:
                # .ttc 是字体集合，必须指定子字体索引，否则 TTFont 会直接抛错
                pdfmetrics.registerFont(
                    TTFont("ChineseFont", str(path), subfontIndex=0)
                )
                self.font_name = "ChineseFont"
                self.font_name_cn = "ChineseFont"
                self.cjk_font_ready = True
                logger.info("报告 PDF 使用中文字体：%s", path)
                break
            except Exception as exc:
                logger.warning("注册中文字体失败，继续尝试下一个：%s (%s)", path, exc)

        if not self.cjk_font_ready:
            logger.error(
                "未找到任何可用中文字体，报告 PDF 中文将显示为方块。"
                "请把中文字体放到 %s，或在服务器安装 fonts-noto-cjk / fonts-wqy-microhei。",
                repo_fonts,
            )

    def _setup_styles(self):
        self.styles.add(ParagraphStyle(
            name='CoverTitle',
            fontName=self.font_name,
            fontSize=24,
            leading=32,
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        self.styles.add(ParagraphStyle(
            name='CoverSubtitle',
            fontName=self.font_name,
            fontSize=14,
            leading=20,
            alignment=TA_CENTER,
            textColor=colors.grey,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            fontName=self.font_name,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor('#1e40af'),
            spaceBefore=15,
            spaceAfter=10,
            leftIndent=0,
        ))
        self.styles.add(ParagraphStyle(
            name='CustomBodyText',
            fontName=self.font_name,
            fontSize=10,
            leading=16,
            alignment=TA_JUSTIFY,
        ))
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            fontName=self.font_name,
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='TableCell',
            fontName=self.font_name,
            fontSize=9,
            leading=13,
        ))
        self.styles.add(ParagraphStyle(
            name='FailItem',
            fontName=self.font_name,
            fontSize=10,
            leading=16,
            textColor=colors.HexColor('#dc2626'),
        ))

    def _generate_report_number(self, record: InspectionRecord) -> str:
        date_str = datetime.now().strftime('%Y-%m%d')
        short_id = str(record.id)[:8].upper()
        return f"EFIS-{date_str}-{short_id}"

    def _get_result_text(self, result: Optional[str]) -> str:
        result_map = {
            'pass': '合格',
            'partial_pass': '基本合格',
            'fail': '不合格',
        }
        return result_map.get(result, '待判定')

    def _get_result_color(self, result: Optional[str]) -> colors.Color:
        color_map = {
            'pass': colors.HexColor('#22c55e'),
            'partial_pass': colors.HexColor('#f59e0b'),
            'fail': colors.HexColor('#ef4444'),
        }
        return color_map.get(result, colors.grey)

    def _get_radio_text(self, value: Optional[str]) -> str:
        if not value:
            return '-'
        radio_map = {
            'pass': '合格',
            'fail': '不合格',
            'na': '不适用',
        }
        return radio_map.get(value, value)

    def _flatten_items(self, items: List[Any], current_category: str = '') -> List[Any]:
        """递归扁平化模板树，只保留叶子检查项，并注入所属分类名。

        - 只要有子节点即一律按分类目录处理（与接口层 / 前端口径保持一致），
          避免历史脏快照里的根节点被当成检查项列进报告；
        - 为每个叶子项注入 `category_name`（最近一级分类目录标题），
          供 PDF 表格分组、/report 接口输出与第三方集成使用（BUG-29）。
        """
        result = []
        for item in items:
            # 兼容字典和 SQLAlchemy 对象
            if isinstance(item, dict):
                is_category = item.get('is_category', False)
                children = item.get('children')
            else:
                is_category = getattr(item, 'is_category', False)
                children = getattr(item, 'children', None)
                # 将 SQLAlchemy 对象转换为字典
                item = {
                    'id': str(getattr(item, 'id', '')),
                    'parent_id': str(getattr(item, 'parent_id', '')) if getattr(item, 'parent_id', None) else None,
                    'title': getattr(item, 'title', '') or '',
                    'description': getattr(item, 'description', None),
                    'check_method': getattr(item, 'check_method', None),
                    'legal_basis': getattr(item, 'legal_basis', None),
                    'standard_ref': getattr(item, 'standard_ref', None),
                    'check_type': getattr(item, 'check_type', None),
                    'result_type': getattr(item, 'result_type', None),
                    'result_options': getattr(item, 'result_options', None),
                    'risk_level': getattr(item, 'risk_level', 'medium'),
                    'is_category': is_category,
                    'sort_order': getattr(item, 'sort_order', 0),
                    'radio_value': getattr(item, 'radio_value', None),
                    'problem_description': getattr(item, 'problem_description', None),
                    'rectification_suggestion': getattr(item, 'rectification_suggestion', None),
                }
            if children:
                is_category = True

            title = item.get('title', '') or ''
            if not is_category:
                item['category_name'] = current_category
                result.append(item)
            if children:
                result.extend(self._flatten_items(children, title or current_category))
        return result

    def _build_cover_page(self, record: InspectionRecord, report_number: str) -> List:
        elements = []
        elements.append(Spacer(1, 60*mm))
        elements.append(Paragraph("现场检查报告", self.styles['CoverTitle']))
        elements.append(Spacer(1, 20*mm))
        cover_data = [
            ['报告编号', report_number],
            ['企业名称', record.enterprise_name or record.enterprise.name if record.enterprise else '-'],
            ['检查日期', record.inspection_date.strftime('%Y年%m月%d日') if record.inspection_date else '-'],
            ['检查员', record.inspector.full_name or record.inspector.username if record.inspector else '-'],
            ['检查类型', '定期检查'],
            ['总体结论', self._get_result_text(record.overall_result)],
        ]
        cover_table = Table(cover_data, colWidths=[40*mm, 80*mm])
        cover_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(cover_table)
        elements.append(PageBreak())
        return elements

    def _build_toc(self) -> List:
        elements = []
        elements.append(Paragraph("目 录", self.styles['CoverTitle']))
        elements.append(Spacer(1, 10*mm))
        toc_items = [
            "一、检查概况",
            "二、企业基本情况",
            "三、检查内容及结果",
            "四、不符合项描述",
            "五、整改建议",
            "六、总体判定",
        ]
        for item in toc_items:
            elements.append(Paragraph(item, self.styles['CustomBodyText']))
            elements.append(Spacer(1, 3*mm))
        elements.append(PageBreak())
        return elements

    def _build_overview_section(self, record: InspectionRecord, template_items: List) -> List:
        elements = []
        elements.append(Paragraph("一、检查概况", self.styles['SectionTitle']))
        all_items = self._flatten_items(template_items)
        pass_count = sum(1 for item in all_items if item.get('radio_value') == 'pass')
        fail_count = sum(1 for item in all_items if item.get('radio_value') == 'fail')
        na_count = sum(1 for item in all_items if item.get('radio_value') in ('na', 'not_applicable'))
        total = len(all_items)
        filled_count = pass_count + fail_count + na_count
        # BUG-04：与报告数据口径一致——占比分母为「已填报项」（排除不适用与未填写）
        rated_count = pass_count + fail_count
        pass_rate = round(pass_count / rated_count * 100, 1) if rated_count > 0 else 0
        fail_rate = round(fail_count / rated_count * 100, 1) if rated_count > 0 else 0
        overview_text = f"""
        本次检查共 {total} 项，其中已填报 {filled_count} 项，未填写 {total - filled_count} 项，结果如下：
        合格项：{pass_count} 项（占已填报 {pass_rate}%）
        不合格项：{fail_count} 项（占已填报 {fail_rate}%）
        不适用项：{na_count} 项
        """
        elements.append(Paragraph(overview_text.replace('\n', '<br/>'), self.styles['CustomBodyText']))
        if record.total_score is not None:
            elements.append(Paragraph(f"得分：{float(record.total_score)} 分", self.styles['CustomBodyText']))
        elements.append(Spacer(1, 5*mm))
        return elements

    def _build_enterprise_section(self, record: InspectionRecord) -> List:
        elements = []
        elements.append(Paragraph("二、企业基本情况", self.styles['SectionTitle']))
        enterprise = record.enterprise
        enterprise_data = [
            ['企业名称', record.enterprise_name or (enterprise.name if enterprise else '-')],
            ['企业地址', record.enterprise_address or (enterprise.address if enterprise else '-')],
            ['联系人', record.contact_person or '-'],
            ['联系电话', record.contact_phone or '-'],
        ]
        if enterprise:
            enterprise_data.extend([
                ['统一社会信用代码', enterprise.credit_code or '-'],
                ['法定代表人', enterprise.legal_person or '-'],
                ['风险等级', enterprise.risk_level or '-'],
            ])
        table = Table(enterprise_data, colWidths=[40*mm, 100*mm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f4ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 5*mm))
        return elements

    def _build_results_section(self, record: InspectionRecord, template_items: List) -> List:
        elements = []
        elements.append(Paragraph("三、检查内容及结果", self.styles['SectionTitle']))
        all_items = self._flatten_items(template_items)
        table_data = [['序号', '检查项目', '检查结果', '备注']]
        # BUG-29：按分类目录分组展示（与 Web 端报告预览一致），分类行合并 4 列
        category_rows: List[int] = []
        fail_rows: List[int] = []
        last_category = None
        item_index = 0
        for item in all_items:
            category = item.get('category_name') or ''
            if category and category != last_category:
                category_rows.append(len(table_data))
                table_data.append([f"📂 分类：{category}", '', '', ''])
                last_category = category
            item_index += 1
            row_idx = len(table_data)
            result = self._get_radio_text(item.get('radio_value'))
            note = item.get('problem_description', '')[:30] if item.get('radio_value') == 'fail' else ''
            table_data.append([
                str(item_index),
                item.get('title', '-')[:25],
                result,
                note[:20] if note else '-',
            ])
            if item.get('radio_value') == 'fail':
                fail_rows.append(row_idx)

        col_widths = [12*mm, 60*mm, 25*mm, 43*mm]
        table = Table(table_data, colWidths=col_widths)
        style_cmds = [
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]
        for row in category_rows:
            style_cmds.extend([
                ('SPAN', (0, row), (-1, row)),
                ('BACKGROUND', (0, row), (-1, row), colors.HexColor('#eff6ff')),
                ('TEXTCOLOR', (0, row), (-1, row), colors.HexColor('#1d4ed8')),
                ('ALIGN', (0, row), (-1, row), 'LEFT'),
            ])
        for row in fail_rows:
            style_cmds.extend([
                ('TEXTCOLOR', (2, row), (2, row), colors.HexColor('#dc2626')),
                ('BACKGROUND', (0, row), (-1, row), colors.HexColor('#fef2f2')),
            ])
        table.setStyle(TableStyle(style_cmds))
        elements.append(table)
        elements.append(Spacer(1, 5*mm))
        return elements

    def _build_fail_items_section(self, template_items: List) -> List:
        elements = []
        all_items = self._flatten_items(template_items)
        fail_items = [item for item in all_items if item.get('radio_value') == 'fail']
        elements.append(Paragraph("四、不符合项描述", self.styles['SectionTitle']))
        if not fail_items:
            elements.append(Paragraph("本次检查未发现不符合项。", self.styles['CustomBodyText']))
        else:
            for idx, item in enumerate(fail_items, 1):
                fail_data = [
                    [f"{idx}. {item.get('title', '未知检查项')}"],
                ]
                if item.get('description'):
                    fail_data.append([f"检查内容：{item.get('description', '')}"])
                if item.get('problem_description'):
                    fail_data.append([f"问题描述：{item.get('problem_description', '')}"])
                fail_table = Table(fail_data, colWidths=[140*mm])
                fail_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#dc2626')),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef2f2')),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#fca5a5')),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(fail_table)
                elements.append(Spacer(1, 3*mm))
        elements.append(Spacer(1, 5*mm))
        return elements

    def _build_rectification_section(self, record: InspectionRecord, template_items: List) -> List:
        elements = []
        all_items = self._flatten_items(template_items)
        fail_items = [item for item in all_items if item.get('radio_value') == 'fail']
        elements.append(Paragraph("五、整改建议", self.styles['SectionTitle']))
        if record.remarks:
            elements.append(Paragraph(record.remarks, self.styles['CustomBodyText']))
        elif fail_items:
            for idx, item in enumerate(fail_items, 1):
                if item.get('rectification_suggestion'):
                    elements.append(Paragraph(
                        f"{idx}. {item.get('title', '')}：{item.get('rectification_suggestion', '')}",
                        self.styles['CustomBodyText']
                    ))
        else:
            elements.append(Paragraph("本次检查未发现需要整改的问题。", self.styles['CustomBodyText']))
        elements.append(Spacer(1, 5*mm))
        return elements

    def _build_conclusion_section(self, record: InspectionRecord) -> List:
        elements = []
        elements.append(Paragraph("六、总体判定", self.styles['SectionTitle']))
        result_text = self._get_result_text(record.overall_result)
        result_color = self._get_result_color(record.overall_result)
        conclusion_data = [
            ['总体结论', result_text],
            ['检查日期', record.inspection_date.strftime('%Y年%m月%d日') if record.inspection_date else '-'],
            ['检查员', record.inspector.full_name or record.inspector.username if record.inspector else '-'],
            ['签名', ''],
        ]
        conclusion_table = Table(conclusion_data, colWidths=[40*mm, 100*mm])
        conclusion_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f4ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (1, 0), (1, 0), result_color),
        ]))
        elements.append(conclusion_table)
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph(
            f"本报告由 EFIS 系统自动生成  ·  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ParagraphStyle(
                name='Footer',
                fontName=self.font_name,
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
            )
        ))
        return elements

    def generate_pdf(self, record: InspectionRecord) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20*mm,
            rightMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm,
        )
        template_items = []
        if record.template_snapshot and 'items' in record.template_snapshot:
            template_items = record.template_snapshot['items']
        elif record.template:
            template_items = record.template.items if hasattr(record.template, 'items') else []
        report_number = self._generate_report_number(record)
        elements = []
        elements.extend(self._build_cover_page(record, report_number))
        elements.extend(self._build_toc())
        elements.extend(self._build_overview_section(record, template_items))
        elements.extend(self._build_enterprise_section(record))
        elements.extend(self._build_results_section(record, template_items))
        elements.extend(self._build_fail_items_section(template_items))
        elements.extend(self._build_rectification_section(record, template_items))
        elements.extend(self._build_conclusion_section(record))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def generate_report_data(self, record: InspectionRecord) -> Dict[str, Any]:
        template_items = []
        if record.template_snapshot and 'items' in record.template_snapshot:
            template_items = record.template_snapshot['items']
        elif record.template:
            template_items = record.template.items if hasattr(record.template, 'items') else []
        all_items = self._flatten_items(template_items)

        # 合并检查记录项的实际结果（InspectionRecordItem）
        # record.items 包含用户填写的实际检查结果（radio_value 等）
        record_items_map = {}
        record_items = getattr(record, 'items', None) or []
        for ri in record_items:
            tid = str(getattr(ri, 'template_item_id', '') or '')
            if tid:
                record_items_map[tid] = {
                    'radio_value': getattr(ri, 'radio_value', None),
                    'result': getattr(ri, 'result', None),
                    'result_text': getattr(ri, 'result_text', None),
                    'problem_description': getattr(ri, 'problem_description', None),
                    'rectification_suggestion': getattr(ri, 'rectification_suggestion', None),
                    'score_value': getattr(ri, 'score_value', None),
                    'numeric_value': getattr(ri, 'numeric_value', None),
                    'text_value': getattr(ri, 'text_value', None),
                    'multi_value': getattr(ri, 'multi_value', None),
                    'audit_evidence': getattr(ri, 'audit_evidence', None),
                    'audit_findings': getattr(ri, 'audit_findings', None),
                }

        # 将实际检查结果合并到模板项中
        for item in all_items:
            item_id = str(item.get('id', '') or '')
            if item_id and item_id in record_items_map:
                ri_data = record_items_map[item_id]
                # BUG-03：result 与 radio_value 字段归一——写入侧可能只填了 result，
                # 报告侧必须同等对待，否则统计与 PDF 全部丢失判定。
                effective_result = ri_data.get('radio_value') or ri_data.get('result')
                if effective_result:
                    item['radio_value'] = effective_result
                if ri_data.get('problem_description'):
                    item['problem_description'] = ri_data['problem_description']
                if ri_data.get('rectification_suggestion'):
                    item['rectification_suggestion'] = ri_data['rectification_suggestion']
                if ri_data.get('result_text'):
                    item['result_text'] = ri_data['result_text']
                if ri_data.get('audit_evidence'):
                    item['audit_evidence'] = ri_data['audit_evidence']
                if ri_data.get('audit_findings'):
                    item['audit_findings'] = ri_data['audit_findings']

        pass_count = sum(1 for item in all_items if item.get('radio_value') == 'pass')
        fail_count = sum(1 for item in all_items if item.get('radio_value') == 'fail')
        na_count = sum(1 for item in all_items if item.get('radio_value') in ('na', 'not_applicable'))
        total = len(all_items)
        filled_count = pass_count + fail_count + na_count
        # BUG-04：合规率 = 已填报合格项 / 已填报项（分子分母均排除「不适用」与「未填写」），
        # 与工作台 /api/analytics/dashboard 口径保持一致。
        rated_count = pass_count + fail_count
        pass_rate = round(pass_count / rated_count * 100, 1) if rated_count > 0 else 0
        fail_items = [item for item in all_items if item.get('radio_value') == 'fail']
        return {
            'report_number': self._generate_report_number(record),
            'generated_at': datetime.now().isoformat(),
            'enterprise': {
                'name': record.enterprise_name or (record.enterprise.name if record.enterprise else '-'),
                'address': record.enterprise_address or (record.enterprise.address if record.enterprise else '-'),
                'contact_person': record.contact_person or '-',
                'contact_phone': record.contact_phone or '-',
                'credit_code': record.enterprise.credit_code if record.enterprise else '-',
                'legal_person': record.enterprise.legal_person if record.enterprise else '-',
                'risk_level': record.enterprise.risk_level if record.enterprise else '-',
            },
            'inspection': {
                'date': record.inspection_date.isoformat() if record.inspection_date else None,
                'inspector': record.inspector.full_name or record.inspector.username if record.inspector else '-',
                'template_name': record.template.name if record.template else (record.template_snapshot.get('name') if record.template_snapshot else '-'),
                'template_version': record.template.version if record.template else (record.template_snapshot.get('version') if record.template_snapshot else '-'),
                'overall_result': record.overall_result,
                'overall_result_text': self._get_result_text(record.overall_result),
                'total_score': float(record.total_score) if record.total_score else None,
                'remarks': record.remarks,
            },
            'statistics': {
                'total': total,
                'pass': pass_count,
                'fail': fail_count,
                'na': na_count,
                'filled': filled_count,
                'unfilled': total - filled_count,
                'pass_rate': pass_rate,
            },
            'items': all_items,
            'fail_items': fail_items,
        }


report_service = ReportService()

