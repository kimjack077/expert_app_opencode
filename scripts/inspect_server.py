#!/usr/bin/env python3
"""只读勘察远程服务器 —— 判断 EFIS 线上真实拓扑。

不写任何文件、不重启任何服务、不修改任何配置。
"""

from __future__ import annotations

import sys

import paramiko

COMMANDS: tuple[tuple[str, str], ...] = (
    ("主机名 / 系统", "hostname; uname -sr"),
    ("/opt/efis 是否存在", "ls -la /opt/efis 2>/dev/null || echo '【不存在 /opt/efis】'"),
    (
        "/home/ubuntu/expert_app 是否存在",
        "ls -la /home/ubuntu/expert_app 2>/dev/null | head -15 || echo '【不存在 /home/ubuntu/expert_app】'",
    ),
    ("systemd efis-backend 状态", "systemctl is-active efis-backend 2>&1; systemctl is-enabled efis-backend 2>&1"),
    (
        "systemd 单元定义",
        "systemctl cat efis-backend 2>/dev/null | head -20 || echo '【无该单元】'",
    ),
    ("nginx 状态", "systemctl is-active nginx 2>&1"),
    ("nginx 站点配置", "ls -la /etc/nginx/sites-enabled/ 2>&1 | head"),
    ("监听端口", "ss -lntp 2>/dev/null | head -25"),
    (
        "后端健康检查",
        "curl -s -o /dev/null -w 'backend_health=%{http_code}\\n' --max-time 8 http://localhost:8000/api/health 2>&1",
    ),
    (
        "首页可达性",
        "curl -s -o /dev/null -w 'root=%{http_code}\\n' --max-time 8 http://localhost/ 2>&1; "
        "curl -s -o /dev/null -w 'h5=%{http_code}\\n' --max-time 8 http://localhost/h5/ 2>&1",
    ),
    (
        "后端代码位置与时间",
        "ls -la /opt/efis/backend/app/utils/soft_delete.py 2>/dev/null || echo '【无 /opt/efis/backend】'; "
        "ls -la /home/ubuntu/expert_app/backend/app/utils/soft_delete.py 2>/dev/null || echo '【无 expert_app/backend】'",
    ),
    (
        "运行中的 uvicorn/vite 进程",
        "ps -eo pid,etime,cmd 2>/dev/null | grep -E 'uvicorn|vite' | grep -v grep || echo '【无】'",
    ),
)


def main() -> int:
    if len(sys.argv) < 4:
        print("用法: inspect_server.py <host> <user> <password>")
        return 2

    host, user, password = sys.argv[1], sys.argv[2], sys.argv[3]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, 22, user, password, timeout=20, allow_agent=False, look_for_keys=False)
    except Exception as exc:  # noqa: BLE001
        print(f"【连接失败】{host}: {type(exc).__name__}: {exc}")
        return 1

    print("=" * 72)
    print(f"只读勘察：{host}")
    print("=" * 72)

    try:
        for label, cmd in COMMANDS:
            print(f"\n── {label} ──")
            _stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
            out = stdout.read().decode("utf-8", "replace").strip()
            err = stderr.read().decode("utf-8", "replace").strip()
            if out:
                print(out)
            if err:
                print(f"[stderr] {err}")
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
