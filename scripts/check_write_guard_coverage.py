# -*- coding: utf-8 -*-
"""验证：写入守卫用 resolve_check_type 后，数值型/描述型检查项不再被误拒。

直接用生产库中的**真实模板项**跑，只读；不写库、不依赖服务进程。

用法（在仓库根目录或任意位置均可）::

    backend/.venv/Scripts/python.exe scripts/check_write_guard_coverage.py

背景：2026-09-19 老杨实测报出「Web 记录页给数值型检查项填数值后保存失败」。
根因是 ``POST /records/{id}/items`` 的守卫直接读 ``template_item.check_type``，
而该列恒为列默认值 ``'radio'``（模板编辑器只写 ``result_type``）。
本脚本用真实数据对比「旧口径 vs 新口径」的拒绝情况。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.utils.item_completion import resolve_check_type          # noqa: E402
from app.utils.item_write_guard import validate_item_payload      # noqa: E402


class Row:
    """把数据库行包装成带属性的对象，模拟 TemplateItem 模型。"""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def main() -> int:
    env = {}
    for line in (REPO_ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

    import psycopg2

    conn = psycopg2.connect(
        host=env["PG_HOST"], port=env["PG_PORT"], dbname=env["PG_DB"],
        user=env["PG_USER"], password=env["PG_PASSWORD"],
    )
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    # 找出「真实类型不是 radio」但 check_type 是列默认值的检查项
    cur.execute("""
        SELECT id, title, check_type, result_type, min_value, max_value, result_options
        FROM template_items
        WHERE is_category IS NOT TRUE
          AND result_type IS NOT NULL AND result_type NOT IN ('pass_fail')
        ORDER BY result_type, title
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    print("=" * 78)
    print("生产库中「check_type 为列默认值、真实类型写在 result_type」的检查项")
    print("=" * 78)
    print("共 %d 项\n" % len(rows))

    # 真实类型 → 前端实际会提交的字段
    probe = {"numeric": ("numeric_value", "100.9"),
             "text": ("text_value", "现场检查未发现异常"),
             "single_choice": ("radio_value", "pass")}

    old_fail = new_fail = 0
    checked = 0

    for tid, title, ctype, rtype, mn, mx, opts in rows:
        rtype = (rtype or "").strip().lower()
        if rtype not in probe:
            continue
        checked += 1
        field, value = probe[rtype]
        item = Row(check_type=ctype, result_type=rtype,
                   min_value=mn, max_value=mx, result_options=opts)

        # 旧实现：直接读 check_type（列默认 'radio'）
        old_err = validate_item_payload(
            check_type=ctype, payload={field: value},
            result_options=opts, min_value=mn, max_value=mx,
        )
        # 新实现：走 resolve_check_type
        new_err = validate_item_payload(
            check_type=resolve_check_type(item), payload={field: value},
            result_options=opts, min_value=mn, max_value=mx,
        )

        if old_err:
            old_fail += 1
        if new_err:
            new_fail += 1

        if old_err != new_err:
            print("【行为改变】%-24s result_type=%-14s" % ((title or "")[:22], rtype))
            print("    旧(读 check_type=%r)：%s" % (ctype, "拒绝 ✗" if old_err else "放行 ✓"))
            print("    新(resolve=%r)：%s" % (resolve_check_type(item),
                                              "拒绝 ✗" if new_err else "放行 ✓"))
            print()

    print("=" * 78)
    print("合计 %d 项：旧实现拒绝 %d 项 / 新实现拒绝 %d 项" % (checked, old_fail, new_fail))
    print("=" * 78)
    if new_fail == 0 and old_fail > 0:
        print("结论：修复生效 —— 真实客户端载荷（只传值、不传 check_type）不再被误拒。")
        return 0
    if old_fail == 0 and new_fail == 0:
        print("结论：这批数据在旧实现下也没被拒（可能已无受影响项）。")
        return 0
    print("结论：仍有 %d 项被拒，需进一步排查。" % new_fail)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
