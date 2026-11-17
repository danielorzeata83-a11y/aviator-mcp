# Aviator MergeQueue — core concepts

Condensed from docs.aviator.co (MIT). Details: https://docs.aviator.co/mergequeue/concepts

## PR lifecycle
| State | Meaning | Usual next step |
|---|---|---|
| open | Not marked ready-to-merge | Add the trigger label, `/aviator merge`, or `queue_pr` |
| pending | Marked ready; a pre-queue condition isn't met yet (checks running, approvals, conflicts) | Usually resolves by itself; the sticky comment on the PR says why |
| queued | Passed pre-conditions; being validated against the latest base branch | Wait; check position and CI |
| blocked | Needs author action: merge conflict, failed required check, approvals removed, head commit changed | Fix, then re-queue (see status codes) |
| merged | Merged by Aviator or manually (with fast-forwarding, "merged" may not show as a GitHub merge) | n/a |
| closed | Closed without merging | n/a |

## Queue modes (`merge_rules.merge_mode.type`)
- **default (sequential):** the PR at the top is updated with the base branch, CI runs, and it merges if green. Throughput is one PR per CI run (30-min CI → max ~48/day).
- **parallel** (Pro plan; needs GitHub draft PRs, so Team/Enterprise): each queued PR gets a **draft "bot" PR** containing the base branch, every PR ahead of it, and itself. When the bot PR's CI passes, the original merges. If a bot PR fails, the failing PR is removed and all later bot PRs are rebuilt (a **queue reset**). Key setting: `parallel_mode.max_parallel_builds`. Stuck CI is handled with a "stuck" label and a timeout; a later green bot PR also merges the earlier ones (eventual consistency).
- **no_queue:** merge rules and checks only; no in-flight PRs are included, so main can still break.

## Batching (parallel mode)
`batch_size` is the number of PRs per bot PR (default 1). `batch_max_wait_minutes` is how long to wait to fill a batch. 10 queued PRs need 10 extra CI runs at size 1, 4 at size 3, 2 at size 5.

**Bisection:** if a batch fails, its PRs are re-queued split into two smaller batches until the culprit is isolated and blocked. Skip-line PRs are never batched.

## Priority (skip-line)
Use the label `mergequeue-priority` (configurable as `labels.skip_line`), or `queue_pr(skip_line=true)`. The PR jumps to the front; multiple skip-line PRs queue among themselves. In parallel mode this **closes and rebuilds all draft PRs**, unless `parallel_mode.non_destructive_skip_line: true` is set (running drafts finish first and `max_parallel_builds` is respected). Removing the label: in sequential mode the PR returns to its original position; in other modes nothing changes.

## Resets (status codes 300–310)
Causes: manual reset, CI failure, a skip-line PR, a dequeue, a closed PR or draft PR, a fast-forward failure, a config change, a timeout, a PR no longer ready, a new commit pushed to a queued PR. Each reset re-runs CI for everything behind it, so expect CI cost and delay.

## Paused queues
Pause per repo or per base branch (glob), e.g. freeze `release-*` while `main` keeps merging. PRs are still processed (and draft PRs created) up to the merge step, but nothing merges. Instant merges stop too. Deactivating a repo stops almost everything (ChangeSets excepted).

## Affected targets
Monorepos can declare which targets a PR touches (directory-based, Nx, GitHub Actions, or `affected_targets` via the API). PRs then only queue behind PRs sharing a target, giving parallel lanes. A skip-line PR only de-prioritizes PRs with the same targets.

## ChangeSets
Group dependent PRs, even across repos, so they validate and merge together.

## Stacked PRs
The open-source `av` CLI manages stacks. Queuing the top PR of a stack (`av pr queue` or `/aviator stack merge`) validates and merges the whole stack as one unit.

## Backport
`/aviator backport <branch>` or `backport_pr` opens a new PR cherry-picking a merged PR onto another branch. Progress is reported as PR comments.
