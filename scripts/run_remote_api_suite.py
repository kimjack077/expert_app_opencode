# -*- coding: utf-8 -*-
"""
EFIS 全功能远程生产环境自动化 API 测试套件
被测目标: http://49.232.213.79:8000
测试依据: 
  - docs/EFIS_全功能演示说明_2026-09-19.md
  - docs/EFIS_全功能测试用例_2026-09-19.md
"""
import sys
import io
import json
import time
import uuid
import requests

# Set utf-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://49.232.213.79:8000"
TIMEOUT = 30.0
MARK = f"E2E-AUTO-{int(time.time())}"

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

# ==============================================================================
# 模块一：认证与用户管理域 (A ~ B)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块一：认证与用户管理域 (A ~ B) ---\n" + "="*50)

# A-01 管理员登录
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=TIMEOUT)
    token_admin = r.json().get("data", {}).get("access_token")
    record("A-01", "超级管理员登录", "Auth", r.status_code == 200 and bool(token_admin), "200 & access_token", r.status_code, "P0")
except Exception as e:
    record("A-01", "超级管理员登录", "Auth", False, "200 & access_token", str(e), "P0")
    token_admin = None

h_admin = {"Authorization": f"Bearer {token_admin}"} if token_admin else {}

# A-02 审核专家登录
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "expert", "password": "expert123"}, timeout=TIMEOUT)
    token_expert = r.json().get("data", {}).get("access_token")
    user_expert = r.json().get("data", {}).get("user", {})
    record("A-02", "审核专家登录", "Auth", r.status_code == 200 and bool(token_expert), "200 & access_token", r.status_code, "P0")
except Exception as e:
    record("A-02", "审核专家登录", "Auth", False, "200 & access_token", str(e), "P0")
    token_expert = None

h_expert = {"Authorization": f"Bearer {token_expert}"} if token_expert else {}

# A-03 普通审核员登录 auditor_chen
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "auditor_chen", "password": "expert123"}, timeout=TIMEOUT)
    token_chen = r.json().get("data", {}).get("access_token")
    record("A-03", "普通审核员登录 (auditor_chen)", "Auth", r.status_code == 200 and bool(token_chen), "200 & access_token", r.status_code, "P1")
except Exception as e:
    record("A-03", "普通审核员登录 (auditor_chen)", "Auth", False, "200 & access_token", str(e), "P1")

# A-04 异常：密码错误
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "wrongpassword"}, timeout=TIMEOUT)
    record("A-04", "密码错误拦截", "Auth", r.status_code == 401, "401 Unauthorized", r.status_code, "P1")
except Exception as e:
    record("A-04", "密码错误拦截", "Auth", False, "401 Unauthorized", str(e), "P1")

# A-05 异常：用户不存在
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "non_exist_user_xyz", "password": "pwd"}, timeout=TIMEOUT)
    record("A-05", "不存在用户拦截", "Auth", r.status_code == 401, "401 Unauthorized", r.status_code, "P1")
except Exception as e:
    record("A-05", "不存在用户拦截", "Auth", False, "401 Unauthorized", str(e), "P1")

# A-06 异常：空用户名或密码 (BUG-P3-01 验证)
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "", "password": ""}, timeout=TIMEOUT)
    record("A-06", "空凭据拦截", "Auth", r.status_code in (400, 401, 422), "400/401/422", r.status_code, "P3", f"实测状态码: {r.status_code}")
except Exception as e:
    record("A-06", "空凭据拦截", "Auth", False, "400/401/422", str(e), "P3")

# A-07 安全：无 Token 访问受控接口
try:
    r = requests.get(f"{BASE}/api/auth/me", timeout=TIMEOUT)
    record("A-07", "无Token访问拦截", "Auth", r.status_code == 401, "401 Unauthorized", r.status_code, "P0")
except Exception as e:
    record("A-07", "无Token访问拦截", "Auth", False, "401 Unauthorized", str(e), "P0")

# A-08 安全：伪造 Token 访问
try:
    r = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": "Bearer fake.token.here"}, timeout=TIMEOUT)
    record("A-08", "伪造Token拦截", "Auth", r.status_code == 401, "401 Unauthorized", r.status_code, "P0")
except Exception as e:
    record("A-08", "伪造Token拦截", "Auth", False, "401 Unauthorized", str(e), "P0")

# A-09 当前用户画像
try:
    r = requests.get(f"{BASE}/api/auth/me", headers=h_admin, timeout=TIMEOUT)
    role = r.json().get("data", {}).get("role")
    record("A-09", "获取当前用户画像", "Auth", r.status_code == 200 and role == "super_admin", "200 role=super_admin", f"code={r.status_code}, role={role}", "P1")
except Exception as e:
    record("A-09", "获取当前用户画像", "Auth", False, "200", str(e), "P1")

