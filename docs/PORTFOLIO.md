# Aviator MergeQueue for Claude — unofficial MCP server + skill

## Problem
Aviator is a merge-queue platform for GitHub monorepos (MergeQueue, stacked PRs, batching, bisection). As of Nov 2026 it had **no connector or plugin in Claude's marketplace and no MCP server**. Its only agent integration is a skill for its stacked-PR CLI. Its competitor Mergify does have a Claude plugin. Developers using Aviator therefore couldn't ask Claude "why isn't my PR merging?" or "which PR broke the batch?".

## Solution
- **MCP server** (Python, official MCP SDK 2.x): 15 tools covering Aviator's REST API v1. 9 read tools (PR status, queue contents and depth, batch/bot PRs, bisection, config + history, analytics, branch/repo pause state) and 6 write tools (queue/dequeue, refresh/sync, pause, backport, config update).
- **Claude skill** `aviator-mergequeue`: troubleshooting workflows, status-code meanings, the config reference, and pitfalls such as parallel-mode resets and skip-line side effects. It uses progressive disclosure: a short SKILL.md plus five reference files.
- Safety by design:
  - write tools are flagged destructive and are never auto-retried;
  - config YAML is validated locally first;
  - errors are rewritten so the model knows what to do next.

## How it was built (pipeline, deterministic first)
1. **Gap check:** live marketplace search plus a GitHub search for existing MCP servers across 13 dev tools. Only 2 had a real gap; Aviator was chosen.
2. **Docs:** found the vendor's MIT-licensed GitBook repo, so no crawling was needed. A tested script cleaned 273 pages → corpus with index, dedup and classification. **0 LLM tokens.**
3. **API surface:** no OpenAPI spec exists, so a tested parser of the REST reference extracted 16 operations with nested params, enums, pagination and response examples. **0 LLM tokens** for extraction.
4. **Server:** test-first; 76 unit tests, **97% coverage**.
5. **Evaluation:** a stateful simulated Aviator API plus 20 realistic tasks, including error and negative cases. Tasks were solved by a separate model instance through the real server code and graded deterministically. The grader was validated with an oracle run (100%) and an empty run (5%).

## Results
| Metric | v0.1 | v0.1 optimized |
|---|---|---|
| Eval tasks passed (blind Sonnet agent, deterministic grading) | 20/20 (100%) | 20/20 (100%) |
| Tool calls per task | 1.0 | 1.0 |
| Tool output per task | ~87 tokens | ~87 tokens |
| Tool list size (tokens shown to the model) | ~2,870 | **~1,980 (−31%)** |
| Skill trigger: recall / false triggers | 10/10 / 0 of 10 (incl. GitHub native queue, Mergify, git bisect) | — |
| Unit tests / coverage | 70 / 97% | 76 / 97% |

## What I'd do with a real account
- Verify `GET /branches` (the docs are ambiguous) and add the GraphQL API via introspection.
- Run the same 20 tasks against a live free-tier workspace.
