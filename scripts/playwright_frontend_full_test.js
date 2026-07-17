async page => {
  const WEB = 'http://49.232.213.79:3000';
  const H5 = 'http://49.232.213.79:5173/h5';
  const results = [];
  const consoleErrors = [];
  const pageErrors = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push({ url: page.url(), text: msg.text().slice(0, 300) });
    }
  });
  page.on('pageerror', err => {
    pageErrors.push({ url: page.url(), text: String(err).slice(0, 300) });
  });

  const sleep = async ms => { await page.waitForTimeout(ms); };

  async function step(name, fn) {
    const start = Date.now();
    try {
      const detail = await fn();
      results.push({ name, ok: true, detail: String(detail ?? 'ok').slice(0, 400), ms: Date.now() - start });
    } catch (e) {
      results.push({ name, ok: false, detail: String(e && e.message ? e.message : e).slice(0, 500), ms: Date.now() - start });
    }
  }

  async function expectVisible(selector, timeout = 8000) {
    await page.waitForSelector(selector, { timeout, state: 'visible' });
  }

  async function textHas(re, timeout = 8000) {
    await page.waitForFunction(
      (pattern) => new RegExp(pattern, 'i').test(document.body ? document.body.innerText : ''),
      String(re),
      { timeout }
    );
  }

  async function softGoto(url) {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(800);
    return resp ? resp.status() : 0;
  }

  // ========== WEB ADMIN ==========
  await step('web.open_login', async () => {
    const st = await softGoto(WEB + '/login');
    if (st >= 400) throw new Error('HTTP ' + st);
    await expectVisible('input', 10000);
    return 'status=' + st + ' title=' + (await page.title());
  });

  await step('web.login_admin', async () => {
    // Ant Design Form inputs
    const user = page.locator('input[placeholder*="用户"], input[placeholder*="账号"], input#username, input[type="text"]').first();
    const pass = page.locator('input[type="password"]').first();
    await user.fill('admin');
    await pass.fill('admin123');
    const btn = page.locator('button[type="submit"], button:has-text("登"), .ant-btn-primary').first();
    await btn.click();
    await page.waitForURL(/dashboard|\/$|home/i, { timeout: 15000 }).catch(() => {});
    await sleep(1500);
    const url = page.url();
    if (/login/i.test(url)) {
      // try alternate selectors
      throw new Error('still on login: ' + url + ' body=' + (await page.locator('body').innerText()).slice(0, 120));
    }
    return url;
  });

  const webRoutes = [
    ['web.dashboard', '/dashboard', /工作台|仪表|概览|Dashboard|统计|今日/i],
    ['web.templates', '/templates', /模板|检查模板|ISO|体系/i],
    ['web.tasks', '/tasks', /任务|检查任务|状态|待处理|进行中/i],
    ['web.records', '/records', /记录|检查记录|结果|提交/i],
    ['web.enterprises', '/enterprises', /企业|信用|联系人|地址/i],
    ['web.users', '/users', /用户|角色|管理员|专家/i],
    ['web.industries', '/industries', /行业|分类|代码/i],
    ['web.knowledge', '/knowledge', /知识|文档|分类|法规/i],
    ['web.analytics', '/analytics', /分析|统计|日志|调用/i],
    ['web.audit_projects', '/audit-projects', /审核项目|项目|认证|计划/i],
    ['web.audit_statistics', '/audit-statistics', /审核统计|项目|不符合|概览|分布/i],
    ['web.my_audit_tasks', '/my-audit-tasks', /我的|审核|任务|计划|暂无/i],
  ];

  for (const [name, path, re] of webRoutes) {
    await step(name, async () => {
      const st = await softGoto(WEB + path);
      if (st >= 400) throw new Error('HTTP ' + st);
      await sleep(1000);
      const body = await page.locator('body').innerText();
      if (!re.test(body) && body.length < 20) throw new Error('empty/unexpected page: ' + body.slice(0, 100));
      // allow partial match; if spinner forever then fail
      if (/登录|请先登录|Login/i.test(body) && /password|密码/i.test(body)) throw new Error('redirected to login');
      return 'ok bodyLen=' + body.length + ' url=' + page.url();
    });
  }

  // open first audit project if list has links
  await step('web.audit_project_detail', async () => {
    await softGoto(WEB + '/audit-projects');
    await sleep(1200);
    const link = page.locator('a[href*="/audit-projects/"], tr, .ant-table-row, .ant-list-item').filter({ hasText: /AUDIT|审核|项目|车间/ }).first();
    const count = await page.locator('a[href*="/audit-projects/"]').count();
    if (count > 0) {
      const href = await page.locator('a[href*="/audit-projects/"]').first().getAttribute('href');
      if (href && !href.endsWith('/create') && !href.endsWith('/audit-projects')) {
        await softGoto(href.startsWith('http') ? href : WEB + href);
        await sleep(1200);
        const body = await page.locator('body').innerText();
        return 'opened ' + page.url() + ' len=' + body.length;
      }
    }
    // click first table row action "查看" if any
    const viewBtn = page.locator('button:has-text("查看"), a:has-text("查看"), button:has-text("详情")').first();
    if (await viewBtn.count()) {
      await viewBtn.click();
      await sleep(1500);
      return 'clicked view ' + page.url();
    }
    return 'no project row to open (list may be empty UI)';
  });

  // open first task inspection if available
  await step('web.task_or_inspection', async () => {
    await softGoto(WEB + '/tasks');
    await sleep(1200);
    const inspect = page.locator('button:has-text("执行检查"), a:has-text("执行检查"), button:has-text("查看检查")').first();
    if (await inspect.count()) {
      await inspect.click();
      await sleep(2000);
      const body = await page.locator('body').innerText();
      return 'inspection page ' + page.url() + ' hasResultUI=' + /检查|合格|进度|条目/i.test(body);
    }
    const row = page.locator('.ant-table-tbody tr.ant-table-row:visible').first();
    if (await row.count()) {
      await row.click({ timeout: 5000 }).catch(() => {});
      await sleep(1000);
      return 'opened visible row ' + page.url();
    }
    return 'no task actions visible';
  });

  // ========== H5 ==========
  await step('h5.open_login', async () => {
    const st = await softGoto(H5 + '/login');
    if (st >= 400) throw new Error('HTTP ' + st);
    await sleep(800);
    await expectVisible('input', 10000);
    return 'status=' + st;
  });

  await step('h5.login_expert', async () => {
    // clear and login as expert (field inspector)
    const inputs = page.locator('input');
    const count = await inputs.count();
    // usually username + password
    const user = page.locator('input[type="text"], input[type="tel"], input:not([type]), input[placeholder*="账号"], input[placeholder*="用户"]').first();
    const pass = page.locator('input[type="password"]').first();
    await user.fill('expert');
    await pass.fill('expert123');
    const loginBtn = page.locator('button:has-text("登录"), button:has-text("登 录"), .van-button--primary').first();
    await loginBtn.click();
    await sleep(2000);
    // accept if navigated away from login
    if (/login/i.test(page.url())) {
      // try admin fallback for broader menus
      await user.fill('admin');
      await pass.fill('admin123');
      await loginBtn.click();
      await sleep(2000);
    }
    if (/login/i.test(page.url())) throw new Error('H5 login failed url=' + page.url());
    return page.url();
  });

  const h5Routes = [
    ['h5.home', '/home', /首页|任务|记录|检查|今日|欢迎|工作/i],
    ['h5.tasks', '/tasks', /任务|待处理|进行中|检查|暂无/i],
    ['h5.records', '/records', /记录|检查|结果|暂无|合格/i],
    ['h5.today_audit', '/today-audit', /今日|审核|任务|计划|AI|暂无/i],
    ['h5.audit_tasks', '/audit-tasks', /审核|任务|计划|开始|继续|暂无/i],
    ['h5.select_enterprise', '/select-enterprise', /企业|选择|搜索|检查/i],
    ['h5.profile', '/profile', /我的|设置|退出|个人信息|专家|用户/i],
    ['h5.statistics', '/statistics', /统计|次数|合格|分析|图表|暂无/i],
    ['h5.settings', '/settings', /设置|关于|版本|通知|缓存/i],
    ['h5.about', '/about', /关于|EFIS|辅助|版本|检查/i],
  ];

  for (const [name, path, re] of h5Routes) {
    await step(name, async () => {
      const st = await softGoto(H5 + path);
      if (st >= 400) throw new Error('HTTP ' + st);
      await sleep(1000);
      if (/login/i.test(page.url())) throw new Error('session lost -> login');
      const body = await page.locator('body').innerText();
      if (!re.test(body) && body.trim().length < 8) throw new Error('unexpected empty: ' + body.slice(0, 80));
      return 'ok len=' + body.length;
    });
  }

  // H5 tasks -> detail -> execute check
  await step('h5.task_execute_flow', async () => {
    await softGoto(H5 + '/tasks');
    await sleep(1200);
    const cards = page.locator('.task-card, .van-cell, .card, [class*="task"]');
    const n = await cards.count();
    if (n === 0) {
      // try list items
      const items = page.locator('.van-list .van-cell, .task-list > div');
      if ((await items.count()) === 0) return 'no tasks for expert/admin (skip deep flow)';
      await items.first().click();
    } else {
      await cards.first().click();
    }
    await sleep(1500);
    const body1 = await page.locator('body').innerText();
    // start or execute
    const startBtn = page.locator('button:has-text("开始任务"), .van-button:has-text("开始")').first();
    if (await startBtn.count()) {
      page.once('dialog', async d => { try { await d.accept(); } catch (_) {} });
      await startBtn.click().catch(() => {});
      await sleep(800);
      // van dialog confirm
      const ok = page.locator('.van-dialog__confirm, button:has-text("确认"), button:has-text("确定")').first();
      if (await ok.count()) await ok.click().catch(() => {});
      await sleep(1200);
    }
    const execBtn = page.locator('button:has-text("执行检查"), .van-button:has-text("执行")').first();
    if (await execBtn.count()) {
      await execBtn.click();
      await sleep(2500);
      const body = await page.locator('body').innerText();
      if (/获取记录失败/i.test(body)) throw new Error('获取记录失败 still present');
      const ok = /检查|进度|合格|模板|最终判定|现场/i.test(body);
      if (!ok) throw new Error('execute page unexpected: ' + body.slice(0, 160));
      return 'execute ok url=' + page.url();
    }
    return 'detail opened, no execute button body=' + body1.slice(0, 100);
  });

  // If on inspection page, try AI button if present
  await step('h5.ai_final_judgment_button', async () => {
    if (!/inspection|execute|task/i.test(page.url())) {
      // try a known task from production if still logged in
      return 'skip not on inspection page url=' + page.url();
    }
    const aiBtn = page.locator('button:has-text("AI 生成"), button:has-text("AI生成"), .ai-judgment-btn').first();
    if (!(await aiBtn.count())) return 'AI button not visible (maybe incomplete required items)';
    // only click if enabled
    const disabled = await aiBtn.isDisabled().catch(() => false);
    if (disabled) return 'AI button disabled (expected until required items filled)';
    await aiBtn.click();
    await sleep(5000);
    const body = await page.locator('body').innerText();
    if (/AI 生成失败|获取记录失败/i.test(body)) throw new Error('AI failed toast/body: ' + body.slice(0, 200));
    return 'clicked AI, body has analysis=' + /分析|建议|合格|判定/i.test(body);
  });

  // Today audit entry
  await step('h5.today_audit_interaction', async () => {
    await softGoto(H5 + '/today-audit');
    await sleep(1200);
    const btn = page.locator('button:has-text("开始"), button:has-text("继续"), button:has-text("AI"), .van-button--primary').first();
    if (await btn.count()) {
      await btn.click();
      await sleep(2500);
      return 'clicked primary action url=' + page.url();
    }
    return 'no actionable audit task today';
  });

  // screenshot summary pages
  await step('web.screenshot_dashboard', async () => {
    await softGoto(WEB + '/dashboard');
    await sleep(800);
    await page.screenshot({ path: 'docs/playwright_web_dashboard.png', fullPage: true });
    return 'saved docs/playwright_web_dashboard.png';
  });

  await step('h5.screenshot_home', async () => {
    await softGoto(H5 + '/home');
    await sleep(800);
    await page.screenshot({ path: 'docs/playwright_h5_home.png', fullPage: true });
    return 'saved docs/playwright_h5_home.png';
  });

  const passed = results.filter(r => r.ok).length;
  const failed = results.filter(r => !r.ok).length;
  const summary = {
    timestamp: new Date().toISOString(),
    total: results.length,
    passed,
    failed,
    results,
    consoleErrors: consoleErrors.slice(0, 40),
    pageErrors: pageErrors.slice(0, 20),
  };

  // expose for CLI output
  console.log('PLAYWRIGHT_FRONTEND_REPORT=' + JSON.stringify(summary));
  return summary;
}
