"""Unofficial MCP server for Aviator MergeQueue (https://aviator.co). Not affiliated with Aviator."""
from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import logic as L
from .client import AviatorClient, AviatorError

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)

PR_FIELDS = ("number", "title", "author", "status", "base_branch", "head_branch", "queued", "queued_at",
             "merged_at", "skip_line", "blocked_reason", "github_url")

INSTRUCTIONS = (
    "Tools for Aviator MergeQueue (merge queue for GitHub PRs). Every tool takes `org` and `repo` "
    "(or repo='org/name'). Read state before changing it. Write tools act on the real queue: confirm "
    "intent with the user for skip_line, pausing, and config changes. For update_config, call get_config "
    "first and send the full edited YAML."
)

Org = Annotated[str | None, Field(description="GitHub org. Optional if repo is 'org/name'.")]
Repo = Annotated[str | None, Field(description="GitHub repo name or 'org/name'.")]
PrNumber = Annotated[int, Field(description="Pull request number.", gt=0)]


def build_server(client: AviatorClient | None = None) -> MCPServer:
    api = client or AviatorClient.from_env()
    instructions = INSTRUCTIONS
    if getattr(api, "demo", False):
        instructions = ("DEMO MODE: all data is simulated (fake org 'acme'); tell the user results are not real. "
                        + INSTRUCTIONS)
    mcp = MCPServer("aviator-unofficial", instructions=instructions)

    async def run(coro_fn):
        try:
            return await coro_fn()
        except (L.InputError, AviatorError) as e:
            raise ToolError(str(e)) from None

    # ---------------- read ----------------
    @mcp.tool(annotations=READ)
    async def list_repositories(limit: Annotated[int, Field(ge=1, le=200)] = 50) -> dict:
        """List repositories connected to Aviator with `paused` (whole-repo pause) and `active`. Branch-level pause state is not readable via Aviator's API."""
        async def go():
            items, more = await api.paginate("/api/v1/repo", limit=limit)
            return {"repositories": items, "count": len(items), "has_more": more}
        return await run(go)

    @mcp.tool(annotations=READ)
    async def get_queue_stats(org: Org = None, repo: Repo = None) -> dict:
        """Live queue depth for a repo: queued, processing and waiting PR counts."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            return await api.get("/api/v1/queue/stats", params={"org": o, "repo": r})
        return await run(go)

    @mcp.tool(annotations=READ)
    async def list_queued_prs(org: Org = None, repo: Repo = None,
                              base_branch: Annotated[str | None, Field(description="Only PRs targeting this branch.")] = None,
                              limit: Annotated[int, Field(ge=1, le=200)] = 50) -> dict:
        """PRs currently in the merge queue, in queue order (number, title, author, status)."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            data = await api.get("/api/v1/pull_request/queued", params={"org": o, "repo": r, "base_branch": base_branch})
            prs = [L.pick(p, PR_FIELDS) for p in (data.get("pull_requests") or [])]
            return L.cap_list(prs, limit)
        return await run(go)

    @mcp.tool(annotations=READ)
    async def get_pr_status(org: Org = None, repo: Repo = None,
                            number: Annotated[int | None, Field(gt=0, description="PR number.")] = None,
                            branch: Annotated[str | None, Field(description="PR head branch.")] = None) -> dict:
        """Merge-queue status of one PR, looked up by `number` OR `branch` (exactly one). Includes its batch (bot) PR, if any."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            data = await api.get("/api/v1/pull_request", params={"org": o, "repo": r, **L.pr_lookup(number, branch)})
            if not isinstance(data, dict):
                return {"result": data}
            out = L.pick(data, PR_FIELDS)
            if isinstance(data.get("bot_pull_request"), dict):
                out["bot_pull_request"] = L.pick(data["bot_pull_request"], ("number", "github_url", "status"))
            return out
        return await run(go)

    @mcp.tool(annotations=READ)
    async def get_bot_pr(number: PrNumber, org: Org = None, repo: Repo = None) -> dict:
        """PRs batched into an Aviator bot (draft) PR. Use it when a batch's CI failed, to see which PRs were in it."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            data = await api.get("/api/v1/bot_pull_request", params={"org": o, "repo": r, "number": number})
            if isinstance(data, dict) and isinstance(data.get("pull_requests"), list):
                data = {**data, "pull_requests": [L.pick(p, PR_FIELDS) for p in data["pull_requests"]]}
            return data
        return await run(go)

    @mcp.tool(annotations=READ)
    async def get_bisection_status(number: PrNumber, org: Org = None, repo: Repo = None) -> dict:
        """Whether Aviator is bisecting a failed batch containing this PR, and the failing bot PR."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            return await api.get("/api/v1/pull_request/bisection", params={"org": o, "repo": r, "number": number})
        return await run(go)

    @mcp.tool(annotations=READ)
    async def get_config(org: Org = None, repo: Repo = None,
                         include_history: Annotated[bool, Field(description="Also return recent config changes (who/when/diff).")] = False,
                         history_start: Annotated[str | None, Field(description="YYYY-MM-DD")] = None,
                         history_end: Annotated[str | None, Field(description="YYYY-MM-DD")] = None,
                         max_chars: Annotated[int, Field(ge=200, le=100_000)] = 8000) -> dict:
        """Current MergeQueue YAML config of a repo, optionally with change history."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            start, end = L.check_range(history_start, history_end)
            text = await api.get("/api/v1/config", params={"org": o, "repo": r})
            out: dict = {"config": L.truncate_text(text if isinstance(text, str) else str(text), max_chars)}
            if include_history:
                items, more = await api.paginate("/api/v1/config/history", key="history", limit=20,
                                                 params={"org": o, "repo": r, "start": start, "end": end})
                out["history"] = {"items": items, "has_more": more}
            return out
        return await run(go)

    @mcp.tool(annotations=READ)
    async def get_analytics(org: Org = None, repo: Repo = None,
                            start: Annotated[str | None, Field(description="YYYY-MM-DD (UTC)")] = None,
                            end: Annotated[str | None, Field(description="YYYY-MM-DD (UTC)")] = None,
                            timezone: Annotated[str | None, Field(description="e.g. Europe/Bucharest")] = None,
                            include_daily: bool = False) -> dict:
        """Merge-queue analytics for a date range: time in queue, PRs merged, blocked reasons. Returns a summary; daily rows on request."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            s, e = L.check_range(start, end)
            data = await api.get("/api/v1/analytics", params={"repo": f"{o}/{r}", "start": s, "end": e, "timezone": timezone})
            data = data if isinstance(data, dict) else {}
            return {"summary": L.summarize_analytics(data), "daily": data if include_daily else "omitted (include_daily=true)"}
        return await run(go)

    # ---------------- write ----------------
    @mcp.tool(annotations=WRITE)
    async def queue_pr(number: PrNumber, org: Org = None, repo: Repo = None,
                       skip_line: Annotated[bool, Field(description="Jump to the front of the queue. Needs authorization; confirm with the user.")] = False,
                       skip_line_reason: str | None = None,
                       affected_targets: list[str] | None = None,
                       merge_commit_title: str | None = None,
                       merge_commit_body: str | None = None) -> dict:
        """Add a PR to the merge queue (Aviator merges it once CI passes)."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            body = L.pr_body("queue", o, r, number, skip_line=skip_line, skip_line_reason=skip_line_reason,
                             affected_targets=affected_targets, merge_commit_title=merge_commit_title,
                             merge_commit_body=merge_commit_body)
            return await api.post("/api/v1/pull_request", json=body)
        return await run(go)

    @mcp.tool(annotations=WRITE)
    async def dequeue_pr(number: PrNumber, org: Org = None, repo: Repo = None) -> dict:
        """Remove a PR from the merge queue (also clears its skip-line options)."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            return await api.post("/api/v1/pull_request", json=L.pr_body("dequeue", o, r, number))
        return await run(go)

    @mcp.tool(annotations=WRITE)
    async def refresh_or_sync_pr(number: PrNumber, action: Literal["refresh", "sync"],
                                 org: Org = None, repo: Repo = None) -> dict:
        """`refresh`: re-evaluate a PR's queue state. `sync`: update the PR branch with its base branch."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            return await api.post("/api/v1/pull_request", json=L.pr_body(action, o, r, number))
        return await run(go)

    @mcp.tool(annotations=WRITE)
    async def set_queue_paused(paused: bool, org: Org = None, repo: Repo = None,
                               branch_pattern: Annotated[str | None, Field(description="Pause only base branches matching this glob, e.g. 'release-*'. Omit to pause the whole repo.")] = None,
                               paused_message: Annotated[str | None, Field(description="Message posted on queued PRs (branch pause only).")] = None) -> dict:
        """Pause or resume merging for a whole repo, or only for matching base branches."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            if branch_pattern:
                body = {"repository": {"org": o, "name": r}, "pattern": branch_pattern, "paused": paused}
                if paused_message:
                    body["paused_message"] = paused_message
                await api.post("/api/v1/branches", json=body)
                scope = f"base branches matching '{branch_pattern}'"
            else:
                if paused_message:
                    raise L.InputError("paused_message is only supported together with branch_pattern.")
                await api.post("/api/v1/repo", json={"org": o, "name": r, "paused": paused})
                scope = "whole repo"
            return {"repo": f"{o}/{r}", "scope": scope, "paused": paused}
        return await run(go)

    @mcp.tool(annotations=WRITE)
    async def backport_pr(number: PrNumber, target_branch: str, org: Org = None, repo: Repo = None) -> dict:
        """Ask Aviator to backport a merged PR onto another branch (it opens a new PR)."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            body = {"target_branch": target_branch, "source_pull": {"number": number, "repository": {"org": o, "name": r}}}
            return await api.post("/api/v1/pull_request/backport", json=body)
        return await run(go)

    @mcp.tool(annotations=WRITE)
    async def update_config(yaml_config: Annotated[str, Field(description="The FULL new aviator config YAML (replaces the current one).")],
                            org: Org = None, repo: Repo = None) -> dict:
        """Replace a repo's MergeQueue YAML config. Call get_config first, edit only what was asked, send the whole file. Parallel mode: merge_rules.merge_mode.type: parallel + merge_mode.parallel_mode.max_parallel_builds / batch_size."""
        async def go():
            o, r = L.resolve_repo(org, repo)
            text = L.check_yaml(yaml_config)
            return await api.post("/api/v1/config", params={"org": o, "repo": r}, content=text, content_type="text/plain")
        return await run(go)

    for tool in mcp._tool_manager._tools.values():  # schema shown to the model; validation unchanged
        tool.parameters = L.compact_schema(tool.parameters)
    return mcp


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
