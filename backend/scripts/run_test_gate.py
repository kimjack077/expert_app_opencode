"""一键测试门禁：按 L1 → L4 分层执行，任一层失败即阻断。

═══════════════════════════════════════════════════════════════════════════
 用法
═══════════════════════════════════════════════════════════════════════════
    cd backend

    # 只跑不需要数据库的两层（提交前自查，约 5 秒）
    .venv\\Scripts\\python.exe scripts/run_test_gate.py --fast

    # 跑全部四层（需要测试库）
    set EFIS_TEST_DB_NAME=db_expert_test
    .venv\\Scripts\\python.exe scripts/run_test_gate.py

    # 只跑指定层
    .venv\\Scripts\\python.exe scripts/run_test_gate.py --only L1,L3

═══════════════════════════════════════════════════════════════════════════
 分层与前置条件
═══════════════════════════════════════════════════════════════════════════
    L1 契约层  contract  口径唯一性 + 跨端字段一致性      无需数据库
    L2 单元层  unit      纯函数逻辑（归类/守恒/合规率）   无需数据库
    L3 接口层  api       CRUD 全链路 + 写入校验 + 权限矩阵  需要隔离测试库
    L3 报表层  report    详情/报告/列表三方对账            需要隔离测试库
    L4 端到端  e2e       前后端联调（需服务在跑）          需要服务

═══════════════════════════════════════════════════════════════════════════
 安全约束（重要）
═══════════════════════════════════════════════════════════════════════════
本地与线上**共用同一个远程数据库**（``PG_HOST=49.232.213.79``，
``PG_DB=db_expert_claude``）。因此：

* 未配置 ``EFIS_TEST_DB_NAME`` / ``EFIS_TEST_DATABASE_URL`` 时，
  本脚本**拒绝执行** L3 及以上，并提示如何创建隔离测试库；
* ``tests/conftest.py`` 另有第二道闸：一旦检测到连接串指向生产主机或库名，
  直接抛 ``RuntimeError`` 拒绝启动，不会"静默写生产"。

换句话说，本脚本不依赖使用者自觉 —— 两道闸都不通过就跑不起来。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

# (层名, pytest marker, 是否需要数据库, 说明)
LEVELS: tuple[tuple[str, str, bool, str], ...] = (
    ("L1", "contract", False, "契约层：口径唯一性 + 跨端字段一致性"),
    ("L2", "unit", False, "单元层：归类 / 守恒律 / 合规率"),
    ("L3-api", "api", True, "接口层：CRUD 全链路 + 写入校验 + 权限矩阵"),
    ("L3-report", "report", True, "报表层：详情 / 报告 / 列表三方对账"),
    ("L4", "e2e", True, "端到端：前后端联调（需服务在跑）"),
)

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"

# pytest 退出码：0 全部通过 / 1 有用例失败 / 5 未收集到任何用例
EXIT_OK = 0
EXIT_NO_TESTS = 5


def _test_db_configured() -> bool:
    return bool(
        os.environ.get("EFIS_TEST_DB_NAME")
        or os.environ.get("EFIS_TEST_DATABASE_URL")
    )


def _safe_write(text: str) -> None:
    """编码安全地写标准输出。

    Windows 控制台常用 GBK，无法编码 pytest 输出里的 ✓ / ✗ 等字符，
    直接 write 会抛 UnicodeEncodeError 打断整层执行。统一降级为可打印字符。
    """
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.write(text.encode(enc, "replace").decode(enc, "replace"))
    sys.stdout.flush()


def _run_level(marker: str, verbose: bool) -> tuple[int, float, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-m",
        marker,
        "-q",
        "--tb=short",
        "-p",
        "no:randomly",
    ]
    if verbose:
        cmd.append("-v")

    started = time.monotonic()
    collected: list[str] = []

    # 流式输出：接口层要跑十几分钟，必须能实时看到进度。
    # 同时把全文收进 collected，供后续判定是否基础设施抖动。
    #
    # PYTHONUNBUFFERED=1 是必需的：pytest 的进度点输出到管道时会被**块缓冲**，
    # 不加这个变量就只能等整层跑完才一次性吐出来，流式输出形同虚设。
    child_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        collected.append(line)
        _safe_write(line)
    proc.wait()

    return proc.returncode, time.monotonic() - started, "".join(collected)


# ---------------------------------------------------------------------------
# 基础设施抖动 vs 真实失败
# ---------------------------------------------------------------------------
# 本地与线上共用同一个**远程**数据库（49.232.213.79，走公网）。
# 实测：一次 14 分钟的全量接口层跑下来，偶发连接被中间链路掐断，
# 表现为 Windows 网络信号灯超时（WinError 121）→ asyncpg
# ConnectionDoesNotExistError → 该请求 500 → 用例失败。
#
# 这类失败**与代码无关**：同样的用例单独跑必然通过。
# 但一个随机失败的门禁比没有门禁更糟 —— 没人会再相信它。
#
# 处置原则：**识别出来就重跑一次，但绝不静默放过**。
# 重跑通过 → 标记为「通过（抖动重试）」并在汇总里显著提示；
# 重跑仍失败 → 如实报失败。宁可多花一轮时间，不可掩盖问题。
TRANSIENT_INFRA_SIGNATURES: tuple[str, ...] = (
    "ConnectionDoesNotExistError",
    "connection was closed in the middle of operation",
    "ConnectionResetError",
    "ConnectionRefusedError",
    "WinError 121",
    "信号灯超时时间已到",
    "server closed the connection unexpectedly",
    "SSLEOFError",
    "TooManyConnectionsError",
    "asyncpg.exceptions.InterfaceError",
)


def _looks_like_infra_flake(output: str) -> str | None:
    """输出里是否出现基础设施抖动的特征；返回命中的特征，未命中返回 None。"""
    for signature in TRANSIENT_INFRA_SIGNATURES:
        if signature in output:
            return signature
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EFIS 分层测试门禁",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="只跑不需要数据库的 L1 + L2（提交前自查用）",
    )
    parser.add_argument(
        "--only",
        default="",
        help="只跑指定层，逗号分隔，如 L1,L3-api（层名见上方说明）",
    )
    parser.add_argument("--verbose", action="store_true", help="透传 -v 给 pytest")
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="不做基础设施抖动重试（CI 严格模式：任何失败都直接判定）",
    )
    args = parser.parse_args()

    selected = LEVELS
    if args.fast:
        selected = tuple(level for level in LEVELS if not level[2])
    elif args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        unknown = wanted - {level[0] for level in LEVELS}
        if unknown:
            print(f"{RED}未知层名：{sorted(unknown)}{RESET}")
            print(f"可用层名：{[level[0] for level in LEVELS]}")
            return 2
        selected = tuple(level for level in LEVELS if level[0] in wanted)

    db_ok = _test_db_configured()
    needs_db = [level[0] for level in selected if level[2]]

    print("=" * 72)
    print("EFIS 分层测试门禁")
    print("=" * 72)
    print(f"测试库环境变量：{'已配置' if db_ok else f'{YELLOW}未配置{RESET}'}")

    if needs_db and not db_ok:
        print()
        print(f"{RED}拒绝执行：以下层需要隔离测试库，但环境变量未配置{RESET}")
        print(f"  {needs_db}")
        print()
        print("本地与线上共用同一个远程数据库，裸跑会写脏生产数据。请先：")
        print(f"  {DIM}-- 一次性创建测试库 --{RESET}")
        print("  CREATE DATABASE db_expert_test TEMPLATE db_expert_claude;")
        print(f"  {DIM}-- 每次执行前设置 --{RESET}")
        print("  set EFIS_TEST_DB_NAME=db_expert_test")
        print()
        print(f"或先跑不需要数据库的层：{DIM}--fast{RESET}")
        return 2

    results: list[tuple[str, str, int, float]] = []
    infra_flakes: list[str] = []
    for name, marker, needs, desc in selected:
        print()
        print("-" * 72)
        print(f"[{name}] {desc}")
        print("-" * 72)

        code, elapsed, output = _run_level(marker, args.verbose)

        # 退出码 5 = 该层还没有用例。这不是失败，但**必须显著提示**，
        # 否则"门禁通过"会让人误以为这层已被覆盖 —— 那是比失败更危险的假象。
        if code == EXIT_NO_TESTS:
            status = f"{YELLOW}无用例{RESET}"
            results.append((name, status, EXIT_OK, elapsed))
            print(f"\n[{name}] {status}  用时 {elapsed:.1f}s")
            print(
                f"{YELLOW}注意：{name} 当前没有任何用例，该层尚未被覆盖。"
                f"{RESET}"
            )
            continue

        flaked_on: str | None = None

        # 失败先看是不是远程库网络抖动：是则重跑一次，但不静默放过
        if code != EXIT_OK and not args.no_retry:
            flaked_on = _looks_like_infra_flake(output)
            if flaked_on:
                print()
                print(
                    f"{YELLOW}[{name}] 命中基础设施抖动特征：{flaked_on}{RESET}"
                )
                print(
                    f"{YELLOW}远程库连接被中断（非代码问题），重跑本层一次以区分"
                    f"抖动与真实失败……{RESET}"
                )
                retry_code, retry_elapsed, retry_output = _run_level(marker, args.verbose)
                elapsed += retry_elapsed

                if retry_code == EXIT_OK:
                    code = EXIT_OK
                    status = f"{GREEN}通过{RESET}{YELLOW}(抖动重试){RESET}"
                    results.append((name, status, EXIT_OK, elapsed))
                    print(f"\n[{name}] {status}  用时 {elapsed:.1f}s")
                    print(
                        f"{YELLOW}注意：本层首次执行因远程库网络抖动失败"
                        f"（{flaked_on}），重跑通过。{RESET}"
                    )
                    print(
                        f"{DIM}这不是代码问题，但若频繁出现，说明到 "
                        f"49.232.213.79 的网络链路不稳定，需排查。{RESET}"
                    )
                    infra_flakes.append(name)
                    continue

                code = retry_code
                output = retry_output
                print(
                    f"{RED}[{name}] 重跑后仍然失败 —— 判定为真实失败，不是抖动。{RESET}"
                )

        status = f"{GREEN}通过{RESET}" if code == EXIT_OK else f"{RED}失败{RESET}"
        results.append((name, status, code, elapsed))
        print(f"\n[{name}] {status}  用时 {elapsed:.1f}s")

        if code != EXIT_OK:
            # 门禁语义：任一层失败即停，避免后续层在坏基础上继续跑
            print(f"{RED}门禁阻断：{name} 未通过，后续层不再执行。{RESET}")
            break

    print()
    print("=" * 72)
    print("结果汇总")
    print("=" * 72)
    for name, status, _, elapsed in results:
        print(f"  {name:<12} {status:<16} {elapsed:>7.1f}s")

    failed = [name for name, _, code, _ in results if code != EXIT_OK]
    executed = {name for name, _, _, _ in results}
    skipped = [level[0] for level in selected if level[0] not in executed]
    uncovered = [name for name, status, _, _ in results if "无用例" in status]

    if skipped:
        print(f"\n  {YELLOW}未执行：{skipped}{RESET}")
    if uncovered:
        print(f"\n  {YELLOW}尚未覆盖（无用例）：{uncovered}{RESET}")
    if infra_flakes:
        print(
            f"\n  {YELLOW}因远程库网络抖动重试后通过：{infra_flakes}{RESET}"
        )
        print(
            f"  {DIM}这些层的用例本身没有问题，失败来自到 49.232.213.79 的网络链路。"
            f"频繁出现需排查链路，否则门禁耗时会被无谓拉长。{RESET}"
        )

    print()
    if failed:
        print(f"{RED}门禁不通过：{failed}{RESET}")
        return 1

    if uncovered:
        # 通过，但明确告知有层未被覆盖，避免"全绿"造成虚假信心
        print(f"{YELLOW}门禁通过（注意：{uncovered} 尚无用例）{RESET}")
        return 0

    print(f"{GREEN}门禁通过{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
