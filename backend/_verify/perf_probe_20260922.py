"""只读性能探测：测量本地到远程 PG 的往返延迟与典型查询耗时。

只执行 SELECT，不写入任何数据（遵守 AGENTS.md 不污染生产库的约束）。
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg

from app.config import settings


async def main() -> None:
    print(f"PG host: {settings.effective_pg_host}:{settings.PG_PORT} db={settings.PG_DB}")

    t0 = time.perf_counter()
    conn = await asyncpg.connect(
        host=settings.effective_pg_host,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        database=settings.PG_DB,
    )
    print(f"connect: {(time.perf_counter() - t0) * 1000:.0f} ms")

    for _ in range(5):
        t = time.perf_counter()
        await conn.fetchval("SELECT 1")
        print(f"SELECT 1 rtt: {(time.perf_counter() - t) * 1000:.0f} ms")

    t = time.perf_counter()
    await conn.fetch("SELECT id, username, role FROM users WHERE is_deleted=false LIMIT 5")
    print(f"users lookup: {(time.perf_counter() - t) * 1000:.0f} ms")

    for table in ("inspection_templates", "inspection_tasks", "enterprises", "inspection_records"):
        t = time.perf_counter()
        n = await conn.fetchval(f"SELECT count(*) FROM {table}")
        print(f"count {table}: {(time.perf_counter() - t) * 1000:.0f} ms (rows={n})")

    # 模拟一次典型列表请求的串行链路: pre_ping + 鉴权查用户 + 列表查询
    t = time.perf_counter()
    await conn.fetchval("SELECT 1")  # pool_pre_ping
    await conn.fetch("SELECT id, username, role FROM users WHERE is_deleted=false LIMIT 1")
    await conn.fetch("SELECT id FROM inspection_templates ORDER BY created_at DESC LIMIT 20")
    print(f"simulated list request chain: {(time.perf_counter() - t) * 1000:.0f} ms")

    await conn.close()


asyncio.run(main())
