# -*- coding: utf-8 -*-
"""
EFIS 全功能增删改查 (CRUD) 全景自动化测试套件
结合 TypeSafe AI System One 进行结构化分诊与严重度裁决
"""
import sys
import io
import json
import time
import uuid
import requests

# Force utf-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://49.232.213.79:8000"
TIMEOUT = 30.0
MARK = f"CRUD-{int(time.time())%100000}"
TYPESAFE_KEY = "apikey_248d67c3d544cad4c14adf7437ac8bd2bea_a4f8fc02303c1bf7ac3d2f28a2b6c732cd70014c597f3dc97c25f3d6bb1f6116"

results = []

def record(case_id, name, module, ok, expected, actual, severity="P2", note=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {case_id} | {name} | Expected: {expected} | Actual: {str(actual)[:120]}")
    results.append({
        "case_id": case_id,
        "name": name,
        "module": module,
        "ok": ok,
        "expected": expected,
        "actual": str(actual),
        "severity": severity,
        "note": note
    })

print(f"============================================================")
print(f"  EFIS 全功能增删改查 (CRUD) 全景测试启动 | 批次: {MARK}")
print(f"  被测环境: {BASE}")
print(f"============================================================")

# ==============================================================================
# 0. 认证准备
# ==============================================================================
print("\n--- [准备] 获取多角色令牌 ---")
try:
    r_adm = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=TIMEOUT)
    token_admin = r_adm.json()["data"]["access_token"]
    user_admin = r_adm.json()["data"]["user"]
    h_admin = {"Authorization": f"Bearer {token_admin}"}
    print("✅ 管理员 admin 登录成功")
except Exception as e:
    print("❌ 管理员登录失败:", e)
    sys.exit(1)

try:
    r_exp = requests.post(f"{BASE}/api/auth/login", json={"username": "expert", "password": "expert123"}, timeout=TIMEOUT)
    token_expert = r_exp.json()["data"]["access_token"]
    user_expert = r_exp.json()["data"]["user"]
    h_expert = {"Authorization": f"Bearer {token_expert}"}
    print("✅ 审核专家 expert 登录成功")
except Exception as e:
    print("❌ 专家登录失败:", e)
    token_expert = None
    h_expert = {}

try:
    r_aud = requests.post(f"{BASE}/api/auth/login", json={"username": "auditor_chen", "password": "expert123"}, timeout=TIMEOUT)
    token_auditor = r_aud.json()["data"]["access_token"]
    h_auditor = {"Authorization": f"Bearer {token_auditor}"}
    print("✅ 普通审核员 auditor_chen 登录成功")
except Exception as e:
    token_auditor = None
    h_auditor = {}

# ==============================================================================
# 1. 认证与用户管理域 (Auth & Users CRUD)
# ==============================================================================
print("\n--- 模块一：认证与用户管理域 (Users CRUD) ---")
test_user_id = None
test_uname = f"u_{MARK.lower()}"
try:
    r = requests.post(f"{BASE}/api/users", headers=h_admin, json={
        "username": test_uname,
        "password": "Password123!",
        "full_name": f"测试审核员_{MARK}",
        "role": "auditor",
        "phone": "13912340001",
        "email": f"{test_uname}@example.com"
    }, timeout=TIMEOUT)
    test_user_id = r.json().get("data", {}).get("id")
    record("CRUD-U-01", "用户[增] 创建新审核员", "User", r.status_code == 200 and bool(test_user_id), "200 & user_id", f"code={r.status_code}, id={test_user_id}", "P1")
except Exception as e:
    record("CRUD-U-01", "用户[增] 创建新审核员", "User", False, "200", str(e), "P1")

try:
    r = requests.get(f"{BASE}/api/users", headers=h_admin, timeout=TIMEOUT)
    users = r.json().get("data", [])
    found_in_list = any(u.get("username") == test_uname for u in users) if test_uname else False
    record("CRUD-U-02", "用户[查] 管理员获取用户列表", "User", r.status_code == 200 and found_in_list, "200 & 包含新用户", f"count={len(users)}, found={found_in_list}", "P1")
except Exception as e:
    record("CRUD-U-02", "用户[查] 用户列表", "User", False, "200", str(e), "P1")

if test_user_id:
    try:
        r = requests.get(f"{BASE}/api/users/{test_user_id}", headers=h_admin, timeout=TIMEOUT)
        u_data = r.json().get("data", {})
        record("CRUD-U-03", "用户[查] 获取用户详情", "User", r.status_code == 200 and u_data.get("username") == test_uname, "200 & 用户画像", f"code={r.status_code}, name={u_data.get('full_name')}", "P2")
    except Exception as e:
        record("CRUD-U-03", "用户[查] 用户详情", "User", False, "200", str(e), "P2")

if test_user_id:
    try:
        r = requests.put(f"{BASE}/api/users/{test_user_id}", headers=h_admin, json={
            "phone": "13999998888",
            "full_name": f"已修改测试员_{MARK}"
        }, timeout=TIMEOUT)
        r_re = requests.get(f"{BASE}/api/users/{test_user_id}", headers=h_admin, timeout=TIMEOUT)
        re_name = r_re.json().get("data", {}).get("full_name")
        record("CRUD-U-04", "用户[改] 修改手机与姓名 (full_name)", "User", r.status_code == 200 and re_name == f"已修改测试员_{MARK}", "200 & full_name已更新", f"update_code={r.status_code}, re_name={re_name}", "P2")
    except Exception as e:
        record("CRUD-U-04", "用户[改] 修改信息", "User", False, "200", str(e), "P2")

if test_user_id:
    try:
        r_del = requests.delete(f"{BASE}/api/users/{test_user_id}", headers=h_admin, timeout=TIMEOUT)
        r_chk = requests.get(f"{BASE}/api/users/{test_user_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-U-05", "用户[删] 软删除用户并验证404排除", "User", r_del.status_code == 200 and r_chk.status_code == 404, "del=200, recheck=404", f"del={r_del.status_code}, chk={r_chk.status_code}", "P2")
    except Exception as e:
        record("CRUD-U-05", "用户[删] 软删除", "User", False, "del=200", str(e), "P2")

# ==============================================================================
# 2. 行业分类全景域 (Industries CRUD)
# ==============================================================================
print("\n--- 模块二：行业分类全景域 (Industries CRUD) ---")
ind_parent_id = None
ind_child_id = None
p_code = f"IND_P_{MARK}"
c_code = f"IND_C_{MARK}"

try:
    r = requests.post(f"{BASE}/api/industries", headers=h_admin, json={"name": f"测试门类_{MARK}", "code": p_code}, timeout=TIMEOUT)
    ind_parent_id = r.json().get("data", {}).get("id")
    record("CRUD-IND-01", "行业[增] 创建大类门类", "Industry", r.status_code == 200 and bool(ind_parent_id), "200 & id", f"code={r.status_code}, id={ind_parent_id}", "P2")