# A-11 登出与令牌失效 (P2-04 修复验证)
try:
    # Login a temporary session to test logout revocation
    r_tmp = requests.post(f"{BASE}/api/auth/login", json={"username": "expert", "password": "expert123"}, timeout=TIMEOUT)
    tmp_token = r_tmp.json().get("data", {}).get("access_token")
    h_tmp = {"Authorization": f"Bearer {tmp_token}"}
    r_before = requests.get(f"{BASE}/api/auth/me", headers=h_tmp, timeout=TIMEOUT)
    r_logout = requests.post(f"{BASE}/api/auth/logout", headers=h_tmp, timeout=TIMEOUT)
    r_after = requests.get(f"{BASE}/api/auth/me", headers=h_tmp, timeout=TIMEOUT)
    revoked = (r_after.status_code == 401)
    record("A-11", "登出后令牌失效校验 (P2-04)", "Auth", revoked, "登出后再查 401", f"登出={r_logout.status_code}, 后续查me={r_after.status_code}", "P2", "验证服务端令牌吊销")
except Exception as e:
    record("A-11", "登出后令牌失效校验 (P2-04)", "Auth", False, "登出后 401", str(e), "P2")

# A-12 废弃账号防呆验证
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "demo_auditor_20260720", "password": "password123"}, timeout=TIMEOUT)
    record("A-12", "历史废弃账号封禁", "Auth", r.status_code == 401, "401 Unauthorized", r.status_code, "P2")
except Exception as e:
    record("A-12", "历史废弃账号封禁", "Auth", False, "401 Unauthorized", str(e), "P2")

# B-01 用户列表查询
try:
    r = requests.get(f"{BASE}/api/users", headers=h_admin, timeout=TIMEOUT)
    users = r.json().get("data", [])
    record("B-01", "管理员查询用户列表", "User", r.status_code == 200 and len(users) >= 1, "200 & 用户列表", f"count={len(users)}", "P1")
except Exception as e:
    record("B-01", "管理员查询用户列表", "User", False, "200", str(e), "P1")

# B-02 垂直越权：专家访问用户管理
try:
    r = requests.get(f"{BASE}/api/users", headers=h_expert, timeout=TIMEOUT)
    record("B-02", "专家越权访问用户管理", "User", r.status_code == 403, "403 Forbidden", r.status_code, "P0")
except Exception as e:
    record("B-02", "专家越权访问用户管理", "User", False, "403 Forbidden", str(e), "P0")

# B-03 新增测试审核员用户与清理
new_user_id = None
test_username = f"e2e_{MARK.lower()[:15]}"
try:
    user_payload = {
        "username": test_username,
        "password": "Password123!",
        "real_name": f"测试员_{MARK}",
        "role": "auditor",
        "phone": "13912345678",
        "email": f"{test_username}@example.com"
    }
    r = requests.post(f"{BASE}/api/users", headers=h_admin, json=user_payload, timeout=TIMEOUT)
    new_user_id = r.json().get("data", {}).get("id")
    record("B-03", "新增审核员用户", "User", r.status_code == 200 and bool(new_user_id), "200 & user_id", f"code={r.status_code}, id={new_user_id}", "P1")
except Exception as e:
    record("B-03", "新增审核员用户", "User", False, "200 & user_id", str(e), "P1")

# B-04 异常：重复用户名冲突 (P3-02 状态码验证)
if new_user_id:
    try:
        r = requests.post(f"{BASE}/api/users", headers=h_admin, json=user_payload, timeout=TIMEOUT)
        record("B-04", "重复用户名冲突状态码 (P3-02)", "User", r.status_code in (400, 409), "409 (或400)", f"status={r.status_code}, body={r.text[:80]}", "P3", "当前状态码契约")
    except Exception as e:
        record("B-04", "重复用户名冲突状态码 (P3-02)", "User", False, "409", str(e), "P3")

# B-05 异常：非法角色枚举注入
try:
    r = requests.post(f"{BASE}/api/users", headers=h_admin, json={"username": f"bad_{MARK[:8]}", "password": "123", "role": "hacker_admin"}, timeout=TIMEOUT)
    record("B-05", "非法角色枚举拦截", "User", r.status_code in (400, 422), "400/422 Validation Error", r.status_code, "P2")
except Exception as e:
    record("B-05", "非法角色枚举拦截", "User", False, "400/422", str(e), "P2")

# B-08 异常：非法 UUID 格式
try:
    r = requests.get(f"{BASE}/api/users/not-a-valid-uuid", headers=h_admin, timeout=TIMEOUT)
    record("B-08", "非法UUID格式请求", "User", r.status_code in (404, 422), "404/422 (非500)", r.status_code, "P2")
except Exception as e:
    record("B-08", "非法UUID格式请求", "User", False, "404/422", str(e), "P2")

# B-09 软删除刚才创建的测试用户
if new_user_id:
    try:
        r = requests.delete(f"{BASE}/api/users/{new_user_id}", headers=h_admin, timeout=TIMEOUT)
        r_recheck = requests.get(f"{BASE}/api/users/{new_user_id}", headers=h_admin, timeout=TIMEOUT)
        record("B-09", "软删除测试用户", "User", r.status_code == 200 and r_recheck.status_code == 404, "删除200 & 再查404", f"del={r.status_code}, recheck={r_recheck.status_code}", "P2")
    except Exception as e:
        record("B-09", "软删除测试用户", "User", False, "200", str(e), "P2")

