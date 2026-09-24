"""验证 DB_POOL_PRE_PING 自动判定逻辑（只读，不连库）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402

SRC = (Path(__file__).resolve().parents[1] / "app" / "config.py").read_text(encoding="utf-8")

# 1. 重复定义自查（上一轮编辑曾把 ALGORITHM 等写了两遍）
for field in ("ALGORITHM: str", "ACCESS_TOKEN_EXPIRE_MINUTES: int", "REFRESH_TOKEN_EXPIRE_DAYS: int"):
    n = SRC.count(field)
    print(f"{field:34s} 定义次数={n}  {'OK' if n == 1 else 'DUPLICATE!'}")

# 2. 本地（连公网远程库，非回环）→ 应自动关闭
local = Settings(_env_file=None, PG_HOST="49.232.213.79")
print(f"本地(PG 公网远端)      effective_host={local.effective_pg_host:15s} pre_ping={local.db_pool_pre_ping}")

# 3. 线上（同机回环，模拟 /home/ubuntu/expert_app 存在时的切换结果）→ 应自动开启
prod_like = Settings(_env_file=None, PG_HOST="127.0.0.1")
print(f"线上(PG 回环)          effective_host={prod_like.effective_pg_host:15s} pre_ping={prod_like.db_pool_pre_ping}")

# 4. 显式覆盖优先
forced_off = Settings(_env_file=None, PG_HOST="127.0.0.1", DB_POOL_PRE_PING=False)
forced_on = Settings(_env_file=None, PG_HOST="49.232.213.79", DB_POOL_PRE_PING=True)
print(f"显式 false 覆盖        pre_ping={forced_off.db_pool_pre_ping}")
print(f"显式 true  覆盖        pre_ping={forced_on.db_pool_pre_ping}")

assert local.db_pool_pre_ping is False
assert prod_like.db_pool_pre_ping is True
assert forced_off.db_pool_pre_ping is False
assert forced_on.db_pool_pre_ping is True
print("ALL ASSERTIONS PASSED")
