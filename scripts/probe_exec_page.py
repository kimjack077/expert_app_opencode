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
    
    # 点击执行检查
    exec_btn = page.locator("button.action-btn.success").first
    exec_btn.scroll_into_view_if_needed()
    exec_btn.click(force=True)
    page.wait_for_selector('.progress-card', timeout=15000)
    
    print("=== 执行页标题/卡片 ===")
    cards = page.locator('.check-item-card').all()
    print("check-item-card 数量:", len(cards))
    for i, c in enumerate(cards):
        radios = c.locator('.van-radio').all()
        print(f"Card {i} 内 radio 数量: {len(radios)}")
    
    categories = page.locator('.category-node').all()
    print("category-node 数量:", len(categories))
    for i, cat in enumerate(categories):
        print(f"Category {i}:", cat.inner_text().strip())
    
    page.screenshot(path="docs/screenshots/probe_exec_page.png")
    print("截图已保存到 docs/screenshots/probe_exec_page.png")
    browser.close()
