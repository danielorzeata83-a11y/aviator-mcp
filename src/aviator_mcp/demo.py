"""Stateful simulated Aviator API (httpx MockTransport): used by AVIATOR_DEMO=1 and by the eval harness."""
from __future__ import annotations

import copy
import json

import httpx
import yaml

CONFIG = """merge_rules:
  labels:
    trigger: mergequeue
    skip_line: mergequeue-priority
  merge_mode:
    type: default
  require_all_checks_pass: true
"""


def default_state() -> dict:
    repos = [{"org": "acme", "name": n, "paused": n == "web", "active": True}
             for n in ["api", "web", "infra", "mobile", "docs", "billing", "auth", "search", "ml", "data", "cli", "sdk"]]
    pr = lambda n, title, status, **kw: {"number": n, "title": title, "author": kw.pop("author", "dev"), "status": status,
                                          "base_branch": kw.pop("base", "main"), "head_branch": f"feat/{n}",
                                          "queued": status == "queued", "skip_line": False, **kw}
    prs = {
        1234: pr(1234, "Login rate limit", "queued", author="ana", bot_pull_request={"number": 5003}),
        1235: pr(1235, "Fix cache key", "queued", author="bob"),
        1236: pr(1236, "Bump deps", "queued", author="cat"),
        1237: pr(1237, "Docs typo", "queued", author="dan"),
        1238: pr(1238, "Metrics", "queued", author="eve"),
        1239: pr(1239, "Refactor", "queued", author="fay"),
        1240: pr(1240, "Payments v2", "blocked", author="gus", blocked_reason="MERGE_CONFLICT (106): merge conflict with main"),
        1241: pr(1241, "Search filters", "queued", author="hal"),
        1242: pr(1242, "Session store", "blocked", author="ivy", blocked_reason="FAILED_TESTS (107): required check 'build_and_test' failed"),
        1243: pr(1243, "UI polish", "queued", author="jon"),
        1250: pr(1250, "Add audit log", "open", author="kim"),
        1251: pr(1251, "Hotfix null deref", "open", author="lee"),
        1300: pr(1300, "Security patch", "merged", author="max"),
        1400: pr(1400, "Release notes", "queued", author="ned", base="release-2.14"),
    }
    return {
        "repos": repos,
        "branches": {"acme/api": [{"pattern": "main", "paused": False}, {"pattern": "release-*", "paused": False},
                                  {"pattern": "hotfix-*", "paused": True, "paused_message": "Hotfix lane closed"}]},
        "prs": {str(k): v for k, v in prs.items()},
        "queue": [1234, 1235, 1236, 1237, 1238, 1239, 1241, 1243, 1400],
        "bot_prs": {"5001": {"number": 5001, "github_url": "https://github.com/acme/api/pull/5001", "target_branch": "main",
                             "status": "failed", "pull_requests": [1241, 1242, 1243]}},
        "config": CONFIG,
        "config_history": [
            {"applied_by": {"gh_username": "jdoe"}, "applied_at": "2026-11-10T09:12:00Z", "commit_sha": "85d4",
             "diff": "-    trigger: ready-to-merge\n+    trigger: mergequeue"},
            {"applied_by": {"gh_username": "asmith"}, "applied_at": "2026-10-02T15:00:00Z", "commit_sha": "11aa",
             "diff": "+  require_all_checks_pass: true"}],
        "analytics": {
            "time_in_queue": [{"date": f"2026-11-{d:02d}", "avg": 20 + d, "p90": 50 + d} for d in range(7, 14)],
            "mergequeue_usage": [{"date": f"2026-11-{d:02d}", "total": 9, "merged_by_bot": 8} for d in range(7, 14)],
            "blocked_reason": [{"date": f"2026-11-{d:02d}", "ci_failure": d % 3, "merge_conflict": 1, "manual_dequeue": 0,
                                "ci_timeout": 0, "other": 0} for d in range(7, 14)]},
        "log": [],
    }


def _json(status: int, data) -> httpx.Response:
    return httpx.Response(status, json=data)


