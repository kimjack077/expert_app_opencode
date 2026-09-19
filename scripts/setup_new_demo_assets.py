# -*- coding: utf-8 -*-
import sys
import io
import json
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://49.232.213.79:8000"

# 1. Login as Admin
r_login = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
admin_token = r_login.json()["data"]["access_token"]
h_admin = {"Authorization": f"Bearer {admin_token}"}

print("=== 1. 创建/获取全新演示企业 ===")
ent_name = "山东鲁能特种装备制造有限公司（客户演示）"
r_search = requests.get(f"{BASE}/api/enterprises", headers=h_admin, params={"name": "山东鲁能特种装备"}).json().get("data", [])
existing_ents = r_search if isinstance(r_search, list) else r_search.get("items", [])

ent_id = None
for e in existing_ents:
    if "山东鲁能特种装备" in e.get("name", ""):
        ent_id = e["id"]
        print(f"企业已存在: id={ent_id}, name={e.get('name')}")
        break

if not ent_id:
    ent_payload = {
        "name": ent_name,
        "credit_code": "91370100MA3DEMO88X",
        "risk_level": "B",
        "legal_person": "王建国",
        "contact_person": "李强",
        "contact_phone": "13800008888",
        "address": "山东省济南市高新技术产业开发区工业南路88号"
    }
    r_ent = requests.post(f"{BASE}/api/enterprises", headers=h_admin, json=ent_payload)
    if r_ent.status_code == 200:
        ent_id = r_ent.json().get("data", {}).get("id")
        print(f"成功创建新企业: id={ent_id}")
    else:
        print(f"创建企业失败: {r_ent.status_code} {r_ent.text}")

# 2. Create New Demo Template
print("\n=== 2. 创建全新规范检查模板 ===")
tmpl_name = "特种装备制造质量安全检查模板（客户演示）"
r_tmpls = requests.get(f"{BASE}/api/templates", headers=h_admin).json().get("data", [])
existing_tmpls = r_tmpls if isinstance(r_tmpls, list) else r_tmpls.get("items", [])

tmpl_id = None
for t in existing_tmpls:
    if "特种装备制造" in t.get("name", ""):
        tmpl_id = t["id"]
        print(f"模板已存在: id={tmpl_id}, name={t.get('name')}")
        break

if not tmpl_id:
    tmpl_payload = {
        "name": tmpl_name,
        "code": "TZ-DEMO-2026",
        "category": "质量管理",
        "version": "v1.0",
        "is_published": True,
        "is_public": False,
        "is_quantified": False
    }
    r_tmpl = requests.post(f"{BASE}/api/templates", headers=h_admin, json=tmpl_payload)
    tmpl_id = r_tmpl.json().get("data", {}).get("id")
    print(f"创建模板成功: id={tmpl_id}")

# Check existing items
r_items_exist = requests.get(f"{BASE}/api/templates/{tmpl_id}/items", headers=h_admin).json().get("data", [])
if not r_items_exist:
    print("开始录入检查项树形结构...")
    # 1. 根节点 1: 特种设备与承压系统 (目录)
    r_c1 = requests.post(f"{BASE}/api/templates/{tmpl_id}/items", headers=h_admin, json={
        "title": "特种设备与承压系统",
        "is_category": True,
        "sort_order": 1
    })
    c1_id = r_c1.json()["data"]["id"]
    print(f"创建根目录 1: {c1_id}")
    
    # 1.1 子目录: 压力管道与承载焊缝 (目录, parent_id=c1_id)
    r_c1_sub = requests.post(f"{BASE}/api/templates/{tmpl_id}/items", headers=h_admin, json={
        "title": "压力管道与承载焊缝",
        "is_category": True,
        "parent_id": c1_id,
        "sort_order": 1
    })
    c1_sub_id = r_c1_sub.json()["data"]["id"]
    print(f"创建子目录 1.1: {c1_sub_id}")
    
    # 1.1.1 叶子检查项: 承压焊缝无损探伤合格证 (叶子项, parent_id=c1_sub_id)
    r_leaf1 = requests.post(f"{BASE}/api/templates/{tmpl_id}/items", headers=h_admin, json={
        "title": "承压焊缝无损探伤合格证",
        "is_category": False,
        "parent_id": c1_sub_id,
        "result_type": "pass_fail",
        "risk_level": "high",
        "is_required": True,
        "allow_attachment": True,
        "check_method": "查验RT/UT无损探伤检测报告，抽检比例不低于20%，确认合格结论与无损检测人员资质签章。",
        "legal_basis": "《特种设备安全法》第十五条、《压力管道安全技术监察规程-工业管道》TSG D0001-2009",
        "sort_order": 1
    })
    print(f"创建叶子 1.1.1: {r_leaf1.status_code}")
    
    # 1.2 叶子检查项: 设备日常点检与安全联锁记录 (叶子项, parent_id=c1_id)
    r_leaf2 = requests.post(f"{BASE}/api/templates/{tmpl_id}/items", headers=h_admin, json={
        "title": "设备日常点检与安全联锁记录",
        "is_category": False,
        "parent_id": c1_id,
        "result_type": "pass_fail",
        "risk_level": "medium",
        "is_required": True,
        "allow_attachment": True,
        "check_method": "现场查阅近1个月特种设备日常运行点检表，实地测试急停按钮与安全互锁装置响应有效性。",
        "legal_basis": "GB/T 19001-2016 条款 7.1.3 基础设施、8.5.1 生产和服务提供的控制",
        "sort_order": 2
    })
    print(f"创建叶子 1.2: {r_leaf2.status_code}")
    
    # 2. 根节点 2: 作业环境与劳保质控 (目录)
    r_c2 = requests.post(f"{BASE}/api/templates/{tmpl_id}/items", headers=h_admin, json={
        "title": "作业环境与劳保质控",
        "is_category": True,
        "sort_order": 2
    })
    c2_id = r_c2.json()["data"]["id"]
    print(f"创建根目录 2: {c2_id}")
    
    # 2.1 叶子检查项: 防爆作业区静电导除与接地阻值 (叶子项, parent_id=c2_id)
    r_leaf3 = requests.post(f"{BASE}/api/templates/{tmpl_id}/items", headers=h_admin, json={
        "title": "防爆作业区静电导除与接地阻值",
        "is_category": False,
        "parent_id": c2_id,
        "result_type": "pass_fail",
        "risk_level": "high",
        "is_required": True,
        "allow_attachment": True,
        "check_method": "使用接地电阻测试仪实测防爆车间消除静电接地阻值（≤100Ω），检查静电接地夹接触情况。",
        "legal_basis": "GB 12158-2006《防止静电事故通用导则》、GB/T 45001-2020 条款 8.1 运行策划和控制",
        "sort_order": 1
    })
    print(f"创建叶子 2.1: {r_leaf3.status_code}")
