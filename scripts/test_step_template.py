# -*- coding: utf-8 -*-
import sys
import io
import time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    
    print("1. Going to login...", flush=True)
    page.goto('http://49.232.213.79:3000/login')
    page.click('text=管理员')
    page.click("button[type='submit']")
    page.wait_for_url('**/dashboard')
    print("2. Logged in dashboard!", flush=True)
    
    print("3. Going to /templates...", flush=True)
    page.goto('http://49.232.213.79:3000/templates')
    page.wait_for_selector(".ant-table-row")
    print("4. Table loaded!", flush=True)
    
    row = page.locator("tr", has_text="质量安全测试")
    edit_btn = row.locator("text=编辑检查项")
    print("5. Clicking 编辑检查项...", flush=True)
    edit_btn.click()
    
    print("6. Waiting for 模板结构视图...", flush=True)
    page.wait_for_selector("text=模板结构视图", timeout=15000)
    print("7. 模板结构视图 found!", flush=True)
    
    # Expand parent node
    parent_node = page.locator(".ant-tree-node-content-wrapper", has_text="测试质量把控").first
    print("8. Clicking parent node...", flush=True)
    parent_node.click()
    time.sleep(1)
    
    alerts = page.locator(".ant-alert").all_inner_texts()
    print("Alerts:\n", "\n".join(alerts), flush=True)
    
    sw = page.locator(".ant-switch").first
    is_disabled = "ant-switch-disabled" in (sw.get_attribute("class") or "")
    print("Switch disabled on parent:", is_disabled, flush=True)
    
    browser.close()
    print("Done!", flush=True)
