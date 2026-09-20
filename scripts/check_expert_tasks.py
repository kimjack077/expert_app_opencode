# -*- coding: utf-8 -*-
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://49.232.213.79:8000'
r_login = requests.post(f'{BASE}/api/auth/login', json={'username': 'expert', 'password': 'expert123'})
expert_token = r_login.json()['data']['access_token']
h_exp = {'Authorization': f'Bearer {expert_token}'}

tasks = requests.get(f'{BASE}/api/tasks?limit=50', headers=h_exp).json()['data']
t_items = tasks.get('items', []) if isinstance(tasks, dict) else tasks
print('Expert tasks count:', len(t_items))
for t in t_items:
    print(f"ID: {t.get('id')} | Title: {t.get('title')} | Status: {t.get('status')}")
