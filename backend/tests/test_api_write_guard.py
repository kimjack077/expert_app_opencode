"""接口层测试：检查项写入侧校验（阶段 3 的端到端验收）。

═══════════════════════════════════════════════════════════════════════════
 这个文件守住什么
═══════════════════════════════════════════════════════════════════════════
第三方测试反复报出的两条严重问题：

* **数据无法录入** —— H5 端把单选结果写进 ``text_value``，接口返回 200、
  库里确实有值，但 PC 端与报告只读 ``radio_value``，界面永远空白。
  用户描述是"填了没反应"，本质是**字段写错却无任何提示**。
* **结论缺失** —— ``radio_value`` 写入拼错的值，无法归类为合格/不合格/不适用，
  报表既不计数也不报错，该检查项在统计里变成「黑洞」。

单元层（``test_item_write_guard.py``）验证校验函数本身；
本文件验证**校验真的挂在了端点上**，且错误信息对使用者可读。

═══════════════════════════════════════════════════════════════════════════
 运行前提
═══════════════════════════════════════════════════════════════════════════
需先把 ``EFIS_TEST_DB_NAME`` 指向独立测试库（见 conftest.py）。
未配置时全部自动 skip —— 本地与生产共用同一个远程库，裸跑会写脏生产数据。

    set EFIS_TEST_DB_NAME=db_expert_test
    .venv\\Scripts\\python.exe -m pytest tests/test_api_write_guard.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.api

RADIO_OPTIONS = {
    "options": [
        {"value": "pass", "label": "合格"},
        {"value": "fail", "label": "不合格"},
        {"value": "na", "label": "不适用"},
    ]
}


def _data(resp):
    """解开统一响应体 ``{code, message, data, timestamp}``。"""
    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:400]}"
    payload = resp.json()
    assert payload.get("code") in (0, 200, "0", "200", None), f"业务码异常: {payload}"
    return payload.get("data")


def _error_text(resp) -> str:
    """把 422 响应体拼成一段可搜索的文本（detail 可能是 str 也可能是 list）。"""
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        return resp.text
    detail = body.get("detail", body)
    if isinstance(detail, list):
        return " | ".join(str(x) for x in detail)
    return str(detail)


# ---------------------------------------------------------------------------
# 造数：一个模板 + 三个不同 check_type 的检查项 + 一条草稿记录
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def guard_template(client, auth_headers):
    """模块级：建一个模板 + 三个不同 check_type 的检查项，全模块共用。

    为什么拆成模块级：模板与检查项在所有用例中**只读不改**，
    每个用例重建一次会让远程库往返次数乘以用例数（实测单用例耗时 ~80s）。
    只有「记录」需要按用例新建——其中一个用例会把记录置为已提交。

    每个 check_type 单独建一个检查项，避免互相干扰：
      * radio   —— 配了 result_options，用于验证取值白名单
      * numeric —— 配了 min/max，用于验证范围校验
      * text    —— 用于验证"类型不匹配"拒绝
    """
    from uuid import uuid4

    suffix = uuid4().hex[:8]

    template = _data(
        client.post(
            "/api/templates",
            json={
                "name": f"E2E_TEST_写入校验模板_{suffix}",
                "code": f"E2EGUARD_{suffix}",
                "description": "自动化测试：写入侧校验",
            },
            headers=auth_headers,
        )
    )
    template_id = template["id"]

    def add_item(**overrides):
        body = {
            "title": f"E2E_TEST_检查项_{overrides.pop('tag', 'x')}_{suffix}",
            "check_type": "radio",
            "is_category": False,
            "sort_order": 0,
        }
        body.update(overrides)
        return _data(
            client.post(
                f"/api/templates/{template_id}/items", json=body, headers=auth_headers
            )
        )["id"]

    payload = {
        "template_id": template_id,
        "radio_item": add_item(tag="radio", check_type="radio", result_options=RADIO_OPTIONS),
        "numeric_item": add_item(
            tag="numeric", check_type="numeric", min_value=0, max_value=100
        ),
        "text_item": add_item(tag="text", check_type="text"),
        # ↓ 真实模板的形态：check_type 停在列默认值 'radio'，类型写在 result_type。
        #   模板编辑器只写 result_type（UI 上的「结论类型」），从不写 check_type。
        #   生产库实测 174 个叶子检查项，check_type 全部是 'radio'，其中
        #   8 个 result_type='numeric'、3 个 result_type='text'。
        "numeric_via_result_type": add_item(tag="numeric_rt", result_type="numeric"),
        "text_via_result_type": add_item(tag="text_rt", result_type="text"),
    }

    yield payload

    # 清理必须复用 session 级 client（新建会触发事件循环冲突）
    try:
        client.delete(f"/api/templates/{template_id}", headers=auth_headers)
    except Exception:  # noqa: BLE001 — 清理失败不应让用例报错
        pass


@pytest.fixture
def guard_fixture(client, auth_headers, guard_template, shared_enterprise_id, cleanup_registry):
    """用例级：基于共享模板建一条草稿记录。

    必须**用例级**（默认 scope）：其中一个用例会把记录置为已提交，
    提交后条目即只读，共享记录会让后续用例全部失败。
    """
    record = _data(
        client.post(
            "/api/records",
            json={
                "template_id": guard_template["template_id"],
                "enterprise_id": shared_enterprise_id,
            },
            headers=auth_headers,
        )
    )
    record_id = record["id"]
    cleanup_registry.append(("records", record_id))

    return {**guard_template, "record_id": record_id}


def _post_item(client, auth_headers, record_id, payload):
    return client.post(
        f"/api/records/{record_id}/items", json=payload, headers=auth_headers
    )


# ---------------------------------------------------------------------------
# 1. 字段白名单 —— 「数据无法录入」的直接防线
# ---------------------------------------------------------------------------


def test_radio_item_rejects_text_value(client, auth_headers, guard_fixture):
    """单选检查项把结果写进 text_value → 必须 422，且提示该写 radio_value。

    这是「数据无法录入」的真实成因：原接口返回 200，数据落在 text_value，
    而 PC 端与报告只读 radio_value，界面永远空白。
    """
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["radio_item"],
            "check_type": "radio",
            "text_value": "符合要求",
        },
    )
    assert resp.status_code == 422, (
        f"单选检查项写入 text_value 应被拒绝，实际 HTTP {resp.status_code}：{resp.text[:300]}"
    )
    message = _error_text(resp)
    assert "radio_value" in message, f"错误信息必须指明正确字段：{message}"


def test_radio_item_accepts_radio_value(client, auth_headers, guard_fixture):
    """字段正确时必须放行 —— 否则正常录入被误伤，问题更大。"""
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["radio_item"],
            "check_type": "radio",
            "radio_value": "pass",
        },
    )
    assert resp.status_code == 200, resp.text[:300]
    assert _data(resp)["template_item_id"] == guard_fixture["radio_item"]


def test_numeric_item_rejects_radio_value(client, auth_headers, guard_fixture):
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["numeric_item"],
            "check_type": "numeric",
            "radio_value": "pass",
        },
    )
    assert resp.status_code == 422
    assert "numeric_value" in _error_text(resp)


def test_text_item_rejects_radio_value(client, auth_headers, guard_fixture):
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["text_item"],
            "check_type": "text",
            "radio_value": "pass",
        },
    )
    assert resp.status_code == 422
    assert "text_value" in _error_text(resp)


def test_numeric_item_declared_via_result_type_accepts_numeric_value(
    client, auth_headers, guard_fixture
):
    """真实模板形态：类型写在 result_type、check_type 停在列默认 'radio'。

    回归缺陷（2026-09-19 老杨实测报出）：Web 记录页给「重点耗能设备运行参数」
    填数值后保存失败，HTTP 422 ——
    「该检查项类型为「单选」，结果应写入 单选结果(radio_value)，
      但本次只写入了 数值结果(numeric_value)」。

    根因：``POST /records/{id}/items`` 的写入守卫直接读 ``template_item.check_type``，
    而该列**恒为列默认值 'radio'**（模板编辑器只写 ``result_type``），
    于是数值型/描述型检查项一律被误判成单选，前端正常提交反被拒绝。
    同一文件的快照写入用的是 ``resolve_check_type()``（正确口径），
    两处不一致 —— 本模块自己制造的「数据无法录入」。

    ⚠️ 本用例**刻意不传 check_type**，因为真实前端只提交
    ``{template_item_id, numeric_value}``；老用例显式传 check_type，
    恰好把这条路径掩盖了。
    """
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["numeric_via_result_type"],
            "numeric_value": "100.9",
        },
    )
    assert resp.status_code == 200, (
        "数值型检查项（类型写在 result_type）提交 numeric_value 必须放行，"
        f"实际 HTTP {resp.status_code}：{resp.text[:300]}"
    )
    body = _data(resp)
    assert body["template_item_id"] == guard_fixture["numeric_via_result_type"]
    assert str(body.get("numeric_value")) == "100.9", "数值必须落到 numeric_value"


def test_text_item_declared_via_result_type_accepts_text_value(
    client, auth_headers, guard_fixture
):
    """同上，描述型：check_type='radio' + result_type='text' 时写 text_value 必须放行。"""
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["text_via_result_type"],
            "text_value": "现场检查未发现异常",
        },
    )
    assert resp.status_code == 200, (
        f"描述型检查项提交 text_value 必须放行，实际 HTTP {resp.status_code}：{resp.text[:300]}"
    )
    assert str(_data(resp).get("text_value")) == "现场检查未发现异常"


def test_numeric_via_result_type_still_rejects_radio_value(
    client, auth_headers, guard_fixture
):
    """放宽的同时不能丢掉守卫的牙齿：这类项写 radio_value 仍应被拒绝。"""
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["numeric_via_result_type"],
            "radio_value": "pass",
        },
    )
    assert resp.status_code == 422, "数值型项写 radio_value 应被拒绝"
    assert "numeric_value" in _error_text(resp)


def test_unknown_check_type_is_rejected(client, auth_headers, guard_fixture):
    """未知 check_type 会让结果落在无人读取的字段上，必须拒绝。"""
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["radio_item"],
            "check_type": "rating",
            "radio_value": "pass",
        },
    )
    assert resp.status_code == 422
    message = _error_text(resp)
    assert "rating" in message and "radio" in message


# ---------------------------------------------------------------------------
# 2. 取值合法性 —— 「结论缺失」的防线
# ---------------------------------------------------------------------------


def test_radio_value_outside_options_is_rejected(client, auth_headers, guard_fixture):
    """取值不在 result_options 内 → 422，并列出可选值。"""
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["radio_item"],
            "check_type": "radio",
            "radio_value": "qualified",
        },
    )
    assert resp.status_code == 422, (
        "取值越界应被拒绝，否则该检查项在统计中无法归类："
        f"HTTP {resp.status_code} {resp.text[:300]}"
    )
    message = _error_text(resp)
    assert "qualified" in message
    assert "pass" in message, f"错误信息应列出可选值：{message}"


def test_numeric_value_must_be_number(client, auth_headers, guard_fixture):
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["numeric_item"],
            "check_type": "numeric",
            "numeric_value": "约 50 米",
        },
    )
    assert resp.status_code == 422
    assert "不是合法数字" in _error_text(resp)


def test_numeric_value_respects_template_bounds(client, auth_headers, guard_fixture):
    """模板配置了 min=0 / max=100，越界必须拒绝。"""
    ok = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["numeric_item"],
            "check_type": "numeric",
            "numeric_value": "50",
        },
    )
    assert ok.status_code == 200, ok.text[:300]

    too_big = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["numeric_item"],
            "check_type": "numeric",
            "numeric_value": "150",
        },
    )
    assert too_big.status_code == 422
    assert "上限" in _error_text(too_big)


# ---------------------------------------------------------------------------
# 3. 校验不得破坏既有正常路径
# ---------------------------------------------------------------------------


def test_validation_does_not_break_legacy_payload(client, auth_headers, guard_fixture):
    """不带 check_type、只带通用 result 字段的历史调用必须继续可用。"""
    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["radio_item"],
            "result": "pass",
            "radio_value": "pass",
        },
    )
    assert resp.status_code == 200, (
        "历史调用方式（只带 result + radio_value）被误伤：" + resp.text[:300]
    )


def test_repeated_write_updates_instead_of_duplicating(client, auth_headers, guard_fixture):
    """同一检查项重复写入必须更新既有条目，不能产生重复行。"""
    payload = {
        "template_item_id": guard_fixture["radio_item"],
        "check_type": "radio",
        "radio_value": "fail",
    }
    first = _post_item(client, auth_headers, guard_fixture["record_id"], payload)
    second = _post_item(client, auth_headers, guard_fixture["record_id"], payload)
    assert first.status_code == 200 and second.status_code == 200
    assert _data(first)["id"] == _data(second)["id"], "重复写入产生了新的检查项条目"

    items = _data(
        client.get(f"/api/records/{guard_fixture['record_id']}/items", headers=auth_headers)
    )
    rows = items.get("items") if isinstance(items, dict) else items
    matched = [
        r for r in rows if r.get("template_item_id") == guard_fixture["radio_item"]
    ]
    assert len(matched) == 1, f"检查项出现重复行：{len(matched)} 条"


def _force_record_status(record_id: str, status: str) -> None:
    """直接把记录状态改到库里的指定值。

    为什么不走 ``POST /records/{id}/submit``：该接口有完整性校验（结论 + 必填项），
    造一份"能通过提交校验"的数据成本远高于本用例要验证的东西。
    本用例只关心「已提交记录不可再改条目」这条既有保护是否仍然生效。
    """
    import psycopg2

    from app.config import settings

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE inspection_records SET status = %s WHERE id = %s",
                (status, record_id),
            )
    finally:
        conn.close()


def test_submitted_record_rejects_item_write(client, auth_headers, guard_fixture):
    """已提交记录为只读 —— 新增的校验逻辑不得把这条既有保护挤掉（BUG-12）。

    风险点：写入侧校验被插在状态检查**之后**是刻意的，
    若有人把它挪到前面并提前 return，这条保护就会被绕过。
    """
    _force_record_status(guard_fixture["record_id"], "submitted")

    resp = _post_item(
        client,
        auth_headers,
        guard_fixture["record_id"],
        {
            "template_item_id": guard_fixture["radio_item"],
            "check_type": "radio",
            "radio_value": "pass",
        },
    )
    assert resp.status_code == 409, (
        f"已提交记录仍可写入条目，BUG-12 回归：HTTP {resp.status_code} {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# 2. 附件持久性 —— 「上传的附件保存后丢失」的直接防线
# ---------------------------------------------------------------------------


def test_saving_result_without_photos_keeps_existing_photos(
    client, auth_headers, guard_fixture
):
    """只提交结果、不带 ``photos`` 字段时，已有附件**必须保留**。

    历史缺陷：``InspectionRecordItemBase.photos`` 原为
    ``Field(default_factory=list)`` —— 前端省略该字段时 Pydantic 补成 ``[]``，
    而端点用 ``if value is not None: setattr(...)`` 判空，``[] is not None`` 成立，
    于是把库里已有附件**覆盖成空**。

    用户看到的是「我每个题目都传了附件，刷新后前两个没了」。
    实测生产记录：4 个检查项只有 2 个留下附件，正是这个覆盖时序造成的。

    修复方式：写侧 schema 的 ``photos`` 默认值改为 ``None``，
    让「未提供」与「显式清空」在语义上分开。
    """
    record_id = guard_fixture["record_id"]
    item_id = guard_fixture["radio_item"]
    photo = "/uploads/inspections/E2E_TEST_keep_me.jpg"

    _post_item(
        client,
        auth_headers,
        record_id,
        {"template_item_id": item_id, "photos": [photo]},
    )

    # ★ 关键动作：只提交结果，完全不带 photos（旧客户端的真实行为）
    _post_item(
        client,
        auth_headers,
        record_id,
        {"template_item_id": item_id, "radio_value": "pass"},
    )

    data = _data(
        client.get(f"/api/records/{record_id}", headers=auth_headers)
    )
    item = next(i for i in data["items"] if i["template_item_id"] == item_id)
    assert item["photos"] == [photo], (
        "省略 photos 字段的写入把已有附件清空了 —— "
        "这是「上传附件后丢失」的根因回归。"
        f"当前 photos={item['photos']!r}"
    )


def test_explicit_empty_photos_still_clears(client, auth_headers, guard_fixture):
    """显式传 ``photos: []`` 仍然要能清空 —— 修默认值时不能把「用户删除附件」堵死。

    与上一条是一对：``None`` = 不改动，``[]`` = 清空。两者语义必须分开。
    """
    record_id = guard_fixture["record_id"]
    item_id = guard_fixture["radio_item"]

    _post_item(
        client,
        auth_headers,
        record_id,
        {"template_item_id": item_id, "photos": ["/uploads/inspections/E2E_TEST_a.jpg"]},
    )
    _post_item(
        client,
        auth_headers,
        record_id,
        {"template_item_id": item_id, "photos": []},
    )

    data = _data(client.get(f"/api/records/{record_id}", headers=auth_headers))
    item = next(i for i in data["items"] if i["template_item_id"] == item_id)
    assert not item["photos"], (
        f"显式传 photos=[] 未能清空附件，用户删不掉已上传的附件：{item['photos']!r}"
    )


def test_record_detail_exposes_photos_for_every_item(client, auth_headers, guard_fixture):
    """``GET /records/{id}`` 必须为每个检查项返回 ``photos`` 字段。

    前端据此渲染附件缩略图，并用 ``item.photos`` 做「必传附件」提交校验。
    字段缺失时两者同时失效：缩略图不显示，且校验恒报"缺附件"。
    """
    data = _data(
        client.get(f"/api/records/{guard_fixture['record_id']}", headers=auth_headers)
    )
    assert data["items"], "记录没有任何检查项，用例前提不成立"
    for item in data["items"]:
        assert "photos" in item, f"检查项 {item.get('item_title')!r} 未返回 photos 字段"
        assert isinstance(item["photos"], list), (
            f"photos 应为列表，实际为 {type(item['photos']).__name__} —— "
            "前端 .length 判断会失效"
        )
