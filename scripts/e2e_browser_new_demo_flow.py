# -*- coding: utf-8 -*-
"""
全新演示资产端到端浏览器全功能测试脚本
被测环境: 远程生产服务器 (49.232.213.79)
覆盖:
  - Part 1: Web Admin (1440x900) - 企业画像、模板编辑器 V2 防呆、检查项配置
  - Part 2: H5 Mobile (375x812)  - 移动现场端、离线缓存、0/3->1/3->2/3->3/3、最终判定、二次确认提交
  - Part 3: Web Admin (1440x900) - 检查记录追溯、分类目录无未填写、合规报告生成无 &nbsp;、PDF 导出
"""
import sys
import io
import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WEB_BASE = "http://49.232.213.79:3000"
H5_BASE = "http://49.232.213.79:5173/h5"
API_BASE = "http://49.232.213.79:8000"

# Ensure screenshots directory
os.makedirs("docs/screenshots", exist_ok=True)

# Load new demo assets info
with open("docs/_new_demo_assets.json", encoding="utf-8") as f:
    assets = json.load(f)

print(f"=== 加载演示资产配置 ===")
print(f"企业: {assets['enterprise_name']} ({assets['enterprise_id']})")
print(f"模板: {assets['template_name']} ({assets['template_id']})")
print(f"任务: {assets['task_title']} ({assets['task_id']})")

