# -*- coding: utf-8 -*-
"""审计追溯：谁、从哪个 IP、在什么时候、对什么资源做了什么。

背景（2026-09-20）：生产库 `inspection_tasks` 116 条与 `inspection_records` 94 条
被整批软删，需要定位操作者。答案全在 ``audit_logs`` 表里：

    id / user_id / username / action / resource_type / resource_id
    detail / ip_address / user_agent / created_at

要点：
  * ``action`` 形如 ``DELETE /api/records/<uuid>``，用 ``split_part`` 即可拆出动词与资源；
  * **登录事件不记用户名**（``POST /api/auth/login`` 时尚未认证，username 为 NULL），
    只能靠紧随其后的业务操作归属推断是谁登录的；
  * 因此排查"谁删的"要按 **(username, ip_address, user_agent)** 三元组聚合，
    再看该 IP 的历史出现日期判断是不是常规用户。

用法（backend 目录下）::

    python ../scripts/audit_trail.py --date 2026-09-20
    python ../scripts/audit_trail.py --since '2026-09-20 01:50' --until '2026-09-20 02:40'
    python ../scripts/audit_trail.py --ip 120.225.21.118
    python ../scripts/audit_trail.py --date 2026-09-20 --writes-only
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from datetime import timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.getcwd())  # 需在 backend/ 目录下运行

from sqlalchemy import text  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402

WRITE_VERBS = ("POST", "PUT", "PATCH", "DELETE")


def _where(args) -> tuple[str, dict]:
    """构造 WHERE 子句。

    asyncpg 对 ``timestamptz`` 的绑定参数做严格类型检查：传**字符串**直接报
    ``DataError``；传**naive datetime** 不报错但恒查不到（实测同样区间
    naive → 0 行，aware → 68 行）。所以必须解析成带时区的 datetime 再绑。
    命令行按 ``audit_logs.created_at`` 的 UTC 口径解释输入。
    """
    from datetime import date, datetime, timezone

    def as_dt(value: str) -> datetime:
        value = value.strip()
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = datetime.combine(date.fromisoformat(value), datetime.min.time())
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    clauses, params = [], {}
    if args.date:
        clauses.append("created_at >= :d0 AND created_at < :d1")
        params["d0"] = as_dt(args.date)
        params["d1"] = params["d0"] + timedelta(days=1)
    if args.since:
        clauses.append("created_at >= :since")
        params["since"] = as_dt(args.since)
    if args.until:
        clauses.append("created_at <= :until")
        params["until"] = as_dt(args.until)
    if args.ip:
        clauses.append("ip_address = :ip")
        params["ip"] = args.ip
    if args.writes_only:
        clauses.append("split_part(action,'/',1) = ANY(:verbs)")
        params["verbs"] = list(WRITE_VERBS)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


async def main(args) -> int:
    where, params = _where(args)
    async with AsyncSessionLocal() as db:
        print("=" * 78)
        print("审计追溯" + (f"  条件：{where.strip() or '（全部）'}" if where else "  条件：全部"))
        print("=" * 78)

        print("\n[1] 按 (用户, IP, 浏览器) 聚合 —— 谁在用这个系统")
        rows = (await db.execute(text(f"""
            SELECT coalesce(username, '(登录未记名)') u, ip_address,
                   left(coalesce(user_agent,''), 44) ua, count(*) c,
                   min(created_at) t0, max(created_at) t1
            FROM audit_logs{where}
            GROUP BY 1,2,3 ORDER BY t0
        """), params)).fetchall()
        for r in rows:
            print(f"    {r[0]:10s} {r[1]:16s} {r[2]:46s} {r[3]:5d} 次  "
                  f"{r[4]:%m-%d %H:%M:%S} ~ {r[5]:%m-%d %H:%M:%S}")

        print("\n[2] 按 (动词, 资源, 用户, IP) 聚合 —— 到底做了什么")
        rows = (await db.execute(text(f"""
            SELECT split_part(action,'/',1) verb,
                   split_part(split_part(action,'/',3),'?',1) res,
                   coalesce(username,'(未记名)') u, ip_address, count(*) c,
                   min(created_at) t0, max(created_at) t1
            FROM audit_logs{where}
            GROUP BY 1,2,3,4 ORDER BY c DESC LIMIT 40
        """), params)).fetchall()
        for r in rows:
            print(f"    {r[0]:7s} /{r[1]:24s} {r[2]:10s} {r[3]:16s} {r[4]:5d} 次  "
                  f"{r[5]:%H:%M:%S} ~ {r[6]:%H:%M:%S}")

        print("\n[3] 删除类动作逐条（最近 40 条）")
        rows = (await db.execute(text(f"""
            SELECT created_at, coalesce(username,'(未记名)'), ip_address, action
            FROM audit_logs{where}{' AND' if where else ' WHERE'} action LIKE 'DELETE%'
            ORDER BY created_at DESC LIMIT 40
        """), params)).fetchall()
        if not rows:
            print("    （无）")
        for r in rows:
            print(f"    {r[0]:%m-%d %H:%M:%S}  {r[1]:10s} {r[2]:16s} {r[3]}")

    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="审计日志追溯")
    ap.add_argument("--date", help="某一天（YYYY-MM-DD）")
    ap.add_argument("--since", help="起始时间（YYYY-MM-DD HH:MM）")
    ap.add_argument("--until", help="结束时间（YYYY-MM-DD HH:MM）")
    ap.add_argument("--ip", help="只看某个 IP")
    ap.add_argument("--writes-only", action="store_true", help="只看写操作（POST/PUT/PATCH/DELETE）")
    sys.exit(asyncio.run(main(ap.parse_args())))
