"""契约层测试：跨端（H5 / 管理端 / 后端）字段与语义一致性。

═══════════════════════════════════════════════════════════════════════════
 为什么要有这个文件
═══════════════════════════════════════════════════════════════════════════
项目有三个前端（``h5-app`` / ``web-admin`` / ``mobile-app``）打同一套 API。
后端 Pydantic 模型**默认 ``extra='ignore'``** —— 前端如果提交了后端不认识的
字段，请求会返回 200、界面提示"保存成功"，但那个字段被静默丢弃、库里什么都没有。
用户看到的现象就是「数据无法录入」，而且没有任何报错可供排查。

这类问题无法用接口测试发现（接口返回是成功的），只能靠**静态比对**：
把前端实际使用的字段名与后端 schema 的字段名对一遍。

本文件做三件事：

1. **字段名一致性** —— 前端提交的每个字段都必须在后端 schema 中存在；
2. **类型枚举一致性** —— 前端出现的 ``check_type`` 字面量后端必须认识；
3. **端点一致性** —— 前端调用的关键路径必须在后端路由表中存在。

不需要数据库，随时可跑::

    .venv\\Scripts\\python.exe -m pytest tests/test_cross_client_consistency.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

# 参与比对的前端工程。mobile-app 是早期端、Agent 写回已禁用，故不纳入门禁。
CLIENT_DIRS = {
    "h5-app": REPO_ROOT / "h5-app" / "src",
    "web-admin": REPO_ROOT / "web-admin" / "src",
}

# 结果承载字段的统一后缀。只比对这类字段，避免把 UI 状态字段也扫进来。
RESULT_FIELD_PATTERN = re.compile(r"\b([a-z][a-z0-9_]*_value)\b")

# 允许前端出现、但后端 schema 中不存在的字段白名单（逐条给出理由）。
# 目前为空。
CLIENT_ONLY_FIELDS: frozenset[str] = frozenset()


def _client_files(exts: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for root in CLIENT_DIRS.values():
        if not root.exists():
            continue
        for ext in exts:
            files.extend(root.rglob(f"*{ext}"))
    return sorted(f for f in files if "node_modules" not in f.parts)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# 1. 字段名一致性：前端提交的字段后端必须认识
# ---------------------------------------------------------------------------


def test_backend_schema_rejects_unknown_fields_loudly():
    """前提校验：后端 schema 若改成 ``extra='allow'``，本文件的结论就不成立了。

    当前是 ``ignore`` —— 未知字段被**静默丢弃**，这正是"保存成功但没数据"的成因。
    若将来改为 ``allow``，请同步更新本文件的说明与断言。
    """
    from app.schemas.record import InspectionRecordItemCreate

    extra = InspectionRecordItemCreate.model_config.get("extra", "ignore")
    assert extra == "ignore", (
        f"检查项写入 schema 的 extra 策略已变为 {extra!r}。"
        "本文件基于「未知字段被静默丢弃」这一事实设计，策略变更后需同步复核。"
    )


def test_client_result_fields_exist_in_backend_schema():
    """前端使用的每个 ``*_value`` 字段都必须存在于后端写入 schema。

    不存在 = 提交后 200 成功但字段被丢弃 = 「数据无法录入」且无任何报错。
    """
    from app.schemas.record import InspectionRecordItemCreate

    allowed = set(InspectionRecordItemCreate.model_fields) | CLIENT_ONLY_FIELDS

    offenders: dict[str, set[str]] = {}
    for path in _client_files((".ts", ".tsx", ".vue", ".js")):
        for match in RESULT_FIELD_PATTERN.finditer(_read(path)):
            field = match.group(1)
            if field not in allowed:
                offenders.setdefault(field, set()).add(
                    path.relative_to(REPO_ROOT).as_posix()
                )

    assert not offenders, (
        "前端使用了后端检查项 schema 中不存在的字段。\n"
        "Pydantic 默认 extra='ignore'，这些字段会被**静默丢弃**：\n"
        "接口返回 200、界面提示保存成功，但库里没有数据。\n\n"
        + "\n".join(
            f"  {field}\n      " + "\n      ".join(sorted(files))
            for field, files in sorted(offenders.items())
        )
        + "\n\n处置：改用后端已支持的字段，或把字段加入后端 schema。"
    )


def test_result_payload_fields_are_all_known_to_write_guard():
    """写入守卫登记的字段集必须与 schema 对齐 —— 两边漂移会让校验形同虚设。"""
    from app.schemas.record import InspectionRecordItemCreate
    from app.utils.item_write_guard import RESULT_PAYLOAD_FIELDS

    schema_fields = set(InspectionRecordItemCreate.model_fields)
    missing = sorted(set(RESULT_PAYLOAD_FIELDS) - schema_fields)
    assert not missing, (
        f"item_write_guard.RESULT_PAYLOAD_FIELDS 中的字段后端 schema 不认识：{missing}"
    )


# ---------------------------------------------------------------------------
# 2. 类型枚举一致性：前端出现的 check_type 后端必须认识
# ---------------------------------------------------------------------------


def test_client_check_type_literals_are_recognised_by_backend():
    """前端比较过的 ``check_type`` 字面量，后端必须都能识别。

    否则会出现两种坏结果：
      · 前端按 A 类型渲染、后端按 B 类型校验 → 正常保存被判 422（无法录入）；
      · 前端按 A 类型写字段、后端按 B 类型读字段 → 数据写进无人读取的位置。
    """
    from app.utils.item_write_guard import CHECK_TYPE_ALIASES, CHECK_TYPE_RESULT_FIELD

    known = set(CHECK_TYPE_RESULT_FIELD) | set(CHECK_TYPE_ALIASES)

    literal = re.compile(
        r"(?:check_type|checkType|result_type|resultType)\s*[=!]==?\s*['\"]([a-z_0-9]+)['\"]"
    )

    offenders: dict[str, set[str]] = {}
    for path in _client_files((".ts", ".tsx", ".vue")):
        for match in literal.finditer(_read(path)):
            value = match.group(1)
            if value not in known:
                offenders.setdefault(value, set()).add(
                    path.relative_to(REPO_ROOT).as_posix()
                )

    assert not offenders, (
        "前端使用了后端不认识的检查项类型：\n"
        + "\n".join(
            f"  {value}\n      " + "\n      ".join(sorted(files))
            for value, files in sorted(offenders.items())
        )
        + f"\n\n后端已知类型：{sorted(known)}"
    )


def test_every_check_type_maps_to_a_field_the_schema_defines():
    """每个 check_type 映射到的结果字段都必须是 schema 中的真实字段。"""
    from app.schemas.record import InspectionRecordItemCreate
    from app.utils.item_write_guard import CHECK_TYPE_RESULT_FIELD

    schema_fields = set(InspectionRecordItemCreate.model_fields)
    for check_type, field in CHECK_TYPE_RESULT_FIELD.items():
        assert field in schema_fields, (
            f"check_type={check_type!r} 映射到 {field!r}，但后端 schema 没有这个字段"
        )


# ---------------------------------------------------------------------------
# 3. 端点一致性：前端调用的关键路径必须存在
# ---------------------------------------------------------------------------


def _backend_route_paths() -> set[str]:
    from app.main import app

    paths = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
    return paths


@pytest.mark.parametrize(
    "path",
    [
        "/api/records/{record_id}/items",
        "/api/records/{record_id}/report",
        "/api/records/{record_id}/submit",
        "/api/records/{record_id}",
        "/api/templates/{template_id}/items",
        "/api/auth/login",
    ],
)
def test_critical_endpoints_exist(path):
    """两端共同依赖的端点必须在后端路由表中存在。"""
    assert path in _backend_route_paths(), (
        f"后端不存在路由 {path} —— 前端调用会得到 404，用户看到「系统报错」"
    )


def test_h5_base_path_is_declared():
    """H5 以 ``/h5/`` 为 base path 发布，构建配置必须与部署一致。

    若 base 配成 ``/``，线上静态资源会 404，表现为"页面白屏/样式全丢"。
    """
    vite_config = REPO_ROOT / "h5-app" / "vite.config.ts"
    if not vite_config.exists():
        pytest.skip("未找到 h5-app/vite.config.ts")

    content = _read(vite_config)
    assert re.search(r"""base\s*:\s*['"]/h5/['"]""", content), (
        "h5-app/vite.config.ts 的 base 不是 '/h5/'。"
        "部署到 nginx 的 /h5/ 路径下会因资源路径不匹配而白屏。"
    )