except Exception as e:
    record("CRUD-IND-01", "行业[增] 创建大类", "Industry", False, "200", str(e), "P2")

if ind_parent_id:
    try:
        r = requests.post(f"{BASE}/api/industries", headers=h_admin, json={"name": f"测试子类_{MARK}", "code": c_code, "parent_id": ind_parent_id}, timeout=TIMEOUT)
        ind_child_id = r.json().get("data", {}).get("id")
        record("CRUD-IND-02", "行业[增] 创建下属子分类", "Industry", r.status_code == 200 and bool(ind_child_id), "200 & id", f"code={r.status_code}, id={ind_child_id}", "P2")
    except Exception as e:
        record("CRUD-IND-02", "行业[增] 创建子类", "Industry", False, "200", str(e), "P2")

try:
    r = requests.get(f"{BASE}/api/industries/tree", headers=h_admin, timeout=TIMEOUT)
    tree = r.json().get("data", [])
    record("CRUD-IND-03", "行业[查] 获取行业分类全景树", "Industry", r.status_code == 200 and len(tree) >= 10, "200 & tree", f"count={len(tree)}", "P1")
except Exception as e:
    record("CRUD-IND-03", "行业[查] 行业树", "Industry", False, "200", str(e), "P1")

if ind_parent_id:
    try:
        r = requests.put(f"{BASE}/api/industries/{ind_parent_id}", headers=h_admin, json={"name": f"更新门类_{MARK}"}, timeout=TIMEOUT)
        record("CRUD-IND-04", "行业[改] 更新行业门类名称", "Industry", r.status_code == 200, "200 OK", r.status_code, "P2")
    except Exception as e:
        record("CRUD-IND-04", "行业[改] 更新名称", "Industry", False, "200", str(e), "P2")

if ind_parent_id and ind_child_id:
    try:
        r_del_p = requests.delete(f"{BASE}/api/industries/{ind_parent_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-IND-05", "行业[删] 有子类时删除父类拦截保护 (P2-02)", "Industry", r_del_p.status_code == 400, "400 Bad Request", f"status={r_del_p.status_code}, text={r_del_p.text[:60]}", "P2")
    except Exception as e:
        record("CRUD-IND-05", "行业[删] 父类保护", "Industry", False, "400", str(e), "P2")

if ind_child_id:
    try:
        r_del_c = requests.delete(f"{BASE}/api/industries/{ind_child_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-IND-06", "行业[删] 删除子分类节点", "Industry", r_del_c.status_code == 200, "200 OK", r_del_c.status_code, "P2")
    except Exception as e:
        record("CRUD-IND-06", "行业[删] 删除子类", "Industry", False, "200", str(e), "P2")

if ind_parent_id:
    try:
        r_del_p2 = requests.delete(f"{BASE}/api/industries/{ind_parent_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-IND-07", "行业[删] 空父类删除成功", "Industry", r_del_p2.status_code == 200, "200 OK", r_del_p2.status_code, "P2")
    except Exception as e:
        record("CRUD-IND-07", "行业[删] 空父类删除", "Industry", False, "200", str(e), "P2")

# ==============================================================================
# 3. 企业档案与子资源全景域 (Enterprise, Qual, Rect, Prod, Risk)
# ==============================================================================
print("\n--- 模块三：企业档案及全量子资源域 (Enterprise Sub-resources CRUD) ---")
test_ent_id = None
credit_code = f"91370100{int(time.time())%100000000:08d}A"

try:
    r = requests.post(f"{BASE}/api/enterprises", headers=h_admin, json={
        "name": f"（E2E全功能测试）测试装备制造公司_{MARK}",
        "credit_code": credit_code,
        "legal_person": f"张法人_{MARK}",
        "contact_phone": "13800009999",
        "risk_level": "B",
        "address": "济南市高新区科技园区88号"
    }, timeout=TIMEOUT)
    test_ent_id = r.json().get("data", {}).get("id")
    record("CRUD-ENT-01", "企业[增] 新建企业档案", "Enterprise", r.status_code == 200 and bool(test_ent_id), "200 & id", f"code={r.status_code}, id={test_ent_id}", "P1")
except Exception as e:
    record("CRUD-ENT-01", "企业[增] 新建企业", "Enterprise", False, "200", str(e), "P1")

if test_ent_id:
    try:
        r = requests.get(f"{BASE}/api/enterprises/{test_ent_id}", headers=h_admin, timeout=TIMEOUT)
        e_data = r.json().get("data", {})
        record("CRUD-ENT-02", "企业[查] 获取企业详情全景画像", "Enterprise", r.status_code == 200 and e_data.get("credit_code") == credit_code, "200 & credit_code一致", f"code={r.status_code}, name={e_data.get('name')}", "P1")
    except Exception as e:
        record("CRUD-ENT-02", "企业[查] 详情", "Enterprise", False, "200", str(e), "P1")

if test_ent_id:
    try:
        r = requests.put(f"{BASE}/api/enterprises/{test_ent_id}", headers=h_admin, json={
            "legal_person": f"王新法人_{MARK}",
            "contact_phone": "13988887777"
        }, timeout=TIMEOUT)
        record("CRUD-ENT-03", "企业[改] 更新企业联系人与法人信息", "Enterprise", r.status_code == 200, "200 OK", r.status_code, "P2")
    except Exception as e:
        record("CRUD-ENT-03", "企业[改] 更新企业", "Enterprise", False, "200", str(e), "P2")

