# aviator-mcp-unofficial

**Unofficial** [Model Context Protocol](https://modelcontextprotocol.io) server for the [Aviator](https://aviator.co) MergeQueue REST API. Lets Claude (or any MCP client) inspect and operate your merge queue: see why a PR isn't merging, find which PR broke a batch, queue or dequeue PRs, pause branches for a release freeze, and read or change the queue config.

> Not affiliated with, endorsed by, or supported by Aviator Technologies, Inc. "Aviator" is their trademark. This project uses only Aviator's public, documented API.

## Tools (14)

| Read (no side effects) | Write (changes the real queue) |
|---|---|
| `list_repositories` — repos + paused/active | `queue_pr` — queue a PR (optional skip-line + reason) |
| `get_queue_stats` — queued / processing / waiting | `dequeue_pr` |
| `list_queued_prs` — queue contents in order | `refresh_or_sync_pr` — `refresh` or `sync` with base |
| `get_pr_status` — by number or branch | `set_queue_paused` — whole repo or a branch glob |
| `get_bot_pr` — PRs inside a batch (draft) PR | `backport_pr` |
| `get_bisection_status` — failed-batch bisection | `update_config` — replace the YAML config (validated locally first) |
| `get_config` — YAML (+ optional change history) | |
| `get_analytics` — summary of queue metrics | |

Write tools are annotated `destructiveHint: true`, so clients can ask for confirmation.

## Install

Requires Python ≥ 3.12.

```bash
pip install git+https://github.com/danielorzeata83-a11y/aviator-mcp
```

Create an API token in Aviator (Settings → API token: an account token, or a personal `av_uat_…` token).

### Claude Code

```bash
claude mcp add aviator --env AVIATOR_API_TOKEN=av_uat_xxx -- aviator-mcp
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "aviator": {
      "command": "aviator-mcp",
      "env": { "AVIATOR_API_TOKEN": "av_uat_xxx", "AVIATOR_DEFAULT_ORG": "acme" }
    }
  }
}
```

### Configuration

| Variable | Required | Meaning |
|---|---|---|
| `AVIATOR_API_TOKEN` | yes | Bearer token |
| `AVIATOR_API_URL` | no | Default `https://api.aviator.co`; set it for on-prem installs |
| `AVIATOR_DEFAULT_ORG` / `AVIATOR_DEFAULT_REPO` | no | Used when a tool call omits `org` / `repo` |

## Examples

- "Why isn't acme/api #1240 merging?" → `get_pr_status` → *blocked: merge conflict with main (code 106)*
- "Batch #5001 failed — who broke it?" → `get_bot_pr` → *#1242, required check build_and_test failed*
- "Pause release-* in acme/api for the freeze" → `set_queue_paused(branch_pattern="release-*")`
- "Switch to parallel mode, 5 builds" → `get_config` → `update_config` with the full edited YAML

A companion **Claude skill** (`skill/aviator-mergequeue`) adds workflows, status codes and the config reference. Install it by copying that folder into your Claude skills directory, or zip it and upload it in Claude.

## Behaviour notes and limitations

- Errors are turned into actionable messages (401 token, 403 permission/repo not configured, 404, 400 field list, 429 rate limit). GET requests retry once on 429/5xx; writes are **never** retried automatically.
- Large outputs are capped: the config YAML is truncated (`max_chars`), lists are limited (`limit`), and analytics return a summary unless `include_daily=true`.
- Not covered in v0.1: the GraphQL API, `user_actions` (Enterprise audit log), and the TestDeck, Releases, Verify and Runbooks APIs.
- Branch-level pause **status** can't be read: tested against the live API, `GET /api/v1/branches` is rejected and the POST form requires `paused` (it changes state). Pausing/resuming branches works via `set_queue_paused`.
- Verified end-to-end against a live Aviator account (Nov 2026): every tool, including queue → merge, a parallel-mode batch, backport, skip-line, sync, branch pause and config update.
- Live-API quirks handled: `affected_targets` and a full merge-commit message (`title` + `body`) are always sent; analytics times are in minutes.
- `AVIATOR_DEMO=1` runs the server on simulated data (no token, no network) for demos.

## Repository layout

| Path | What it is |
|---|---|
| `src/aviator_mcp/` | The MCP server (`server.py` tools, `client.py` HTTP + errors, `logic.py` validation, `demo.py` simulated API) |
| `tests/` | Unit tests (HTTP mocked with respx) |
| `eval/` | 20-task evaluation harness on a simulated Aviator world |
| `skill/aviator-mergequeue/` | Claude skill: `SKILL.md` + references |
| `skill/eval/` | Skill-triggering evaluation |
| `docs/PORTFOLIO.md` | Problem → solution → measured results |

## Development

```bash
pip install -e ".[dev]"
pytest --cov=aviator_mcp          # unit tests (HTTP mocked with respx)
bash eval/oracle.sh               # validates the evaluation harness
```

## License

MIT. API knowledge is derived from Aviator's documentation (github.com/aviator-co/gitbook-docs, MIT).