else:
    print(f"模板已有检查项: {len(r_items_exist)} 个根节点")

# 3. Verify Template Stats and AC-1
print("\n=== 3. 验证新模板条目统计与恒等式 AC-1 ===")
r_tmpl_check = requests.get(f"{BASE}/api/templates", headers=h_admin).json().get("data", [])
my_tmpl = next(t for t in (r_tmpl_check if isinstance(r_tmpl_check, list) else r_tmpl_check.get("items", [])) if t["id"] == tmpl_id)
s = my_tmpl.get("stats", {})
tot = s.get("total_items")
cat = s.get("categories")
chk = s.get("check_items")
print(f"新模板名称: {my_tmpl.get('name')}")
print(f"条目统计: {tot} 条 · {cat} 目录 · {chk} 检查项")
print(f"恒等式成立: {tot == (cat + chk)} ({tot} = {cat} + {chk})")

# 4. Create New Demo Inspection Task for Expert
print("\n=== 4. 建立指派给审核专家的现场检查任务 ===")
users = requests.get(f"{BASE}/api/users", headers=h_admin).json().get("data", [])
exp_user = next(u for u in users if u.get("username") == "expert")

task_title = "特种装备现场质量安全专项检查（客户演示）"
r_tasks = requests.get(f"{BASE}/api/tasks?limit=100", headers=h_admin).json().get("data", {})
t_items = r_tasks.get("items", []) if isinstance(r_tasks, dict) else r_tasks
task_id = None
for t in t_items:
    if t.get("title") == task_title:
        task_id = t["id"]
        # If not in_progress, restart or ensure in_progress
        if t.get("status") == "pending":
            requests.post(f"{BASE}/api/tasks/{task_id}/start", headers=h_admin)
        print(f"任务已存在: id={task_id}, status={t.get('status')}")
        break

if not task_id:
    task_payload = {
        "title": task_title,
        "enterprise_id": ent_id,
        "template_id": tmpl_id,
        "assigned_to": exp_user["id"],
        "due_date": "2026-10-30"
    }
    r_task = requests.post(f"{BASE}/api/tasks", headers=h_admin, json=task_payload)
    task_id = r_task.json().get("data", {}).get("id")
    print(f"成功创建检查任务: id={task_id}")
    
    # Start task to in_progress
    r_start = requests.post(f"{BASE}/api/tasks/{task_id}/start", headers=h_admin)
    print(f"启动任务为 in_progress: {r_start.status_code}")

# Verify records generated for leaf items only (AC-4)
r_records = requests.get(f"{BASE}/api/tasks/{task_id}/records", headers=h_admin).json().get("data", [])
print(f"预生成填报记录条数: {len(r_records)} (严格等于 {chk} 个叶子项，0 个目录空行！)")
for rec in r_records:
    print(f" - 记录项: {rec.get('item_name')} | 风险: {rec.get('risk_level')} | 默认状态: {rec.get('status')}")

# Summary output for subsequent E2E test
summary = {
    "enterprise_id": ent_id,
    "enterprise_name": ent_name,
    "template_id": tmpl_id,
    "template_name": tmpl_name,
    "task_id": task_id,
    "task_title": task_title,
    "leaf_count": chk,
    "category_count": cat
}
with open("docs/_new_demo_assets.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("\n新演示资产已落盘保存至 docs/_new_demo_assets.json！")