# --- 企业资质 (Qualifications CRUD) ---
test_qual_id = None
if test_ent_id:
    try:
        r_qual = requests.post(f"{BASE}/api/enterprises/{test_ent_id}/qualifications", headers=h_admin, json={
            "enterprise_id": test_ent_id,
            "qual_type": "质量管理体系认证 (ISO 9001)",
            "cert_no": f"CERT-Q-{MARK}",
            "product_name": "特种承压设备及管道",
            "issue_authority": "中国质量认证中心 (CQC)",
            "valid_from": "2024-01-01",
            "valid_until": "2027-01-01"
        }, timeout=TIMEOUT)
        test_qual_id = r_qual.json().get("data", {}).get("id")
        record("CRUD-QUAL-01", "资质[增] 新增企业体系认证证书资质", "Qualification", r_qual.status_code == 200 and bool(test_qual_id), "200 & qual_id", f"code={r_qual.status_code}, id={test_qual_id}", "P1")
    except Exception as e:
        record("CRUD-QUAL-01", "资质[增] 新增资质", "Qualification", False, "200", str(e), "P1")

    try:
        r_qlist = requests.get(f"{BASE}/api/enterprises/{test_ent_id}/qualifications", headers=h_admin, timeout=TIMEOUT)
        qlist = r_qlist.json().get("data", [])
        has_cert = any(q.get("cert_no") == f"CERT-Q-{MARK}" for q in qlist)
        record("CRUD-QUAL-02", "资质[查] 查询企业资质列表", "Qualification", r_qlist.status_code == 200 and has_cert, "200 & 包含新资质", f"count={len(qlist)}, has_cert={has_cert}", "P1")
    except Exception as e:
        record("CRUD-QUAL-02", "资质[查] 资质列表", "Qualification", False, "200", str(e), "P1")

    if test_qual_id:
        try:
            r_qup = requests.put(f"{BASE}/api/enterprises/qualifications/{test_qual_id}", headers=h_admin, json={
                "valid_until": "2028-01-01",
                "product_name": "特种承压设备及超导管道"
            }, timeout=TIMEOUT)
            record("CRUD-QUAL-03", "资质[改] 更新企业资质有效期与产品范围", "Qualification", r_qup.status_code == 200, "200 OK", r_qup.status_code, "P2")
        except Exception as e:
            record("CRUD-QUAL-03", "资质[改] 更新资质", "Qualification", False, "200", str(e), "P2")

    if test_qual_id:
        try:
            r_qdel = requests.delete(f"{BASE}/api/enterprises/qualifications/{test_qual_id}", headers=h_admin, timeout=TIMEOUT)
            r_qre = requests.get(f"{BASE}/api/enterprises/{test_ent_id}/qualifications", headers=h_admin, timeout=TIMEOUT)
            qlist_re = r_qre.json().get("data", [])
            has_deleted = any(q.get("id") == test_qual_id for q in qlist_re)
            record("CRUD-QUAL-04", "资质[删] 软删除企业资质并确认排除", "Qualification", r_qdel.status_code == 200 and not has_deleted, "del=200, excluded", f"del={r_qdel.status_code}, still_exists={has_deleted}", "P2")
        except Exception as e:
            record("CRUD-QUAL-04", "资质[删] 删除资质", "Qualification", False, "200", str(e), "P2")

# --- 企业产品 (Products CRUD) ---
if test_ent_id:
    try:
        r_prod = requests.post(f"{BASE}/api/enterprises/{test_ent_id}/products", headers=h_admin, json={
            "enterprise_id": test_ent_id,
            "name": f"承压锅炉特种管道_{MARK}",
            "category": "压力容器及管道",
            "specification": "GL-2026-X",
            "annual_output": 5000.0,
            "output_unit": "米"
        }, timeout=TIMEOUT)
        record("CRUD-PROD-01", "产品[增] 新增受审核企业主要产品", "Product", r_prod.status_code == 200, "200 OK", r_prod.status_code, "P2")
    except Exception as e:
        record("CRUD-PROD-01", "产品[增] 新增产品", "Product", False, "200", str(e), "P2")

    try:
        r_plist = requests.get(f"{BASE}/api/enterprises/{test_ent_id}/products", headers=h_admin, timeout=TIMEOUT)
        plist = r_plist.json().get("data", [])
        record("CRUD-PROD-02", "产品[查] 查询企业产品清单", "Product", r_plist.status_code == 200 and len(plist) >= 1, "200 & products", f"count={len(plist)}", "P2")
    except Exception as e:
        record("CRUD-PROD-02", "产品[查] 产品清单", "Product", False, "200", str(e), "P2")

# --- 企业整改台账 (Rectifications CRUD) ---
test_rect_id = None
if test_ent_id:
    try:
        r_rect = requests.post(f"{BASE}/api/enterprises/rectifications/", headers=h_admin, json={
            "enterprise_id": test_ent_id,
            "issue_description": f"焊接车间未按规定佩戴防静电劳保用品_{MARK}",
            "rectification_requirement": "统一组织防爆车间穿戴规范培训，换发防静电工服",
            "deadline": "2026-10-15"
        }, timeout=TIMEOUT)
        test_rect_id = r_rect.json().get("data", {}).get("id")
        record("CRUD-RECT-01", "整改[增] 开具并登记企业现场整改单", "Rectification", r_rect.status_code == 200 and bool(test_rect_id), "200 & rect_id", f"code={r_rect.status_code}, id={test_rect_id}", "P1")
    except Exception as e:
        record("CRUD-RECT-01", "整改[增] 新增整改", "Rectification", False, "200", str(e), "P1")

    try:
        r_rlist = requests.get(f"{BASE}/api/enterprises/rectifications/?enterprise_id={test_ent_id}", headers=h_admin, timeout=TIMEOUT)
        rlist = r_rlist.json().get("data", [])
        record("CRUD-RECT-02", "整改[查] 按企业过滤整改台账列表", "Rectification", r_rlist.status_code == 200 and len(rlist) >= 1, "200 & list", f"count={len(rlist)}", "P1")
    except Exception as e:
        record("CRUD-RECT-02", "整改[查] 整改列表", "Rectification", False, "200", str(e), "P1")

    if test_rect_id:
        try:
            r_rup = requests.put(f"{BASE}/api/enterprises/rectifications/{test_rect_id}", headers=h_admin, json={
                "rectification_result": "培训已完成，发放全套检验合格合格证与照片",
                "status": "submitted"
            }, timeout=TIMEOUT)
            record("CRUD-RECT-03", "整改[改] 补充整改措施与提交验收", "Rectification", r_rup.status_code == 200, "200 OK", r_rup.status_code, "P2")
        except Exception as e:
            record("CRUD-RECT-03", "整改[改] 更新整改", "Rectification", False, "200", str(e), "P2")

    if test_rect_id:
        try:
            r_rev = requests.post(f"{BASE}/api/enterprises/rectifications/{test_rect_id}/review?status=approved&rectification_result=现场抽查合格，予以通过关闭", headers=h_admin, timeout=TIMEOUT)
            rev_ok = (r_rev.status_code == 200 and r_rev.json().get("data", {}).get("status") == "approved")
            record("CRUD-RECT-04", "整改[审] 审核员验收整改并闭环流转 approved", "Rectification", rev_ok, "200 & approved", f"code={r_rev.status_code}, status={r_rev.json().get('data', {}).get('status')}", "P1")
        except Exception as e:
            record("CRUD-RECT-04", "整改[审] 验收整改", "Rectification", False, "200", str(e), "P1")

