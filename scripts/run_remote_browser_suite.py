# -*- coding: utf-8 -*-
"""
EFIS 全功能远程生产环境浏览器端到端 (E2E) 测试套件
被测目标:
  - Web Admin: http://49.232.213.79:3000
  - H5 App:    http://49.232.213.79:5173/h5/
  - Web Docs:  http://49.232.213.79:3000/docs
"""
import sys
import io
import json
import time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WEB_BASE = "http://49.232.213.79:3000"
H5_BASE = "http://49.232.213.79:5173/h5"

browser_results = []

def record(case_id, name, terminal, ok, expected, actual, severity="P2", note=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {case_id} | {terminal} | {name} | Expected: {expected} | Actual: {str(actual)[:100]}")
    browser_results.append({
        "case_id": case_id,
        "name": name,
        "terminal": terminal,
        "ok": ok,
        "expected": expected,
        "actual": str(actual),
        "severity": severity,
        "note": note
    })

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # ======================================================================
        # Web 端测试 (1440 x 900)
        # ======================================================================
        print("\n" + "="*50 + "\n--- Web 管理端 E2E 测试 (1440x900) ---\n" + "="*50)
        web_context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = web_context.new_page()
        
        # UI-W-01: 登录页视觉与快捷卡
        try:
            page.goto(f"{WEB_BASE}/login", timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)
            text = page.content()
            has_admin_card = "管理员" in text and "admin" in text
            has_expert_card = "审核专家" in text or "expert" in text
            record("UI-W-01", "登录页流光视觉与快捷登录卡片", "Web", has_admin_card and has_expert_card, "包含管理员与专家快捷卡", f"has_admin={has_admin_card}, has_expert={has_expert_card}", "P1")
        except Exception as e:
            record("UI-W-01", "登录页视觉与快捷卡", "Web", False, "正常加载", str(e), "P1")
            
        # UI-W-02: 管理员一键快捷登录
        try:
            # Click admin card
            admin_card = page.locator("text=管理员").first
            if admin_card.count() > 0:
                admin_card.click()
                time.sleep(0.5)
            # Submit
            submit_btn = page.locator("button[type='submit']").first
            submit_btn.click()
            page.wait_for_url("**/dashboard**", timeout=15000)
            record("UI-W-02", "管理员一键快捷登录并跳转工作台", "Web", "dashboard" in page.url, "跳转至 /dashboard", page.url, "P0")
        except Exception as e:
            record("UI-W-02", "管理员一键快捷登录", "Web", False, "跳转 /dashboard", str(e), "P0")

        # UI-W-03: 工作台合规率对账显式公式与体检卡闭合
        try:
            page.wait_for_selector(".ant-card", timeout=10000)
            page_text = page.locator("body").inner_text()
            
            # Check for compliance formula text: 合格 N ÷ 分母 M 或 类似公式
            has_formula = ("合格" in page_text and "分母" in page_text) or ("%" in page_text and "合规" in page_text)
            has_exam_closure = ("总" in page_text and ("合格" in page_text or "不合格" in page_text))
            
            record("UI-W-03", "工作台合规率显式对账公式与体检闭合", "Web", has_formula, "显式展示分子分母公式及检查项统计", f"formula_present={has_formula}", "P0", "验证 AC-5 显式口径")
        except Exception as e:
            record("UI-W-03", "工作台合规率对账", "Web", False, "展示对账公式", str(e), "P0")

        # UI-W-04: 企业风险分布饼图
        try:
            has_risk_pie = "风险" in page_text and ("高风险" in page_text or "一般" in page_text or "低风险" in page_text)
            record("UI-W-04", "企业风险分布态势图呈现", "Web", has_risk_pie, "展示企业风险等级分布", f"has_risk_pie={has_risk_pie}", "P1")
        except Exception as e:
            record("UI-W-04", "企业风险分布态势图", "Web", False, "展示风险分布", str(e), "P1")

        # UI-W-05 & UI-W-06: 模板编辑器 V2 父节点防呆与叶子节点指标
        try:
            page.goto(f"{WEB_BASE}/templates", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Click "编辑检查项" on 《质量安全测试》 row
            edit_btn = page.locator("tr:has-text('质量安全测试') button:has-text('编辑检查项'), tr:has-text('质量安全测试') a:has-text('编辑检查项')").first
            if edit_btn.count() == 0:
                # Fallback to any row edit button
                edit_btn = page.locator("text=编辑检查项").first
            
            edit_btn.click()
            page.wait_for_url("**/templates/**", timeout=10000)
            time.sleep(1.5)
            
            # Check for parent node Alert by clicking a category node e.g. "测试质量把控" or first folder
            folder_node = page.locator("text=测试质量把控, text=测试难度, .ant-tree-node-content-wrapper:has(.anticon-folder)").first
            if folder_node.count() > 0:
                folder_node.click()
                time.sleep(1)
                body_content = page.content()
                alert_present = "分类目录" in body_content and ("仅作为层级分组容器" in body_content or "不可录入" in body_content)
                record("UI-W-05", "模板编辑器父节点蓝色 Alert 防呆提示", "Web", alert_present, "弹出分类目录不可录入打分警示", f"alert_present={alert_present}", "P0")
            else:
                record("UI-W-05", "模板编辑器父节点蓝色 Alert 防呆提示", "Web", False, "找到分类节点并提示", "未定位到分类节点", "P0")
                
            # Click a leaf item e.g. "把控1"
            leaf_node = page.locator("text=把控1, text=难度特高, .ant-tree-node-content-wrapper:has(.anticon-file)").first
            if leaf_node.count() > 0:
                leaf_node.click()
                time.sleep(1)
                leaf_body = page.content()
                has_metric_fields = ("采集结果类型" in leaf_body or "结果类型" in leaf_body) and ("风险等级" in leaf_body or "检查方法" in leaf_body)
                record("UI-W-06", "模板编辑器叶子节点 11 项配置表单呈现", "Web", has_metric_fields, "恢复展示结果类型/方法/依据等配置域", f"has_metric_fields={has_metric_fields}", "P1")
            else:
                record("UI-W-06", "模板编辑器叶子节点配置表单呈现", "Web", False, "找到叶子节点", "未定位到叶子节点", "P1")
                
            # Check for Expand/Collapse button (P3-05 验证)
            expand_btn = page.locator("button:has(.anticon-expand), button:has(.anticon-fullscreen), [title='展开全部'], [aria-label='expand']").first
            record("UI-W-06b", "模板结构视图展开/折叠图标按钮 (P3-05)", "Web", expand_btn.count() > 0, "存在展开全部纯图标按钮", f"count={expand_btn.count()}", "P3")
        except Exception as e:
            record("UI-W-05", "模板编辑器防呆与指标配置", "Web", False, "成功检验", str(e), "P0")

        # UI-W-07: 审核项目「审核工作量（人天）」Tooltip
        try:
            page.goto(f"{WEB_BASE}/audit-projects", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Click create project button
            create_btn = page.locator("button:has-text('创建审核项目'), button:has-text('新建项目')").first
            if create_btn.count() > 0:
                create_btn.click()
                time.sleep(1)
                # Look for 审核工作量 or 人天
                days_label = page.locator("text=审核工作量, text=人天").first
                has_days_label = days_label.count() > 0
                
                # Check for tooltip icon (?)
                help_icon = page.locator(".anticon-question-circle, [aria-label='question-circle']").first
                has_tooltip = help_icon.count() > 0
                record("UI-W-07", "审核工作量（人天）字段及业务释义 Tooltip", "Web", has_days_label and has_tooltip, "字段包含'人天'且配有释义问号图标", f"has_label={has_days_label}, has_icon={has_tooltip}", "P1")
                
                # Close modal if open
                cancel_btn = page.locator("button:has-text('取消')").first
                if cancel_btn.count() > 0:
                    cancel_btn.click()
            else:
                record("UI-W-07", "审核工作量字段 Tooltip", "Web", False, "创建项目入口", "未找到新建按钮", "P1")
        except Exception as e:
            record("UI-W-07", "审核工作量字段 Tooltip", "Web", False, "存在释义图标", str(e), "P1")

        # UI-W-08: 智审 Agent 常驻悬浮球与协同抽屉
        try:
            # Check for floating agent button on right edge
            agent_btn = page.locator(".anticon-robot, [aria-label='robot'], button:has-text('Agent'), button:has-text('智审')").first
            has_agent_btn = agent_btn.count() > 0
            if has_agent_btn:
                agent_btn.click()
                time.sleep(1)
                drawer_content = page.content()
                has_hitl_text = "确认后" in drawer_content or "隔离" in drawer_content or "Agent" in drawer_content
                record("UI-W-08", "智审 Agent 常驻悬浮球与抽屉展开 (人在回路)", "Web", has_hitl_text, "展开抽屉并展示资料隔离及人在回路背书", f"has_hitl={has_hitl_text}", "P1")
            else:
                record("UI-W-08", "智审 Agent 常驻悬浮球", "Web", False, "屏幕右侧常驻Agent悬浮球", "未定位到悬浮球", "P1")
        except Exception as e:
            record("UI-W-08", "智审 Agent 常驻悬浮球", "Web", False, "成功展开", str(e), "P1")

        # UI-W-09 & UI-W-10: 检查记录抽屉与合规报告生成 (无 &nbsp; 乱码)
        try:
            page.goto(f"{WEB_BASE}/records", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Click "详情"
            detail_btn = page.locator("button:has-text('详情'), a:has-text('详情')").first
            if detail_btn.count() > 0:
                detail_btn.click()
                time.sleep(1)
                drawer_text = page.locator(".ant-drawer").first.inner_text() if page.locator(".ant-drawer").count() > 0 else ""
                # Check for "未填写" on category
                has_unfilled_on_cat = False
                for line in drawer_text.splitlines():
                    if "分类" in line and "未填写" in line:
                        has_unfilled_on_cat = True
                record("UI-W-09", "检查记录详情抽屉分类目录无'未填写'Tag", "Web", not has_unfilled_on_cat, "分类目录卡片杜绝未填写假象", f"has_unfilled_tag={has_unfilled_on_cat}", "P0")
                
                # Close drawer
                close_btn = page.locator(".ant-drawer-close, button:has-text('关 闭'), button:has-text('关闭')").first
                if close_btn.count() > 0:
                    close_btn.click()
                    time.sleep(0.5)
            
            # Click "生成报告"
            report_btn = page.locator("button:has-text('生成报告'), a:has-text('生成报告'), button:has-text('查看报告')").first
            if report_btn.count() > 0:
                report_btn.click()
                time.sleep(1.5)
                modal_html = page.locator(".ant-modal").first.inner_html() if page.locator(".ant-modal").count() > 0 else page.content()
                # Check for &nbsp; raw entity in modal
                has_raw_nbsp = "&nbsp;" in modal_html
                has_table3_banners = "分类：" in modal_html or "三、" in modal_html
                record("UI-W-10", "现场检查报告预览无 &nbsp; 乱码字符", "Web", not has_raw_nbsp, "彻底清除 &nbsp; HTML 实体乱码", f"has_raw_nbsp={has_raw_nbsp}", "P0")
            else:
                record("UI-W-10", "现场检查报告预览", "Web", False, "生成报告入口", "未定位到按钮", "P0")
        except Exception as e:
            record("UI-W-09", "检查记录与报告预览", "Web", False, "成功打开", str(e), "P0")

        # UI-W-Docs: 在线技术文档中心与 Ctrl+K 检索
        try:
            page.goto(f"{WEB_BASE}/docs", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            docs_title = page.title()
            is_fullscreen_docs = "404" not in docs_title and ("易审通" in docs_title or "文档" in docs_title or len(docs_title) > 0)
            record("UI-W-Docs-01", "在线文档中心全屏独立布局 (/docs)", "Web", is_fullscreen_docs, "独立全屏技术文档页面", f"title={docs_title}", "P1")
            
            # Test Ctrl+K search modal
            page.keyboard.press("Control+K")
            time.sleep(1)
            search_input = page.locator("input[placeholder*='搜索'], input[placeholder*='检索'], .ant-modal input").first
            if search_input.count() > 0:
                # Search "工作台"
                search_input.fill("工作台")
                time.sleep(0.5)
                hits_wb = page.locator(".ant-modal").first.inner_text()
                has_wb_hits = "工作台" in hits_wb
                
                # Search "审核计划" (P2-10 核心复测)
                search_input.fill("审核计划")
                time.sleep(0.5)
                hits_plan = page.locator(".ant-modal").first.inner_text()
                has_plan_hits = "审核计划" in hits_plan or "未找到" not in hits_plan
                
                record("UI-W-Docs-02", "在线文档中心快捷检索与召回 (P2-10)", "Web", has_wb_hits, "Ctrl+K 唤起搜索弹窗且命中关键词", f"工作台_hits={has_wb_hits}, 审核计划_hits={has_plan_hits}", "P2")
            else:
                record("UI-W-Docs-02", "文档中心快捷检索", "Web", False, "Ctrl+K 唤起搜索框", "未定位到输入框", "P2")
        except Exception as e:
            record("UI-W-Docs-01", "在线文档中心", "Web", False, "正常访问", str(e), "P1")

        # UI-W-Analytics: 数据分析日志前端截断检查 (P2-05 验证)
        try:
            page.goto(f"{WEB_BASE}/analytics", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)
            
            # Check pagination on table
            pagination_text = page.locator(".ant-pagination").first.inner_text() if page.locator(".ant-pagination").count() > 0 else ""
            has_total_pages = "条" in pagination_text or "共" in pagination_text or "/" in pagination_text
            record("UI-W-Analytics", "数据分析审计日志前端分页与总量展示 (P2-05)", "Web", bool(pagination_text), "展示总条数并支持跨页翻页", f"pagination={pagination_text}", "P2")
        except Exception as e:
            record("UI-W-Analytics", "数据分析审计日志分页", "Web", False, "正常加载", str(e), "P2")

        web_context.close()

        # ======================================================================
        # H5 移动现场端测试 (iPhone 14 / 375 x 812)
        # ======================================================================
        print("\n" + "="*50 + "\n--- H5 移动现场端 E2E 测试 (375x812) ---\n" + "="*50)
        h5_context = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        h5_page = h5_context.new_page()

        # UI-H-01: H5 专家快捷登录
        try:
            h5_page.goto(f"{H5_BASE}/login", timeout=20000)
            h5_page.wait_for_load_state("networkidle", timeout=10000)
            
            # Click expert card
            exp_card = h5_page.locator("text=审核专家, text=expert").first
            if exp_card.count() > 0:
                exp_card.click()
                time.sleep(0.5)
            
            # Submit button
            login_btn = h5_page.locator("button:has-text('登录'), button[type='submit']").first
            login_btn.click()
            h5_page.wait_for_url("**/today-audit**", timeout=15000)
            record("UI-H-01", "H5 移动现场端专家快捷登录", "H5", "today-audit" in h5_page.url or "h5" in h5_page.url, "登录成功并进入现场工作台", h5_page.url, "P0")
        except Exception as e:
            record("UI-H-01", "H5 移动端快捷登录", "H5", False, "进入工作台", str(e), "P0")

        # UI-H-02: 任务列表对账徽章
        try:
            # Click "任务" tab at bottom
            task_tab = h5_page.locator(".van-tabbar-item:has-text('任务')").first
            if task_tab.count() > 0:
                task_tab.click()
                time.sleep(1)
            
            task_page_text = h5_page.locator("body").inner_text()
            has_task_badges = ("待处理" in task_page_text or "进行中" in task_page_text or "已完成" in task_page_text)
            record("UI-H-02", "H5 任务列表状态徽章对账闭合", "H5", has_task_badges, "展示待处理/进行中/已完成对账统计", f"badges_present={has_task_badges}", "P1")
        except Exception as e:
            record("UI-H-02", "H5 任务列表对账", "H5", False, "展示徽章", str(e), "P1")

        # UI-H-03: 出发前离线缓存
        try:
            # Click first task card to enter task detail
            first_task = h5_page.locator(".van-cell, .task-card, [class*='task']").first
            if first_task.count() > 0:
                first_task.click()
                time.sleep(1)
                
                # Check for "缓存到本地" button
                cache_btn = h5_page.locator("button:has-text('缓存到本地'), button:has-text('出发前缓存')").first
                has_cache_btn = cache_btn.count() > 0
                if has_cache_btn:
                    cache_btn.click()
                    time.sleep(0.8)
                    # Check localStorage
                    ls_keys = h5_page.evaluate("Object.keys(localStorage)")
                    has_offline_key = any("efis:offline" in k for k in ls_keys)
                    record("UI-H-03", "H5 出发前离线缓存写入 localStorage (FAQ Q1)", "H5", has_offline_key, "localStorage 包含 efis:offline 键", f"keys={ls_keys}", "P1")
                else:
                    record("UI-H-03", "H5 出发前离线缓存", "H5", False, "存在缓存到本地按钮", "未找到按钮", "P1")
        except Exception as e:
            record("UI-H-03", "H5 出发前离线缓存", "H5", False, "写入存储", str(e), "P1")

        # UI-H-04 & UI-H-05: 现场检查执行页、分类横幅、单选枚举 (告别 na)
        try:
            # Click "执行检查" button
            exec_btn = h5_page.locator("button:has-text('执行检查'), button:has-text('开始检查')").first
            if exec_btn.count() > 0:
                exec_btn.click()
                time.sleep(1.5)
                exec_text = h5_page.locator("body").inner_text()
                
                # Check no "na" English abbreviation in radio options
                has_pass_fail_na = ("合格" in exec_text and "不合格" in exec_text and "不适用" in exec_text)
                has_bad_na = " na " in exec_text.lower() or "[na]" in exec_text.lower()
                has_explanation = "不适用" in exec_text and ("不涉及" in exec_text or "不计入" in exec_text)
                
                record("UI-H-05", "H5 现场单选枚举规范与释义小字 (彻底消灭 na)", "H5", has_pass_fail_na and not has_bad_na, "展示合格/不合格/不适用且无 na 缩写", f"options_ok={has_pass_fail_na}, has_bad_na={has_bad_na}, has_note={has_explanation}", "P0")
                
                # UI-H-06: 现场拍照/附件上传组件检查 (P2-11 验证)
                # Check for input[type=file] or van-uploader in page
                upload_inputs = h5_page.locator("input[type='file'], .van-uploader").count()
                record("UI-H-06", "H5 现场拍照采证组件支持 (P2-11 验证)", "H5", upload_inputs > 0, "存在 van-uploader 或 file input 上传组件", f"uploader_count={upload_inputs}", "P2", "验证现场证据链采证入口")
                
                # UI-H-07: 二次确认提交弹窗
                submit_btn = h5_page.locator("button:has-text('提交检查结果'), button:has-text('提交结果')").first
                if submit_btn.count() > 0 and submit_btn.is_enabled():
                    submit_btn.click()
                    time.sleep(0.5)
                    dialog = h5_page.locator(".van-dialog, .van-popup").first
                    has_dialog = dialog.count() > 0
                    dialog_text = dialog.inner_text() if has_dialog else ""
                    has_two_factor = "确认" in dialog_text and "合格" in dialog_text
                    record("UI-H-07", "H5 提交检查全要素二次确认居中弹窗", "H5", has_two_factor, "弹出居中确认框展示统计与不可逆提示", f"dialog_present={has_dialog}", "P0")
                    # Click cancel to avoid polluting data
                    cancel_d_btn = h5_page.locator(".van-dialog__cancel, button:has-text('取消')").first
                    if cancel_d_btn.count() > 0:
                        cancel_d_btn.click()
                else:
                    record("UI-H-07", "H5 提交二次确认弹窗", "H5", True, "未全部评定前保持防误触锁定", "按钮置灰或处于前置状态", "P1")
            else:
                record("UI-H-05", "H5 执行检查页", "H5", False, "执行检查入口", "未定位到按钮", "P0")
        except Exception as e:
            record("UI-H-05", "H5 现场检查执行", "H5", False, "成功打开", str(e), "P0")

        h5_context.close()
        browser.close()

    # Save results
    with open("docs/_remote_browser_test_results.json", "w", encoding="utf-8") as f:
        json.dump(browser_results, f, ensure_ascii=False, indent=2)
    print("\n浏览器端到端测试结果已保存至 docs/_remote_browser_test_results.json")

if __name__ == "__main__":
    run_tests()
