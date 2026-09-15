/**
 * capture_all_screens.js
 * 真实登录 Web 端与 H5 端，抓取所有功能模块的高清真实界面截图
 */
const { chromium } = require('C:/Users/yang/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core');
const path = require('path');
const fs = require('fs');

const BROWSER_EXE = 'C:/Users/yang/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const TARGET_DIR = path.resolve(__dirname, 'web-admin/public/docs-assets');
fs.mkdirSync(TARGET_DIR, { recursive: true });

// 优先使用远端线上服务（数据最完整丰富），也可 fallback 本地
const BASE_WEB = 'http://49.232.213.79:3000';
const BASE_H5 = 'http://49.232.213.79:5173/h5';

async function waitText(page, kw, maxMs = 15000) {
  const t0 = Date.now();
  while (Date.now() - t0 < maxMs) {
    const text = await page.evaluate(() => document.body.innerText).catch(() => '');
    if (text.includes(kw)) return true;
    await page.waitForTimeout(400);
  }
  return false;
}

(async () => {
  console.log('🚀 启动 Chromium 浏览器...');
  const browser = await chromium.launch({
    headless: true,
    executablePath: BROWSER_EXE,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    // ==========================================
    // 1. H5 移动端全流程截图 (iPhone 14 视口 390x844)
    // ==========================================
    console.log('📱 正在抓取 H5 移动端界面...');
    const h5Context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
      locale: 'zh-CN',
      deviceScaleFactor: 2,
    });
    const h5Page = await h5Context.newPage();

    // 1.1 H5 登录页
    await h5Page.goto(`${BASE_H5}/login`, { waitUntil: 'networkidle' });
    await h5Page.waitForTimeout(1000);
    await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_01_login.png') });
    console.log('  ✓ h5_01_login.png');

    // 登录 expert (现场专家/审核员)
    const expertBtn = h5Page.locator('button', { hasText: '专家' }).first();
    if (await expertBtn.count() > 0) {
      await expertBtn.click();
    } else {
      await h5Page.fill('input[type="text"]', 'expert');
      await h5Page.fill('input[type="password"]', 'expert123');
    }
    const submitBtn = h5Page.locator('button', { hasText: '登录' }).first();
    if (await submitBtn.count() > 0) {
      await submitBtn.click();
    }
    await h5Page.waitForTimeout(2500);

    // 1.2 H5 首页 / 今日审核
    await h5Page.goto(`${BASE_H5}/today-audit`, { waitUntil: 'networkidle' }).catch(() => {});
    await h5Page.waitForTimeout(2000);
    await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_02_today_audit.png') });
    console.log('  ✓ h5_02_today_audit.png');

    // 1.3 H5 审核任务列表
    await h5Page.goto(`${BASE_H5}/tasks`, { waitUntil: 'networkidle' }).catch(() => {});
    await h5Page.waitForTimeout(2000);
    await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_03_tasks_list.png') });
    console.log('  ✓ h5_03_tasks_list.png');

    // 1.4 H5 任务详情 / 现场检查执行
    // 点击第一个任务进入详情
    const taskCard = h5Page.locator('.van-card, .task-card, .van-cell, [class*="task"]').first();
    if (await taskCard.count() > 0) {
      await taskCard.click().catch(() => {});
      await h5Page.waitForTimeout(2000);
      await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_04_task_detail.png') });
      console.log('  ✓ h5_04_task_detail.png');

      // 寻找进入检查执行的按钮
      const execBtn = h5Page.locator('button', { hasText: /开始检查|继续检查|执行/ }).first();
      if (await execBtn.count() > 0) {
        await execBtn.click().catch(() => {});
        await h5Page.waitForTimeout(2500);
        await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_05_inspection_execution.png') });
        console.log('  ✓ h5_05_inspection_execution.png');
      }
    }

    // 1.5 H5 现场 AI 审核会话 (AiAuditSession)
    await h5Page.goto(`${BASE_H5}/ai-audit`, { waitUntil: 'networkidle' }).catch(() => {});
    await h5Page.waitForTimeout(2000);
    // 如果没有 /ai-audit，尝试找带 AI 标识的按钮或者通过路由
    if (h5Page.url().includes('ai')) {
      await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_07_ai_audit_session.png') });
      console.log('  ✓ h5_07_ai_audit_session.png');
    }

    // 1.6 H5 审核记录列表
    await h5Page.goto(`${BASE_H5}/records`, { waitUntil: 'networkidle' }).catch(() => {});
    await h5Page.waitForTimeout(2000);
    await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_09_records_list.png') });
    console.log('  ✓ h5_09_records_list.png');

    // 1.7 H5 个人中心 / 离线管理
    await h5Page.goto(`${BASE_H5}/profile`, { waitUntil: 'networkidle' }).catch(() => {});
    await h5Page.waitForTimeout(1500);
    await h5Page.screenshot({ path: path.join(TARGET_DIR, 'h5_12_profile_offline.png') });
    console.log('  ✓ h5_12_profile_offline.png');

    await h5Context.close();

    // ==========================================
    // 2. Web 管理端全流程截图 (1440x900)
    // ==========================================
    console.log('💻 正在抓取 Web 管理端界面...');
    const webContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: 'zh-CN',
    });
    const webPage = await webContext.newPage();

    // 2.1 Web 登录界面
    await webPage.goto(`${BASE_WEB}/login`, { waitUntil: 'networkidle' });
    await webPage.waitForTimeout(1000);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_01_login.png') });
    console.log('  ✓ web_01_login.png');

    // 登录 admin
    const adminCard = webPage.locator('button', { hasText: 'admin / admin123' }).first();
    if (await adminCard.count() > 0) {
      await adminCard.click();
      await webPage.locator('button', { hasText: '立即登录' }).first().click();
    } else {
      await webPage.fill('input[id*="username"]', 'admin');
      await webPage.fill('input[id*="password"]', 'admin123');
      await webPage.locator('button[type="submit"], button:has-text("登录")').first().click();
    }
    await webPage.waitForURL(/dashboard/, { timeout: 15000 }).catch(() => {});
    await webPage.waitForTimeout(2000);

    // 2.2 工作台 Dashboard
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_02_dashboard.png') });
    console.log('  ✓ web_02_dashboard.png');

    // 2.3 我的审核任务
    await webPage.goto(`${BASE_WEB}/my-audit-tasks`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_03_my_tasks.png') });
    console.log('  ✓ web_03_my_tasks.png');

    // 2.4 审核项目列表
    await webPage.goto(`${BASE_WEB}/audit-projects`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_04_audit_projects.png') });
    console.log('  ✓ web_04_audit_projects.png');

    // 2.5 新建项目页
    await webPage.goto(`${BASE_WEB}/audit-projects/create`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_05_project_create.png') });
    console.log('  ✓ web_05_project_create.png');

    // 2.6 项目详情全景及各个 Tab (点击进入第一个审核项目)
    await webPage.goto(`${BASE_WEB}/audit-projects`, { waitUntil: 'networkidle' });
    await webPage.waitForTimeout(1500);
    const viewBtn = webPage.locator('a, button', { hasText: /查看|详情/ }).first();
    if (await viewBtn.count() > 0) {
      await viewBtn.click().catch(() => {});
      await webPage.waitForTimeout(2000);
      // 概览
      await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_06_project_overview.png') });
      console.log('  ✓ web_06_project_overview.png');

      // 切换 Tab: 审核组 / 团队
      const teamTab = webPage.locator('.ant-tabs-tab', { hasText: /审核组|团队/ }).first();
      if (await teamTab.count() > 0) {
        await teamTab.click();
        await webPage.waitForTimeout(1000);
        await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_07_project_team.png') });
        console.log('  ✓ web_07_project_team.png');
      }

      // 切换 Tab: 审核计划
      const planTab = webPage.locator('.ant-tabs-tab', { hasText: /计划|日程/ }).first();
      if (await planTab.count() > 0) {
        await planTab.click();
        await webPage.waitForTimeout(1000);
        await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_08_project_plan.png') });
        console.log('  ✓ web_08_project_plan.png');
      }

      // 切换 Tab: 会议管理
      const meetTab = webPage.locator('.ant-tabs-tab', { hasText: /会议/ }).first();
      if (await meetTab.count() > 0) {
        await meetTab.click();
        await webPage.waitForTimeout(1000);
        await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_09_project_meetings.png') });
        console.log('  ✓ web_09_project_meetings.png');
      }

      // 切换 Tab: 现场检查记录
      const recTab = webPage.locator('.ant-tabs-tab', { hasText: /现场记录|检查记录/ }).first();
      if (await recTab.count() > 0) {
        await recTab.click();
        await webPage.waitForTimeout(1000);
        await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_10_field_records.png') });
        console.log('  ✓ web_10_field_records.png');
      }

      // 切换 Tab: 不符合项
      const ncTab = webPage.locator('.ant-tabs-tab', { hasText: /不符合项|整改/ }).first();
      if (await ncTab.count() > 0) {
        await ncTab.click();
        await webPage.waitForTimeout(1000);
        await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_12_nonconformities.png') });
        console.log('  ✓ web_12_nonconformities.png');
      }

      // 展开智审 Agent 侧边面板
      const agentBtn = webPage.locator('button, [class*="agent"]', { hasText: /智审 Agent|AI/ }).first();
      if (await agentBtn.count() > 0) {
        await agentBtn.click().catch(() => {});
        await webPage.waitForTimeout(1500);
        await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_11_ai_agent.png') });
        console.log('  ✓ web_11_ai_agent.png');
      }
    }

    // 2.7 检查记录与报告
    await webPage.goto(`${BASE_WEB}/records`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_13_records_reports.png') });
    console.log('  ✓ web_13_records_reports.png');

    // 2.8 检查模板
    await webPage.goto(`${BASE_WEB}/templates`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_14_templates.png') });
    console.log('  ✓ web_14_templates.png');

    // 2.9 知识库
    await webPage.goto(`${BASE_WEB}/knowledge`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_16_knowledge.png') });
    console.log('  ✓ web_16_knowledge.png');

    // 2.10 企业管理
    await webPage.goto(`${BASE_WEB}/enterprises`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_17_enterprises.png') });
    console.log('  ✓ web_17_enterprises.png');

    // 2.11 用户管理
    await webPage.goto(`${BASE_WEB}/users`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_18_users.png') });
    console.log('  ✓ web_18_users.png');

    // 2.12 统计分析
    await webPage.goto(`${BASE_WEB}/analytics`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_19_analytics.png') });
    console.log('  ✓ web_19_analytics.png');

    // 2.13 在线文档中心自身
    await webPage.goto(`${BASE_WEB}/docs`, { waitUntil: 'networkidle' }).catch(() => {});
    await webPage.waitForTimeout(1500);
    await webPage.screenshot({ path: path.join(TARGET_DIR, 'web_20_online_docs.png') });
    console.log('  ✓ web_20_online_docs.png');

    await webContext.close();
    console.log('🎉 所有真实页面截图抓取完毕！');
  } catch (err) {
    console.error('抓取出现错误:', err);
  } finally {
    await browser.close();
  }
})();
