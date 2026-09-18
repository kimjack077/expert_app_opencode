#!/usr/bin/env python3
"""仅部署后端 —— 依赖与前端未变时的最小风险部署。

═══════════════════════════════════════════════════════════════════════════
 为什么需要这个脚本（而不是直接用 deploy.py / deploy_server.py）
═══════════════════════════════════════════════════════════════════════════
线上真实拓扑（2026-09-17 实测，与 docs/agents/ops.md 的描述已不一致）：

    /home/ubuntu/expert_app/backend     后端，nohup uvicorn :8000
    /home/ubuntu/expert_app/web-admin   前端，npx vite preview :3000
    /home/ubuntu/expert_app/h5-app      前端，npx vite preview :5173

    注意：`/opt/efis`、systemd `efis-backend`、nginx 这套在 49.232.213.79 上
    **都不存在**（那是另一台已不可达的机器 62.234.0.182 的拓扑）。

两个现成脚本都不适用：

* ``deploy.py``（全量）—— 会重装后端依赖、重建两个前端、全部重启。
  当 ``requirements.txt`` 与前端源码相对线上**零差异**时，这些动作只增加风险
  与停机时间：前端重建一旦失败，会把本来正常的前端一起弄挂。
* ``deploy_server.py``（仅后端）—— 会在服务器上执行 ``alembic upgrade``。
  本地与线上**共用同一个远程生产库**，运维文档明确要求「不跑数据库迁移」。
  该脚本会让生产库结构被迁移脚本改动，**不可使用**。

本脚本只做三件事，停机时间约数秒，前端完全不受影响：

    1. 上传 backend/（沿用 deploy.py 的排除规则，含 backend/.env）
    2. 重启 uvicorn（pkill + nohup，与 deploy.py 启动方式一致）
    3. 健康检查 + 部署内容校验（确认新模块真的落到了线上）

═══════════════════════════════════════════════════════════════════════════
 用法
═══════════════════════════════════════════════════════════════════════════
    backend/.venv\\Scripts\\python.exe scripts/deploy_backend_only.py --dry-run
    backend/.venv\\Scripts\\python.exe scripts/deploy_backend_only.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import paramiko  # noqa: E402

# 复用 deploy.py 的上传实现与排除规则，避免两套逻辑漂移
from deploy import (  # noqa: E402
    EXCLUDES,
    HOST,
    PASSWORD,
    PORT,
    REMOTE_DIR,
    USER,
    run_remote_command,
    upload_directory,
)

# 部署后必须在服务器上出现的新模块 —— 用来证明「新代码真的上去了」，
# 而不是只看服务是否存活（服务存活但跑的是旧代码是最坏的假象）。
EXPECTED_NEW_FILES: tuple[str, ...] = (
    "app/utils/business_time.py",
    "app/utils/item_write_guard.py",
)

# 部署后必须在既有文件里出现的新标记（用于确认文件内容已更新）
EXPECTED_MARKERS: tuple[tuple[str, str], ...] = (
    ("app/utils/soft_delete.py", "INDIRECT_CASCADE_POLICY"),
    ("app/utils/item_stats.py", "classify_item"),
)

HEALTH_URL = "http://localhost:8000/api/health"


def _ssh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, PORT, USER, PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    return client


def _run(ssh, cmd: str, timeout: int = 120) -> tuple[bool, str]:
    ok, out, err = run_remote_command(ssh, cmd, timeout=timeout)
    return ok, (out or err or "")


def _health_code(ssh) -> str:
    _, out = _run(
        ssh,
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 8 {HEALTH_URL} || echo 000",
        timeout=30,
    )
    return out.strip().splitlines()[-1].strip() if out.strip() else "000"


def _current_uvicorn_pid(ssh) -> str:
    _, out = _run(
        ssh,
        "pgrep -f 'uvicorn app.main:app' | head -1 || echo ''",
        timeout=30,
    )
    return out.strip().splitlines()[-1].strip() if out.strip() else ""


def main() -> int:
    parser = argparse.ArgumentParser(description="仅部署后端（最小风险）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要执行的动作，不实际执行")
    args = parser.parse_args()

    print("=" * 72)
    print("EFIS 仅后端部署")
    print("=" * 72)
    print(f"  目标：{USER}@{HOST}:{PORT}{REMOTE_DIR}/backend")
    print(f"  模式：{'试运行（不落盘）' if args.dry_run else '实际执行'}")
    print()

    if args.dry_run:
        print("将执行：")
        print("  1. SFTP 上传 backend/（排除 .venv / __pycache__ / *.pyc / .git / .env）")
        print("  2. 单独同步 backend/.env")
        print("  3. pkill -f 'uvicorn app.main:app' 后以 nohup 重启")
        print(f"  4. 健康检查 {HEALTH_URL} 直到返回 200")
        print("  5. 校验新模块与标记已落到服务器")
        print("\n前端（web-admin:3000 / h5-app:5173）不会被触碰。")
        return 0

    print("[1/5] 连接服务器……")
    ssh = _ssh()
    print("  连接成功")
    sftp = ssh.open_sftp()

    try:
        print("\n[2/5] 上传 backend/ ……")
        count = upload_directory(sftp, "backend", f"{REMOTE_DIR}/backend", EXCLUDES["backend"])
        print(f"  上传完成：{count} 个文件")

        print("\n  同步 backend/.env ……")
        sftp.put(str(ROOT / "backend" / ".env"), f"{REMOTE_DIR}/backend/.env")
        print("  backend/.env 同步完成")

        old_pid = _current_uvicorn_pid(ssh)
        print(f"\n[3/5] 重启后端（重启前 PID：{old_pid or '未运行'}）……")

        ok, _ = _run(ssh, "pkill -f 'uvicorn app.main:app' || true", timeout=30)
        # 等端口释放，避免新进程绑定失败
        for _ in range(20):
            code = _health_code(ssh)
            if code == "000":
                break
            time.sleep(0.5)
        time.sleep(1)

        start_cmd = (
            f"cd {REMOTE_DIR}/backend && source .venv/bin/activate && "
            f"nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 "
            f"> {REMOTE_DIR}/backend.log 2>&1 & echo $!"
        )
        ok, out = _run(ssh, start_cmd, timeout=60)
        new_pid = out.strip().splitlines()[-1].strip() if out.strip() else ""
        print(f"  已启动，PID：{new_pid or '<未取到>'}")

        print("\n[4/5] 健康检查……")
        code = "000"
        for attempt in range(30):
            time.sleep(1)
            code = _health_code(ssh)
            if code == "200":
                print(f"  {HEALTH_URL} → 200（第 {attempt + 1} 次探测）")
                break
            print(f"  等待中…… HTTP {code}（第 {attempt + 1} 次）")

        if code != "200":
            print("\n【失败】后端未在 30 秒内恢复 200。")
            print("排查命令：")
            print(f"  tail -80 {REMOTE_DIR}/backend.log")
            print("如需回滚：重新上传旧版本 backend/ 后重启。")
            return 1

        print("\n[5/5] 校验部署内容……")
        problems: list[str] = []

        for rel in EXPECTED_NEW_FILES:
            _, out = _run(ssh, f"test -f {REMOTE_DIR}/backend/{rel} && echo YES || echo NO", timeout=30)
            if "YES" not in out:
                problems.append(f"缺少新文件：{rel}")
            else:
                print(f"  [OK] 新文件已就位：{rel}")

        for rel, marker in EXPECTED_MARKERS:
            _, out = _run(
                ssh,
                f"grep -c '{marker}' {REMOTE_DIR}/backend/{rel} || echo 0",
                timeout=30,
            )
            count = out.strip().splitlines()[-1].strip() if out.strip() else "0"
            if count.isdigit() and int(count) > 0:
                print(f"  [OK] {rel} 含标记 {marker}（{count} 处）")
            else:
                problems.append(f"{rel} 未找到标记：{marker}")

        # 进程与端口复核
        _, out = _run(ssh, "ps -eo pid,etime,cmd | grep 'uvicorn app.main:app' | grep -v grep || echo NONE", timeout=30)
        print(f"  运行中的后端进程：{out.strip()}")

        print()
        print("=" * 72)
        if problems:
            print("部署完成，但**内容校验未通过**：")
            for p in problems:
                print(f"  - {p}")
            print("\n服务已返回 200，但可能仍在跑旧代码，请人工确认。")
            return 1

        print("部署完成，内容校验全部通过。")
        print("=" * 72)
        print(f"  后端 API:   http://{HOST}:8000")
        print(f"  Web Admin:  http://{HOST}:3000   （未改动）")
        print(f"  H5 App:     http://{HOST}:5173   （未改动）")
        print(f"  后端日志:   {REMOTE_DIR}/backend.log")
        return 0

    finally:
        sftp.close()
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
