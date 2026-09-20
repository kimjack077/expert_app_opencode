import requests
import json

BASE = 'http://49.232.213.79:8000'
r_login = requests.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
admin_token = r_login.json()['data']['access_token']
headers = {'Authorization': f'Bearer {admin_token}'}

print('=== 1. DASHBOARD ===')
dash = requests.get(f'{BASE}/api/analytics/dashboard', headers=headers).json()['data']
print('Tasks:', dash['tasks'])
print('Inspections:', dash['inspections'])
print('Compliance Rate:', dash.get('compliance_rate'))

print('\n=== 2. AUDIT PROJECTS ===')
prjs = requests.get(f'{BASE}/api/audit-projects', headers=headers).json()['data']
prjs_items = prjs if isinstance(prjs, list) else prjs.get('items', [])
print('Projects count:', len(prjs_items))
for p in prjs_items:
    print(f" - {p.get('project_no')}: {p.get('title')} (status: {p.get('status')})")

print('\n=== 3. ENTERPRISES ===')
ents = requests.get(f'{BASE}/api/enterprises', headers=headers).json()['data']
ents_items = ents if isinstance(ents, list) else ents.get('items', [])
print('Enterprises count:', len(ents_items))
for e in ents_items:
    print(f" - {e.get('name')} | risk: {e.get('risk_level')}")

print('\n=== 4. TEMPLATES & AC-1 ===')
tmpls = requests.get(f'{BASE}/api/templates', headers=headers).json()['data']
tmpls_items = tmpls if isinstance(tmpls, list) else tmpls.get('items', [])
print('Templates count:', len(tmpls_items))
for t in tmpls_items:
    tot = t.get('total_items')
    cat = t.get('categories_count')
    itm = t.get('items_count')
    match = (tot == (cat + itm)) if tot is not None and cat is not None and itm is not None else False
    print(f" - {t.get('name')}: total={tot}, cat={cat}, items={itm} | AC-1 valid: {match}")

print('\n=== 5. KNOWLEDGE DOCUMENTS ===')
docs = requests.get(f'{BASE}/api/knowledge/documents', headers=headers).json()['data']
docs_items = docs if isinstance(docs, list) else docs.get('items', [])
print('Knowledge docs count:', len(docs_items))
for d in docs_items:
    print(f" - {d.get('title')} | is_markdown: {d.get('is_markdown')} | status: {d.get('status')}")

print('\n=== 6. STATISTICS OVERVIEW ===')
stats = requests.get(f'{BASE}/api/statistics/overview', headers=headers).json()['data']
print('Statistics overview:', stats)

print('\n=== 7. MY TASKS (EXPERT) ===')
t_expert = requests.post(f'{BASE}/api/auth/login', json={'username': 'expert', 'password': 'expert123'}).json()['data']['access_token']
h_exp = {'Authorization': f'Bearer {t_expert}'}
my_tasks = requests.get(f'{BASE}/api/audit-projects/my-tasks', headers=h_exp).json().get('data', [])
print('Expert my-tasks count:', len(my_tasks))
for mt in my_tasks:
    print(f" - {mt.get('area_name')}: {mt.get('status')} | task_id: {mt.get('task_id')}")

print('\n=== 8. DAILY INSPECTION TASKS ===')
tasks = requests.get(f'{BASE}/api/tasks?limit=100', headers=headers).json()['data']
t_items = tasks.get('items', []) if isinstance(tasks, dict) else tasks
print('Daily inspection tasks count:', len(t_items))
