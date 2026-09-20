# -*- coding: utf-8 -*-
import sys
import io
import time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    
    page.goto('http://49.232.213.79:3000/login')
    page.click('text=管理员')
    page.click('button[type=submit]')
    page.wait_for_url('**/dashboard')
    
    page.goto('http://49.232.213.79:3000/templates')
    page.wait_for_selector(".ant-table-row", timeout=10000)
    
    # Click 编辑检查项 on row with 质量安全测试
    row = page.locator("tr", has_text="质量安全测试")
    edit_btn = row.locator("text=编辑检查项")
    edit_btn.click()
    
    # Wait for TemplateEditorV2 to render
    page.wait_for_selector("text=模板结构视图", timeout=10000)
    time.sleep(1)
    print("TemplateEditorV2 rendered successfully!")
    
    # Check tree view title and action icons (P3-05 展开/折叠全部)
    expand_btn = page.locator(".anticon-expand, [title*='展开'], [aria-label*='expand']").first
    print("Expand icon button count:", expand_btn.count())
    
    # 1. Click parent node: 测试质量把控
    parent_node = page.locator(".ant-tree-node-content-wrapper", has_text="测试质量把控").first
    print("Parent node found:", parent_node.count() > 0)
    if parent_node.count() > 0:
        parent_node.click()
        time.sleep(1)
        alerts = page.locator(".ant-alert").all_inner_texts()
        print("Alerts after clicking parent:\n", "\n".join(alerts))
        
        sw = page.locator(".ant-switch").first
        is_disabled = "ant-switch-disabled" in (sw.get_attribute("class") or "")
        print("Switch is disabled on parent:", is_disabled)
        
        # Verify scoring fields hidden
        form_text = page.locator(".ant-card").last.inner_text()
        has_method = "检查方法" in form_text
        has_basis = "法律依据" in form_text
        has_ai_prompt = "AI 提示词" in form_text or "AI提示词" in form_text
        print("Parent form hides check_method:", not has_method)
        print("Parent form hides legal_basis:", not has_basis)
        print("Parent form hides ai_prompt:", not has_ai_prompt)
        
    # 2. Click leaf node: 把控1
    leaf_node = page.locator(".ant-tree-node-content-wrapper", has_text="把控1").first
    print("\nLeaf node found:", leaf_node.count() > 0)
    if leaf_node.count() > 0:
        leaf_node.click()
        time.sleep(1)
        alerts2 = page.locator(".ant-alert").count()
        print("Alert count on leaf:", alerts2)
        
        sw2 = page.locator(".ant-switch").first
        is_disabled2 = "ant-switch-disabled" in (sw2.get_attribute("class") or "")
        print("Switch is disabled on leaf:", is_disabled2)
        
        form_text2 = page.locator(".ant-card").last.inner_text()
        has_type = "采集结果类型" in form_text2 or "结果类型" in form_text2
        has_method2 = "检查方法" in form_text2
        has_basis2 = "法律依据" in form_text2
        print("Leaf form shows result_type:", has_type)
        print("Leaf form shows check_method:", has_method2)
        print("Leaf form shows legal_basis:", has_basis2)
        
    browser.close()
