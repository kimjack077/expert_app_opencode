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
    
    # 访问任务详情
    page.goto(f"{H5_BASE}/task/{assets['task_id']}")
    page.wait_for_selector('.task-content', timeout=10000)
    
    # 1. 离线缓存
    cache_btn = page.locator(".offline-card button").first
    cache_btn.evaluate("el => el.click()")
    page.wait_for_selector('.offline-card.cached', timeout=8000)
    print("离线缓存已完成:", page.locator('.offline-card').get_attribute('class'))
    
    # 2. 点击执行检查
    exec_btn = page.locator("button.action-btn.success").first
    exec_btn.evaluate("el => el.click()")
    page.wait_for_selector('.inspection-content', timeout=10000)
    print("已进入现场检查执行页, URL:", page.url)
    
    # 3. 评定 3 个检查项为合格
    cards = page.locator('.check-item-card').all()
    print(f"检查项卡片数: {len(cards)}")
    for i, card in enumerate(cards):
        card.locator('.van-radio').first.evaluate("el => el.click()")
        page.wait_for_timeout(600)
        prog = page.locator('.progress-header').inner_text()
        print(f"评定项 {i+1}, 当前进度:", prog)
        
    page.screenshot(path="docs/screenshots/new_10_h5_exec_3_of_3.png")
    
    # 4. 判定为合格
    verdict_card = page.locator('.judgment-card').first
    verdict_card.locator('.van-radio').first.evaluate("el => el.click()")
    page.wait_for_timeout(600)
    print("已选中最终判定为合格")
    
    # 5. 提交
    submit_btn = page.locator('button.submit-btn').first
    print("提交按钮文字:", submit_btn.inner_text().strip())
    submit_btn.evaluate("el => el.click()")
    
    page.wait_for_selector('.van-dialog', timeout=10000)
    print("确认弹窗文本:\n", page.locator('.van-dialog').inner_text())
    page.screenshot(path="docs/screenshots/new_11_h5_submit_confirm_dialog.png")
    
    # 6. 确认提交
    confirm_btn = page.locator('.van-dialog__confirm').first
    confirm_btn.evaluate("el => el.click()")
    print("已点击弹窗确认")
    
    page.wait_for_url('**/tasks', timeout=15000)
    print("已成功返回任务列表, URL:", page.url)
    page.screenshot(path="docs/screenshots/new_12_h5_task_completed.png")
    
    browser.close()
    print("H5 端到端流转全部跑通！")