if test_ent_id:
    try:
        r_risk = requests.get(f"{BASE}/api/enterprises/{test_ent_id}/risk-profile", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-RISK-01", "画像[查] 获取企业动态风险等级与历史体检画像", "Enterprise", r_risk.status_code == 200, "200 OK", f"code={r_risk.status_code}, keys={list(r_risk.json().get('data', {}).keys())}", "P2")
    except Exception as e:
        record("CRUD-RISK-01", "画像[查] 风险画像", "Enterprise", False, "200", str(e), "P2")

# ==============================================================================
# 4. 检查模板与树形条目细粒度全景域 (Templates & Items CRUD)
# ==============================================================================
print("\n--- 模块四：检查模板与树形条目细粒度全景域 (Templates & Items CRUD) ---")
test_tmpl_id = None

try:
    r_tc = requests.post(f"{BASE}/api/templates", headers=h_admin, json={
        "name": f"（E2E全功能测试）特种承压设备检验模板_{MARK}",
        "category": "特种设备",
        "description": "用于全功能增删改查测试之专用模板",
        "standard_codes": ["Q", "S"],
        "version": "1.0"
    }, timeout=TIMEOUT)
    test_tmpl_id = r_tc.json().get("data", {}).get("id")
    record("CRUD-TMPL-01", "模板[增] 创建新检查模板草稿", "Template", r_tc.status_code == 200 and bool(test_tmpl_id), "200 & tmpl_id", f"code={r_tc.status_code}, id={test_tmpl_id}", "P1")
except Exception as e:
    record("CRUD-TMPL-01", "模板[增] 创建模板", "Template", False, "200", str(e), "P1")

if test_tmpl_id:
    try:
        r_tlist = requests.get(f"{BASE}/api/templates", headers=h_admin, timeout=TIMEOUT)
        tmpls = r_tlist.json().get("data", [])
        my_t = next((t for t in tmpls if t.get("id") == test_tmpl_id), None)
        stats = my_t.get("stats", {}) if my_t else {}
        stat_ok = (stats.get("total_items") == 0 and stats.get("categories") == 0 and stats.get("check_items") == 0)
        record("CRUD-TMPL-02", "模板[查] 空模板初始统计恒等式 0=0+0 (AC-1)", "Template", stat_ok, "0条·0目录·0检查项", f"stats={stats}", "P1")
    except Exception as e:
        record("CRUD-TMPL-02", "模板[查] 空模板统计", "Template", False, "0=0+0", str(e), "P1")

test_cat_id = None
test_leaf_id = None
if test_tmpl_id:
    try:
        r_ic1 = requests.post(f"{BASE}/api/templates/{test_tmpl_id}/items", headers=h_admin, json={
            "title": f"1. 管道焊缝与探伤分类_{MARK}",
            "is_category": True,
            "sort_order": 1
        }, timeout=TIMEOUT)
        test_cat_id = r_ic1.json().get("data", {}).get("id")
        record("CRUD-ITEM-01", "条目[增] 创建一级分类目录节点", "TemplateItem", r_ic1.status_code == 200 and bool(test_cat_id), "200 & id", f"code={r_ic1.status_code}, id={test_cat_id}", "P1")
    except Exception as e:
        record("CRUD-ITEM-01", "条目[增] 创建分类目录", "TemplateItem", False, "200", str(e), "P1")

    if test_cat_id:
        try:
            r_ic2 = requests.post(f"{BASE}/api/templates/{test_tmpl_id}/items", headers=h_admin, json={
                "title": f"1.1 超声波探伤合格率检查_{MARK}",
                "parent_id": test_cat_id,
                "is_category": False,
                "check_type": "radio",
                "risk_level": "high",
                "check_method": "查验近3个月UT探伤报告及探伤人员资质",
                "legal_basis": "TSG 21-2016 第4.2.3条",
                "allow_attachment": True,
                "sort_order": 1
            }, timeout=TIMEOUT)
            test_leaf_id = r_ic2.json().get("data", {}).get("id")
            record("CRUD-ITEM-02", "条目[增] 在目录下创建叶子检查项", "TemplateItem", r_ic2.status_code == 200 and bool(test_leaf_id), "200 & id", f"code={r_ic2.status_code}, id={test_leaf_id}", "P1")
        except Exception as e:
            record("CRUD-ITEM-02", "条目[增] 创建叶子项", "TemplateItem", False, "200", str(e), "P1")

    try:
        r_tree = requests.get(f"{BASE}/api/templates/{test_tmpl_id}/items", headers=h_admin, timeout=TIMEOUT)
        tree_items = r_tree.json().get("data", [])
        has_cat = any(i.get("id") == test_cat_id and len(i.get("children", [])) == 1 for i in tree_items)
        record("CRUD-ITEM-03", "条目[查] 查询模板树形完整层级 (1目录+1子项)", "TemplateItem", r_tree.status_code == 200 and has_cat, "200 & 包含层级树", f"count={len(tree_items)}, tree_valid={has_cat}", "P1")
    except Exception as e:
        record("CRUD-ITEM-03", "条目[查] 模板树形", "TemplateItem", False, "200", str(e), "P1")

    if test_leaf_id:
        try:
            r_iup = requests.put(f"{BASE}/api/templates/items/{test_leaf_id}", headers=h_admin, json={
                "title": f"1.1 超声波与射线探伤综合判定_{MARK}",
                "check_method": "查验RT及UT双重检验报告",
                "risk_level": "medium"
            }, timeout=TIMEOUT)
            record("CRUD-ITEM-04", "条目[改] 修改叶子项检查方法与风险等级", "TemplateItem", r_iup.status_code == 200, "200 OK", r_iup.status_code, "P2")
        except Exception as e:
            record("CRUD-ITEM-04", "条目[改] 修改叶子项", "TemplateItem", False, "200", str(e), "P2")

    try:
        r_pub = requests.post(f"{BASE}/api/templates/{test_tmpl_id}/publish", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-TMPL-03", "模板[发] 模板由草稿发布扭转为 published", "Template", r_pub.status_code == 200, "200 OK", r_pub.status_code, "P1")
    except Exception as e:
        record("CRUD-TMPL-03", "模板[发] 发布模板", "Template", False, "200", str(e), "P1")

    test_copied_tmpl_id = None
    try:
        r_copy = requests.post(f"{BASE}/api/templates/{test_tmpl_id}/copy", headers=h_admin, timeout=TIMEOUT)
        test_copied_tmpl_id = r_copy.json().get("data", {}).get("id")
        record("CRUD-TMPL-04", "模板[复] 复制模板树生成独立新副本", "Template", r_copy.status_code == 200 and bool(test_copied_tmpl_id), "200 & copied_id", f"code={r_copy.status_code}, id={test_copied_tmpl_id}", "P2")
    except Exception as e:
        record("CRUD-TMPL-04", "模板[复] 复制模板", "Template", False, "200", str(e), "P2")

    if test_copied_tmpl_id:
        requests.delete(f"{BASE}/api/templates/{test_copied_tmpl_id}", headers=h_admin, timeout=TIMEOUT)

    if test_leaf_id:
        try:
            r_idel = requests.delete(f"{BASE}/api/templates/items/{test_leaf_id}", headers=h_admin, timeout=TIMEOUT)
            record("CRUD-ITEM-05", "条目[删] 软删除叶子检查项", "TemplateItem", r_idel.status_code == 200, "200 OK", r_idel.status_code, "P2")
        except Exception as e:
            record("CRUD-ITEM-05", "条目[删] 删除叶子项", "TemplateItem", False, "200", str(e), "P2")

# ==============================================================================
# 5. 审核项目全生命周期策划与深入子资源域 (Audit Projects Full CRUD)
# ==============================================================================
print("\n--- 模块五：审核项目全生命周期与子资源域 (Audit Projects Full CRUD) ---")
test_prj_id = None
tmpl_use_id = test_tmpl_id if test_tmpl_id else "ac675135-17d2-49e5-b873-15cd9580b289"

if test_ent_id:
    try:
        r_pc = requests.post(f"{BASE}/api/audit-projects", headers=h_admin, json={
            "title": f"（E2E全功能测试）特种设备承压四体系初次认证审核_{MARK}",
            "enterprise_id": test_ent_id,
            "audit_type": "initial",
            "standard_codes": ["Q", "E", "S", "En"],
            "audit_days": 3.0,
            "plan_start_date": "2026-11-01",
            "plan_end_date": "2026-11-03",
            "scope": "特种承压设备制造及安装"
        }, timeout=TIMEOUT)
        test_prj_id = r_pc.json().get("data", {}).get("id")
        record("CRUD-PRJ-01", "项目[增] 立项多体系 QESEn 审核项目", "AuditProject", r_pc.status_code == 200 and bool(test_prj_id), "200 & prj_id", f"code={r_pc.status_code}, id={test_prj_id}", "P0")
    except Exception as e:
        record("CRUD-PRJ-01", "项目[增] 立项项目", "AuditProject", False, "200", str(e), "P0")

if test_prj_id:
    try:
        r_pr = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}", headers=h_admin, timeout=TIMEOUT)
        p_data = r_pr.json().get("data", {})
        r_prog = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}/progress", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-PRJ-02", "项目[查] 获取项目基础画像与推进度 (progress)", "AuditProject", r_pr.status_code == 200 and r_prog.status_code == 200, "200 OK", f"status={p_data.get('status')}", "P1")
    except Exception as e:
        record("CRUD-PRJ-02", "项目[查] 项目详情", "AuditProject", False, "200", str(e), "P1")

