"""heal_categories.py - 根节点/分类目录存量数据自愈脚本

治理目标（对应《EFIS_外部测试问题清单》A 类主线）：

1. 找出所有分类目录（显式 ``is_category=True`` 的条目 ∪ 存在有效子节点的父节点），
   统一规范化为纯分类目录：清空全部检查项属性（判定类型、分值、检查方法等）。
2. 清理 task_item_records 中历史 bug 遗留的**完全空白**分类目录记录。
   仅当结果、结果值、文本、检查员备注、AI 建议**全部为空**时才清理；
   带填写结果的分类记录保留（属用户真实操作痕迹），由接口层统一过滤。

用法::

    # 预演（默认，只统计不写入，强烈建议先跑一次）
    python -m scripts.heal_categories

    # 实际执行写入
    python -m scripts.heal_categories --apply

注意（AGENTS.md 硬约束）：
    本地与线上共用同一个远程数据库（PG_HOST=49.232.213.79 / PG_DB=db_expert_claude），
    本脚本一旦带 --apply 执行，等同于直接修改生产数据。
    执行前请先备份 template_items 与 task_item_records 两张表。
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import and_, delete, func, or_, select, update  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.task import TaskItemRecord  # noqa: E402
from app.models.template import TemplateItem  # noqa: E402
from app.utils.category import (  # noqa: E402
    CATEGORY_FIELD_OVERRIDES,
    parent_id_subquery,
)
from app.utils.soft_delete import not_deleted  # noqa: E402


def _empty_record_condition(category_ids):
    """"完全空白"的分类目录记录条件。

    只有当结果、文本、备注、AI 建议**全部为空**时才认定为垃圾记录，
    避免误删"用户填了备注但没选结论"这类有信息量的记录。
    """
    return and_(
        TaskItemRecord.template_item_id.in_(category_ids),
        TaskItemRecord.result.is_(None),
        TaskItemRecord.result_value.is_(None),
        TaskItemRecord.result_text.is_(None),
        TaskItemRecord.inspector_note.is_(None),
        TaskItemRecord.llm_suggestion.is_(None),
    )


async def heal(apply: bool = False) -> None:
    mode = "【写入模式】" if apply else "【预演模式 · 不写入】"
    print(f"=== 根节点与层级关系自愈 {mode} ===")

    async with AsyncSessionLocal() as db:
        # 1. 所有拥有有效子节点的父节点 ID
        parents_res = await db.execute(
            select(TemplateItem.parent_id).where(
                TemplateItem.parent_id.is_not(None),
                not_deleted(TemplateItem),
            )
        )
        parent_ids = list({row[0] for row in parents_res.all() if row[0]})
        print(f"1) 存在有效子节点的父节点：{len(parent_ids)} 个")

        # 2. 分类目录全集 = 显式标记 is_category 的条目 ∪ 存在有效子节点的父节点。
        #    刻意不过滤 is_deleted：已软删除的分类项同样可能挂着历史垃圾记录
        #    （例如「测试级别」的子项被删光后，它自己仍是 is_category=True）。
        cat_res = await db.execute(
            select(TemplateItem.id).where(
                or_(
                    TemplateItem.is_category.is_(True),
                    TemplateItem.id.in_(parent_id_subquery()),
                )
            )
        )
        category_ids = {row[0] for row in cat_res.all()}
        print(f"2) 分类目录全集（含无子节点的空分类）：{len(category_ids)} 个")

        if not category_ids:
            print("   无需处理，退出。")
            return

        # 3. 待清理的分类目录空白记录
        empty_res = await db.execute(
            select(func.count(TaskItemRecord.id)).where(
                _empty_record_condition(category_ids)
            )
        )
        empty_count = empty_res.scalar() or 0
        print(f"3) 待清理的分类目录空白填报记录：{empty_count} 条")

        # 4. 带填写结果的分类记录（保留，由接口层过滤，不删）
        kept_res = await db.execute(
            select(func.count(TaskItemRecord.id)).where(
                TaskItemRecord.template_item_id.in_(category_ids),
                TaskItemRecord.result.is_not(None),
            )
        )
        print(f"4) 保留（带历史填写结果、仅接口层过滤）：{kept_res.scalar() or 0} 条")

        if not apply:
            print()
            print("以上为预演结果，未做任何写入。确认无误后加 --apply 重新执行。")
            return

        # 5. 规范化分类目录（字段清单统一取自 app/utils/category）
        upd_res = await db.execute(
            update(TemplateItem)
            .where(TemplateItem.id.in_(category_ids))
            .values(**CATEGORY_FIELD_OVERRIDES)
        )
        print(f"5) 已规范化 {upd_res.rowcount} 个条目为标准分类目录")

        # 6. 清理分类目录空白记录（TaskItemRecord 无软删除字段，按硬删除处理）
        del_res = await db.execute(
            delete(TaskItemRecord).where(_empty_record_condition(category_ids))
        )
        print(f"6) 已清理 {del_res.rowcount} 条分类目录空白填报记录")

        await db.commit()
        print("=== 自愈完成（已提交）===")


def main() -> None:
    parser = argparse.ArgumentParser(description="根节点/分类目录存量数据自愈")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际写入数据库；不加此参数时仅预演统计",
    )
    args = parser.parse_args()
    asyncio.run(heal(apply=args.apply))


if __name__ == "__main__":
    main()
