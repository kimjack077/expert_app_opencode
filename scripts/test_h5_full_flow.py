# -*- coding: utf-8 -*-
"""
H5 移动现场端完整流程自动化测试 (使用临时 E2E 任务，测完清理)
"""
import sys
import io
import time
import requests
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://49.232.213.79:8000"
H5_BASE = "http://49.232.213.79:5173/h5"

# 1. Admin login to setup test task
r_login = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
admin_token = r_login.json()["data"]["access_token"]
h_admin = {"Authorization": f"Bearer {admin_token}"}

# Get demo enterprise & template
ents = requests.get(f"{BASE}/api/enterprises", headers=h_admin).json()["data"]
ent_id = (ents[0] if isinstance(ents, list) else ents.get("items", [])[0])["id"]

tmpls = requests.get(f"{BASE}/api/templates", headers=h_admin).json()["data"]
tmpl_demo = next(t for t in tmpls if "质量安全测试" in t["name"])

users = requests.get(f"{BASE}/api/users", headers=h_admin).json()["data"]
exp_user = next(u for u in users if u["username"] == "expert")

# Create task for expert
r_t = requests.post(f"{BASE}/api/tasks", headers=h_admin, json={
    "title": "（E2E自动化）质量安全现场检查",
    "enterprise_id": ent_id,
    "template_id": tmpl_demo["id"],
    "assigned_to": exp_user["id"]
})
task_id = r_t.json()["data"]["id"]
print(f"Created test task: {task_id}")

# Start task to in_progress
r_start = requests.post(f"{BASE}/api/tasks/{task_id}/start", headers=h_admin)
print(f"Started task: status={r_start.status_code}")

h5_results = {}

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()
        
        # 1. Login as expert
        page.goto(f"{H5_BASE}/login")
        page.click("text=审核专家")
        page.click("button:has-text('登录')")
        page.wait_for_url("**/today-audit", timeout=15000)
        print("H5 expert logged in successfully!")
        
        # 2. Go to Tasks tab
        page.click(".van-tabbar-item:has-text('任务')")
        time.sleep(1)
        print("Switched to Tasks tab.")
        
        # Check badges
        task_text = page.locator("body").inner_text()
        print("Tasks overview:\n", task_text[:200].replace("\n", " | "))
        
        # Click the in-progress test task
        task_card = page.locator(".van-cell, [class*='task']", has_text="（E2E自动化）质量安全现场检查").first
        print("Found test task card:", task_card.count() > 0)
        task_card.click()
        time.sleep(1.5)
        print("Entered task detail URL:", page.url)
        
        # Check "出发前缓存"
        cache_btn = page.locator("button:has-text('缓存到本地')").first
        h5_results["has_cache_btn"] = (cache_btn.count() > 0)
        print("Cache button present:", h5_results["has_cache_btn"])
        if h5_results["has_cache_btn"]:
            cache_btn.click()
            time.sleep(1)
            ls_keys = page.evaluate("Object.keys(localStorage)")
            h5_results["offline_cached"] = any("efis:offline" in k for k in ls_keys)
            print("Offline cache in localStorage:", h5_results["offline_cached"], "keys:", [k for k in ls_keys if "efis" in k])
            
        # Click "执行检查"
        exec_btn = page.locator("button:has-text('执行检查'), button:has-text('开始检查')").first
        h5_results["has_exec_btn"] = (exec_btn.count() > 0)
        print("Exec button present:", h5_results["has_exec_btn"])
        
        if h5_results["has_exec_btn"]:
            exec_btn.click()
            time.sleep(2)
            print("Execution page URL:", page.url)
            exec_text = page.locator("body").inner_text()
            
            # Check Category banners
            has_cat1 = "测试难度" in exec_text
            has_cat2 = "测试质量把控" in exec_text
            h5_results["category_banners"] = (has_cat1 and has_cat2)
            print("Category banners present:", h5_results["category_banners"])
            
            # Check radio options: 合格 / 不合格 / 不适用, NO na!
            has_pass = "合格" in exec_text
            has_fail = "不合格" in exec_text
            has_na = "不适用" in exec_text
            has_bad_na = " na " in exec_text.lower() or "[na]" in exec_text.lower()
            h5_results["radio_options_valid"] = (has_pass and has_fail and has_na and not has_bad_na)
            print("Radio options valid (no na):", h5_results["radio_options_valid"])
            
            # Check explanatory note
            h5_results["has_explanation"] = "「不适用」=" in exec_text or "不涉及本次受审对象" in exec_text
            print("Explanatory note below radio:", h5_results["has_explanation"])
            
            # Check upload / photo component in execution or item
            file_inputs_count = page.locator("input[type='file'], .van-uploader").count()
            h5_results["file_upload_count"] = file_inputs_count
            print("File upload inputs count in execution page:", file_inputs_count)
            
            # Check leaf progress: initially 0/2
            h5_results["initial_progress_0_2"] = "0/2" in exec_text
            print("Initial progress 0/2:", h5_results["initial_progress_0_2"])
            
            # Select pass on first item
            pass_buttons = page.locator("text=合格").all()
            print("Pass buttons count:", len(pass_buttons))
            if len(pass_buttons) >= 2:
                # Click first pass
                pass_buttons[0].click()
                time.sleep(0.8)
                text_after_1 = page.locator("body").inner_text()
                h5_results["progress_1_2"] = "1/2" in text_after_1
                print("Progress 1/2 after first click:", h5_results["progress_1_2"])
                
                # Click second pass
                pass_buttons[1].click()
                time.sleep(0.8)
                text_after_2 = page.locator("body").inner_text()
                h5_results["progress_2_2"] = "2/2" in text_after_2
                print("Progress 2/2 after second click:", h5_results["progress_2_2"])
                
                # Check final verdict card auto expansion
                has_verdict_card = "最终判定结论" in text_after_2 or "最终判定" in text_after_2
                h5_results["verdict_card_expanded"] = has_verdict_card
                print("Verdict card auto-expanded:", has_verdict_card)
                
                # Check submit button
                submit_btn = page.locator("button:has-text('提交检查结果')").first
                h5_results["submit_btn_active"] = (submit_btn.count() > 0 and submit_btn.is_enabled())
                print("Submit button active:", h5_results["submit_btn_active"])
                
                if h5_results["submit_btn_active"]:
                    submit_btn.click()
                    time.sleep(0.8)
                    dialog = page.locator(".van-dialog, .van-popup").first
                    dialog_text = dialog.inner_text() if dialog.count() > 0 else ""
                    h5_results["confirm_dialog"] = ("确定" in dialog_text or "确认" in dialog_text or "合格" in dialog_text)
                    print("Two-factor confirmation dialog present:", h5_results["confirm_dialog"])
                    print("Dialog snippet:\n", dialog_text.replace("\n", " | "))
                    
                    # Click cancel
                    cancel_btn = page.locator(".van-dialog__cancel, button:has-text('取消')").first
                    if cancel_btn.count() > 0:
                        cancel_btn.click()
                        time.sleep(0.5)
                        print("Clicked cancel on dialog.")
        
        context.close()
        browser.close()
finally:
    # Always clean up test task!
    r_del = requests.delete(f"{BASE}/api/tasks/{task_id}", headers=h_admin)
    print(f"Cleaned up test task: {r_del.status_code}")

print("\n=== H5 Flow Test Results ===")
for k, v in h5_results.items():
    print(f" - {k}: {v}")
