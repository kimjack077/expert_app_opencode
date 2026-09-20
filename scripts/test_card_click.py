import json
from playwright.sync_api import sync_playwright

with open('docs/_new_demo_assets.json', 'r', encoding='utf-8') as f:
    assets = json.load(f)

H5_BASE = 'http://49.232.213.79:5173/h5'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={'width': 375, 'height': 812})
    page = ctx.new_page()
    page.goto(f'{H5_BASE}/login')
    page.click('text=审核专家')
    page.click("button:has-text('登录')")
    page.wait_for_url('**/today-audit')
    
    # 切换任务 tab
    page.click(".van-tabbar-item:has-text('任务')")
    page.wait_for_selector('.task-card', timeout=10000)
    print("当前 URL:", page.url)
    
    # 点击卡片
    card = page.locator(".task-card", has_text="特种装备现场质量安全专项检查").first
    print("点击卡片前 URL:", page.url)
    card.click()
    page.wait_for_timeout(2000)
    print("点击卡片后 URL:", page.url)
    print("页面标题:", page.locator('h1').inner_text() if page.locator('h1').count() > 0 else "无 h1")
    browser.close()
