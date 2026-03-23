---
name: dev-starter
description: 启动专家现场工作辅助系统的后端、Web管理端和H5移动端三个服务。当用户要求启动项目开发环境、启动后端前端服务或运行项目时使用此skill。
---

# 开发环境启动器

此skill用于启动专家现场工作辅助系统(EFIS)的完整开发环境，包括：
- 后端 API 服务 (FastAPI)
- Web 管理端 (React + Ant Design)
- H5 移动端 (Vue 3 + Vant)

## 启动命令

### 1. 后端服务

```bash
cd /d/sofeware/expert_app_opencode/backend
./venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- 端口: 8000
- API文档: http://localhost:8000/api/docs

### 2. Web管理端

```bash
cd /d/sofeware/expert_app_opencode/web-admin
npm run dev
```

- 端口: 3000
- 访问地址: http://localhost:3000

### 3. H5移动端

```bash
cd /d/sofeware/expert_app_opencode/h5-app
npm run dev
```

- 端口: 5174
- 访问地址: http://localhost:5174/h5/

## 快速启动脚本

可以使用 PowerShell 一键启动所有服务：

```powershell
# 后端 (使用虚拟环境)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'd:/sofeware/expert_app_opencode/backend'; ./venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

# Web管理端  
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'd:/sofeware/expert_app_opencode/web-admin'; npm run dev"

# H5移动端
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'd:/sofeware/expert_app_opencode/h5-app'; npm run dev"
```

## 环境要求

- Node.js 18+
- Python 3.10+
- PostgreSQL (已配置在 62.234.0.182:5432)
- Redis (如需缓存功能)

## 项目结构

```
expert_app_opencode/
├── backend/           # FastAPI后端
│   ├── venv/         # Python虚拟环境
│   └── app/
│       ├── main.py   # 应用入口
│       ├── config.py # 配置
│       └── routers/  # API路由
├── web-admin/        # React管理后台
│   └── src/
│       ├── pages/    # 页面组件
│       └── services/ # API服务
├── h5-app/           # Vue3移动端
│   └── src/
│       ├── views/    # 页面视图
│       └── api/      # API封装
└── skills/           # 技能包
```