if test_prj_id:
    try:
        r_pup = requests.put(f"{BASE}/api/audit-projects/{test_prj_id}", headers=h_admin, json={
            "scope": "更新后范围：特种承压设备制造、管道安装及压力容器安全保障",
            "remarks": "由 E2E 自动化测试程序更新备注"
        }, timeout=TIMEOUT)
        record("CRUD-PRJ-03", "项目[改] 修改项目审核范围与业务备注", "AuditProject", r_pup.status_code == 200, "200 OK", r_pup.status_code, "P2")
    except Exception as e:
        record("CRUD-PRJ-03", "项目[改] 修改项目", "AuditProject", False, "200", str(e), "P2")

# --- 审核组分工 (Team Members CRUD) ---
test_member_id = None
if test_prj_id and user_expert:
    try:
        r_team = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/team", headers=h_admin, json={
            "member_id": user_expert.get("id"),
            "role": "leader",
            "responsible_systems": ["Q", "S"],
            "qualification_codes": ["TZ-10.01"]
        }, timeout=TIMEOUT)
        test_member_id = r_team.json().get("data", {}).get("id")
        record("CRUD-TEAM-01", "组员[增] 指派组长与专业代码资质", "AuditTeam", r_team.status_code == 200 and bool(test_member_id), "200 & member_id", f"code={r_team.status_code}, id={test_member_id}", "P1")
    except Exception as e:
        record("CRUD-TEAM-01", "组员[增] 指派组员", "AuditTeam", False, "200", str(e), "P1")

    try:
        r_tlist = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}/team", headers=h_admin, timeout=TIMEOUT)
        tlist = r_tlist.json().get("data", [])
        record("CRUD-TEAM-02", "组员[查] 查询项目审核组成员清单", "AuditTeam", r_tlist.status_code == 200 and len(tlist) >= 1, "200 & members", f"count={len(tlist)}", "P1")
    except Exception as e:
        record("CRUD-TEAM-02", "组员[查] 组员列表", "AuditTeam", False, "200", str(e), "P1")

    if test_member_id:
        try:
            r_tup = requests.put(f"{BASE}/api/audit-projects/team/{test_member_id}", headers=h_admin, json={
                "responsible_systems": ["Q", "E", "S", "En"]
            }, timeout=TIMEOUT)
            record("CRUD-TEAM-03", "组员[改] 更新审核组成员认证体系分工", "AuditTeam", r_tup.status_code == 200, "200 OK", r_tup.status_code, "P2")
        except Exception as e:
            record("CRUD-TEAM-03", "组员[改] 更新分工", "AuditTeam", False, "200", str(e), "P2")

# --- 审核计划日程 (Plan Items CRUD) ---
test_plan_id = None
test_plan_task_id = None
if test_prj_id:
    try:
        r_plan = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/plan", headers=h_admin, json={
            "plan_date": "2026-11-01",
            "time_start": "09:00",
            "time_end": "12:00",
            "area_name": f"承压锅炉制造一部_{MARK}",
            "template_id": tmpl_use_id,
            "assigned_member_ids": [user_expert.get("id")] if user_expert else []
        }, timeout=TIMEOUT)
        pdata = r_plan.json().get("data", {})
        test_plan_id = pdata.get("id")
        test_plan_task_id = pdata.get("inspection_task_id")
        record("CRUD-PLAN-01", "日程[增] 创建审核排期日程并自动派发任务", "AuditPlan", r_plan.status_code == 200 and bool(test_plan_id), "200 & plan_id", f"code={r_plan.status_code}, plan_id={test_plan_id}", "P1")
    except Exception as e:
        record("CRUD-PLAN-01", "日程[增] 创建排期", "AuditPlan", False, "200", str(e), "P1")

    try:
        r_plist = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}/plan", headers=h_admin, timeout=TIMEOUT)
        plist = r_plist.json().get("data", [])
        record("CRUD-PLAN-02", "日程[查] 查询审核计划日程明细清单", "AuditPlan", r_plist.status_code == 200 and len(plist) >= 1, "200 & plans", f"count={len(plist)}", "P1")
    except Exception as e:
        record("CRUD-PLAN-02", "日程[查] 日程列表", "AuditPlan", False, "200", str(e), "P1")

    if test_plan_id:
        try:
            r_pup = requests.put(f"{BASE}/api/audit-projects/plan/{test_plan_id}", headers=h_admin, json={
                "time_start": "09:30",
                "time_end": "12:30",
                "area_name": f"承压锅炉改建车间_{MARK}"
            }, timeout=TIMEOUT)
            record("CRUD-PLAN-03", "日程[改] 调整审核日程时间段与受审车间", "AuditPlan", r_pup.status_code == 200, "200 OK", r_pup.status_code, "P2")
        except Exception as e:
            record("CRUD-PLAN-03", "日程[改] 调整日程", "AuditPlan", False, "200", str(e), "P2")

