# -*- coding: utf-8 -*-
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://49.232.213.79:8000'
r_login = requests.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
admin_token = r_login.json()['data']['access_token']
h_admin = {'Authorization': f'Bearer {admin_token}'}

tasks = requests.get(f'{BASE}/api/tasks?limit=100', headers=h_admin).json()['data']
t_items = tasks.get('items', []) if isinstance(tasks, dict) else tasks
print('Total tasks:', len(t_items))
for t in t_items:
    if '质量安全' in t.get('title', '') or '客户演示' in t.get('title', '') or '盛发' in t.get('title', ''):
        print(f"ID: {t.get('id')} | Title: {t.get('title')} | Status: {t.get('status')} | Assignee: {t.get('assigned_to')}")
