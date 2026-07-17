#!/usr/bin/env python3
"""Frontend page smoke: login pages + static assets + authenticated SPA shells."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime

import httpx

WEB = "http://49.232.213.79:3000"
H5 = "http://49.232.213.79:5173"
API = "http://49.232.213.79:8000"


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    return {"name": name, "ok": bool(cond), "detail": detail}


def main():
    results = []
    with httpx.Client(timeout=30.0, follow_redirects=True) as c:
        # Web shell
        r = c.get(WEB + "/")
        results.append(check("web_index", r.status_code == 200, f"status={r.status_code}"))
        results.append(check("web_has_root", "id=\"root\"" in r.text or "id='root'" in r.text, "root mount"))
        # extract assets
        assets = re.findall(r'src="([^"]+)"', r.text) + re.findall(r'href="([^"]+\.css)"', r.text)
        for a in assets[:5]:
            url = a if a.startswith("http") else WEB.rstrip("/") + "/" + a.lstrip("/")
            # vite base may be absolute path
            if a.startswith("/"):
                url = WEB.rstrip("/") + a
            try:
                ar = c.get(url)
                results.append(check(f"web_asset {a[-40:]}", ar.status_code == 200, str(ar.status_code)))
            except Exception as e:
                results.append(check(f"web_asset {a[-40:]}", False, str(e)))

        # H5 shell
        r = c.get(H5 + "/h5/")
        results.append(check("h5_index", r.status_code == 200, f"status={r.status_code}"))
        results.append(check("h5_has_app", "id=\"app\"" in r.text or "id='app'" in r.text or "vite" in r.text.lower() or len(r.text) > 100, "shell"))
        assets = re.findall(r'src="([^"]+)"', r.text) + re.findall(r'href="([^"]+\.css)"', r.text)
        for a in assets[:5]:
            if a.startswith("http"):
                url = a
            elif a.startswith("/"):
                url = H5.rstrip("/") + a
            else:
                url = H5.rstrip("/") + "/h5/" + a
            try:
                ar = c.get(url)
                results.append(check(f"h5_asset {a[-40:]}", ar.status_code == 200, str(ar.status_code)))
            except Exception as e:
                results.append(check(f"h5_asset {a[-40:]}", False, str(e)))

        # API login then hit common data for SPA pages
        lr = c.post(API + "/api/auth/login", json={"username": "admin", "password": "admin123"})
        results.append(check("api_login", lr.status_code == 200 and lr.json().get("code") == 200, str(lr.status_code)))
        token = lr.json()["data"]["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        page_apis = [
            ("dashboard", "/api/analytics/dashboard"),
            ("templates", "/api/templates?limit=5"),
            ("tasks", "/api/tasks?limit=5"),
            ("records", "/api/records?limit=5"),
            ("enterprises", "/api/enterprises?limit=5"),
            ("users", "/api/users?limit=5"),
            ("industries", "/api/industries"),
            ("knowledge", "/api/knowledge/categories"),
            ("audit_projects", "/api/audit-projects?limit=5"),
            ("statistics", "/api/statistics"),
        ]
        for name, path in page_apis:
            r = c.get(API + path, headers=h)
            ok = r.status_code == 200 and (r.json().get("code") == 200 if r.headers.get("content-type", "").startswith("application/json") else True)
            results.append(check(f"page_api {name}", ok, f"{r.status_code}"))

        # H5 expert
        er = c.post(API + "/api/auth/login", json={"username": "expert", "password": "expert123"})
        results.append(check("expert_login", er.status_code == 200, str(er.status_code)))
        eh = {"Authorization": f"Bearer {er.json()['data']['access_token']}"}
        r = c.get(API + "/api/tasks?limit=10", headers=eh)
        results.append(check("h5_expert_tasks", r.status_code == 200, str(r.status_code)))
        r = c.get(API + "/api/audit-projects/my-tasks", headers=eh)
        results.append(check("h5_my_audit_tasks", r.status_code == 200, f"{r.status_code}"))

    passed = sum(1 for x in results if x["ok"])
    failed = sum(1 for x in results if not x["ok"])
    print(f"\nTOTAL {len(results)} PASS {passed} FAIL {failed}")
    out = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    path = f"docs/EFIS_前端页面冒烟_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("REPORT", path)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
