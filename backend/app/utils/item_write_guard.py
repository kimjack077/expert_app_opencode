"""检查项写入侧校验 —— 挡住"数据存进去了但没人读得到"的静默丢失。

═══════════════════════════════════════════════════════════════════════════
 为什么要有这个模块
═══════════════════════════════════════════════════════════════════════════
模板检查项按 ``check_type`` 分为 6 类，每类的结果**存在不同字段**：

    score         → score_value      （打分）
    radio         → radio_value      （单选）
    multi_check   → multi_value      （多选）
    numeric       → numeric_value    （数值）
    text          → text_value       （文本）
    audit_3level  → radio_value      （审核三级评估，复用单选字段）

``POST /records/{record_id}/items`` 原先**不做任何校验**：前端把结果写进哪个字段
就落哪个字段。于是出现两类第三方反复报出的问题：

1. **数据无法录入** —— H5 端把单选结果写进 ``text_value``，接口 200 成功、
   库里确实有值，但 PC 端与报告只读 ``radio_value``，界面上永远是空的。
   用户看到的现象是"填了没反应"，本质是**字段写错但无提示**。

2. **结论缺失** —— ``radio_value`` 写入了不在 ``result_options`` 里的值
   （如拼错的 ``"qualified"``），该值无法归类为合格/不合格/不适用，
   报表里既不计数也不报错，检查项变成"黑洞"。

本模块把这两类问题在**写入时**拦下并给出可操作的错误信息。

═══════════════════════════════════════════════════════════════════════════
 设计原则
═══════════════════════════════════════════════════════════════════════════
* **只在确定有问题时拒绝**。历史数据里 ``check_type`` 全部为 ``radio``，
  但代码声称支持 6 类；因此对**未知 check_type** 明确拒绝（防止再写入
  无法被读取的字段），对**已知 check_type 但未带结果字段**放行（允许分步保存）。
* **错误信息面向使用者**，说清"哪个字段该写哪个字段"，
  不要只抛 "422 Unprocessable Entity"。
* **不做隐式改写**。不把 ``text_value`` 悄悄搬到 ``radio_value`` ——
  静默改写会让前端继续写错字段，问题被掩盖而非解决。
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

# check_type → 该类型唯一合法的结果字段
CHECK_TYPE_RESULT_FIELD: dict[str, str] = {
    "score": "score_value",
    "radio": "radio_value",
    "multi_check": "multi_value",
    "numeric": "numeric_value",
    "text": "text_value",
    "audit_3level": "radio_value",
}

# check_type 历史别名。
#   pass_fail —— 旧字段 ``result_type`` 的取值，语义等同单选。
#   前端读取时写的是 ``check_type || result_type || 'pass_fail'``，
#   因此客户端完全可能把 ``pass_fail`` 回传上来。若不认它，
#   正常保存会被判成"未知类型"而拒绝 —— 那就成了我们自己制造的
#   「数据无法录入」。
CHECK_TYPE_ALIASES: dict[str, str] = {
    "pass_fail": "radio",
    "pass-fail": "radio",
}

# 全部结果承载字段（用于检测"写错了字段"）
RESULT_PAYLOAD_FIELDS: tuple[str, ...] = (
    "score_value",
    "radio_value",
    "multi_value",
    "numeric_value",
    "text_value",
)

# 中文名，用于错误信息
CHECK_TYPE_LABEL: dict[str, str] = {
    "score": "打分",
    "radio": "单选",
    "multi_check": "多选",
    "numeric": "数值",
    "text": "文本",
    "audit_3level": "三级评估",
}

FIELD_LABEL: dict[str, str] = {
    "score_value": "打分结果(score_value)",
    "radio_value": "单选结果(radio_value)",
    "multi_value": "多选结果(multi_value)",
    "numeric_value": "数值结果(numeric_value)",
    "text_value": "文本结果(text_value)",
}

_MAX_TEXT_LENGTH = 20000


def _is_blank(value: Any) -> bool:
    """空值判定：None / 空串 / 空列表 / 全空白串都算"没写"。"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def option_values(result_options: Any) -> list[str]:
    """从 ``result_options`` 中提取允许的取值集合。

    该字段是自由 JSON，库中实际存在三种形态（2026-09 探查 232 条模板项）：

        {"options": [{"value": "pass", "label": "合格", ...}]}
        [{"label": "符合", "value": "pass", "color": "green"}]
        null                        ← 125 条，无选项配置

    因此本函数**宽容解析**：能取到就返回，取不到返回空列表表示"不校验取值"。
    绝不能因为结构不认识就报错——那会把历史数据判成非法。
    """
    if not result_options:
        return []

    options = result_options
    if isinstance(result_options, dict):
        # 包裹形态：{"options": [...]} / {"values": [...]} / {"items": [...]}
        # 注意：**只有确实命中包裹键时才下钻**。否则 options 会变成空列表，
        # 导致 {"pass": "合格"} 这种"键即取值"的形态被漏掉（实测踩过）。
        wrapped = None
        for key in ("options", "values", "items", "choices"):
            if key in result_options:
                wrapped = result_options[key]
                break
        options = wrapped if wrapped is not None else result_options

    values: list[str] = []
    if isinstance(options, (list, tuple)):
        for entry in options:
            if isinstance(entry, dict):
                raw = entry.get("value", entry.get("key"))
                if raw is not None:
                    values.append(str(raw))
            elif entry is not None:
                values.append(str(entry))
    elif isinstance(options, str):
        values = [options]
    # 其余形态（未识别的 dict、数字、布尔…）一律返回空列表 = 不校验取值。
    #
    # 为什么不把扁平 dict 当"键即取值"映射：
    #   {"pass": "合格"} 看起来可以解析，但 {"unknown_key": 1} 这类结构会被
    #   解析成 allowed=["unknown_key"]，于是正常写入 radio_value="pass"
    #   反被拒绝 —— 那正是本模块要消除的「数据无法录入」。
    #   库中 232 条模板项的实测形态只有三种（{"options":[...]} / [{value,label}] /
    #   null），扁平映射并不存在，因此选择 fail-open：不认识就不校验。

    return [v for v in values if v.strip()]