# --- 首末次会议全生命周期 (Meetings CRUD) ---
test_meeting_id = None
if test_prj_id:
    try:
        r_mc = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/meetings", headers=h_admin, json={
            "meeting_type": "opening",
            "meeting_time": "2026-11-01T08:30:00Z",
            "participants_enterprise": "张总经理, 李管理者代表, 赵车间主任",
            "participants_audit_team": [user_expert.get("id")] if user_expert else [],
            "key_points": "确认QESEn四体系审核范围、抽样方法与保密安全协议"
        }, timeout=TIMEOUT)
        test_meeting_id = r_mc.json().get("data", {}).get("id")
        record("CRUD-MEET-01", "会议[增] 创建首次会议纪要 (opening)", "AuditMeeting", r_mc.status_code == 200 and bool(test_meeting_id), "200 & meeting_id", f"code={r_mc.status_code}, id={test_meeting_id}", "P1")
    except Exception as e:
        record("CRUD-MEET-01", "会议[增] 创建会议", "AuditMeeting", False, "200", str(e), "P1")

    try:
        r_mlist = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}/meetings", headers=h_admin, timeout=TIMEOUT)
        mlist = r_mlist.json().get("data", [])
        record("CRUD-MEET-02", "会议[查] 查询项目首末次会议列表", "AuditMeeting", r_mlist.status_code == 200 and len(mlist) >= 1, "200 & meetings", f"count={len(mlist)}", "P1")
    except Exception as e:
        record("CRUD-MEET-02", "会议[查] 会议列表", "AuditMeeting", False, "200", str(e), "P1")

    if test_meeting_id:
        try:
            r_mup = requests.put(f"{BASE}/api/audit-projects/meetings/{test_meeting_id}", headers=h_admin, json={
                "key_points": "确认四体系审核范围，双方达成一致，企业全员签署安全告知书"
            }, timeout=TIMEOUT)
            record("CRUD-MEET-03", "会议[改] 修改会议纪要核心要点", "AuditMeeting", r_mup.status_code == 200, "200 OK", r_mup.status_code, "P2")
        except Exception as e:
            record("CRUD-MEET-03", "会议[改] 修改会议", "AuditMeeting", False, "200", str(e), "P2")

# --- 不符合项全流程 (Nonconformities CRUD) ---
test_nc_id = None
if test_prj_id:
    try:
        r_nc = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/nonconformities", headers=h_admin, json={
            "severity": "minor",
            "certification_system": "Q",
            "clause_no": "8.5.1",
            "description": f"焊接作业指导书未受控发布且无编号_{MARK}",
            "corrective_action_required": "封存作废老旧指导书，下发经审批的受控版本"
        }, timeout=TIMEOUT)
        test_nc_id = r_nc.json().get("data", {}).get("id")
        record("CRUD-NC-01", "不符合项[增] 现场开具一般不符合项 (minor)", "Nonconformity", r_nc.status_code == 200 and bool(test_nc_id), "200 & nc_id", f"code={r_nc.status_code}, id={test_nc_id}", "P1")
    except Exception as e:
        record("CRUD-NC-01", "不符合项[增] 开具不符合项", "Nonconformity", False, "200", str(e), "P1")

    try:
        r_nclist = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}/nonconformities", headers=h_admin, timeout=TIMEOUT)
        nclist = r_nclist.json().get("data", [])
        record("CRUD-NC-02", "不符合项[查] 查询项目不符合项清单", "Nonconformity", r_nclist.status_code == 200 and len(nclist) >= 1, "200 & list", f"count={len(nclist)}", "P1")
    except Exception as e:
        record("CRUD-NC-02", "不符合项[查] 列表", "Nonconformity", False, "200", str(e), "P1")

    if test_nc_id:
        try:
            r_ncup = requests.put(f"{BASE}/api/audit-projects/nonconformities/{test_nc_id}", headers=h_admin, json={
                "description": f"焊接作业指导书未受控发布且无版本编号，存在工艺混淆风险_{MARK}"
            }, timeout=TIMEOUT)
            record("CRUD-NC-03", "不符合项[改] 补充不符合事实描述", "Nonconformity", r_ncup.status_code == 200, "200 OK", r_ncup.status_code, "P2")
        except Exception as e:
            record("CRUD-NC-03", "不符合项[改] 修改不符合项", "Nonconformity", False, "200", str(e), "P2")

    if test_nc_id:
        try:
            r_nc_conf = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/nonconformities/{test_nc_id}/confirm", headers=h_admin, timeout=TIMEOUT)
            record("CRUD-NC-04", "不符合项[确] 受审企业与组长双重确认关闭", "Nonconformity", r_nc_conf.status_code == 200, "200 OK", r_nc_conf.status_code, "P1")
        except Exception as e:
            record("CRUD-NC-04", "不符合项[确] 确认不符合项", "Nonconformity", False, "200", str(e), "P1")

# --- 报告多格式导出 (Export PDF & Word 带 ?token= 参数) ---
if test_prj_id:
    try:
        r_exp_pdf = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}/export/pdf?token={token_admin}", headers=h_admin, timeout=TIMEOUT)
        # Passed quality check returns 200, unpassed quality check returns 409
        is_expected = r_exp_pdf.status_code in (200, 409)
        record("CRUD-EXP-01", "导出[PDF] 审核报告 PDF 导出接口存活与门禁响应", "Export", is_expected, "200(通过)或409(门禁拦截)", f"code={r_exp_pdf.status_code}", "P2")
    except Exception as e:
        record("CRUD-EXP-01", "导出[PDF] PDF导出", "Export", False, "200/409", str(e), "P2")

    try:
        r_exp_doc = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}/export/word?token={token_admin}", headers=h_admin, timeout=TIMEOUT)
        is_expected = r_exp_doc.status_code in (200, 409)
        record("CRUD-EXP-02", "导出[Word] 审核报告 Word 导出接口存活与门禁响应", "Export", is_expected, "200(通过)或409(门禁拦截)", f"code={r_exp_doc.status_code}", "P2")
    except Exception as e:
        record("CRUD-EXP-02", "导出[Word] Word导出", "Export", False, "200/409", str(e), "P2")

# ==============================================================================
# 6. 多模态媒体与现场采证域 (Media CRUD)
# ==============================================================================
print("\n--- 模块六：多模态媒体与现场采证域 (Media CRUD) ---")
test_media_id = None
try:
    tiny_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    files = {"file": ("test_evidence.png", tiny_png, "image/png")}
    data = {}
    if test_plan_task_id:
        data["task_id"] = test_plan_task_id
        
    r_med = requests.post(f"{BASE}/api/media/upload", headers=h_admin, files=files, data=data, timeout=TIMEOUT)
    test_media_id = r_med.json().get("data", {}).get("id")
    record("CRUD-MED-01", "媒体[增] 上传现场拍照凭据图片 (MIME校验)", "Media", r_med.status_code == 200 and bool(test_media_id), "200 & media_id", f"code={r_med.status_code}, id={test_media_id}", "P1")
except Exception as e:
    record("CRUD-MED-01", "媒体[增] 上传媒体", "Media", False, "200", str(e), "P1")