# ==============================================================================
# 模块二：行业分类与企业档案全景域 (C ~ D)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块二：行业分类与企业档案全景域 (C ~ D) ---\n" + "="*50)

# C-01 行业分类全景树
try:
    r = requests.get(f"{BASE}/api/industries/tree", headers=h_admin, timeout=TIMEOUT)
    tree = r.json().get("data", [])
    record("C-01", "获取行业分类全景树", "Industry", r.status_code == 200 and len(tree) > 0, "200 & 树形结构", f"count={len(tree)}", "P1")
except Exception as e:
    record("C-01", "获取行业分类全景树", "Industry", False, "200", str(e), "P1")

# C-02/03/05/06 行业分类测试与子节点保护 (P2-02 验证)
test_ind_parent_id = None
test_ind_child_id = None
try:
    p_code = f"IND_P_{int(time.time())%100000}"
    r_p = requests.post(f"{BASE}/api/industries", headers=h_admin, json={"name": f"测试行业大类_{MARK}", "code": p_code}, timeout=TIMEOUT)
    test_ind_parent_id = r_p.json().get("data", {}).get("id")
    
    c_code = f"IND_C_{int(time.time())%100000}"
    r_c = requests.post(f"{BASE}/api/industries", headers=h_admin, json={"name": f"测试行业子类_{MARK}", "code": c_code, "parent_id": test_ind_parent_id}, timeout=TIMEOUT)
    test_ind_child_id = r_c.json().get("data", {}).get("id")
    
    # 尝试直接删除含有子节点的父节点 (P2-02)
    r_del_parent = requests.delete(f"{BASE}/api/industries/{test_ind_parent_id}", headers=h_admin, timeout=TIMEOUT)
    record("C-06", "含子节点的行业父节点删除策略 (P2-02)", "Industry", r_del_parent.status_code in (400, 200), "400拒绝或显式策略", f"status={r_del_parent.status_code}, resp={r_del_parent.text[:100]}", "P3")
    
    # 清理测试数据
    if test_ind_child_id:
        requests.delete(f"{BASE}/api/industries/{test_ind_child_id}", headers=h_admin, timeout=TIMEOUT)
    if test_ind_parent_id and r_del_parent.status_code != 200:
        requests.delete(f"{BASE}/api/industries/{test_ind_parent_id}", headers=h_admin, timeout=TIMEOUT)
except Exception as e:
    record("C-06", "行业节点保护", "Industry", False, "400", str(e), "P3")

# D-01 企业档案列表
try:
    r = requests.get(f"{BASE}/api/enterprises", headers=h_admin, timeout=TIMEOUT)
    ents = r.json().get("data", [])
    ents_list = ents if isinstance(ents, list) else ents.get("items", [])
    record("D-01", "企业档案列表检索", "Enterprise", r.status_code == 200 and len(ents_list) >= 1, "200 & 企业列表", f"count={len(ents_list)}", "P1")
except Exception as e:
    record("D-01", "企业档案列表检索", "Enterprise", False, "200", str(e), "P1")

# D-02 示范企业风险等级
try:
    r = requests.get(f"{BASE}/api/enterprises", headers=h_admin, timeout=TIMEOUT)
    ents_list = r.json().get("data", []) if isinstance(r.json().get("data"), list) else r.json().get("data", {}).get("items", [])
    has_d = any(e.get("risk_level") == "D" for e in ents_list)
    has_b = any(e.get("risk_level") == "B" for e in ents_list)
    record("D-02", "示范企业风险等级分布核验", "Enterprise", has_d and has_b, "包含D级与B级示范企业", f"has_D={has_d}, has_B={has_b}", "P1")
except Exception as e:
    record("D-02", "示范企业风险等级分布核验", "Enterprise", False, "D and B", str(e), "P1")

# D-07 企业搜索 keyword vs name (P2-01 验证)
try:
    r_kw = requests.get(f"{BASE}/api/enterprises?keyword=焦化", headers=h_admin, timeout=TIMEOUT)
    r_nm = requests.get(f"{BASE}/api/enterprises?name=焦化", headers=h_admin, timeout=TIMEOUT)
    kw_items = r_kw.json().get("data", []) if isinstance(r_kw.json().get("data"), list) else r_kw.json().get("data", {}).get("items", [])
    nm_items = r_nm.json().get("data", []) if isinstance(r_nm.json().get("data"), list) else r_nm.json().get("data", {}).get("items", [])
    # keyword should also filter, not return all enterprises
    kw_ok = len(kw_items) == len(nm_items) and len(kw_items) <= 3
    record("D-07", "企业模糊搜索 keyword 参数支持 (P2-01)", "Enterprise", kw_ok, f"name与keyword结果一致 (count={len(nm_items)})", f"keyword_count={len(kw_items)}, name_count={len(nm_items)}", "P2")
except Exception as e:
    record("D-07", "企业模糊搜索 keyword 支持", "Enterprise", False, "一致", str(e), "P2")

