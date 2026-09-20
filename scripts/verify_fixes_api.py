# -*- coding: utf-8 -*-
import sys
import io
import json
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://49.232.213.79:8000"

# Admin login
r_login = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
admin_token = r_login.json()["data"]["access_token"]
h_admin = {"Authorization": f"Bearer {admin_token}"}

# 1. Test AuditTeamMember POST schema
print("=== 1. Test AuditTeamMember ===")
ents = requests.get(f"{BASE}/api/enterprises", headers=h_admin).json()["data"]
ent_id = (ents[0] if isinstance(ents, list) else ents.get("items", [])[0])["id"]

# Create temporary project
r_p = requests.post(f"{BASE}/api/audit-projects", headers=h_admin, json={
    "title": "（E2E自动化）组员测试项目",
    "enterprise_id": ent_id,
    "audit_type": "recertification",
    "standard_codes": ["Q"]
})
p_id = r_p.json()["data"]["id"]

# Get user expert id
users = requests.get(f"{BASE}/api/users", headers=h_admin).json()["data"]
exp_user = next(u for u in users if u["username"] == "expert")

# Add team member
team_payload = {
    "member_id": exp_user["id"],
    "role_in_team": "leader",
    "certification_systems": ["Q"]
}
r_team = requests.post(f"{BASE}/api/audit-projects/{p_id}/team", headers=h_admin, json=team_payload)
print("Team add status:", r_team.status_code, r_team.text[:100])

# Duplicate add
r_team_dup = requests.post(f"{BASE}/api/audit-projects/{p_id}/team", headers=h_admin, json=team_payload)
print("Team duplicate add status:", r_team_dup.status_code, r_team_dup.text[:100])

# Delete project
r_p_del = requests.delete(f"{BASE}/api/audit-projects/{p_id}", headers=h_admin)
print("Project delete status:", r_p_del.status_code)

# 2. Test Statistics by-clause
print("\n=== 2. Test Statistics by-clause ===")
r_clause = requests.get(f"{BASE}/api/statistics/nonconformities/by-clause", headers=h_admin)
print("by-clause data:", json.dumps(r_clause.json().get("data"), ensure_ascii=False))

# 3. Test Template Items Tree structure
print("\n=== 3. Test Template Items Tree ===")
tmpls = requests.get(f"{BASE}/api/templates", headers=h_admin).json()["data"]
t_demo = next(t for t in tmpls if "质量安全测试" in t["name"])
r_items = requests.get(f"{BASE}/api/templates/{t_demo['id']}/items", headers=h_admin)
items_data = r_items.json()["data"]
print("Items count:", len(items_data))
for it in items_data:
    print(" - Item:", it.get("name") or it.get("title"), "id:", it.get("id"), "is_category:", it.get("is_category"), "children:", len(it.get("children", [])))

# 4. Fresh Expert Login for B-02 and J-01
print("\n=== 4. Fresh Expert Login & Routes ===")
r_exp_fresh = requests.post(f"{BASE}/api/auth/login", json={"username": "expert", "password": "expert123"})
exp_token = r_exp_fresh.json()["data"]["access_token"]
h_exp = {"Authorization": f"Bearer {exp_token}"}

# B-02: Expert access /users -> Expect 403
r_b02 = requests.get(f"{BASE}/api/users", headers=h_exp)
print("B-02 Expert access /users status:", r_b02.status_code)

# J-01: Expert access /my-tasks -> Expect 200
r_j01 = requests.get(f"{BASE}/api/audit-projects/my-tasks", headers=h_exp)
print("J-01 Expert access /my-tasks status:", r_j01.status_code, "count:", len(r_j01.json().get("data", [])))

# SEC-01: Expert delete template -> Expect 403
r_sec01 = requests.delete(f"{BASE}/api/templates/{t_demo['id']}", headers=h_exp)
print("SEC-01 Expert delete template status:", r_sec01.status_code)