if test_plan_task_id:
    try:
        r_mlist = requests.get(f"{BASE}/api/media/task/{test_plan_task_id}", headers=h_admin, timeout=TIMEOUT)
        mlist = r_mlist.json().get("data", [])
        record("CRUD-MED-02", "媒体[查] 获取任务已上传现场多模态文件", "Media", r_mlist.status_code == 200 and len(mlist) >= 1, "200 & list", f"count={len(mlist)}", "P1")
    except Exception as e:
        record("CRUD-MED-02", "媒体[查] 任务媒体", "Media", False, "200", str(e), "P1")

if test_media_id:
    try:
        r_mdel = requests.delete(f"{BASE}/api/media/{test_media_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-MED-03", "媒体[删] 删除作废采证文件并清理存储", "Media", r_mdel.status_code == 200, "200 OK", r_mdel.status_code, "P2")
    except Exception as e:
        record("CRUD-MED-03", "媒体[删] 删除媒体", "Media", False, "200", str(e), "P2")

# ==============================================================================
# 7. 日常检查任务与现场记录域 (Tasks & Records CRUD)
# ==============================================================================
print("\n--- 模块七：日常检查任务与现场记录域 (Tasks & Records CRUD) ---")
test_dt_id = None
if test_ent_id:
    try:
        r_tc = requests.post(f"{BASE}/api/tasks", headers=h_admin, json={
            "title": f"（E2E全功能测试）车间安全消防专项抽检_{MARK}",
            "enterprise_id": test_ent_id,
            "template_id": tmpl_use_id,
            "assigned_to": user_expert.get("id") if user_expert else None
        }, timeout=TIMEOUT)
        test_dt_id = r_tc.json().get("data", {}).get("id")
        record("CRUD-TASK-01", "任务[增] 创建车间日常巡查任务", "Task", r_tc.status_code == 200 and bool(test_dt_id), "200 & task_id", f"code={r_tc.status_code}, id={test_dt_id}", "P1")
    except Exception as e:
        record("CRUD-TASK-01", "任务[增] 创建任务", "Task", False, "200", str(e), "P1")

