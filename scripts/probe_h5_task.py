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
    page.goto(f"{H5_BASE}/task/{assets['task_id']}")
    page.wait_for_selector('.task-content', timeout=10000)
    print("=== 页面文本 ===")
    print(page.locator('body').inner_text())
    print("\n=== 按钮列表 ===")
    buttons = page.locator('button').all()
    for i, b in enumerate(buttons):
        print(f"Btn {i}: text='{b.inner_text().strip()}', class='{b.get_attribute('class')}'")
    browser.close()
