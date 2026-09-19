"""风险等级口径的契约门禁。

背景：``app/routers/analytics.py`` 与 ``app/routers/enterprises.py`` 曾**各写一份**
等级映射，且都把 ``A`` 归为 ``high``、把 ``C``/``D`` 归为 ``low``，与前端
``Enterprises`` 列表的标签（A=低风险、D=高风险）**完全倒挂**——工作台
「风险预警企业」因此把低风险企业算成高风险，真正的高风险企业反而不触发预警。

本文件做两件事：
1. 锁定 ``app.utils.risk_level`` 的正确映射；
2. 静态扫描 ``app/``，禁止再出现自建的风险等级映射。
"""

import re
from pathlib import Path

import pytest

from app.utils.risk_level import (
    BUCKET_LEVELS,
    LEVEL_LABELS,
    normalize_risk_bucket,
    levels_in_bucket,
    risk_level_label,
)

pytestmark = pytest.mark.contract

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_ROOT / "app"

#: 唯一允许出现「等级 → 风险桶」映射的文件（相对 app/ 的 posix 路径）
ALLOWED_MAPPING_FILES = {"utils/risk_level.py"}

#: 形如 "A": "high" / 'C': 'low' 的自建映射
LEVEL_TO_BUCKET_PATTERN = re.compile(
    r"""["']([ABCD])["']\s*:\s*["'](high|medium|low)["']"""
)


def test_等级到风险桶的映射与前端语义一致():
    """A=低风险、B=一般（中）、C=较高、D=高——与前端标签逐一对齐。"""
    assert normalize_risk_bucket("A") == "low"
    assert normalize_risk_bucket("B") == "medium"
    assert normalize_risk_bucket("C") == "high"
    assert normalize_risk_bucket("D") == "high"


def test_历史倒挂组合必须被明确排除():
    """把 A 归为 high、把 C/D 归为 low 是本次修复的原始缺陷，不得回归。"""
    assert normalize_risk_bucket("A") != "high"
    assert normalize_risk_bucket("C") != "low"
    assert normalize_risk_bucket("D") != "low"


def test_未评级与未知取值按低风险处理且不放大风险():
    for value in (None, "", "   ", "Z9", "unknown"):
        assert normalize_risk_bucket(value) == "low"


def test_已是风险桶的取值幂等():
    for bucket in ("high", "medium", "low"):
        assert normalize_risk_bucket(bucket) == bucket
        assert normalize_risk_bucket(bucket.upper()) == bucket


def test_风险桶反查等级可覆盖全部取值():
    """三个桶的并集必须覆盖 A/B/C/D 与未评级，且互不重叠。"""
    covered: list = []
    for bucket in ("high", "medium", "low"):
        covered.extend(levels_in_bucket(bucket))
    assert set(covered) == {"A", "B", "C", "D", None}
    # 无重复归属
    assert len(covered) == len(set(covered))
    assert BUCKET_LEVELS["high"] == ("C", "D")


def test_中文标签与前端一致():
    assert LEVEL_LABELS["A"] == "A级（低风险）"
    assert LEVEL_LABELS["B"] == "B级（一般）"
    assert LEVEL_LABELS["C"] == "C级（较高风险）"
    assert LEVEL_LABELS["D"] == "D级（高风险）"
    assert risk_level_label(None) == "未评级"
    assert risk_level_label("Z9") == "Z9"


def test_app_内不存在自建的风险等级映射():
    """任何 app/ 下的模块都不得再手写 A/B/C/D → high/medium/low 的映射。"""
    offenders: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = path.relative_to(APP_DIR).as_posix()
        if rel in ALLOWED_MAPPING_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = LEVEL_TO_BUCKET_PATTERN.search(line)
            if match:
                offenders.append(f"{rel}:{lineno}  {line.strip()}")

    assert not offenders, (
        "检测到自建的风险等级映射，请改为调用 app.utils.risk_level：\n"
        + "\n".join(f"  {item}" for item in offenders)
    )


def test_两个历史调用点都引用统一口径():
    """analytics 与企业路由必须引用 app.utils.risk_level，而不是自己实现。"""
    for rel in ("routers/analytics.py", "routers/enterprises.py"):
        text = (APP_DIR / rel).read_text(encoding="utf-8", errors="ignore")
        assert "app.utils.risk_level" in text, f"{rel} 未引用统一的风险等级口径"
