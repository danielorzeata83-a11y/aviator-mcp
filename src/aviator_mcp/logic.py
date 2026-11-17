"""Pure logic: input validation, request bodies, response shaping. No I/O."""
from __future__ import annotations

import datetime as dt
import os
import re

import yaml

_SLUG = re.compile(r"^[A-Za-z0-9_.-]+$")
PR_ACTIONS = {"queue", "update", "dequeue", "refresh", "sync"}


class InputError(ValueError):
    """Invalid tool input, reported to the model without calling the API."""


def resolve_repo(org: str | None, repo: str | None) -> tuple[str, str]:
    """Return (org, repo). Accepts repo='org/name' and AVIATOR_DEFAULT_ORG/REPO env fallbacks."""
    repo = repo or os.getenv("AVIATOR_DEFAULT_REPO")
    org = org or None
    if repo and "/" in repo:
        o, _, repo = repo.partition("/")
        if org and org != o:
            raise InputError(f"org '{org}' conflicts with repo '{o}/{repo}'. Pass one of them.")
        org = o
    org = org or os.getenv("AVIATOR_DEFAULT_ORG")
    if not repo:
        raise InputError("Missing repo. Pass repo='org/name' (or set AVIATOR_DEFAULT_REPO).")
    if not org:
        raise InputError("Missing org. Pass org='github-org' or repo='org/name' (or set AVIATOR_DEFAULT_ORG).")
    for label, v in (("org", org), ("repo", repo)):
        if not _SLUG.match(v):
            raise InputError(f"Invalid {label} '{v}': use the GitHub name only (letters, digits, - _ .).")
    return org, repo


def check_pr_number(n: int) -> int:
    if n <= 0:
        raise InputError(f"PR number must be a positive integer, got {n}.")
    return n


def check_date(s: str | None) -> str | None:
    if s is None:
        return None
    try:
        dt.date.fromisoformat(s)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            raise ValueError
    except ValueError:
        raise InputError(f"Invalid date '{s}': use YYYY-MM-DD (UTC).") from None
    return s


def check_range(start: str | None, end: str | None) -> tuple[str | None, str | None]:
    start, end = check_date(start), check_date(end)
    if start and end and start > end:
        raise InputError(f"start ({start}) is after end ({end}).")
    return start, end


def pr_lookup(number: int | None, branch: str | None) -> dict:
    if (number is None) == (not branch):
        raise InputError("Pass exactly one of `number` or `branch`.")
    return {"number": check_pr_number(number)} if number is not None else {"branch": branch}


def pr_body(action: str, org: str, repo: str, number: int, *, skip_line: bool | None = None,
            skip_line_reason: str | None = None, skip_validation: bool | None = None,
            affected_targets: list[str] | None = None, merge_commit_title: str | None = None,
            merge_commit_body: str | None = None) -> dict:
    """Body for POST /api/v1/pull_request."""
    if action not in PR_ACTIONS:
        raise InputError(f"Unknown action '{action}'. Valid: {sorted(PR_ACTIONS)}.")
    if skip_line_reason and not skip_line:
        raise InputError("skip_line_reason requires skip_line=true.")
    if action not in ("queue", "update") and (skip_line or skip_validation):
        raise InputError("skip_line / skip_validation are only valid when you queue a PR.")
    pr: dict = {"number": check_pr_number(number), "repository": {"org": org, "name": repo}}
    opts = {"skip_line": skip_line or None, "skip_line_reason": skip_line_reason,
            "skip_validation": skip_validation or None, "affected_targets": affected_targets}
    pr.update({k: v for k, v in opts.items() if v is not None})
    if action == "queue" and affected_targets is None:
        pr["affected_targets"] = []  # required by the live API for queue, despite the docs
    if merge_commit_body and not merge_commit_title:
        raise InputError("merge_commit_body requires merge_commit_title.")
    if merge_commit_title:
        # Live API rejects a message without a body ("Invalid pull_request object").
        pr["merge_commit_message"] = {"title": merge_commit_title, "body": merge_commit_body or merge_commit_title}
    return {"action": action, "pull_request": pr}


def check_yaml(text: str) -> str:
    if not text or not text.strip():
        raise InputError("yaml_config is empty.")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise InputError(f"yaml_config is not valid YAML: {e}") from None
    if not isinstance(data, dict):
        raise InputError("yaml_config must be a YAML mapping (e.g. starting with `merge_rules:`).")
    return text


def truncate_text(text: str, max_chars: int) -> dict:
    return {"text": text[:max_chars], "truncated": len(text) > max_chars, "total_chars": len(text)}


def cap_list(items: list, limit: int) -> dict:
    return {"items": items[:limit], "count": min(len(items), limit), "total": len(items), "truncated": len(items) > limit}


def pick(d: dict, keys: tuple[str, ...]) -> dict:
    return {k: d[k] for k in keys if k in d}


def summarize_analytics(data: dict) -> dict:
    """Aggregate Aviator's daily analytics lists into a few numbers. Time values are minutes (verified live)."""
    days = {row.get("date") for v in data.values() if isinstance(v, list) for row in v if isinstance(row, dict)}
    out: dict = {"days": len(days)}
    tiq = data.get("time_in_queue") or []
    if tiq:
        out["time_in_queue_avg_minutes"] = round(sum(r.get("avg", 0) for r in tiq) / len(tiq), 1)
        out["time_in_queue_p90_max_minutes"] = max(r.get("p90", 0) for r in tiq)
    usage = data.get("mergequeue_usage") or []
    if usage:
        out["prs_merged_total"] = sum(r.get("total", 0) for r in usage)
        out["prs_merged_by_aviator"] = sum(r.get("merged_by_bot", 0) for r in usage)
    blocked = data.get("blocked_reason") or []
    if blocked:
        totals: dict = {}
        for r in blocked:
            for k, v in r.items():
                if k != "date" and isinstance(v, (int, float)):
                    totals[k] = totals.get(k, 0) + v
        out["blocked_totals"] = totals
    return out


def compact_schema(schema):
    """Drop auto-generated `title`s and collapse Optional `anyOf [T, null]` (default None) to `T`.

    Only changes what the model reads; argument validation still uses the original pydantic model.
    """
    if isinstance(schema, list):
        return [compact_schema(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: compact_schema(v) for k, v in schema.items() if k != "title"}
    any_of = out.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2 and {"type": "null"} in any_of:
        inner = next(x for x in any_of if x != {"type": "null"})
        out.pop("anyOf")
        if out.get("default", 0) is None:
            out.pop("default")
        out = {**inner, **out}
    if "properties" in out:
        out["properties"] = {k: compact_schema(v) for k, v in schema["properties"].items()}
    return out