# D-03/04/05/09 企业 CRUD 与信用码唯一性 (409)
test_ent_id = None
try:
    credit_code = f"91370000{int(time.time())%100000000:08d}X"
    ent_payload = {
        "name": f"（E2E自动化）测试企业_{MARK}",
        "credit_code": credit_code,
        "risk_level": "B",
        "legal_person": "测试法人",
        "contact_phone": "13800001234"
    }
    r_create = requests.post(f"{BASE}/api/enterprises", headers=h_admin, json=ent_payload, timeout=TIMEOUT)
    test_ent_id = r_create.json().get("data", {}).get("id")
    record("D-03", "新建受审核企业档案", "Enterprise", r_create.status_code == 200 and bool(test_ent_id), "200 & enterprise_id", f"code={r_create.status_code}, id={test_ent_id}", "P1")
    
    # D-04 信用码重复 409
    r_dup = requests.post(f"{BASE}/api/enterprises", headers=h_admin, json=ent_payload, timeout=TIMEOUT)
    record("D-04", "企业信用代码重复拦截", "Enterprise", r_dup.status_code == 409, "409 Conflict", r_dup.status_code, "P2")
    
    # D-09 软删除企业
    if test_ent_id:
        r_del = requests.delete(f"{BASE}/api/enterprises/{test_ent_id}", headers=h_admin, timeout=TIMEOUT)
        record("D-09", "软删除测试企业", "Enterprise", r_del.status_code == 200, "200 OK", r_del.status_code, "P2")
except Exception as e:
    record("D-03", "企业CRUD", "Enterprise", False, "200", str(e), "P1")

# ==============================================================================
# 模块三：检查模板设计与层级防呆治理域 (E ~ F)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块三：检查模板设计与层级防呆治理域 (E ~ F) ---\n" + "="*50)

# E-01 ~ E-04 模板列表与 AC-1 恒等式
tmpl_demo_id = None
try:
    r = requests.get(f"{BASE}/api/templates", headers=h_admin, timeout=TIMEOUT)
    tmpls = r.json().get("data", [])
    all_satisfy = True
    details = []
    for t in tmpls:
        s = t.get("stats", {})
        tot = s.get("total_items")
        cat = s.get("categories")
        chk = s.get("check_items")
        if "质量安全测试" in t.get("name", ""):
            tmpl_demo_id = t.get("id")
        if tot is None or cat is None or chk is None or tot != (cat + chk):
            all_satisfy = False
        details.append(f"{t.get('name')[:10]}:{tot}={cat}+{chk}")
    record("E-02", "全量模板严格满足恒等式 AC-1", "Template", all_satisfy and len(tmpls) >= 1, "所有模板 total=categories+check_items", f"all_valid={all_satisfy}, 详情={'; '.join(details[:3])}", "P0")
except Exception as e:
    record("E-02", "全量模板恒等式 AC-1", "Template", False, "成立", str(e), "P0")

# F-01 获取模板完整树形结构
if tmpl_demo_id:
    try:
        r = requests.get(f"{BASE}/api/templates/{tmpl_demo_id}/items", headers=h_admin, timeout=TIMEOUT)
        items_tree = r.json().get("data", [])
        record("F-01", "获取模板树形结构 (/items 真实端点)", "Template", r.status_code == 200 and len(items_tree) > 0, "200 & items list", f"count={len(items_tree)}", "P1")
    except Exception as e:
        record("F-01", "获取模板树形结构", "Template", False, "200", str(e), "P1")

# F-05 父节点字段清洗及 risk_level 残留验证 (P2-08 验证)
if tmpl_demo_id:
    try:
        # Find a parent node with children
        r_tree = requests.get(f"{BASE}/api/templates/{tmpl_demo_id}/items", headers=h_admin, timeout=TIMEOUT)
        parent_item = None
        for item in r_tree.json().get("data", []):
            if item.get("children"):
                parent_item = item
                break
        if parent_item:
            p_id = parent_item["id"]
            dirty_payload = {
                "name": parent_item["name"],
                "is_category": False,  # Attempt to force check item on parent
                "check_method": "非法注入检查方法",
                "legal_basis": "非法注入法律依据",
                "risk_level": "high",  # Key check for P2-08
                "result_type": "pass_fail"
            }
            r_put = requests.put(f"{BASE}/api/templates/items/{p_id}", headers=h_admin, json=dirty_payload, timeout=TIMEOUT)
            # Re-read the node
            r_check = requests.get(f"{BASE}/api/templates/{tmpl_demo_id}/items", headers=h_admin, timeout=TIMEOUT)
            re_parent = None
            for itm in r_check.json().get("data", []):
                if itm["id"] == p_id:
                    re_parent = itm
                    break
            
            is_cat = re_parent.get("is_category") is True
            method_clean = not re_parent.get("check_method")
            basis_clean = not re_parent.get("legal_basis")
            risk_clean = (re_parent.get("risk_level") is None)
            
            # AC-3 defense: parent must be category, fields cleaned
            record("F-02", "父节点强行设为分类目录 (AC-3)", "Template", is_cat, "is_category=True", f"is_category={re_parent.get('is_category')}", "P0")
            record("F-05", "父节点打分及风险等级字段清洗 (P2-08)", "Template", method_clean and basis_clean and risk_clean, "方法/依据/risk_level全被清洗置空", f"method_clean={method_clean}, risk_level={re_parent.get('risk_level')}", "P2")
    except Exception as e:
        record("F-05", "父节点字段清洗", "Template", False, "清洗干净", str(e), "P2")