def _validate_numeric(
    raw: Any, min_value: Optional[float], max_value: Optional[float]
) -> list[str]:
    errors: list[str] = []
    try:
        number = float(str(raw).strip())
    except (TypeError, ValueError):
        return [
            f"数值类型检查项的结果 {raw!r} 不是合法数字，"
            "请写入形如 \"12.5\" 的数值（不要带单位或中文）。"
        ]

    if min_value is not None and number < float(min_value):
        errors.append(f"数值结果 {number} 小于允许下限 {min_value}。")
    if max_value is not None and number > float(max_value):
        errors.append(f"数值结果 {number} 大于允许上限 {max_value}。")
    return errors


def validate_item_payload(
    *,
    check_type: Optional[str],
    payload: dict[str, Any],
    result_options: Any = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allowed_result_values: Optional[Iterable[str]] = None,
) -> list[str]:
    """校验一次检查项写入。返回错误信息列表，空列表表示通过。

    ``payload`` 只需包含结果字段（``radio_value`` / ``numeric_value`` 等），
    值为 ``None`` 的字段视为未提供。

    ``allowed_result_values`` 用于 ``radio`` 类：若调用方已知合法判定值
    （如 :data:`app.utils.item_stats.PASS_VALUES` 等），可一并传入做白名单校验。
    """
    errors: list[str] = []

    # ---- 1. check_type 必须可识别 ----
    normalized = (check_type or "").strip().lower() or None
    if normalized is not None:
        normalized = CHECK_TYPE_ALIASES.get(normalized, normalized)

    if normalized is None:
        # 未提供 check_type：无法判断该写哪个字段，放行但不做字段白名单，
        # 仍做值本身的合法性校验（见下方）。
        pass
    elif normalized not in CHECK_TYPE_RESULT_FIELD:
        return [
            f"未知的检查项类型 check_type={check_type!r}。"
            f"允许值：{', '.join(sorted(set(CHECK_TYPE_RESULT_FIELD) | set(CHECK_TYPE_ALIASES)))}。"
            "写入未知类型会让结果落在无人读取的字段上，请修正模板。"
        ]

    provided = {
        field: payload.get(field)
        for field in RESULT_PAYLOAD_FIELDS
        if not _is_blank(payload.get(field))
    }

    # ---- 2. 字段白名单：只在「该写的字段为空、却写了别的字段」时拒绝 ----
    #
    # ⚠️ 判定规则必须精确到这一步，否则会误伤真实客户端：
    #
    #   · H5 保存时一次性提交**全部**结果字段（其余为空串），
    #     形如 {radio_value: 'pass', text_value: '', numeric_value: '', ...}；
    #   · web-admin 逐字段提交，形如 {template_item_id, radio_value}。
    #
    # 两种形态在「该写的字段有值」时都是正常保存，绝不能拒绝。
    # 真正会造成数据丢失的只有一种情形：**该写的字段是空的，值写到了别的字段上**
    # —— 接口会返回成功、库里也确实有值，但界面与报告读的是那个空字段，
    # 用户看到的是"填了没反应"。这才是本模块要拦的东西。
    if normalized is not None and provided:
        expected = CHECK_TYPE_RESULT_FIELD[normalized]
        if expected not in provided:
            mismatched = [f for f in provided if f != expected]
            if mismatched:
                type_label = CHECK_TYPE_LABEL.get(normalized, normalized)
                errors.append(
                    f"该检查项类型为「{type_label}」，结果应写入 "
                    f"{FIELD_LABEL[expected]}，"
                    f"但本次只写入了 {'、'.join(FIELD_LABEL[f] for f in mismatched)}。"
                    "写错字段的数据在界面与报告里读不到，等于没填。"
                )

    # ---- 3. 取值合法性 ----
    if "radio_value" in provided:
        raw = str(provided["radio_value"]).strip()
        allowed = list(allowed_result_values or []) + option_values(result_options)
        if allowed and raw not in {str(v) for v in allowed}:
            errors.append(
                f"单选结果 {raw!r} 不在该检查项的选项范围内。"
                f"可选值：{'、'.join(sorted({str(v) for v in allowed}))}。"
                "无法归类的取值会让该检查项在统计中变成「黑洞」。"
            )

    if "multi_value" in provided:
        if not isinstance(provided["multi_value"], list):
            errors.append(
                "多选结果 multi_value 必须是数组，"
                f"收到 {type(provided['multi_value']).__name__}。"
            )
        else:
            allowed = list(allowed_result_values or []) + option_values(result_options)
            if allowed:
                allowed_set = {str(v) for v in allowed}
                unknown = [v for v in provided["multi_value"] if str(v) not in allowed_set]
                if unknown:
                    errors.append(
                        f"多选结果包含未定义的选项：{'、'.join(map(str, unknown))}。"
                        f"可选值：{'、'.join(sorted(allowed_set))}。"
                    )

    if "numeric_value" in provided:
        errors.extend(
            _validate_numeric(provided["numeric_value"], min_value, max_value)
        )

    if "score_value" in provided:
        raw = provided["score_value"]
        try:
            float(str(raw).strip())
        except (TypeError, ValueError):
            errors.append(
                f"打分结果 {raw!r} 不是合法数字，请写入数值（不要带单位或中文）。"
            )

    if "text_value" in provided and len(str(provided["text_value"])) > _MAX_TEXT_LENGTH:
        errors.append(
            f"文本结果过长（{len(str(provided['text_value']))} 字），"
            f"上限 {_MAX_TEXT_LENGTH} 字，请拆分或改为附件。"
        )

    return errors