if test_dt_id:
    try:
        r_tr = requests.get(f"{BASE}/api/tasks/{test_dt_id}", headers=h_admin, timeout=TIMEOUT)
        t_data = r_tr.json().get("data", {})
        r_ts = requests.get(f"{BASE}/api/tasks/statistics", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-TASK-02", "任务[查] 查询任务详情与全局统计看板", "Task", r_tr.status_code == 200 and r_ts.status_code == 200, "200 OK", f"status={t_data.get('status')}", "P1")
    except Exception as e:
        record("CRUD-TASK-02", "任务[查] 任务详情", "Task", False, "200", str(e), "P1")

if test_dt_id:
    try:
        r_start = requests.post(f"{BASE}/api/tasks/{test_dt_id}/start", headers=h_expert, timeout=TIMEOUT)
        record("CRUD-TASK-03", "任务[动] 审核员启动任务扭转为 in_progress", "Task", r_start.status_code == 200, "200 OK", r_start.status_code, "P1")
    except Exception as e:
        record("CRUD-TASK-03", "任务[动] 启动任务", "Task", False, "200", str(e), "P1")

if test_dt_id:
    try:
        r_tup = requests.put(f"{BASE}/api/tasks/{test_dt_id}", headers=h_admin, json={
            "remarks": "现场抽检正常推进中，已核验消防设备"
        }, timeout=TIMEOUT)
        record("CRUD-TASK-04", "任务[改] 更新日常任务执行备注", "Task", r_tup.status_code == 200, "200 OK", r_tup.status_code, "P2")
    except Exception as e:
        record("CRUD-TASK-04", "任务[改] 更新任务", "Task", False, "200", str(e), "P2")

if test_dt_id:
    try:
        r_canc = requests.post(f"{BASE}/api/tasks/{test_dt_id}/cancel", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-TASK-05", "任务[销] 管理员取消任务扭转为 cancelled (P2-03)", "Task", r_canc.status_code == 200, "200 OK", r_canc.status_code, "P2")
    except Exception as e:
        record("CRUD-TASK-05", "任务[销] 取消任务", "Task", False, "200", str(e), "P2")

if test_dt_id:
    try:
        r_tdel = requests.delete(f"{BASE}/api/tasks/{test_dt_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-TASK-06", "任务[删] 软删除日常检查任务", "Task", r_tdel.status_code == 200, "200 OK", r_tdel.status_code, "P2")
    except Exception as e:
        record("CRUD-TASK-06", "任务[删] 删除任务", "Task", False, "200", str(e), "P2")

# ==============================================================================
# 8. 资源级联清理与基线复原 (Cascade Soft Delete)
# ==============================================================================
print("\n--- 模块八：资源级联清理与基线复原 (Cascade Soft Delete) ---")
if test_prj_id:
    try:
        r_pdel = requests.delete(f"{BASE}/api/audit-projects/{test_prj_id}", headers=h_admin, timeout=TIMEOUT)
        r_pre = requests.get(f"{BASE}/api/audit-projects/{test_prj_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-CLN-01", "项目[删] 级联软删除审核项目及其子资源 (P1-01)", "AuditProject", r_pdel.status_code == 200 and r_pre.status_code == 404, "del=200 & recheck=404", f"del={r_pdel.status_code}, chk={r_pre.status_code}", "P0")
    except Exception as e:
        record("CRUD-CLN-01", "项目[删] 级联删除项目", "AuditProject", False, "200", str(e), "P0")

if test_tmpl_id:
    try:
        r_tdel2 = requests.delete(f"{BASE}/api/templates/{test_tmpl_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-CLN-02", "模板[删] 软删除测试检查模板", "Template", r_tdel2.status_code == 200, "200 OK", r_tdel2.status_code, "P2")
    except Exception as e:
        record("CRUD-CLN-02", "模板[删] 删除模板", "Template", False, "200", str(e), "P2")

if test_ent_id:
    try:
        r_edel = requests.delete(f"{BASE}/api/enterprises/{test_ent_id}", headers=h_admin, timeout=TIMEOUT)
        r_ere = requests.get(f"{BASE}/api/enterprises/{test_ent_id}", headers=h_admin, timeout=TIMEOUT)
        record("CRUD-CLN-03", "企业[删] 软删除测试企业档案并核对404", "Enterprise", r_edel.status_code == 200 and r_ere.status_code == 404, "del=200 & recheck=404", f"del={r_edel.status_code}, chk={r_ere.status_code}", "P1")
    except Exception as e:
        record("CRUD-CLN-03", "企业[删] 删除企业", "Enterprise", False, "200", str(e), "P1")

# ==============================================================================
# 9. 测试执行结果统计与 TypeSafe AI 智能分诊
# ==============================================================================
print("\n" + "="*50 + "\n--- 测试执行汇总 ---\n" + "="*50)
total_tests = len(results)
pass_tests = sum(1 for r in results if r["ok"])
fail_tests = sum(1 for r in results if not r["ok"])
print(f"总执行 CRUD 用例数: {total_tests} | 通过: {pass_tests} | 失败: {fail_tests} | 通过率: {pass_tests/total_tests*100:.1f}%")

with open("docs/_full_crud_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("✅ CRUD 原始测试结果已保存至 docs/_full_crud_test_results.json")

# ==============================================================================
# 10. TypeSafe AI System One 结构化智能分诊
# ==============================================================================
print("\n" + "="*50 + "\n--- TypeSafe AI System One 智能分诊启动 ---")
print("使用模型: jev-latest | 端点: https://api.typesafe.ai/v1/systemone")

# Collect any real defects or findings
findings_to_triage = [
    {
        "case_id": "DEFECT-01",
        "name": "演示项目门禁当前 score=75 未通过 (存在 UNSUBMITTED_RECORDS, INCOMPLETE_PLAN_ITEMS)",
        "module": "AuditProject QualityGate",
        "actual": "passed=false, score=75, blocking_count=2, 导出交付包返回 409 Conflict",
        "context": "客户演示第四幕/第九幕中，项目因排期存在未提交记录拦截归档"
    },
    {
        "case_id": "DEFECT-02",
        "name": "服务端登出全局吊销同用户全部 Token (基于 token_revoked_at)",
        "module": "Auth Logout",
        "actual": "单端退出导致多端登录并发被踢 401 Unauthorized",
        "context": "讲师在 Web 端退出登录会导致手机 H5 端同一 expert 账号失效"
    },
    {
        "case_id": "DEFECT-03",
        "name": "H5 现场拍照入口需点进条目详情，执行长列表未直接内联拍照组件",
        "module": "H5 Inspection UI",
        "actual": "长列表仅呈现判定单选框，需点击条款卡片进入 InspectItem.vue 才能拍照",
        "context": "审核员初次使用可能不易发现拍照入口"
    },
    {
        "case_id": "DEFECT-04",
        "name": "条款 TOP 10 响应键为 clause_no 而非通用 name 字段",
        "module": "Statistics Nonconformities",
        "actual": "GET /api/statistics/nonconformities/by-clause 返回键为 clause_no 与 distribution 接口的 name 不统一",
        "context": "前端图表适配器需做字段重命名映射"
    },
    {
        "case_id": "DEFECT-05",
        "name": "企业/产品/资质接口子资源路由冗余强校验 enterprise_id",
        "module": "Enterprise Sub-resources",
        "actual": "POST /api/enterprises/{id}/qualifications 路径已含 ID，但请求体 Pydantic 校验仍强制要求 enterprise_id",
        "context": "前端若未在 body 重复传递 enterprise_id 会报 422"
    },
    {
        "case_id": "DEFECT-06",
        "name": "整改验收接口 status 字段未声明 Body() 默认转为 Query 参数",
        "module": "Enterprise Rectifications",
        "actual": "POST /api/enterprises/rectifications/{id}/review 若以 JSON body 传 status 返回 422",
        "context": "接口设计偏离标准 RESTful JSON 传参模式"
    },
    {
        "case_id": "DEFECT-07",
        "name": "文档中心 `/docs` 检索为结构化元数据索引非长文本倒排",
        "module": "Docs Center",
        "actual": "Ctrl+K 搜索对标题和关键词精准，但对正文深层特定生僻词零召回",
        "context": "当前纯前端静态抽取，暂未引入 Minisearch / Lunr 倒排"
    }
]

triaged_findings = []

for item in findings_to_triage:
    print(f"\n正在通过 TypeSafe Jev 分诊: {item['case_id']} - {item['name'][:35]}...")
    ts_payload = {
        "model": "jev-latest",
        "state": f"缺陷实体与上下文:\n用例编号: {item.get('case_id')}\n名称: {item.get('name')}\n模块: {item.get('module')}\n实际现象: {item.get('actual')}\n业务背景: {item.get('context', '')}",
        "questions": {
            "defect_category": {
                "type": "choice",
                "instructions": "该技术或业务发现项的归类属性是什么？",
                "criteria": {
                    "seed_data_state": "演示种子数据状态未闭环或门禁前置条件未满足",
                    "architecture_tradeoff": "架构安全机制与多端并发体验的折中设计",
                    "ux_discoverability": "前端界面功能路径较深或可发现性体验项",
                    "api_contract_naming": "API 响应字段命名风格不统一微瑕",
                    "api_param_convention": "API 入参规范不统一或多余必填校验",
                    "code_defect": "系统代码逻辑严重缺陷"
                }
            },
            "severity_score": {
                "type": "score",
                "instructions": "该问题对系统的严重程度评分",
                "criteria": [
                    "微瑕/体验优化建议 (P3)",
                    "一般问题/边界轻微缺陷 (P2)",
                    "严重缺陷/核心功能受损 (P1)",
                    "致命阻断/主流程瘫痪 (P0)"
                ]
            },
            "demo_blocker_prob": {
                "type": "noul",
                "instructions": "该问题是否会导致客户十幕现场演示主线发生中断？"
            },
            "remediation_strategy": {
                "type": "choice",
                "instructions": "建议采取的最佳处置对策是什么？",
                "criteria": {
                    "doc_demo_script": "代码行为正确或安全保护，由讲师正面话术释义化解",
                    "operational_notice": "操作规范提示，保持单端专人登录",
                    "product_backlog": "纳入下一版本常规体验优化",
                    "immediate_hotfix": "必须立即修改代码修复并重启"
                }
            }
        }
    }
    try:
        resp = requests.post(
            "https://api.typesafe.ai/v1/systemone",
            headers={"Authorization": f"Bearer {TYPESAFE_KEY}", "Content-Type": "application/json"},
            json=ts_payload,
            timeout=20
        )
        if resp.status_code == 200:
            answers = resp.json().get("answers", {})
            cat = answers.get("defect_category", {}).get("choice")
            sev = answers.get("severity_score", {}).get("score")
            noul = answers.get("demo_blocker_prob", {}).get("noul")
            rem = answers.get("remediation_strategy", {}).get("choice")
            print(f"  --> Jev 判定: Category={cat} | SevScore={sev} | BlockerProb={noul} | Remediation={rem}")
            triaged_findings.append({
                **item,
                "jev_category": cat,
                "jev_severity": sev,
                "jev_blocker_prob": noul,
                "jev_remediation": rem
            })
        else:
            print(f"  --> TypeSafe 请求失败: {resp.status_code} {resp.text[:100]}")
    except Exception as ex:
        print(f"  --> TypeSafe 调用异常: {ex}")

with open("docs/_typesafe_triaged_findings.json", "w", encoding="utf-8") as f:
    json.dump(triaged_findings, f, ensure_ascii=False, indent=2)
print("\n✅ TypeSafe AI 智能分诊全量结果已保存至 docs/_typesafe_triaged_findings.json")
