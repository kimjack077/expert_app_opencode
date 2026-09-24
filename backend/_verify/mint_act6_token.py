"""只读：为「引用软删模板的任务」的负责人 mint token（不登录、不写库）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.config import settings  # noqa: E402
from app.utils.security import create_access_token  # noqa: E402

USER_IDS = ("642db41e-6c3c-4ef3-bb8b-cb26ca0aab8c", "4d7549ee-e8a9-4c85-be45-08a8b7635e01")


async def main() -> None:
    conn = await asyncpg.connect(
        host=settings.effective_pg_host,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        database=settings.PG_DB,
    )
    rows = await conn.fetch(
        "SELECT id, username, role, is_deleted, is_active FROM users WHERE id = ANY($1::uuid[])",
        list(USER_IDS),
    )
    await conn.close()
    for r in rows:
        print(dict(r))
    # 取第一个有效用户 mint token
    for r in rows:
        if not r["is_deleted"] and r["is_active"]:
            token = create_access_token({"sub": r["username"], "rv": None, "sid": "act6-probe"})
            Path(__file__).with_name("probe_token.txt").write_text(
                f"{r['username']}\n{token}", encoding="utf-8"
            )
            print(f"token minted for {r['username']}")
            return
    print("NO ACTIVE USER among assignees")


asyncio.run(main())
