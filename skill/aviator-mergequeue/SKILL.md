---
name: aviator-mergequeue
description: Operate and troubleshoot Aviator MergeQueue (aviator.co), the GitHub merge queue. Use when the user mentions Aviator, MergeQueue, "the merge queue", queuing/dequeuing a PR, skip-line, a stuck or blocked PR in the queue, a failed batch or draft (bot) PR, bisection, pausing merges or a release freeze, backports via Aviator, the aviator YAML config (merge_rules, parallel_mode, batch_size), or queue analytics. Not for GitHub's native merge queue, Mergify or Graphite.
---

# Aviator MergeQueue

Aviator merges GitHub PRs through a queue: a PR is marked ready (label, `/aviator merge`, or API), passes pre-queue checks, gets validated against the latest base branch (plus PRs ahead of it), then merges.

## Tools
- **MCP server `aviator-unofficial`** (preferred if connected): 8 read tools (`get_pr_status`, `list_queued_prs`, `get_queue_stats`, `get_bot_pr`, `get_bisection_status`, `get_config`, `get_analytics`, `list_repositories`) and 6 write tools (`queue_pr`, `dequeue_pr`, `refresh_or_sync_pr`, `set_queue_paused`, `backport_pr`, `update_config`).
- **No MCP?** Use the REST API directly (`references/api.md`) with `AVIATOR_API_TOKEN`, or tell the user the equivalent GitHub slash command (`references/slash-commands.md`).

Always pass `org` and `repo` (or `repo="org/name"`). Never invent them: ask, or infer from the git remote.

## Workflows

**"Why isn't PR #N merging?"**
1. `get_pr_status` → read `status` (open / pending / queued / blocked / merged).
2. `blocked` → map the reason with `references/status-codes.md` (e.g. 106 merge conflict, 107 failed tests, 116 commit added) and tell the user the fix.
3. `queued` but slow → `get_queue_stats` + `list_queued_prs` (position). If it has a `bot_pull_request`, check that batch's CI.
4. `pending` → a pre-queue condition isn't met yet (checks running, approvals, conflicts).

**"The batch failed — which PR broke it?"** `get_pr_status` → `get_bot_pr` (PRs in the batch) → `get_bisection_status`. While bisecting, Aviator re-queues the batch split in two; the culprit gets `blocked`. Report findings; don't dequeue PRs unless asked.

**Queue / dequeue / sync** — act directly when the user asks. For **skip-line**, confirm first and pass a reason: in parallel mode it resets all running draft PRs (wasted CI) unless `non_destructive_skip_line` is on.

**Freeze / pause** — `set_queue_paused` with `branch_pattern` (e.g. `release-*`) pauses only those base branches; without it the whole repo pauses. Paused queues still validate PRs but don't merge.

**Config change** — `get_config` → edit only the requested keys → show the user the diff → `update_config` with the FULL YAML. On 400, fix the listed paths. Key names: `references/config.md`. A config change resets a parallel queue (code 307).

**Queue health / reporting** — `get_analytics` with a date range; it returns a summary (avg time in queue, PRs merged, blocked reasons). Don't compute numbers you weren't given.

## Concepts you need to get right
Queue modes, parallel mode, batching, bisection, affected targets, ChangeSets, stacked PRs: see `references/concepts.md`. Read it before explaining behavior or changing `merge_mode`.

## Pitfalls
- In parallel mode, dequeuing a PR, closing a draft PR, or pushing a new commit resets subsequent draft PRs. Warn before doing this to a busy queue.
- `GET /pull_request` needs exactly one of `number` or `branch`, even though the docs mark both as required.
- Parallel mode needs a Pro plan and GitHub draft PRs (Team/Enterprise). Explain this if the user's config is rejected.
- Write calls that fail with 5xx may or may not have been applied: re-read the state before retrying.
- Branch-level pause status is not readable via the API; only the whole-repo `paused` flag (list_repositories). Ask the user or check the Aviator dashboard for branch pauses.
- 403 often means the repo isn't configured in Aviator, or the token lacks skip-line rights. It is not a bug in the request.

## References (load only when needed)
- `references/api.md`: every REST endpoint, its params and example responses.
- `references/config.md`: the full MergeQueue YAML configuration reference.
- `references/status-codes.md`: blocked and reset codes with their meaning.
- `references/slash-commands.md`: `/aviator merge|cancel|refresh|sync|backport` etc.
- `references/concepts.md`: lifecycle, queue modes, parallel mode, batching, bisection, priority.
