"""从 LLM 文本输出中稳健地提取 JSON。

不同网关/模型即使传了 ``response_format={"type": "json_object"}``，也可能返回：

* 前后包裹 Markdown 代码围栏（```json ... ```）
* 前置空行、思考段落或说明文字（"以下是结果：\\n\\n{...}"）
* 末尾多余的逗号或说明

直接 ``json.loads(content)`` 会抛 ``JSONDecodeError``，调用方若未兜底就会把
"AI 服务暂时不可用" 返回给用户 —— 实际上模型已经给出了合法 JSON。
本模块提供统一的提取入口，避免每个服务各写一份脆弱的解析逻辑。
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _try_loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def extract_json(text: Any) -> Any:
    """解析 LLM 输出中的 JSON；无法解析时抛出 ``ValueError``。

    依次尝试：原文 → 代码围栏内容 → 首个 ``{``/``[`` 到最后一个闭合符号。
    """
    if text is None:
        raise ValueError("empty LLM response")
    raw = str(text).strip()
    if not raw:
        raise ValueError("empty LLM response")

    parsed = _try_loads(raw)
    if parsed is not None:
        return parsed

    for match in _FENCE_RE.finditer(raw):
        parsed = _try_loads(match.group(1).strip())
        if parsed is not None:
            return parsed

    # 截取第一个对象/数组起点到最后一个闭合符号
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = raw.find(open_ch)
        end = raw.rfind(close_ch)
        if start != -1 and end > start:
            candidate = raw[start : end + 1]
            parsed = _try_loads(candidate)
            if parsed is not None:
                return parsed

    raise ValueError(f"invalid JSON from LLM: {raw[:120]!r}")
