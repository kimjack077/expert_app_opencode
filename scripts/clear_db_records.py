import sys
import asyncio
import argparse
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import text
from app.database import AsyncSessionLocal

# ⚠️ 本地与线上共用同一个远程数据库（db_expert_claude）。
# 本脚本默认仅预演（只统计各表行数），必须显式加 --apply 才会真正清空，
# 且永远不要对生产库运行 --apply。

TABLES = [
    "inspection_record_items",
    "inspection_records",
    "template_items",
    "inspection_templates",
]


async def preview():
    async with AsyncSessionLocal() as session:
        print("== 预演模式（不修改数据）。将清空以下表：")
        total = 0
        for t in TABLES:
            n = (await session.execute(text(f"SELECT count(*) FROM {t}"))).scalar() or 0
            total += n
            print(f"   {t}: {n} 行")
        print(f"合计 {total} 行。确认无误后请追加 --apply 执行。")


async def apply():
    async with AsyncSessionLocal() as session:
        for t in TABLES:
            await session.execute(text(f"TRUNCATE TABLE {t} CASCADE;"))
        await session.commit()
        print("All data cleared successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="清空检查模板与检查记录表（危险操作，默认仅预演）"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真正执行清空；不带该参数仅预演统计行数",
    )
    args = parser.parse_args()

    if args.apply:
        asyncio.run(apply())
    else:
        asyncio.run(preview())