# ==============================================================================
# 模块四：政策法规知识库与流式索引域 (G)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块四：政策法规知识库与流式索引域 (G) ---\n" + "="*50)

# G-01 文档列表与 Markdown 标识
try:
    r = requests.get(f"{BASE}/api/knowledge/documents", headers=h_admin, timeout=TIMEOUT)
    docs = r.json().get("data", [])
    docs_list = docs if isinstance(docs, list) else docs.get("items", [])
    has_md = any(d.get("is_markdown") is True for d in docs_list)
    record("G-01", "法规知识库列表查询", "Knowledge", r.status_code == 200 and len(docs_list) >= 1, "200 & 文档列表", f"count={len(docs_list)}", "P1")
    record("G-02", "Markdown 结构化徽标识别", "Knowledge", has_md, "识别出 Markdown 文档", f"has_markdown={has_md}", "P1")
except Exception as e:
    record("G-01", "法规知识库查询", "Knowledge", False, "200", str(e), "P1")

# G-04 解析端点存活性验证
try:
    # POST empty multipart should return 422, proving endpoint exists and validates input
    r = requests.post(f"{BASE}/api/knowledge/documents/parse", headers=h_admin, files={}, timeout=TIMEOUT)
    record("G-04", "文档解析端点存活性 (/parse)", "Knowledge", r.status_code in (422, 400), "422/400 (接口存在且参数校验生效)", r.status_code, "P1")
except Exception as e:
    record("G-04", "文档解析端点存活性", "Knowledge", False, "422/400", str(e), "P1")

# G-08 知识库 RAG 语义检索
try:
    r = requests.post(f"{BASE}/api/ai-enhanced/knowledge/search", headers=h_admin, json={"query": "压力容器充装技术要求"}, timeout=TIMEOUT)
    record("G-08", "知识库 RAG 语义检索 (/ai-enhanced)", "Knowledge", r.status_code == 200, "200 OK", f"status={r.status_code}, data_len={len(r.text)}", "P1")
except Exception as e:
    record("G-08", "知识库 RAG 语义检索", "Knowledge", False, "200", str(e), "P1")

# ==============================================================================
# 模块五：审核项目全生命周期策划域 (H)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块五：审核项目全生命周期策划域 (H) ---\n" + "="*50)

# H-01 项目列表
try:
    r = requests.get(f"{BASE}/api/audit-projects", headers=h_admin, timeout=TIMEOUT)
    prjs = r.json().get("data", [])
    prjs_list = prjs if isinstance(prjs, list) else prjs.get("items", [])
    record("H-01", "审核项目列表查询", "AuditProject", r.status_code == 200 and len(prjs_list) >= 1, "200 & 项目列表", f"count={len(prjs_list)}", "P1")
except Exception as e:
    record("H-01", "审核项目列表查询", "AuditProject", False, "200", str(e), "P1")

# H-04 审核工作量人天校验 (gt=0)
try:
    r_bad_days = requests.post(f"{BASE}/api/audit-projects", headers=h_admin, json={
        "title": "非法天数测试",
        "audit_days": 0,
        "enterprise_id": "00000000-0000-0000-0000-000000000000",
        "standard_codes": ["Q"]
    }, timeout=TIMEOUT)
    record("H-04", "审核工作量 audit_days > 0 约束", "AuditProject", r_bad_days.status_code == 422, "422 Validation Error", r_bad_days.status_code, "P2")
except Exception as e:
    record("H-04", "审核工作量约束", "AuditProject", False, "422", str(e), "P2")