def handler_for(state: dict):
    def handle(req: httpx.Request) -> httpx.Response:
        p, q, m = req.url.path, dict(req.url.params), req.method
        body = json.loads(req.content) if req.content and req.headers.get("content-type", "").startswith("application/json") else None
        state["log"].append({"method": m, "path": p, "query": q, "body": body if body is not None else (req.content.decode() or None)})
        prs = state["prs"]

        def repo_ok(org, name):
            return any(r["org"] == org and r["name"] == name for r in state["repos"])

        if p == "/api/v1/repo" and m == "GET":
            page = int(q.get("page", 1))
            return _json(200, state["repos"][(page - 1) * 10: page * 10])
        if p == "/api/v1/repo" and m == "POST":
            for r in state["repos"]:
                if r["org"] == body["org"] and r["name"] == body["name"]:
                    r["paused"] = body["paused"]
                    return _json(200, r)
            return _json(404, {"error": "not-found", "message": "repository not found"})
        if p == "/api/v1/branches":
            key = f"{body['repository']['org']}/{body['repository']['name']}"
            if "paused" not in body:  # read-only call
                return _json(200, {"branches": state["branches"].get(key, []), "repository": body["repository"]})
            branches = state["branches"].setdefault(key, [])
            for b in branches:
                if b["pattern"] == body["pattern"]:
                    b.update(paused=body["paused"], paused_message=body.get("paused_message"))
                    break
            else:
                branches.append({"pattern": body["pattern"], "paused": body["paused"]})
            return _json(200, body)

        org, repo = q.get("org", "acme"), q.get("repo", "api")
        if "repo" in q and "/" not in q["repo"] and not repo_ok(org, repo):
            return _json(403, {"error": "forbidden", "message": f"repository ({org}/{repo}) not found (is this repo configured with Aviator?)"})

        if p == "/api/v1/queue/stats":
            n = len(state["queue"])
            return _json(200, {"depth": {"queued": n, "processing": 3, "waiting": n - 3}})
        if p == "/api/v1/pull_request/queued":
            items = [prs[str(n)] for n in state["queue"] if not q.get("base_branch") or prs[str(n)]["base_branch"] == q["base_branch"]]
            return _json(200, {"pull_requests": items})
        if p == "/api/v1/pull_request" and m == "GET":
            if "number" in q:
                pr = prs.get(q["number"])
            else:
                pr = next((x for x in prs.values() if x["head_branch"] == q.get("branch")), None)
            return _json(200, pr) if pr else _json(404, {"error": "not-found", "message": "pull_request not found"})
        if p == "/api/v1/pull_request" and m == "POST":
            action, n = body["action"], str(body["pull_request"]["number"])
            pr = prs.get(n)
            if not pr:
                return _json(404, {"error": "not-found", "message": "pull_request not found"})
            if action == "queue":
                pr.update(status="queued", queued=True, skip_line=bool(body["pull_request"].get("skip_line")),
                          skip_line_reason=body["pull_request"].get("skip_line_reason"))
                if int(n) in state["queue"]:
                    state["queue"].remove(int(n))
                state["queue"].insert(0, int(n)) if pr["skip_line"] else state["queue"].append(int(n))
            elif action == "dequeue":
                pr.update(status="open", queued=False, skip_line=False)
                state["queue"] = [x for x in state["queue"] if x != int(n)]
            else:
                pr.setdefault("actions", []).append(action)
            return _json(200, {"pull_request": pr})
        if p == "/api/v1/pull_request/backport":
            n = str(body["source_pull"]["number"])
            if n not in prs:
                return _json(404, {"error": "not-found", "message": "pull_request not found"})
            prs[n].setdefault("backports", []).append(body["target_branch"])
            return _json(200, {**body, "message": f"Backporting initiated for {n} to {body['target_branch']}."})
        if p == "/api/v1/pull_request/bisection":
            n = int(q["number"])
            if n in (1241, 1242, 1243):
                return _json(200, {"pull_request": {"number": n}, "is_bisecting": False,
                                   "bisection": {"round": 2, "last_failed_bot_pull_request": {"number": 5001}},
                                   "result": "PR #1242 identified as failing; #1241 and #1243 re-queued"})
            return _json(200, {"pull_request": {"number": n}, "is_bisecting": False, "bisection": None})
        if p == "/api/v1/bot_pull_request":
            b = state["bot_prs"].get(q["number"])
            if not b:
                return _json(404, {"error": "not-found", "message": "bot pull request not found"})
            return _json(200, {**b, "pull_requests": [prs[str(x)] for x in b["pull_requests"]]})
        if p == "/api/v1/config" and m == "GET":
            return httpx.Response(200, text=state["config"])
        if p == "/api/v1/config" and m == "POST":
            text = req.content.decode()
            try:
                data = yaml.safe_load(text)
                assert isinstance(data, dict) and "merge_rules" in data
            except Exception:
                return _json(400, {"errors": ["config: could not parse merge_rules"]})
            mm = data["merge_rules"].get("merge_mode", {})
            pm = (mm or {}).get("parallel_mode") or {}
            if "max_parallel_builds" in pm and not isinstance(pm["max_parallel_builds"], int):
                return _json(400, {"errors": ["mergeRules -> mergeMode -> parallelMode -> maxParallelBuilds: not an integer"]})
            state["config"] = text
            return _json(200, {"success": True})
        if p == "/api/v1/config/history":
            page = int(q.get("page", 1))
            return _json(200, {"repository": {"org": org, "name": repo}, "history": state["config_history"] if page == 1 else []})
        if p == "/api/v1/analytics":
            return _json(200, state["analytics"])
        return _json(404, {"error": "not-found", "message": f"no route {m} {p}"})

    return handle


def fresh() -> dict:
    return copy.deepcopy(default_state())
