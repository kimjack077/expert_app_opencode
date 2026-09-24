"""只读探测线上部署状态 v2（正确处理 run_remote_command 返回的 (stdout, stderr)）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import paramiko  # noqa: E402

from deploy import HOST, PASSWORD, PORT, REMOTE_DIR, USER, run_remote_command  # noqa: E402

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)


def run(cmd: str) -> str:
    res = run_remote_command(ssh, cmd)
    if isinstance(res, tuple):
        out = res[0] or ""
        err = res[1] or ""
        return (out + ("\n[stderr] " + err if err.strip() else "")).strip()
    return str(res).strip()


CHECKS = [
    ("uvicorn 进程与启动时间",
     "ps -o pid,lstart,cmd -p $(pgrep -f 'uvicorn app.main:app' | head -1) --no-headers"),
    ("backend 目录体积", f"du -sh {REMOTE_DIR}/backend"),
    ("关键文件时间戳",
     f"ls -l --time-style=+%H:%M:%S {REMOTE_DIR}/backend/app/utils/security.py "
     f"{REMOTE_DIR}/backend/app/routers/tasks.py"),
    ("新标记(窗口函数计数)", f"grep -c 'count().over()' {REMOTE_DIR}/backend/app/routers/tasks.py"),
    ("新标记(鉴权缓存)", f"grep -c '_load_user_by_username' {REMOTE_DIR}/backend/app/utils/security.py"),
    ("健康检查", "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health"),
]

for label, cmd in CHECKS:
    try:
        print(f"[{label}]\n{run(cmd)}\n")
    except Exception as exc:
        print(f"[{label}] ERROR {exc}\n")

ssh.close()