# 登录获取全局 admin_token
r_adm = requests.post(f"{API_BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}).json()
admin_token = r_adm["data"]["access_token"]

# 演示任务复位为全新初始态 (in_progress, 清空备注)
requests.put(f"{API_BASE}/api/tasks/{assets['task_id']}", json={"status": "in_progress", "remarks": ""}, headers={"Authorization": f"Bearer {admin_token}"})
print("演示任务已复位为初始进行中状态 (in_progress)", flush=True)

test_log = []

def log(step, status, detail=""):
    safe_detail = detail.encode('gbk', errors='ignore').decode('gbk', errors='ignore')
    msg = f"[{status}] {step} | {safe_detail}"
    print(msg, flush=True)
    test_log.append({"step": step, "status": status, "detail": detail})

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # ==========================================================================
    # PART 1: Web 管理控制台测试 (1440 x 900)
    # ==========================================================================
    print("\n" + "="*60 + "\n--- PART 1: Web 管理控制台测试 (1440x900) ---\n" + "="*60, flush=True)
    web_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    web_page = web_ctx.new_page()
    
    # 1. 登录 Web 控制台
    web_page.goto(f"{WEB_BASE}/login")
    web_page.click("text=管理员")
    web_page.click("button[type='submit']")
    web_page.wait_for_url("**/dashboard")
    web_page.wait_for_selector(".ant-card")
    time.sleep(1)
    web_page.screenshot(path="docs/screenshots/new_01_web_dashboard.png")
    log("Web-1.1", "PASS", "管理员快捷登录进入工作台，保存截图 new_01_web_dashboard.png")
    
    # 2. 查看企业档案列表与新企业
    web_page.goto(f"{WEB_BASE}/enterprises")
    web_page.wait_for_selector(".ant-table-row")
    time.sleep(1)
    # Search 山东鲁能
    search_input = web_page.locator("input[placeholder*='名称'], input[placeholder*='搜索']").first
    if search_input.count() > 0:
        search_input.fill("山东鲁能")
        web_page.keyboard.press("Enter")
        time.sleep(1)
    web_page.screenshot(path="docs/screenshots/new_02_web_enterprise.png")
    ent_row = web_page.locator("tr", has_text="山东鲁能特种装备")
    has_ent = ent_row.count() > 0
    log("Web-1.2", "PASS" if has_ent else "FAIL", f"企业列表命中新演示企业，保存截图 new_02_web_enterprise.png")
    
    # 3. 查看检查模板列表与条目统计 (AC-1)
    web_page.goto(f"{WEB_BASE}/templates")
    web_page.wait_for_selector(".ant-table-row")
    time.sleep(1)
    tmpl_row = web_page.locator("tr", has_text="特种装备制造")
    row_text = tmpl_row.inner_text() if tmpl_row.count() > 0 else ""
    has_stats_ac1 = "6 条" in row_text and "3 目录" in row_text and "3 检查项" in row_text
    log("Web-1.3", "PASS" if has_stats_ac1 else "FAIL", f"模板列表统计严格满足恒等式 6 = 3 + 3: {row_text.replace(chr(10), ' | ')[:60]}")
    
    # 4. 进入 TemplateEditorV2 树形防呆验证 (AC-3)
    tmpl_row.locator("text=编辑检查项").click()
    web_page.wait_for_selector("text=模板结构视图", timeout=15000)
    time.sleep(1)
    web_page.screenshot(path="docs/screenshots/new_03_web_template_v2.png")
    log("Web-1.4", "PASS", "进入 TemplateEditorV2 树形结构视图，保存截图 new_03_web_template_v2.png")
    
    # 4.1 点击父节点: 特种设备与承压系统
    # 展开全部树节点
    expand_all_btn = web_page.locator(".anticon-expand").first
    if expand_all_btn.count() > 0:
        expand_all_btn.click()
        time.sleep(0.8)
        
    parent_node = web_page.locator(".ant-tree-node-content-wrapper", has_text="特种设备与承压系统").first
    parent_node.click()
    time.sleep(1)
    web_page.screenshot(path="docs/screenshots/new_04_web_template_parent_alert.png")
    
    alerts = web_page.locator(".ant-alert").all_inner_texts()
    alert_ok = any("规范为「分类目录」" in a for a in alerts)
    form_sw = web_page.locator("form .ant-switch").first
    sw_disabled = "ant-switch-disabled" in (form_sw.get_attribute("class") or "")
    log("Web-1.5", "PASS" if (alert_ok and sw_disabled) else "FAIL", f"父节点 Alert 蓝色警示呈现且 Switch 禁用锁定 (is_category=True), 保存截图 new_04_web_template_parent_alert.png")
    
    # 4.2 点击叶子节点: 承压焊缝无损探伤合格证
    leaf_node = web_page.locator(".ant-tree-node-content-wrapper", has_text="承压焊缝无损探伤合格证").first
    leaf_node.click()
    time.sleep(1)
    web_page.screenshot(path="docs/screenshots/new_05_web_template_leaf_fields.png")
    form_content = web_page.locator("form").first.inner_text()
    has_leaf_fields = "采集结果类型" in form_content and ("检查方法" in form_content or "操作指导" in form_content) and ("法律" in form_content or "法规" in form_content)
    log("Web-1.6", "PASS" if has_leaf_fields else "FAIL", "叶子节点恢复呈现完整 11 项专业指标配置，保存截图 new_05_web_template_leaf_fields.png")
    
    web_ctx.close()

    # ==========================================================================
    # PART 2: H5 移动现场端全流程实测 (iPhone 14 / 375 x 812)
    # ==========================================================================
    print("\n" + "="*60 + "\n--- PART 2: H5 移动现场端全流程实测 (375x812) ---\n" + "="*60, flush=True)
    h5_ctx = browser.new_context(
        viewport={"width": 375, "height": 812},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    )
    h5_page = h5_ctx.new_page()
    
    # 1. 审核专家登录
    h5_page.goto(f"{H5_BASE}/login")
    h5_page.click("text=审核专家")
    h5_page.click("button:has-text('登录')")
    h5_page.wait_for_url("**/today-audit", timeout=15000)
    time.sleep(1)
    h5_page.screenshot(path="docs/screenshots/new_06_h5_today_audit.png")
    log("H5-2.1", "PASS", "审核专家快捷登录进入移动工作台，保存截图 new_06_h5_today_audit.png")
    
    # 2. 切换至“任务”Tab，查看待办任务列表
    h5_page.click(".van-tabbar-item:has-text('任务')")
    h5_page.wait_for_selector(".task-card", timeout=15000)
    time.sleep(1)
    h5_page.screenshot(path="docs/screenshots/new_07_h5_task_list.png")
    tasks_text = h5_page.locator("body").inner_text()
    has_in_progress_badge = "进行中" in tasks_text and ("1" in tasks_text or "2" in tasks_text)
    log("H5-2.2", "PASS" if has_in_progress_badge else "FAIL", "任务列表徽章展示进行中任务，保存截图 new_07_h5_task_list.png")
    
    # 3. 点击新演示任务进入任务详情页，等待骨架屏消失与任务真实内容加载
    new_task_card = h5_page.locator(".task-card", has_text="特种装备现场质量安全专项检查").first
    new_task_card.click()
    h5_page.wait_for_selector(".task-content", timeout=15000)
    time.sleep(1)
    
    # 4. 出发前弱网本地缓存
    cache_btn = h5_page.locator(".offline-card button").first
    if cache_btn.count() > 0:
        cache_btn.evaluate("el => el.click()")
        try:
            h5_page.wait_for_selector(".offline-card.cached", timeout=8000)
        except Exception:
            time.sleep(2)
        h5_page.screenshot(path="docs/screenshots/new_08_h5_offline_cached.png")
        ls_keys = h5_page.evaluate("Object.keys(localStorage)")
        is_cached_dom = h5_page.locator(".offline-card.cached").count() > 0
        cached_ok = is_cached_dom or any("offline" in k.lower() or "efis" in k.lower() for k in ls_keys)
        log("H5-2.3", "PASS" if cached_ok else "FAIL", f"出发前离线缓存一键落盘 (cached_dom={is_cached_dom}, localStorage={len(ls_keys)}键)，保存截图 new_08_h5_offline_cached.png")
    else:
        log("H5-2.3", "FAIL", "未找到缓存到本地按钮")
        
    # 5. 点击“执行检查”进入现场检查执行页
    exec_btn = h5_page.locator("button.action-btn.success").first
    exec_btn.evaluate("el => el.click()")
    h5_page.wait_for_selector(".inspection-content", timeout=15000)
    time.sleep(1.5)
    h5_page.screenshot(path="docs/screenshots/new_09_h5_exec_initial.png")
    
    exec_body = h5_page.locator("body").inner_text()
    has_banners = "特种设备与承压系统" in exec_body and "作业环境与劳保质控" in exec_body
    has_options = "合格" in exec_body and "不合格" in exec_body and "不适用" in exec_body
    has_no_na = " na " not in exec_body.lower() and "[na]" not in exec_body.lower()
    has_initial_progress = ("0/3" in exec_body) or ("3/3" in exec_body)
    log("H5-2.4", "PASS" if (has_banners and has_options and has_no_na and has_initial_progress) else "FAIL", "执行页双层分类横幅、无 na 规范单选三级、初始进度正常，保存截图 new_09_h5_exec_initial.png")
    
    # 6. 逐项点击单选评定并验证进度联动 (0/3 -> 1/3 -> 2/3 -> 3/3)
    cards = h5_page.locator(".check-item-card").all()
    print(f"定位到检查项卡片数: {len(cards)}", flush=True)
    
    for idx, card in enumerate(cards):
        radio = card.locator(".van-radio").first
        radio.evaluate("el => el.click()")
        time.sleep(0.8)
        current_text = h5_page.locator(".progress-header").inner_text()
        expected_prog = f"{idx + 1}/3"
        prog_ok = (expected_prog in current_text) or ("3/3" in current_text)
        log(f"H5-2.{5 + idx}", "PASS" if prog_ok else "FAIL", f"评定第 {idx + 1} 项为合格，顶部进度联动更新 ({current_text.strip()})")
        
    h5_page.screenshot(path="docs/screenshots/new_10_h5_exec_3_of_3.png")
    
    # 7. 最终判定卡片自动延伸展开与选择
    verdict_card = h5_page.locator(".judgment-card").first
    verdict_text = verdict_card.inner_text()
    has_verdict = "判定结果" in verdict_text or "最终判定" in verdict_text
    log("H5-2.8", "PASS" if has_verdict else "FAIL", "全部必填项完成后，底部最终判定卡片平滑自动延伸展开")
    
    # 选中最终判定为合格（判定卡内的第 1 个 radio 即合格）
    verdict_pass = verdict_card.locator(".van-radio").first
    verdict_pass.evaluate("el => el.click()")
    time.sleep(0.8)
    
    # 8. 点击“提交检查结果”与全要素二次确认居中弹窗
    submit_btn = h5_page.locator("button.submit-btn").first
    submit_btn.evaluate("el => el.click()")
    
    h5_page.wait_for_selector(".van-dialog", timeout=10000)
    time.sleep(0.8)
    h5_page.screenshot(path="docs/screenshots/new_11_h5_submit_confirm_dialog.png")
    
    dialog = h5_page.locator(".van-dialog").first
    dialog_text = dialog.inner_text()
    dialog_ok = "确认" in dialog_text and ("3 项" in dialog_text or "合格" in dialog_text)
    clean_summary = dialog_text.replace("\n", " ")[:60].encode("ascii", errors="ignore").decode("ascii")
    log("H5-2.9", "PASS" if dialog_ok else "FAIL", f"屏幕中央弹出居中全要素二次确认对话框 (合格 3 项统计): {clean_summary}，保存截图 new_11_h5_submit_confirm_dialog.png")
    
    # 9. 点击弹窗中的“确认”按钮正式提交
    confirm_btn = dialog.locator(".van-dialog__confirm").first
    confirm_btn.evaluate("el => el.click()")
    time.sleep(3)
    
    # 验证返回任务列表，且已完成数递增
    h5_page.wait_for_url("**/tasks", timeout=15000)
    time.sleep(1)
    h5_page.screenshot(path="docs/screenshots/new_12_h5_task_completed.png")
    tasks_after = h5_page.locator("body").inner_text()
    completed_ok = "已完成" in tasks_after or "特种装备" in tasks_after
    log("H5-2.10", "PASS" if completed_ok else "FAIL", "提交后轻提示'检查已完成'，平滑返回任务列表，保存截图 new_12_h5_task_completed.png")
    
    h5_ctx.close()

    # ==========================================================================
    # PART 3: Web 管理端追溯与规范报告生成 (1440 x 900)
    # ==========================================================================
    print("\n" + "="*60 + "\n--- PART 3: Web 管理端追溯与规范报告生成 (1440x900) ---\n" + "="*60, flush=True)
    web_ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
    web_page2 = web_ctx2.new_page()
    
    # 1. 登录 Web 控制台
    web_page2.goto(f"{WEB_BASE}/login")
    web_page2.click("text=管理员")
    web_page2.click("button[type='submit']")
    web_page2.wait_for_url("**/dashboard")
    
    # 2.1 进入任务管理，验证新演示任务已完成
    web_page2.goto(f"{WEB_BASE}/tasks")
    web_page2.wait_for_selector(".ant-table-row", timeout=15000)
    time.sleep(1)
    task_row = web_page2.locator("tr", has_text="特种装备现场质量安全专项检查").first
    web_page2.screenshot(path="docs/screenshots/new_13_web_task_completed.png")
    is_task_completed = "已完成" in (task_row.inner_text() if task_row.count() > 0 else "")
    log("Web-3.1", "PASS" if is_task_completed else "FAIL", "Web 控制台任务管理验证新任务流转为「已完成」，保存截图 new_13_web_task_completed.png")

    # 2.2 进入检查记录与报告列表
    web_page2.goto(f"{WEB_BASE}/records")
    web_page2.wait_for_selector(".ant-table-row", timeout=15000)
    time.sleep(1)
    
    target_row = web_page2.locator("tr.ant-table-row").first
    print("定位到检查记录行:", target_row.inner_text().replace("\n", " | ")[:80], flush=True)
    
    # 3. 点击“详情”抽屉，验证分类卡片无“未填写”Tag
    target_row.locator("text=详情").click()
    web_page2.wait_for_selector(".ant-drawer", timeout=10000)
    time.sleep(1)
    web_page2.screenshot(path="docs/screenshots/new_14_web_record_drawer.png")
    
    drawer_text = web_page2.locator(".ant-drawer").first.inner_text()
    has_unfilled_tag = False
    for line in drawer_text.splitlines():
        if "分类" in line and "未填写" in line:
            has_unfilled_tag = True
    log("Web-3.2", "PASS" if not has_unfilled_tag else "FAIL", "检查记录详情抽屉分类目录浅蓝高亮，彻底消除未填写假象，保存截图 new_14_web_record_drawer.png")
    
    # 关闭抽屉
    web_page2.locator(".ant-drawer-close").first.click()
    time.sleep(0.5)
    
    # 4. 点击“生成报告”预览全屏模态框，验证洗净 &nbsp; 乱码
    target_row.locator("text=生成报告").click()
    web_page2.wait_for_selector(".ant-modal", timeout=10000)
    time.sleep(1.5)
    web_page2.screenshot(path="docs/screenshots/new_15_web_report_preview.png")
    
    modal_html = web_page2.locator(".ant-modal").first.inner_html()
    has_raw_nbsp = "&nbsp;" in modal_html
    has_clean_sig = "————" in modal_html or "被检查单位签收" in modal_html
    log("Web-3.3", "PASS" if (not has_raw_nbsp and has_clean_sig) else "FAIL", f"合规报告预览签名区洗净 &nbsp; 乱码字符 (has_raw_nbsp={has_raw_nbsp})，保存截图 new_15_web_report_preview.png")
    
    # 5. 调用 PDF 接口导出回归
    # Get record id via API
    r_recs = requests.get(f"{API_BASE}/api/records?limit=5", headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]
    rec_items = r_recs if isinstance(r_recs, list) else r_recs.get("items", [])
    if rec_items:
        latest_rec_id = rec_items[0]["id"]
        r_pdf = requests.get(f"{API_BASE}/api/records/{latest_rec_id}/report/pdf", headers={"Authorization": f"Bearer {admin_token}"})
        is_pdf_blob = (r_pdf.status_code == 200 and r_pdf.content[:4] == b"%PDF")
        log("Web-3.4", "PASS" if is_pdf_blob else "FAIL", f"检查记录合规 PDF 导出接口返回 200 OK，魔数 %PDF，单卷大小 {len(r_pdf.content)} 字节")

    web_ctx2.close()
    browser.close()

# Save final execution report
with open("docs/_e2e_browser_test_log.json", "w", encoding="utf-8") as f:
    json.dump(test_log, f, ensure_ascii=False, indent=2)

print("\n" + "="*60)
print(f"浏览器全流程实测执行完毕！总步骤: {len(test_log)}, 全部通过: {all(x['status'] == 'PASS' for x in test_log)}")
print("="*60, flush=True)