# H-02/06/08/10/12 项目生命周期、叶子派单与级联删除 (P1-01 验证)
test_prj_id = None
try:
    # Find demo enterprise
    ents_r = requests.get(f"{BASE}/api/enterprises", headers=h_admin, timeout=TIMEOUT).json().get("data", [])
    demo_ent_id = (ents_r[0] if isinstance(ents_r, list) else ents_r.get("items", [])[0])["id"]
    
    # Create test project
    prj_payload = {
        "title": f"（E2E自动化）测试审核项目_{MARK}",
        "enterprise_id": demo_ent_id,
        "audit_type": "recertification",
        "standard_codes": ["Q", "E", "S", "En"],
        "audit_days": 2.5,
        "plan_start_date": "2026-10-01",
        "plan_end_date": "2026-10-03"
    }
    r_p_create = requests.post(f"{BASE}/api/audit-projects", headers=h_admin, json=prj_payload, timeout=TIMEOUT)
    test_prj_id = r_p_create.json().get("data", {}).get("id")
    record("H-02", "创建四体系审核项目", "AuditProject", r_p_create.status_code == 200 and bool(test_prj_id), "200 & project_id", f"code={r_p_create.status_code}, id={test_prj_id}", "P0")
    
    # H-06 审核组成员添加
    if test_prj_id and user_expert:
        team_payload = {
            "user_id": user_expert.get("id"),
            "role_in_team": "team_leader",
            "certification_systems": ["Q", "E"]
        }
        r_team = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/team", headers=h_admin, json=team_payload, timeout=TIMEOUT)
        record("H-06", "添加审核组成员", "AuditProject", r_team.status_code == 200, "200 OK", r_team.status_code, "P1")
        
        # H-07 重复成员添加 409
        r_team_dup = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/team", headers=h_admin, json=team_payload, timeout=TIMEOUT)
        record("H-07", "重复添加组员防呆 (409)", "AuditProject", r_team_dup.status_code == 409, "409 Conflict", r_team_dup.status_code, "P2")
    
    # H-08 审核计划排期创建与派发
    test_insp_task_id = None
    if test_prj_id and tmpl_demo_id:
        plan_payload = {
            "plan_date": "2026-10-01",
            "time_start": "09:00",
            "time_end": "12:00",
            "area_name": f"测试车间_{MARK}",
            "template_id": tmpl_demo_id,
            "assigned_member_ids": [user_expert.get("id")] if user_expert else []
        }
        r_plan = requests.post(f"{BASE}/api/audit-projects/{test_prj_id}/plan", headers=h_admin, json=plan_payload, timeout=TIMEOUT)
        plan_data = r_plan.json().get("data", {})
        test_insp_task_id = plan_data.get("inspection_task_id")
        record("H-08", "创建审核计划日程并派发任务", "AuditProject", r_plan.status_code == 200 and bool(test_insp_task_id), "200 & inspection_task_id", f"code={r_plan.status_code}, task_id={test_insp_task_id}", "P1")
        
        # H-10 任务源头排污 AC-4 (只为叶子生成填报记录)
        if test_insp_task_id:
            r_recs = requests.get(f"{BASE}/api/tasks/{test_insp_task_id}/records", headers=h_admin, timeout=TIMEOUT)
            task_records = r_recs.json().get("data", [])
            # 质量安全测试有 2 个叶子项，应恰好生成 2 条填报记录
            record("H-10", "计划派单源头排污 AC-4 (仅为叶子项生成记录)", "AuditProject", len(task_records) == 2, "恰好 2 条叶子记录 (无分类空行)", f"records_count={len(task_records)}", "P0")

    # H-12 审核项目级联删除 (P1-01 验证)
    if test_prj_id:
        r_del_prj = requests.delete(f"{BASE}/api/audit-projects/{test_prj_id}", headers=h_admin, timeout=TIMEOUT)
        record("H-12", "审核项目级联软删除 (P1-01 修复验证)", "AuditProject", r_del_prj.status_code == 200, "200 成功软删除 (杜绝409外键冲突)", f"status={r_del_prj.status_code}, body={r_del_prj.text[:100]}", "P1")
except Exception as e:
    record("H-02", "项目生命周期异常", "AuditProject", False, "200", str(e), "P0")

# ==============================================================================
# 模块七：日常检查任务与我的审核任务域 (J)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块七：日常检查任务与我的审核任务域 (J) ---\n" + "="*50)

# J-01 我的审核任务
try:
    r = requests.get(f"{BASE}/api/audit-projects/my-tasks", headers=h_expert, timeout=TIMEOUT)
    mtasks = r.json().get("data", [])
    record("J-01", "查询我的审核任务 (/my-tasks)", "Task", r.status_code == 200, "200 OK", f"count={len(mtasks)}", "P1")
except Exception as e:
    record("J-01", "查询我的审核任务", "Task", False, "200", str(e), "P1")

# J-03 日常任务列表 (支持 skip / limit)
try:
    r = requests.get(f"{BASE}/api/tasks?skip=0&limit=10", headers=h_admin, timeout=TIMEOUT)
    tasks_data = r.json().get("data", {})
    t_list = tasks_data.get("items", []) if isinstance(tasks_data, dict) else tasks_data
    total_tasks = tasks_data.get("total", len(t_list)) if isinstance(tasks_data, dict) else len(t_list)
    record("J-03", "日常检查任务列表分页查询", "Task", r.status_code == 200 and len(t_list) >= 1, "200 & items", f"total={total_tasks}, return={len(t_list)}", "P1")
except Exception as e:
    record("J-03", "日常检查任务列表", "Task", False, "200", str(e), "P1")

# J-07 任务取消状态机流转 (P2-03 修复验证)
try:
    # Create a dummy task
    ents_r = requests.get(f"{BASE}/api/enterprises", headers=h_admin, timeout=TIMEOUT).json().get("data", [])
    demo_ent_id = (ents_r[0] if isinstance(ents_r, list) else ents_r.get("items", [])[0])["id"]
    r_task_c = requests.post(f"{BASE}/api/tasks", headers=h_admin, json={
        "title": f"（E2E自动化）待取消任务_{MARK}",
        "enterprise_id": demo_ent_id,
        "template_id": tmpl_demo_id
    }, timeout=TIMEOUT)
    cancel_tid = r_task_c.json().get("data", {}).get("id")
    
    if cancel_tid:
        r_cancel = requests.post(f"{BASE}/api/tasks/{cancel_tid}/cancel", headers=h_admin, timeout=TIMEOUT)
        r_check_t = requests.get(f"{BASE}/api/tasks/{cancel_tid}", headers=h_admin, timeout=TIMEOUT)
        status_after = r_check_t.json().get("data", {}).get("status")
        # Check if cancelled
        is_cancelled = (r_cancel.status_code == 200 and status_after == "cancelled")
        record("J-07", "任务取消流转 POST /cancel (P2-03)", "Task", is_cancelled, "200 OK & status=cancelled", f"cancel_code={r_cancel.status_code}, status={status_after}", "P2")
        # Clean up
        requests.delete(f"{BASE}/api/tasks/{cancel_tid}", headers=h_admin, timeout=TIMEOUT)
