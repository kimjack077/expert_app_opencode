"""Frontend fetch URL config guard.

Regression for a bug reported on 2026-09-19: clicking "AI generate final judgment"
on `/inspection/:id` (task mode) silently fails with "AI generation failed, please retry".

Root cause: `web-admin/src/components/InspectionForm/index.tsx` and
`web-admin/src/pages/RecordInspection/index.tsx` both build their SSE fetch URL as

    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

In production, `web-admin/.env.production` sets `VITE_API_URL=` to empty, so the
fallback hits and the browser sends the SSE request to **the user's own**
localhost:8000 — which is never running the backend. The connection is refused,
the request never reaches the server, and the backend log shows nothing at all
(very hard to diagnose).

Fix: change the fallback to empty string `''`. The fetch then builds a relative
path `/api/...`, which the browser resolves against the current origin
(`http://49.232.213.79:3000`). The nginx instance on the server listens on
port 3000 and reverse-proxies `/api` and `/uploads` to `127.0.0.1:8000`, so the
SSE works.

This test forbids the dangerous pattern in any future change.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# backend/tests/test_frontend_url_config.py → parents[2] == 项目根
ROOT = Path(__file__).resolve().parents[2]
WEB_ADMIN_SRC = ROOT / "web-admin" / "src"

DANGEROUS_PATTERN = re.compile(
    r"""import\.meta\.env\.VITE_API_URL\s*\|\|\s*['"]http://localhost:8000['"]"""
)

# vite.config.ts 的 dev server proxy 是 dev-only，build 后不生效，属于合法开发配置
ALLOWLIST_PATHS = {ROOT / "web-admin" / "vite.config.ts"}


def _scan_file(path: Path) -> list[tuple[int, str]]:
    if path in ALLOWLIST_PATHS:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    out = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if DANGEROUS_PATTERN.search(line):
            out.append((lineno, line.strip()))
    return out


def _all_web_admin_files() -> list[Path]:
    if not WEB_ADMIN_SRC.exists():
        return []
    return sorted(WEB_ADMIN_SRC.rglob("*.ts")) + sorted(WEB_ADMIN_SRC.rglob("*.tsx"))


@pytest.mark.parametrize("path", _all_web_admin_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_dangerous_api_url_fallback(path: Path):
    violations = _scan_file(path)
    assert not violations, (
        f"{path.relative_to(ROOT)} 含危险 API URL fallback：\n"
        + "\n".join(f"  L{n}: {line}" for n, line in violations)
        + "\n\n正确写法：`import.meta.env.VITE_API_URL || ''`，由浏览器拼相对路径，"
        "经 nginx 反代到后端。填 localhost:8000 会让 SSE 请求打到用户本机、"
        "后端无日志、且与 2026-09-19 现场 bug 同型。"
    )


def test_env_production_keeps_vite_api_url_empty():
    env_prod = ROOT / "web-admin" / ".env.production"
    assert env_prod.exists(), f"缺少 {env_prod}"
    for line in env_prod.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key.strip() == "VITE_API_URL":
            assert value.strip() == "", (
                f"web-admin/.env.production 中 VITE_API_URL 必须为空字符串，"
                f"当前为 {value!r}；填 localhost:8000 会让 SSE 失败，"
                "重现 2026-09-19 现场 bug。"
            )
            return
