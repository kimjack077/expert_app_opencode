---
alwaysApply: false
---
如果程序没有运行，需要运行，后端都用虚拟环境运行
后端：.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
web端：npm run dev
H5端：npm run dev