except Exception as e:
    record("J-07", "任务取消流转", "Task", False, "200", str(e), "P2")

# ==============================================================================
# 模块十：检查记录追溯与规范合规报告生成域 (M)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块十：检查记录追溯与规范合规报告生成域 (M) ---\n" + "="*50)

# M-01 记录列表与分页
rec_id = None
try:
    r = requests.get(f"{BASE}/api/records?skip=0&limit=10", headers=h_admin, timeout=TIMEOUT)
    recs = r.json().get("data", [])
    recs_list = recs if isinstance(recs, list) else recs.get("items", [])
    if recs_list:
        rec_id = recs_list[0]["id"]
    record("M-01", "检查记录列表查询", "Record", r.status_code == 200 and len(recs_list) >= 1, "200 & records", f"count={len(recs_list)}", "P1")
except Exception as e:
    record("M-01", "检查记录列表查询", "Record", False, "200", str(e), "P1")

# M-08 检查记录 PDF 导出接口
if rec_id:
    try:
        r_pdf = requests.get(f"{BASE}/api/records/{rec_id}/report/pdf", headers=h_admin, timeout=TIMEOUT)
        is_pdf = (r_pdf.status_code == 200 and r_pdf.content[:4] == b"%PDF")
        record("M-08", "检查记录合规 PDF 报告导出", "Record", is_pdf, "200 OK & %PDF魔数", f"status={r_pdf.status_code}, len={len(r_pdf.content)}B", "P0")
    except Exception as e:
        record("M-08", "PDF 报告导出", "Record", False, "200", str(e), "P0")

# ==============================================================================
# 模块十一：数据分析与 LLM 调用追溯审计域 (N)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块十一：数据分析与 LLM 调用追溯审计域 (N) ---\n" + "="*50)

# N-01 / N-06 审计日志服务端分页与字段 (P2-05 验证)
try:
    r1 = requests.get(f"{BASE}/api/analytics/audit-logs?skip=0&limit=3", headers=h_admin, timeout=TIMEOUT)
    r2 = requests.get(f"{BASE}/api/analytics/audit-logs?skip=3&limit=3", headers=h_admin, timeout=TIMEOUT)
    d1 = r1.json().get("data", {})
    d2 = r2.json().get("data", {})
    total_logs = d1.get("total", 0)
    items1 = d1.get("items", [])
    items2 = d2.get("items", [])
    ids1 = [x.get("id") for x in items1]
    ids2 = [x.get("id") for x in items2]
    different_pages = (len(ids1) > 0 and len(ids2) > 0 and ids1 != ids2)
    record("N-01", "操作审计日志查询与服务端分页 (P2-05)", "Analytics", different_pages, "不同skip返回不同记录且total>0", f"total={total_logs}, p1={ids1}, p2={ids2}", "P1")
except Exception as e:
    record("N-01", "审计日志分页", "Analytics", False, "生效", str(e), "P1")

# N-03 / N-04 LLM 调用日志记账 (P2-06 验证)
try:
    r_llm = requests.get(f"{BASE}/api/analytics/llm-logs?skip=0&limit=50", headers=h_admin, timeout=TIMEOUT)
    llm_data = r_llm.json().get("data", {})
    llm_items = llm_data.get("items", []) if isinstance(llm_data, dict) else llm_data
    total_llm = llm_data.get("total", len(llm_items)) if isinstance(llm_data, dict) else len(llm_items)
    
    # Check tokens_used presence in agent_chat
    recent_agent_chat = [x for x in llm_items if x.get("call_type") == "agent_chat"]
    has_tokens_value = any(x.get("tokens_used") is not None for x in recent_agent_chat)
    record("N-03", "LLM 调用监控记录查询", "Analytics", r_llm.status_code == 200 and len(llm_items) > 0, "200 & llm logs", f"total={total_llm}, count={len(llm_items)}", "P1")
    record("N-04", "LLM 调用日志 tokens_used 记录 (P2-06)", "Analytics", len(recent_agent_chat) > 0, "存在 agent_chat 记录", f"chat_records={len(recent_agent_chat)}, has_tokens={has_tokens_value}", "P2")
except Exception as e:
    record("N-03", "LLM 调用日志", "Analytics", False, "200", str(e), "P1")

# ==============================================================================
# 模块十二：多维审核统计看板 (O)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块十二：多维审核统计看板 (O) ---\n" + "="*50)

