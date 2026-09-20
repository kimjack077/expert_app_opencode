import json, requests

with open('docs/_new_demo_assets.json', 'r', encoding='utf-8') as f:
    assets = json.load(f)

r = requests.post('http://49.232.213.79:8000/api/auth/login', json={'username':'expert','password':'expert123'}).json()
token = r['data']['access_token']
tid = assets['task_id']
task = requests.get(f'http://49.232.213.79:8000/api/tasks/{tid}', headers={'Authorization': f'Bearer {token}'}).json()['data']
print('Task Status:', task['status'])
print('Task Title:', task['title'])
