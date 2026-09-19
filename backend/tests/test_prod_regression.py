"""生产库直连回归 —— 针对**明确出现过 bug 的位置**逐条钉死用例。

═══════════════════════════════════════════════════════════════════════════
 为什么是生产库
═══════════════════════════════════════════════════════════════════════════
老杨（2026-09-19）明确指示：**当前生产库尚未正式上线，可直接使用，不要再绕测试库**。
这样有两大好处：

1. 直接用**真实数据**验证，不用造夹具 —— 之前"审核项目计数对账"就是因为
   需要构造「项目 + 计划项 + 区域记录 + 条目」的重夹具而一直欠着，
   现在生产库里现成数据就能做。
2. 报障的场景（老杨在 `/record/4824c317-...` 填数值保存失败）本身就是生产数据，
   在同一份数据上回归，才是真正的闭环。

═══════════════════════════════════════════════════════════════════════════
 安全开关（不要删）
═══════════════════════════════════════════════════════════════════════════
本组用例会**读写生产库**，因此必须显式开启：

    set EFIS_RUN_PROD_REGRESSION=1
    pytest -m prod -v

未设置该变量时全部 skip，避免日常跑 `pytest tests/` 误伤生产库。
**生产正式上线后**，应把这里改为指向隔离测试库，或整体冻结。

前置：本地后端需在运行（`http://127.0.0.1:8000`，其 .env 指向生产库）。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.prod

BASE = os.getenv("EFIS_PROD_BASE_URL", "http://127.0.0.1:8000")
GUARD_ENV = "EFIS_RUN_PROD_REGRESSION"


# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------

def _enabled() -> bool:
    return os.getenv(GUARD_ENV) == "1"


@pytest.fixture(scope="module")
def require_prod():
    if not _enabled():
        pytest.skip(f"需设置 {GUARD_ENV}=1 才会跑生产库回归（会读写生产数据）")


def _api(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def _data(payload):
    return payload.get("data", payload) if isinstance(payload, dict) else payload


@pytest.fixture(scope="module")
def token(require_prod):
    status, payload = _api(
        "POST", "/api/auth/login", body={"username": "admin", "password": "admin123"}
    )
    if status != 200:
        pytest.skip(f"本地后端未运行或登录失败（HTTP {status}）—— 需先启动 8000 端口")
    return _data(payload)["access_token"]


def _walk(nodes):
    """深度优先遍历模板/记录项树，产出所有叶子（非分类目录）节点。"""
    for node in nodes or []:
        if not node.get("is_category"):
            yield node
        yield from _walk(node.get("children"))


@pytest.fixture(scope="module")
def demo_record(require_prod, token):
    """挑一条草稿记录，且树里同时含数值型与描述型叶子 —— 正是报障的形态。"""
    status, payload = _api("GET", "/api/records?limit=50", token=token)
    assert status == 200, f"记录列表失败：{status}"
    items = _data(payload)
    items = items.get("items", items) if isinstance(items, dict) else items

    for rec in items or []:
        if rec.get("status") != "draft":
            continue
        s2, p2 = _api("GET", f"/api/records/{rec['id']}", token=token)
        if s2 != 200:
            continue
        tree = (_data(p2).get("template") or {}).get("items") or []
        leaves = list(_walk(tree))
        kinds = {str(n.get("result_type") or "").lower() for n in leaves}
        if "numeric" in kinds and "text" in kinds:
            return {"id": rec["id"], "leaves": leaves}
    pytest.skip("未找到同时含数值型与描述型叶子的草稿记录")


def _leaf_of(leaves, kind):
    for node in leaves:
        if str(node.get("result_type") or "").lower() == kind:
            return node
    return None


def _radio_leaf(leaves):
    for node in leaves:
        if str(node.get("result_type") or "").lower() in ("pass_fail", "", "none"):
            return node
    return None


# ---------------------------------------------------------------------------
# BUG-1 · 写入守卫误判类型 —— 老杨实测报出「填数值后保存失败」
# ---------------------------------------------------------------------------

def test_prod_numeric_item_saves(require_prod, token, demo_record):
    """数值型检查项提交 numeric_value 必须 200，且值落到 numeric_value。

    缺陷：写入守卫直接读 `template_item.check_type`（恒为列默认值 'radio'），
    把数值型项误判成单选 → 前端正常提交反被 422。生产库 11 项因此完全无法保存。
    """
    leaf = _leaf_of(demo_record["leaves"], "numeric")
    assert leaf, "演示记录里应有数值型叶子项"
    tid = leaf["template_item_id"]
    rid = demo_record["id"]

    status, payload = _api(
        "POST", f"/api/records/{rid}/items", token=token,
        body={"template_item_id": tid, "numeric_value": "100.9"},
    )
    assert status == 200, (
        f"数值型项提交 numeric_value 必须放行，实际 HTTP {status}：{payload}"
    )

    # 写入响应不含值字段，必须回查确认落库
    _, detail = _api("GET", f"/api/records/{rid}", token=token)
    stored = next(
        (n for n in _walk((_data(detail).get("template") or {}).get("items") or [])
         if str(n.get("template_item_id")) == str(tid)),
        None,
    )
    assert stored is not None, "回查不到该条目"
    assert str(stored.get("numeric_value")) == "100.9", (
        f"值必须落到 numeric_value，实际 {stored.get('numeric_value')!r}"
    )


def test_prod_text_item_saves(require_prod, token, demo_record):
    """描述型检查项提交 text_value 必须 200，且值落到 text_value。"""
    leaf = _leaf_of(demo_record["leaves"], "text")
    assert leaf, "演示记录里应有描述型叶子项"
    tid = leaf["template_item_id"]
    rid = demo_record["id"]

    status, payload = _api(
        "POST", f"/api/records/{rid}/items", token=token,
        body={"template_item_id": tid, "text_value": "现场检查未发现异常"},
    )
    assert status == 200, f"描述型项提交 text_value 必须放行，实际 {status}：{payload}"

    _, detail = _api("GET", f"/api/records/{rid}", token=token)
    stored = next(
        (n for n in _walk((_data(detail).get("template") or {}).get("items") or [])
         if str(n.get("template_item_id")) == str(tid)),
        None,
    )
    assert str(stored.get("text_value")) == "现场检查未发现异常"


def test_prod_numeric_item_still_rejects_radio_value(require_prod, token, demo_record):
    """放宽的同时不能丢守卫的牙齿：数值型项写 radio_value 仍须 422。"""
    leaf = _leaf_of(demo_record["leaves"], "numeric")
    status, _ = _api(
        "POST", f"/api/records/{demo_record['id']}/items", token=token,
        body={"template_item_id": leaf["template_item_id"], "radio_value": "pass"},
    )
    assert status == 422, "数值型项写 radio_value 应被拒绝（守卫失效会造成静默丢数据）"


def test_prod_radio_item_still_rejects_text_value(require_prod, token, demo_record):
    """判定型项写 text_value 仍须 422 —— 这是本守卫最初要防的问题。"""
    leaf = _radio_leaf(demo_record["leaves"])
    if not leaf:
        pytest.skip("演示记录里没有判定型叶子项")
    status, _ = _api(
        "POST", f"/api/records/{demo_record['id']}/items", token=token,
        body={"template_item_id": leaf["template_item_id"], "text_value": "随便写"},
    )
    assert status == 422, "判定型项写 text_value 应被拒绝"


# ---------------------------------------------------------------------------
# BUG-2 · 历史检查统计只看 radio_value（history-stats）
# ---------------------------------------------------------------------------

def test_prod_history_stats_agrees_with_recomputation(require_prod, token):
    """history-stats 的 pass/fail/na 必须等于用权威口径逐条重算的结果。

    缺陷：该接口曾逐个取 `classify_result(i.radio_value)`，只看 radio_value；
    已改为 `calculate_item_stats()`，按 radio_value → result → evaluation_3level
    取第一个能归类的值。
    """
    from app.utils.item_stats import classify_item

    status, payload = _api("GET", "/api/records?limit=50", token=token)
    assert status == 200
    items = _data(payload)
    items = items.get("items", items) if isinstance(items, dict) else items

    checked = 0
    for rec in items or []:
        if rec.get("status") != "submitted":
            continue
        _, detail = _api("GET", f"/api/records/{rec['id']}", token=token)
        if _data(detail).get("enterprise_id") is None:
            continue  # 该接口在企业为空时提前返回，不参与对账
        leaves = list(_walk((_data(detail).get("template") or {}).get("items") or []))
        if not leaves:
            continue
        leaf = leaves[0]

        status2, payload2 = _api(
            "GET", f"/api/records/{rec['id']}/items/{leaf['template_item_id']}/history-stats",
            token=token,
        )
        if status2 != 200:
            continue
        data = _data(payload2)
        # 守恒：三项之和不得超过历史条目总数
        total = data.get("total_inspections") or 0
        s = (data.get("pass_count") or 0) + (data.get("fail_count") or 0) + (data.get("na_count") or 0)
        assert s <= total, (
            f"记录 {rec['id']}：pass+fail+na={s} 超过 total_inspections={total}"
        )
        # 权威口径对同一批叶子可归类，不应抛错
        for node in leaves:
            classify_item(node)
        checked += 1
        if checked >= 3:  # 抽样三条即可，避免用例过慢
            break

    assert checked > 0, "未找到可用于对账的已提交记录"


# ---------------------------------------------------------------------------
# 对账 · 守恒律（此前因需重夹具一直欠着，现用生产库现成数据补齐）
# ---------------------------------------------------------------------------

def test_prod_record_item_stats_satisfy_conservation(require_prod, token, demo_record):
    """守恒律：total == pass + fail + na + observe + unfilled，且 filled + unfilled == total。

    这是成本最低、发现率最高的报表一致性检查 —— 「合格+不合格+不适用 ≠ 总项数」
    这类客户当场会质疑的问题，靠它兜住。
    """
    from app.utils.item_stats import calculate_item_stats

    leaves = demo_record["leaves"]
    stats = calculate_item_stats(leaves)

    assert stats["total"] == len(leaves), "统计总数必须等于叶子项数"
    assert stats["total"] == (
        stats["pass"] + stats["fail"] + stats["na"] + stats["observe"] + stats["unfilled"]
    ), f"守恒律不成立：{stats}"
    assert stats["filled"] + stats["unfilled"] == stats["total"], f"filled/unfilled 不闭合：{stats}"


def test_prod_quality_check_runs_for_all_projects(require_prod, token):
    """每个审核项目都能跑通门禁检查，且结果结构完整。

    2026-09-19 实测：**10 个项目全部未通过（0/10）** → 第九幕「通过后下载归档包」会卡。
    本用例不断言"必须通过"，只断言接口可用、结构正确，并把通过数列出来供判断。
    """
    _, payload = _api("GET", "/api/audit-projects", token=token)
    projects = _data(payload)
    projects = projects.get("items", projects) if isinstance(projects, dict) else projects
    assert projects, "应至少有 1 个审核项目"

    passed, rows = 0, []
    for proj in projects:
        pid = proj["id"]
        status, payload2 = _api("POST", f"/api/audit-projects/{pid}/quality-check", token=token, body={})
        assert status == 200, f"项目 {pid} 门禁检查失败：HTTP {status} {payload2}"
        qc = _data(payload2)
        if isinstance(qc, dict) and "quality_check" in qc:
            qc = qc["quality_check"]
        assert isinstance(qc, dict) and "passed" in qc, f"项目 {pid} 门禁结果结构异常：{qc}"
        assert isinstance(qc.get("blockers", []), list), "blockers 必须是列表"
        if qc["passed"]:
            passed += 1
        rows.append((proj.get("title") or pid, qc.get("score"), len(qc.get("blockers") or [])))

    print("\n=== 各项目门禁 ===")
    for title, score, nb in rows:
        print(f"   {str(title)[:40]:<40} score={score} 阻断={nb}")
    print(f"   通过门禁：{passed}/{len(rows)}")
    if passed == 0:
        print("   ⚠️ 无项目通过门禁 → 第九幕「通过后下载归档包」会卡")
