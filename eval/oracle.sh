#!/usr/bin/env bash
# Validates the grader: the ideal tool calls + ideal answers must score 100%.
set -e
cd "$(dirname "$0")/.."
rm -rf eval/out
C="python3 eval/call.py --task"
$C 1 list_repositories '{}' >/dev/null
$C 2 get_queue_stats '{"repo":"acme/api"}' >/dev/null
$C 3 list_queued_prs '{"repo":"acme/api","base_branch":"main","limit":3}' >/dev/null
$C 4 get_pr_status '{"repo":"acme/api","number":1240}' >/dev/null
$C 5 queue_pr '{"repo":"acme/api","number":1250}' >/dev/null
$C 6 queue_pr '{"repo":"acme/api","number":1251,"skip_line":true,"skip_line_reason":"prod outage"}' >/dev/null
$C 7 dequeue_pr '{"repo":"acme/api","number":1234}' >/dev/null
$C 8 refresh_or_sync_pr '{"repo":"acme/api","number":1235,"action":"sync"}' >/dev/null
$C 9 get_bot_pr '{"repo":"acme/api","number":5001}' >/dev/null
$C 10 set_queue_paused '{"repo":"acme/api","paused":true,"branch_pattern":"release-*"}' >/dev/null
$C 11 set_queue_paused '{"repo":"acme/web","paused":false}' >/dev/null
$C 12 backport_pr '{"repo":"acme/api","number":1300,"target_branch":"release-2.14"}' >/dev/null
$C 13 get_config '{"repo":"acme/api"}' >/dev/null
$C 14 get_config '{"repo":"acme/api","include_history":true}' >/dev/null
$C 15 get_config '{"repo":"acme/api"}' >/dev/null
$C 15 update_config "{\"repo\":\"acme/api\",\"yaml_config\":\"merge_rules:\\n  labels:\\n    trigger: mergequeue\\n    skip_line: mergequeue-priority\\n  merge_mode:\\n    type: parallel\\n    parallel_mode:\\n      max_parallel_builds: 5\\n  require_all_checks_pass: true\\n\"}" >/dev/null
$C 16 get_analytics '{"repo":"acme/api","start":"2026-11-07","end":"2026-11-13"}' >/dev/null
$C 17 list_repositories '{}' >/dev/null
$C 18 queue_pr '{"repo":"acme/api","number":9999}' >/dev/null
$C 19 queue_pr '{"repo":"acme/api","number":1250}' >/dev/null
cat > eval/out/answers.json <<'J'
{"1":"acme/api is not paused.","2":"6 queued (3 processing, 3 waiting).","3":"#1234, #1235, #1236",
 "4":"#1240 is blocked: merge conflict with main.","5":"Queued.","6":"Queued with skip-line.","7":"Dequeued.","8":"Synced.",
 "9":"#1242 broke it (FAILED_TESTS).","10":"Paused release-*.","11":"Unpaused.","12":"Backport started.",
 "13":"Trigger label is mergequeue.","14":"jdoe changed trigger to mergequeue.","15":"Done.",
 "16":"Avg 30 min in queue; 63 PRs merged.","17":"12 repos; only web is paused.","18":"PR #9999 not found.",
 "19":"The Aviator API token is not configured.","20":"Feed it and refrigerate."}
J
python3 eval/grade.py
