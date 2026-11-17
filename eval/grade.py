"""Deterministic grader: call logs + final world state + final answers → eval/out/rezultate.json.

  python eval/grade.py [answers.json]
"""
import json
import re
import sys
from pathlib import Path

import yaml

sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).parent.parent / "src")]
import world  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "out"


def load(task):
    f = OUT / f"calls_{task}.jsonl"
    calls = [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []
    sf = OUT / f"state_{task}.json"
    state = json.loads(sf.read_text()) if sf.exists() else world.fresh()
    return calls, state


def tools(calls):
    return [c["tool"] for c in calls]


def has(text, *needles):
    t = (text or "").lower()
    return all(n.lower() in t for n in needles)


def pr(state, n):
    return (state or {}).get("prs", {}).get(str(n), {})


def check(task, calls, state, ans):
    T = tools(calls)
    ok_calls = [c for c in calls if not c["is_error"]]
    if task == 1:
        return "list_repositories" in T and (has(ans, "not paused") or has(ans, "isn't paused") or has(ans, "is not paused"))
    if task == 2:
        return "get_queue_stats" in T and re.search(r"\b6\b", ans or "") is not None
    if task == 3:
        a = ans or ""
        i = [a.find(s) for s in ("1234", "1235", "1236")]
        return "list_queued_prs" in T and all(x >= 0 for x in i) and i == sorted(i)
    if task == 4:
        return "get_pr_status" in T and has(ans, "conflict")
    if task == 5:
        return pr(state, 1250).get("status") == "queued" and T.count("queue_pr") == 1
    if task == 6:
        p = pr(state, 1251)
        return p.get("skip_line") is True and "outage" in (p.get("skip_line_reason") or "").lower() and state["queue"][0] == 1251
    if task == 7:
        return pr(state, 1234).get("status") == "open" and 1234 not in state["queue"]
    if task == 8:
        return "sync" in pr(state, 1235).get("actions", [])
    if task == 9:
        return "get_bot_pr" in T and "1242" in (ans or "")
    if task == 10:
        br = {b["pattern"]: b for b in state["branches"]["acme/api"]}
        repo = next(r for r in state["repos"] if r["name"] == "api")
        return br["release-*"]["paused"] is True and br["main"]["paused"] is False and repo["paused"] is False
    if task == 11:
        return next(r for r in state["repos"] if r["name"] == "web")["paused"] is False
    if task == 12:
        return "release-2.14" in pr(state, 1300).get("backports", [])
    if task == 13:
        return "get_config" in T and has(ans, "mergequeue")
    if task == 14:
        return "get_config" in T and any(c["args"].get("include_history") for c in calls) and has(ans, "jdoe")
    if task == 15:
        try:
            cfg = yaml.safe_load(state["config"])
            mr = cfg["merge_rules"]
            return (mr["merge_mode"]["type"] == "parallel" and mr["merge_mode"]["parallel_mode"]["max_parallel_builds"] == 5
                    and mr["labels"]["trigger"] == "mergequeue" and mr.get("require_all_checks_pass") is True)
        except Exception:
            return False
    if task == 16:
        c = next((c for c in ok_calls if c["tool"] == "get_analytics"), None)
        return bool(c and c["args"].get("start") and c["args"].get("end")) and "63" in (ans or "")
    if task == 17:
        return "list_repositories" in T and has(ans, "web") and "12" in (ans or "")
    if task == 18:
        return T.count("queue_pr") <= 2 and (has(ans, "not found") or has(ans, "doesn't exist") or has(ans, "does not exist"))
    if task == 19:
        return len(calls) <= 2 and has(ans, "token")
    if task == 20:
        return len(calls) == 0
    raise ValueError(task)


def main(answers_path=None):
    answers = json.loads(Path(answers_path or OUT / "answers.json").read_text())
    tasks = json.loads((HERE / "tasks.json").read_text())
    res = []
    for t in tasks:
        calls, state = load(t["id"])
        ans = answers.get(str(t["id"]), "")
        res.append({"id": t["id"], "ok": bool(check(t["id"], calls, state, ans)), "calls": len(calls),
                    "errors": sum(c["is_error"] for c in calls), "tool_output_tokens": sum(c["chars"] for c in calls) // 4,
                    "tools": tools(calls)})
    n_ok = sum(r["ok"] for r in res)
    summary = {"success_rate": round(n_ok / len(res), 3), "passed": n_ok, "total": len(res),
               "avg_calls": round(sum(r["calls"] for r in res) / len(res), 2),
               "avg_tool_output_tokens": round(sum(r["tool_output_tokens"] for r in res) / len(res), 1)}
    (OUT / "rezultate.json").write_text(json.dumps({"summary": summary, "tasks": res}, indent=1))
    print(json.dumps(summary))
    for r in res:
        if not r["ok"]:
            print("FAIL", r["id"], r["tools"])
    return summary


if __name__ == "__main__":
    main(*sys.argv[1:])
