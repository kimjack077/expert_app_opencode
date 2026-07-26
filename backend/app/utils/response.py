"""统一的 API 响应封装。

历史问题：8 个路由各自定义了一份 ``make_response``，且 ``timestamp`` 格式不统一
（有的是 ``datetime`` 对象、有的是 ``utcnow().isoformat()+"Z"``、有的带 tz）。
同一个 API 契约在不同端点上返回的时间格式不一样，前端只能各处特判。

所有路由统一从这里引入。
"""

from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """带时区的 ISO8601 时间戳，全项目统一格式。"""
    return datetime.now(timezone.utc).isoformat()


def make_response(
    data: Any = None,
    code: int = 200,
    message: str = "success",
) -> dict[str, Any]:
    """构造标准响应体 ``{code, message, data, timestamp}``。"""
    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": utc_now_iso(),
    }
