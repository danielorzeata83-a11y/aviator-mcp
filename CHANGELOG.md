# Changelog

## 0.1.2 — 2026-11-16
All 14 tools verified end-to-end against a live Aviator account (queue → merge, parallel batch, backport, skip-line, sync, config update, branch pause). Fixes for live-API behaviour that differs from the docs:
- `queue_pr` always sends `affected_targets` (the API requires it).
- `merge_commit_message` always sends both `title` and `body`; a body without a title is rejected locally.
- Analytics times are reported in **minutes** (fields renamed `*_minutes`).
- Error responses with a `null` message no longer show "Aviator said: None".

## 0.1.1 — 2026-11-16
- Tested against a live Aviator account. Removed `get_branch_status`: Aviator's API cannot read branch pause status (GET rejected; POST requires `paused`). 14 tools.
- New `AVIATOR_DEMO=1` mode: simulated data, no token, no network.

## 0.1.0 — 2026-11-14
- First version: 15 tools (9 read, 6 write) over Aviator's REST API v1.
- Actionable error mapping, a single retry for GET requests, no automatic retry for writes, page-based pagination, output capping.
- Unit tests (respx) and a 20-task evaluation harness on a simulated Aviator world.