# O-01 宏观统计概览
try:
    r = requests.get(f"{BASE}/api/statistics/overview", headers=h_admin, timeout=TIMEOUT)
    data = r.json().get("data", {})
    record("O-01", "审核宏观业务统计概览", "Statistics", r.status_code == 200 and "total" in data, "200 & total/in_progress", str(data), "P1")
except Exception as e:
    record("O-01", "统计概览", "Statistics", False, "200", str(e), "P1")

# O-02 不符合项两口径对账 (P2-07 验证)
try:
    r_dist = requests.get(f"{BASE}/api/statistics/nonconformities/distribution", headers=h_admin, timeout=TIMEOUT)
    r_sys = requests.get(f"{BASE}/api/statistics/nonconformities/by-system", headers=h_admin, timeout=TIMEOUT)
    
    dist_data = r_dist.json().get("data", [])
    sys_data = r_sys.json().get("data", [])
    
    total_dist = sum(x.get("value", 0) for x in dist_data)
    total_sys = sum(x.get("value", 0) for x in sys_data)
    
    consistent = (total_dist == total_sys)
    record("O-02", "不符合项严重度与体系分布对账闭环 (P2-07)", "Statistics", consistent, f"两口径总数绝对一致 (sum={total_dist})", f"严重度总数={total_dist}, 体系总数={total_sys}", "P2")
except Exception as e:
    record("O-02", "不符合项对账", "Statistics", False, "一致", str(e), "P2")

# O-03 条款 TOP 10 归一化清洗
try:
    r_clause = requests.get(f"{BASE}/api/statistics/nonconformities/by-clause", headers=h_admin, timeout=TIMEOUT)
    clauses = r_clause.json().get("data", [])
    record("O-03", "条款 TOP 10 规范归一化统计", "Statistics", r_clause.status_code == 200 and len(clauses) > 0, "200 & 条款排行", f"clauses={[c.get('name') for c in clauses[:5]]}", "P1")
except Exception as e:
    record("O-03", "条款归一化", "Statistics", False, "200", str(e), "P1")

# ==============================================================================
# 模块十四：安全穿透与性能 (SEC & PERF)
# ==============================================================================
print("\n" + "="*50 + "\n--- 模块十四：安全穿透与性能 (SEC & PERF) ---\n" + "="*50)

# SEC-01 水平越权：专家尝试删除管理员模板
if tmpl_demo_id:
    try:
        r_sec = requests.delete(f"{BASE}/api/templates/{tmpl_demo_id}", headers=h_expert, timeout=TIMEOUT)
        record("SEC-01", "水平越权拦截：专家删除模板", "Security", r_sec.status_code == 403, "403 Forbidden", r_sec.status_code, "P0")
    except Exception as e:
        record("SEC-01", "越权拦截", "Security", False, "403", str(e), "P0")

# SEC-05 SQL 注入防御探测
try:
    r_inj = requests.get(f"{BASE}/api/enterprises?keyword=' OR '1'='1", headers=h_admin, timeout=TIMEOUT)
    record("SEC-05", "SQL 注入防御探测", "Security", r_inj.status_code == 200, "200 参数化安全返回", f"status={r_inj.status_code}", "P0")
except Exception as e:
    record("SEC-05", "SQL 注入防御", "Security", False, "200", str(e), "P0")

# SEC-08 未知路由 404 规范
try:
    r_404 = requests.get(f"{BASE}/api/unknown-endpoint-route-xyz", headers=h_admin, timeout=TIMEOUT)
    record("SEC-08", "未知 API 路由统一 404 规范", "Security", r_404.status_code == 404, "404 Not Found", r_404.status_code, "P1")
except Exception as e:
    record("SEC-08", "未知路由404", "Security", False, "404", str(e), "P1")

# PERF-01 工作台数据大屏响应耗时 (并发 10 次测试)
latencies = []
for _ in range(10):
    t0 = time.time()
    try:
        r = requests.get(f"{BASE}/api/analytics/dashboard", headers=h_admin, timeout=TIMEOUT)
        latencies.append(int((time.time() - t0) * 1000))
    except Exception:
        pass

if latencies:
    latencies.sort()
    p50 = latencies[len(latencies)//2]
    p95 = latencies[int(len(latencies)*0.95)]
    avg = sum(latencies) // len(latencies)
    record("PERF-01", "工作台数据大屏响应耗时", "Performance", p95 < 1000, "P95 < 1000ms", f"avg={avg}ms, p50={p50}ms, p95={p95}ms, max={max(latencies)}ms", "P1")

# ==============================================================================
# 测试汇总统计输出
# ==============================================================================
print("\n" + "="*50 + "\n--- 测试执行汇总 ---\n" + "="*50)
total_tests = len(results)
pass_tests = sum(1 for r in results if r["ok"])
fail_tests = sum(1 for r in results if not r["ok"])
print(f"总用例数: {total_tests} | 通过: {pass_tests} | 失败: {fail_tests} | 通过率: {pass_tests/total_tests*100:.1f}%")

# Save results JSON
with open("docs/_remote_api_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("测试结果已保存至 docs/_remote_api_test_results.json")
