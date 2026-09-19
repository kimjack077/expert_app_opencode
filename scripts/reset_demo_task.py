import json
import requests

with open('docs/_new_demo_assets.json', 'r', encoding='utf-8') as f:
    assets = json.load(f)

API_BASE = 'http://49.232.213.79:8000'

r = requests.post(f"{API_BASE}/api/auth/login", json={'username': 'admin', 'password': 'admin123'}).json()
token = r['data']['access_token']

task_id = assets['task_id']
r_put = requests.put(
    f"{API_BASE}/api/tasks/{task_id}",
    json={'status': 'in_progress', 'remarks': ''},
    headers={'Authorization': f'Bearer {token}'}
)
print("演示任务复位结果:", r_put.status_code, r_put.json().get('message'))

# 验证任务当前状态
r_get = requests.get(
    f"{API_BASE}/api/tasks/{task_id}",
    headers={'Authorization': f'Bearer {token}'}
).json()['data']
print(f"✅ 任务「{r_get['title']}」当前状态: {r_get['status']}，已处于随时供现场演示填报状态！")
