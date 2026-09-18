import os
import io
import logging
from datetime import datetime, timedelta, timezone
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
from app.utils.item_stats import calculate_item_stats, classify_result, compliance_rate
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
        """生成报告编号：EFIS-{检查日期}-{记录 ID 前 8 位}。

        日期段必须取「检查日期」而非「当前日期」：原实现用 datetime.now()，
        同一份记录在不同日期打开会得到不同编号（今天 EFIS-2026-0915-XXXX，
        明天变成 EFIS-2026-0916-XXXX），报告编号失去唯一标识意义。
        """
        source = getattr(record, "inspection_date", None) or datetime.now()
        if source.tzinfo is not None:
            # 库内是 UTC，转成东八区再取日期，与界面展示的「检查日期」保持一致
            source = source.astimezone(timezone(timedelta(hours=8)))
        date_str = source.strftime('%Y-%m%d')
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
        - 兼容扁平结构（数据库模板快照中的扁平 items，无 children 嵌套但带 parent_id）。
        """
        # 检查是否全部无嵌套 children 且非空
        has_nested_children = any(
            bool(it.get('children') if isinstance(it, dict) else getattr(it, 'children', None))
            for it in items
        )
        if not has_nested_children and items:
            items_by_id = {}
            parent_ids = set()
            for it in items:
                it_id = str(it.get('id', '') if isinstance(it, dict) else (getattr(it, 'id', '') or ''))
                it_pid = str(it.get('parent_id', '') if isinstance(it, dict) else (getattr(it, 'parent_id', '') or ''))
                if it_id:
                    items_by_id[it_id] = it
                if it_pid:
                    parent_ids.add(it_pid)

            result = []
            for it in items:
                is_cat = bool(it.get('is_category', False) if isinstance(it, dict) else getattr(it, 'is_category', False))
                it_id = str(it.get('id', '') if isinstance(it, dict) else (getattr(it, 'id', '') or ''))
                if is_cat or (it_id and it_id in parent_ids):
                    continue

                item_dict = it if isinstance(it, dict) else {
                    'id': str(getattr(it, 'id', '')),
                    'parent_id': str(getattr(it, 'parent_id', '')) if getattr(it, 'parent_id', None) else None,
                    'title': getattr(it, 'title', '') or '',
                    'description': getattr(it, 'description', None),
                    'check_method': getattr(it, 'check_method', None),
                    'legal_basis': getattr(it, 'legal_basis', None),
                    'standard_ref': getattr(it, 'standard_ref', None),
                    'check_type': getattr(it, 'check_type', None),
                    'result_type': getattr(it, 'result_type', None),
                    'result_options': getattr(it, 'result_options', None),
                    'risk_level': getattr(it, 'risk_level', 'medium'),
                    'is_category': False,
                    'sort_order': getattr(it, 'sort_order', 0),
                    'unit': getattr(it, 'unit', None),
                    'radio_value': getattr(it, 'radio_value', None),
                    'score_value': getattr(it, 'score_value', None),
                    'numeric_value': getattr(it, 'numeric_value', None),
                    'text_value': getattr(it, 'text_value', None),
                    'multi_value': getattr(it, 'multi_value', None),
                    'problem_description': getattr(it, 'problem_description', None),
                    'rectification_suggestion': getattr(it, 'rectification_suggestion', None),
                }

                cat_name = ''
                cur_pid = str(item_dict.get('parent_id') or '')
                while cur_pid and cur_pid in items_by_id:
                    parent = items_by_id[cur_pid]
                    p_title = parent.get('title', '') if isinstance(parent, dict) else getattr(parent, 'title', '')
                    if p_title:
                        cat_name = p_title
                        break
                    cur_pid = str(parent.get('parent_id', '') if isinstance(parent, dict) else (getattr(parent, 'parent_id', '') or ''))

                item_copy = dict(item_dict)
                item_copy['category_name'] = cat_name
                result.append(item_copy)
            return result

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
                    'unit': getattr(item, 'unit', None),
                    'radio_value': getattr(item, 'radio_value', None),
                    'score_value': getattr(item, 'score_value', None),
                    'numeric_value': getattr(item, 'numeric_value', None),
                    'text_value': getattr(item, 'text_value', None),
                    'multi_value': getattr(item, 'multi_value', None),
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

    def _get_merged_items(self, record: InspectionRecord) -> List[Dict[str, Any]]:
        """获取并合并检查记录中的所有叶子项数据。"""
        template_items = []
        if record.template_snapshot and 'items' in record.template_snapshot:
            template_items = record.template_snapshot['items']
        elif record.template:
            template_items = record.template.items if hasattr(record.template, 'items') else []
        all_items = self._flatten_items(template_items)

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
                    # 审核记录（检查项级），录入页写入的就是 inspector_note；
                    # 此处原先漏merge，导致报告与详情都看不到用户填写的审核记录。
                    'inspector_note': getattr(ri, 'inspector_note', None),
                    'photos': getattr(ri, 'photos', None) or [],
                }

        for item in all_items:
            item_id = str(item.get('id', '') or '')
            if item_id and item_id in record_items_map:
                ri_data = record_items_map[item_id]
                effective_result = ri_data.get('radio_value') or ri_data.get('result')
                if effective_result:
                    item['radio_value'] = effective_result
                if ri_data.get('problem_description'):
                    item['problem_description'] = ri_data['problem_description']
                if ri_data.get('rectification_suggestion'):
                    item['rectification_suggestion'] = ri_data['rectification_suggestion']
                if ri_data.get('result_text'):
                    item['result_text'] = ri_data['result_text']
                if ri_data.get('score_value') is not None:
                    item['score_value'] = ri_data['score_value']
                if ri_data.get('numeric_value') is not None:
                    item['numeric_value'] = ri_data['numeric_value']
                if ri_data.get('text_value') is not None:
                    item['text_value'] = ri_data['text_value']
                if ri_data.get('multi_value') is not None:
                    item['multi_value'] = ri_data['multi_value']
                if ri_data.get('audit_evidence'):
                    item['audit_evidence'] = ri_data['audit_evidence']
                if ri_data.get('audit_findings'):
                    item['audit_findings'] = ri_data['audit_findings']
                if ri_data.get('inspector_note'):
                    item['inspector_note'] = ri_data['inspector_note']
                if ri_data.get('photos'):
                    item['photos'] = ri_data['photos']
        return all_items

    def _build_cover_page(self, record: InspectionRecord, report_number: str) -> List:
        elements = []
        elements.append(Spacer(1, 60*mm))
        elements.append(Paragraph("现场检查报告", self.styles['CoverTitle']))
        elements.append(Spacer(1, 20*mm))
        cover_data = [
            ['报告编号', report_number],
            ['企业名称', record.enterprise_name or (record.enterprise.name if record.enterprise else '-')],
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

    def _build_overview_section(self, record: InspectionRecord, all_items: List) -> List:
        elements = []
        elements.append(Paragraph("一、检查概况", self.styles['SectionTitle']))
        _stats = calculate_item_stats(all_items)
        pass_count = _stats['pass']
        fail_count = _stats['fail']
        na_count = _stats['na']
        observe_count = _stats.get('observe', 0)
        total = _stats['total']
        filled_count = _stats['filled']
        pass_rate = compliance_rate(_stats)
        overview_text = f"""
        本次检查共 {total} 项，其中已填报 {filled_count} 项，未填写 {total - filled_count} 项，合格率 {pass_rate}%。结果如下：
        合格项：{pass_count} 项
        不合格项：{fail_count} 项
        不适用项：{na_count} 项
        观察项：{observe_count} 项
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
            ['联系人', record.contact_person or (enterprise.contact_person if enterprise else None) or '-'],
            ['联系电话', record.contact_phone or (enterprise.contact_phone if enterprise else None) or '-'],
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

    def _build_results_section(self, record: InspectionRecord, all_items: List) -> List:
        elements = []
        elements.append(Paragraph("三、检查内容及结果", self.styles['SectionTitle']))
        table_data = [['序号', '检查项目', '检查结果', '备注']]
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

            res_type = item.get('result_type')
            if res_type == 'text' or item.get('text_value'):
                result = str(item.get('text_value') or '-')[:15]
            elif res_type == 'numeric' or item.get('numeric_value') is not None:
                val = item.get('numeric_value')
                unit = item.get('unit') or ''
                result = f"{val}{unit}" if val is not None else '-'
            elif res_type == 'score' or item.get('score_value') is not None:
                result = f"{item.get('score_value')}分" if item.get('score_value') is not None else '-'
            else:
                result = self._get_radio_text(item.get('radio_value'))

            note = item.get('problem_description', '')[:30] if classify_result(item.get('radio_value')) == 'fail' else ''
            table_data.append([
                str(item_index),
                item.get('title', '-')[:25],
                result,
                note[:20] if note else '-',
            ])
            if classify_result(item.get('radio_value')) == 'fail':
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

    def _build_fail_items_section(self, all_items: List) -> List:
        elements = []
        fail_items = [item for item in all_items if classify_result(item.get('radio_value')) == 'fail']
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

    def _build_rectification_section(self, record: InspectionRecord, all_items: List) -> List:
        elements = []
        fail_items = [item for item in all_items if classify_result(item.get('radio_value')) == 'fail']
        elements.append(Paragraph("五、整改建议", self.styles['SectionTitle']))
        has_items_with_suggestion = False
        if fail_items:
            for idx, item in enumerate(fail_items, 1):
                if item.get('rectification_suggestion'):
                    has_items_with_suggestion = True
                    elements.append(Paragraph(
                        f"{idx}. {item.get('title', '')}：{item.get('rectification_suggestion', '')}",
                        self.styles['CustomBodyText']
                    ))
            if not has_items_with_suggestion:
                elements.append(Paragraph("请针对上述不符合项制定具体整改措施并按期完成整改复查。", self.styles['CustomBodyText']))
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
        ]
        if record.judgment_note:
            conclusion_data.append(['判定说明', record.judgment_note])
        if record.remarks:
            conclusion_data.append(['检查备注', record.remarks])
        conclusion_data.extend([
            ['检查日期', record.inspection_date.strftime('%Y年%m月%d日') if record.inspection_date else '-'],
            ['检查员', record.inspector.full_name or record.inspector.username if record.inspector else '-'],
            ['签名', ''],
        ])
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
        all_items = self._get_merged_items(record)
        report_number = self._generate_report_number(record)
        elements = []
        elements.extend(self._build_cover_page(record, report_number))
        elements.extend(self._build_toc())
        elements.extend(self._build_overview_section(record, all_items))
        elements.extend(self._build_enterprise_section(record))
        elements.extend(self._build_results_section(record, all_items))
        elements.extend(self._build_fail_items_section(all_items))
        elements.extend(self._build_rectification_section(record, all_items))
        elements.extend(self._build_conclusion_section(record))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def generate_report_data(self, record: InspectionRecord) -> Dict[str, Any]:
        all_items = self._get_merged_items(record)

        # 统计一律走 app.utils.item_stats（唯一口径来源）
        _stats = calculate_item_stats(all_items)
        pass_count = _stats['pass']
        fail_count = _stats['fail']
        na_count = _stats['na']
        observe_count = _stats.get('observe', 0)
        total = _stats['total']
        filled_count = _stats['filled']
        pass_rate = compliance_rate(_stats)
        fail_items = [item for item in all_items if classify_result(item.get('radio_value')) == 'fail']
        return {
            'report_number': self._generate_report_number(record),
            'generated_at': datetime.now().isoformat(),
            'enterprise': {
                'name': record.enterprise_name or (record.enterprise.name if record.enterprise else '-'),
                'address': record.enterprise_address or (record.enterprise.address if record.enterprise else '-'),
                'contact_person': record.contact_person or (
                    record.enterprise.contact_person if record.enterprise else None
                ) or '-',
                'contact_phone': record.contact_phone or (
                    record.enterprise.contact_phone if record.enterprise else None
                ) or '-',
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
                'judgment_note': record.judgment_note,
            },
            'statistics': {
                'total': total,
                'pass': pass_count,
                'fail': fail_count,
                'na': na_count,
                # 观察项（中间态）：前端汇总表必须单独列一行，
                # 否则「合格+不合格+不适用」小于 total，客户当场就能看出对不上账。
                'observe': observe_count,
                'filled': filled_count,
                'unfilled': total - filled_count,
                'pass_rate': pass_rate,
            },
            'items': all_items,
            'fail_items': fail_items,
        }


report_service = ReportService()