# ---------------------------------------------------------------------------
# 4. 语义字段归属：「判定说明」与「检查备注」是两个字段
# ---------------------------------------------------------------------------


def test_judgment_note_is_a_real_backend_field():
    """后端必须同时存在 ``judgment_note`` 与 ``remarks``，且语义不同。

    历史缺陷：两个前端都把「判定说明」写进 ``remarks``，
    于是「检查任务创建时填的备注」会显示成「判定说明」，
    报告里的「整改建议」也拿备注当内容。用户质疑"这个字段是不是一一对应的"。
    """
    from app.schemas.record import InspectionRecordUpdate

    fields = set(InspectionRecordUpdate.model_fields)
    assert "judgment_note" in fields, "后端缺少 judgment_note 字段，「判定说明」无处安放"
    assert "remarks" in fields, "后端缺少 remarks 字段，「检查备注」无处安放"


def _payload_keys(src: str, call: str) -> list[set[str]]:
    """抽出 ``call(`` 后第一个 ``{...}`` 对象字面量的顶层键名。

    只做括号配对，不做语法分析——够用且不会误伤。嵌套对象的键也会被收集，
    但本用例只关心 ``overall_result`` / ``remarks`` / ``judgment_note`` 三个键。
    """
    results: list[set[str]] = []
    for match in re.finditer(re.escape(call) + r"\s*\(", src):
        start = src.find("{", match.end())
        if start < 0:
            continue
        depth = 0
        end = start
        while end < len(src):
            if src[end] == "{":
                depth += 1
            elif src[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        body = src[start + 1: end]
        results.append(set(re.findall(r"(?:^|,)\s*([A-Za-z_]\w*)\s*:", body)))
    return results


def test_no_client_writes_judgment_into_the_remarks_field():
    """保存「最终判定」的载荷里，判定说明必须走 ``judgment_note``，不得走 ``remarks``。

    这是**跨端字段错位**的直接防线。实测事故：PC 已改读 ``judgment_note``，
    H5 仍写 ``remarks`` —— 用户在 H5 填的判定说明出现在 PC 的「检查备注」里，
    PC 的「判定说明」永远为空。两端各写各的，用户会认为"改了一半"。

    注意：局部变量叫什么名字无所谓（PC 就叫 ``finalJudgment.remarks``），
    这里只校验**发出去的字段名**。
    """
    offenders: list[str] = []

    for path in _client_files((".vue", ".tsx", ".ts")):
        src = _read(path)
        for call in ("updateRecord", "updateRecordItem", "update_record"):
            for keys in _payload_keys(src, call):
                if "overall_result" not in keys:
                    continue
                if "remarks" in keys and "judgment_note" not in keys:
                    offenders.append(
                        f"  {path.relative_to(REPO_ROOT).as_posix()}  ->  载荷键 {sorted(keys)}"
                    )

    assert not offenders, (
        "保存最终判定的载荷把「判定说明」写进了 remarks（检查备注）：\n"
        + "\n".join(offenders)
        + "\n\n处置：改为 `judgment_note: <判定说明值>`，与另一端保持一致。"
    )


def test_every_client_reads_judgment_note_from_backend():
    """两端都必须真的读取后端返回的 ``judgment_note``。

    只写不读 = 保存成功但界面永远空白，用户描述为"填了没反应"。
    """
    missing = [
        name
        for name, root in CLIENT_DIRS.items()
        if root.exists()
        and not any(
            "judgment_note" in _read(p)
            for p in root.rglob("*")
            if p.suffix in (".ts", ".tsx", ".vue", ".js")
        )
    ]
    assert not missing, (
        f"这些前端完全没有引用 judgment_note：{missing} —— "
        "「判定说明」字段未接入，保存后界面不会显示。"
    )


# ---------------------------------------------------------------------------
# 5. 详情接口必须提供报告渲染所需的全部字段
# ---------------------------------------------------------------------------


def _record_detail_enterprise_keys() -> set[str]:
    """从 ``get_record`` 的源码里抽出它返回的 enterprise 字段名。"""
    src = _read(BACKEND_DIR / "app" / "routers" / "records.py")
    marker = '"enterprise": {\n            "id": str(record.enterprise.id)'
    start = src.find(marker)
    if start < 0:
        # 兜底：找 detail 端点里带 record.enterprise 的那一段
        for m in re.finditer(r'"enterprise": \{', src):
            seg = src[m.start(): m.start() + 1200]
            if "record.enterprise" in seg:
                start = m.start()
                break
    assert start >= 0, "未能在 records.py 中定位 get_record 的 enterprise 返回块"
    block = src[start: src.find("if record.enterprise", start)]
    return set(re.findall(r'"([a-z_]+)":', block))


def test_record_detail_enterprise_exposes_fields_the_report_renders():
    """PC 报告预览读的企业字段，``GET /records/{id}`` 必须都返回。

    历史缺陷：该接口的 enterprise 只返回 ``{id, name}``，而
    ``InspectionReport`` 读的是 ``enterprise.legal_person / credit_code /
    risk_level / enterprise_type / address / contact_person / contact_phone``
    → 全部 undefined，再被前端 ``.filter(([, v]) => v)`` 过滤掉整行。
    用户看到的是「企业基本信息少了几行」，而不是「显示 —」，
    比原来更难发现——因为少掉的字段完全不可见。
    """
    rendered = {
        "address",
        "legal_person",
        "contact_person",
        "contact_phone",
        "enterprise_type",
        "risk_level",
        "credit_code",
    }
    provided = _record_detail_enterprise_keys()
    missing = sorted(rendered - provided)
    assert not missing, (
        f"GET /records/{{id}} 的 enterprise 缺少报告要渲染的字段：{missing}\n"
        f"当前返回：{sorted(provided)}"
    )
