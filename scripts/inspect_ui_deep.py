# -*- coding: utf-8 -*-
"""
Deep inspection of UI-W-05, UI-W-07, UI-H-03/05 on remote production.
"""
import sys
import io
import time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WEB_BASE = "http://49.232.213.79:3000"
H5_BASE = "http://49.232.213.79:5173/h5"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # -------------------------------------------------------------
    # 1. Inspect Web Templates and Projects
    # -------------------------------------------------------------
    web = browser.new_context(viewport={"width": 1440, "height": 900})
    page = web.new_page()
    
    # Login
    page.goto(f"{WEB_BASE}/login")
    page.click("text=管理员")
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard")
    print("Logged in as admin.")
    
    # Check UI-W-07: AuditProjects Create
    print("\n--- Inspecting UI-W-07: AuditProjects Create ---")
    page.goto(f"{WEB_BASE}/audit-projects/create")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(1)
    form_text = page.locator("form").inner_text()
    print("Form labels snippet:\n", "\n".join([line for line in form_text.splitlines() if any(k in line for k in ["审核", "天", "体系", "企业", "名称", "工作量"])][:10]))
    
    # Check UI-W-05: Templates V2
    print("\n--- Inspecting UI-W-05: TemplateEditorV2 ---")
    page.goto(f"{WEB_BASE}/templates")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(1)
    # Find table rows
    rows = page.locator("tr").all_inner_texts()
    print("Template rows count:", len(rows))
    for r in rows[:4]:
        print(" - Row:", r.replace("\n", " | ")[:80])
    
    # Click first edit items link/button
    edit_link = page.locator("text=编辑检查项, text=设计, text=编辑").first
    print("Edit link text:", edit_link.inner_text() if edit_link.count() > 0 else "None")
    if edit_link.count() > 0:
        edit_link.click()
        time.sleep(2)
        print("Current template editor URL:", page.url)
        editor_text = page.locator("body").inner_text()
        print("Editor body snippet:", editor_text[:300].replace("\n", " | "))
        
        # Look for tree nodes
        nodes = page.locator(".ant-tree-treenode").all_inner_texts()
        print("Tree nodes count:", len(nodes))
        for n in nodes[:5]:
            print(" - Node:", n.replace("\n", " | "))

    web.close()
    
    # -------------------------------------------------------------
    # 2. Inspect H5 Task Detail & Execution
    # -------------------------------------------------------------
    h5 = browser.new_context(
        viewport={"width": 375, "height": 812},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    )
    h5_page = h5.new_page()
    
    print("\n--- Inspecting H5 Mobile End ---")
    h5_page.goto(f"{H5_BASE}/login")
    h5_page.click("text=审核专家")
    h5_page.click("button:has-text('登录')")
    h5_page.wait_for_url("**/today-audit")
    print("H5 Logged in. URL:", h5_page.url)
    
    # View today audit page
    today_text = h5_page.locator("body").inner_text()
    print("Today audit snippet:", today_text[:200].replace("\n", " | "))
    
    # Navigate to Tasks tab
    h5_page.click(".van-tabbar-item:has-text('任务')")
    time.sleep(1)
    print("Tasks page URL:", h5_page.url)
    tasks_text = h5_page.locator("body").inner_text()
    print("Tasks page text:\n", tasks_text[:400].replace("\n", " | "))
    
    # Look for tasks elements
    task_items = h5_page.locator(".van-cell, .van-card, [class*='task']").all()
    print("Task elements count:", len(task_items))
    
    # Click the in-progress task
    in_progress_card = h5_page.locator("text=进行中").first
    if in_progress_card.count() > 0:
        print("Found '进行中' task card, clicking...")
        in_progress_card.click()
        time.sleep(1.5)
        print("After click task URL:", h5_page.url)
        detail_text = h5_page.locator("body").inner_text()
        print("Task detail snippet:\n", detail_text[:500].replace("\n", " | "))
        
        # Check buttons on detail page
        buttons = h5_page.locator("button").all_inner_texts()
        print("Buttons on detail page:", buttons)
        
        # If there's an action button like "开始检查" or "继续检查" or "执行检查"
        exec_btn = h5_page.locator("button:has-text('检查')").first
        if exec_btn.count() > 0:
            print("Found check button:", exec_btn.inner_text(), "- clicking...")
            exec_btn.click()
            time.sleep(2)
            print("Execution page URL:", h5_page.url)
            exec_page_text = h5_page.locator("body").inner_text()
            print("Execution page snippet:\n", exec_page_text[:500].replace("\n", " | "))
            
            # Check for upload component
            file_inputs = h5_page.locator("input[type='file'], .van-uploader").count()
            print("File inputs/uploaders count:", file_inputs)
            
            # Check buttons on execution page
            exec_buttons = h5_page.locator("button").all_inner_texts()
            print("Buttons on execution page:", exec_buttons)

    h5.close()
    browser.close()
