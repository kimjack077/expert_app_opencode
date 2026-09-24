"""只读：取一个管理员用户名并在本地签发 token（不登录、不写库），用于计时探测。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.config import settings  # noqa: E402
from app.utils.security import create_access_token  # noqa: E402


async def main() -> None:
    conn = await asyncpg.connect(
        host=settings.effective_pg_host,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        database=settings.PG_DB,
    )
    row = await conn.fetchrow(
        "SELECT username FROM users WHERE is_deleted=false AND is_active=true "
        "AND role IN ('admin','super_admin') ORDER BY created_at LIMIT 1"
    )
    await conn.close()
    username = row["username"]
    token = create_access_token({"sub": username, "rv": None, "sid": "perf-probe"})
    out = Path(__file__).with_name("probe_token.txt")
    out.write_text(f"{username}\n{token}", encoding="utf-8")
    print(f"token minted for {username}")


asyncio.run(main())
