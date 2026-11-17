<!-- Source: docs.aviator.co (github.com/aviator-co/gitbook-docs, MIT License, © Aviator Technologies, Inc.). Unmodified except for markup cleanup. -->

# Configuration Reference MergeQueue

MergeQueue communicates with pull request using GitHub labels, GitHub comments and the [Aviator CLI](../../aviator-cli/). To learn about how to apply the rules, read the [intro guide to Merge Rules](../configuration-file.md).

This page will guide you through the entire configuration files and all the possible ways you can customize your MergeQueue experience.

## Merge Rules

### Labels

```yaml
merge_rules:
  labels:
    trigger: "label_name"
    skip_line: "skip_line"
    merge_failed: "blocked"
    skip_delete_branch: "do-not-delete"
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| trigger | String | ( Required ). This label is used to identify that a pull request is ready to be processed by Aviator bot. Once labeled, the bot will verify that the PR has passed all the required conditions and then merge the PR. |
| skip_line | String | When tagged with this label, Aviator bot will move the PR to the front of the queue. |
| merge_failed | String | If the pull request fails to merge, Aviator bot will add this label. |
| skip_delete_branch | String | If delete_branch is enabled, Aviator bot will skip deleting a branch with this label after merging. |

### Preconditions

```yaml
merge_rules:
  labels:
    trigger: "label_name"
  preconditions:
    number_of_approvals: 1
    required_checks:
      # Note: both a string or a more detailed conditional check is accepted
      # for conditional_check, both skipped and success are considered passing
      - check_1
      - name: conditional_check
        acceptable_statuses:
          - skipped
          - success
      - "golang-*"  # matches golang-test, golang-lint, etc.
    use_github_mergeability: true
    conversation_resolution_required: false
    require_verified_commits: false
    validations:
    - name: missing JIRA ticket in PR title
      match:
        type: title
        regex:
        - -\s\[[^\]]*\]
        - ()
    - name: validation_body
      match:
        type: body
        regex:
        - -\s\[[^\]]*\]yam
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| number_of_approvals | Integer | Minimum number of reviewers that should approve the PullRequest before it can qualify to be merged. Defaults to 1. |
| required_checks | List[Union[String, ConditionalCheck]] | Checks that need to pass before Aviator bot will merge the PR. Supports shell wildcard (glob) patterns. Also supports other acceptable CI statuses if your repo uses conditional status checks. See the Example tab. |
| use_github_mergeability | Boolean | Determines whether to use the default required checks specified in branch protection rules on GitHub. When this setting is enabled, Aviator bot will ignore required_checks . Defaults to true . |
| conversation_resolution_required | Boolean | Determines whether Aviator bot will queue the PR only after all conversations are resolved. Defaults to false . |
| require_verified_commits | Boolean | Determines whether Aviator bot will require every commit in the PR to be signed with a GPG key that GitHub has verified. Defaults to false . |
| validations | List[Validation] | Custom validation rules using regexes for the PR body or title. See the Example tab for more details. |

#### acceptable\_statuses

By default a required status check has to be in `success` or `skipped` state for the check to be considered valid. When `acceptable_statuses` are provided for a check, Aviator will modify that behavior. The possible values of the status are:

* `success`
* `pending`
* `failure`
* `cancelled`
* `timed_out`
* `skipped`
* `neutral`
* `action_required`
* `stale`
* `unknown`
* `error`
* `blocked`
* `missing`

Note that `missing` is a special status that represents that the status check has not been reported at all in GitHub by the CI provider.

#### validations

Custom validation rules let you require the PR title or body to match one or more regexes before the PR can be queued. Each entry has a `name` and a `match` object.

| Name | Type | Description |
|---|---|---|
| name | String | A descriptive name for the validation rule. Surfaced in the failure reason when the rule does not match. |
| match.type | String | Which PR field to match against. One of title or body . |
| match.regex | String or List[String] | A single regex or a list of regexes to match against the selected field. |

### Dequeue Conditions

When a queued pull request stops satisfying a precondition, Aviator normally keeps it in the queue and moves it back to `pending`, so it proceeds on its own once the condition is resolved again. Dequeue conditions change that for specific reasons: instead of waiting in the queue, the pull request is taken out of it and has to be queued again.

```yaml
merge_rules:
  labels:
    trigger: "label_name"
  dequeue_conditions:
    not_approved: true
```

| Name | Type | Description |
|---|---|---|
| not_approved | Boolean | Determines whether Aviator removes a pull request from the queue when it no longer satisfies the approval requirements, instead of leaving it queued as pending . The pull request has to be re-queued once it is approved again. Defaults to false . |

A dequeued pull request returns to the open state with the queue and ready labels removed, and Aviator posts a comment naming the reason it was removed.

This applies while the pull request is waiting in the queue. Once it has been tagged for merge — in [parallel mode](../concepts/parallel-mode/README.md), while its draft PR is building — losing approval blocks the PR as usual, so that the in-flight draft PR is reset.

For [stacked PRs](../how-to-guides/merging-stacked-prs.md), the stack is validated as a unit, so the dequeue applies to the whole stack: every other queued member (ancestors and descendants) is removed from the queue as well and gets a comment naming the member that caused it.

### Queue Modes

| Name | Type | Description |
|---|---|---|
| type | String | Determines the mode. Options are: default, parallel, no-queue. |

#### Parallel Mode

The following are only applicable if the above `merge_mode` is set to `parallel`. You can learn more about [Parallel Mode here](../concepts/parallel-mode/).

```
merge_rules:
  labels:
    trigger: "label_name"
  merge_mode:
    type: "parallel" # other modes: "default", "no-queue"
    parallel_mode:
      use_affected_targets: false
      use_fast_forwarding: true
      max_parallel_builds: 10
      max_parallel_paused_builds: 1
      max_requeue_attempts: 3
      update_before_requeue: true
      stuck_pr_label: "label"
      stuck_pr_timeout_mins: 90
      bypass_stuck_state: false
      draft_checks_started_timeout_mins: 0
      block_parallel_builds_label: "block_batch"
      check_mergeability_to_queue: false
      wait_for_pending_github_workflows: false
      override_required_checks:
        - "check 1"
        - check_2
        # Note: both a string or a more detailed conditional check is accepted
        # for conditional_check, both skipped and success are considered passing
        - name: conditional_check
          acceptable_statuses:
            - skipped
            - success
      batch_size: 1
      batch_max_wait_minutes: 0
      require_all_draft_checks_pass: false
      skip_draft_when_up_to_date: false
      use_optimistic_validation: true
      optimistic_validation_failure_depth: 2
      reuse_draft_pr_on_failure: true
      use_proactive_dequeue: false
      proactive_dequeue_delay_seconds: 300
      non_destructive_skip_line: false
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| max_parallel_builds | Integer | The maximum number of builds that Aviator bot will run at any time. Defaults to no limit. |
| max_topup_builds | Integer | The number of extra draft PRs that may be tagged on top of max_parallel_builds once their builds have passed CI but are waiting to merge behind earlier PRs. When 0 (default), max_parallel_builds caps the total number of in-flight draft PRs, whether passed or still running. When set, max_parallel_builds instead caps only the draft PRs actively running CI, and Aviator tops up to keep that many builds running while allowing up to max_parallel_builds + max_topup_builds draft PRs open in total. Requires max_parallel_builds to be set. |
| max_parallel_paused_builds | Integer | Must be less than max_parallel_builds . Defaults to null . The maximum number of PRs in a paused state that Aviator will create draft PRs for. If set to 0, Aviator will not create any draft PRs on paused base branches. If set to null there will be no specific limit for paused PRs. The number of paused draft PRs always counts towards the cap set by max_parallel_builds . |
| max_requeue_attempts | Integer | The maximum number of times Aviator bot will requeue a CI run after failing. Note that PRs will only be requeued if the original PR CI is passing but the draft PR CI fails. Defaults to no requeuing. |
| update_before_requeue | Boolean | Whether to update the PR with the base branch when doing an auto-requeue. This is only applicable if max_requeue_attempts is set. Defaults to false . |
| stuck_pr_label | String | The label that Aviator bot will add if it determines a PR to be stuck. |
| stuck_pr_timeout_mins | Integer | Aviator bot will determine the PR to be stuck after the specified timeout and dequeue it. A stuck state in parallel mode is when the draft PR has passed CI but the original PR's CI is still pending. Defaults to 0, which means that Aviator will dequeue the PR immediately. |
| bypass_stuck_state | Boolean | If enabled, Aviator will try to bypass the stuck state and try to merge the PR in the stuck state itself. Defaults to false |
| draft_checks_started_timeout_mins | Integer | If a draft (bot) PR's required checks never start (are still missing) after this many minutes, Aviator re-checks GitHub in case a webhook was missed and, if the checks are still missing, dequeues the PR. Distinct from ci_timeout_mins , which applies to checks that have started but stayed pending. Defaults to 0 , which disables this timeout. |
| block_parallel_builds_label | String | Once added to a PR, no further Draft PRs will be built on top of it until that PR is merged or dequeued. |
| check_mergeability_to_queue | Boolean | If enabled, Aviator bot will only queue the PR if it passes all mergeability checks. Defaults to false . |
| wait_for_pending_github_workflows | Boolean | Hold a PR out of the queue while GitHub has a workflow run for its latest commit that has not started yet. Until those runs report, GitHub treats the checks they will post as missing and declines the merge, so queueing produces a merge GitHub refuses. Useful where CI is re-triggered by events that do not change the commit, such as labelling. Learn more about pending workflow runs . Defaults to false . |
| use_affected_targets | Boolean | If enabled, allows using affected targets in your repo. |
| use_fast_forwarding | Boolean | If enabled, uses fast forwarding to merge PRs. |
| override_required_checks | List[Union[String, ConditionalCheck]] | Use this attribute if you would like different checks for your original PRs and draft PRs. The checks defined here will be used for the draft PRs created in Parallel mode. Supports shell wildcard (glob) patterns. Also supports other acceptable CI statuses if your repo uses conditional status checks. See the Example tab. |
| batch_size | Integer | The number of queued PRs batched together for a draft PR CI run. Defaults to 1. |
| batch_max_wait_minutes | Integer | The time to wait before creating the next batch of PRs if there are not enough queued PRs to create a full batch. Defaults to 0. |
| require_all_draft_checks_pass | Boolean | Determines if Aviator will enforce all checks to pass for the constructed draft PRs. If true, any single failing test will cause the draft PR to fail. These checks include the ones we receive status updates for via GitHub. This may work well if your repo has conditional checks. Requires at least one check to be present. Defaults to false . |
| skip_draft_when_up_to_date | Boolean | Skips creation of the staging draft PR to validate the CI if the original PR is already up to date and no other PR is currently queued. This is usually a good optimization to avoid running extra CI cycles. Defaults to true . |
| use_optimistic_validation | Boolean | If the CI of the top staging draft PR is still running or has failed, and any subsequent draft PR passes, then optimistically use that success result to validate the top PR as passing. Defaults to false . |
| optimistic_validation_failure_depth | Integer | Requires use_optimistic_validation to be true . If the CI of the top staging draft PR has failed, wait for subsequent draft PR CIs to also fail before dequeuing the PR. The number represents how many draft PRs do we wait to fail before dequeuing a PR. For e.g., if set to 1, it will dequeue immediately after the top staging draft PR fails, but if set to 2, it will wait for one more subsequent draft PR to fail before dequeuing the top PR. Only the next max(3, optimistic_validation_failure_depth) draft PRs count, and the wait ends once none of them is still running. Value should always be 1 or larger. Defaults to 1 . |
| reuse_draft_pr_on_failure | Boolean | Controls draft PR behavior after CI failures in parallel mode. When true (default), force-pushes changes to the same bot PR/branch to resync and retry. When false , closes the previous bot PR and creates a new one with a new branch. This allows starting fresh with a clean CI state after failures. |
| use_proactive_dequeue | Boolean | If enabled, Aviator will proactively dequeue PRs from the middle of the queue when CI results indicate the batch introduced a failure. This is determined by checking if all dependent draft PRs have no failing CI while the current draft PR has at least one failing required check. Learn more about proactive dequeue . Defaults to false . |
| proactive_dequeue_delay_seconds | Integer | Number of seconds to wait after a draft PR CI failure is detected before proactively dequeuing. This delay helps avoid false positives from transient or flaky test failures. Only applicable when use_proactive_dequeue is true . Defaults to 0 (no delay). |
| non_destructive_skip_line | Boolean | If enabled, skip_line PRs no longer reset the queue. Draft PRs that are already running finish CI and merge as normal, and skip_line PRs are picked ahead of all other queued PRs for the next draft PR. skip_line PRs also respect max_parallel_builds and wait for capacity instead of exceeding it. Learn more about priority without resetting the queue . Defaults to false . |

#### Parallel Bisection

When a batch of draft PRs fails CI in parallel mode, bisection narrows down which PR introduced the failure by splitting the batch and re-running the pieces. These settings, also nested under `parallel_mode`, control that behavior. They only apply when `merge_mode.type` is set to `parallel`.

```yaml
merge_rules:
  labels:
    trigger: "label_name"
  merge_mode:
    type: "parallel"
    parallel_mode:
      use_parallel_bisection: true
      max_parallel_bisected_builds: 5
      max_bisection_attempts: 3
      max_bisected_batch_size: 4
      block_batch_on_checks:
        - "integration/*"
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| use_parallel_bisection | Boolean | If enabled, bisected batches are run in parallel to identify the culprit PR and requeue all the clean PRs. Defaults to null (disabled). |
| max_parallel_bisected_builds | Integer | A separate quota for bisected builds. When set, bisected builds run in parallel and do not consume the quota for regular builds ( max_parallel_builds ). Defaults to null . |
| max_bisection_attempts | Integer | If set, a PR is marked as failed after being bisected this many times. Otherwise, the PR is only marked as failed once it runs alone in a bisected batch of size 1. Defaults to null . |
| max_bisected_batch_size | Integer | The maximum number of PRs in a bisected batch. If not set, each batch is split into two. Defaults to null . |
| block_batch_on_checks | List[String] | Required checks whose failure blocks every PR in the batch instead of bisecting it. Use this for checks whose failures can't be pinned on a single PR, where bisecting only re-runs the same failure. Applies to batches of two or more PRs; failures on other checks still bisect. When use_proactive_dequeue is enabled, a listed check that is also in flaky_retry.retriable_checks does not block a batch dequeued from the middle of the queue. Supports shell wildcard (glob) patterns. Defaults to null . |

### Auto Update

```
merge_rules:
  labels:
    trigger: "label_name"
  auto_update:
    enabled: true
    label: "auto_update"
    max_runs_for_update: 10
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| enabled | Boolean | If enabled, Aviator bot will keep your branches up to date with the main branch. Defaults to false . |
| label | String | Aviator bot will only keep branches with this label up to date with the main branch. Leave empty to auto merge without a label. If no label is provided and auto_update is enabled, by default the Aviator bot will update all PRs. |
| max_runs_for_update | Integer | The maximum number of times Aviator bot will update your branch. Defaults to no limit. |

### Merge Commit

```
merge_rules:
  labels:
    trigger: "label_name"
  merge_commit:
    use_title_and_body: true
    cut_body_before: "----"
    cut_body_after: "+++"
    strip_html_comments: false
    include_coauthors: true
    apply_title_regexes:
      - pattern: "AVTR-"
        replace: "AVTR_"
        applies_to: "both"
      - pattern: "MQ-BOT"
        replace: "MQ BOT"
        applies_to: "merge_commit"
      - pattern: '^\[(WIP|Draft)\]\s*'
        replace: ""
        match_type: "regex"
      - pattern: '(\w+)-(\d+)'
        replace: '[\1-\2]'
        match_type: "regex"
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| use_title_and_body | Boolean | Determines whether Aviator bot will replace default commit messages offered by GitHub. Defaults to true . |
| cut_body_before | String | A marker string to cut the PR body description. The commit message will contain the PR body after this marker. Leave empty for no cropping. |
| cut_body_after | String | A marker string to cut the PR body description. The commit message will contain the PR body before this marker. Leave empty for no cropping. |
| strip_html_comments | Boolean | Strip out the hidden HTML comments from the commit message when merging the PR. Defaults to false . |
| include_coauthors | Boolean | Include coauthors (if any) in the commit message when merging the PR. Defaults to false . |
| apply_title_regexes | List[ReplacePattern] | Contains the strings pattern and replace to indicate what pattern to replace in the PR title, plus an optional applies_to that controls where the regex is applied. applies_to accepts both (default), draft_pr (only the bot/draft PR title in parallel mode), or merge_commit (only the merge commit title). Configs without applies_to behave as both . An optional match_type controls how pattern is matched: string (default) replaces literal occurrences of pattern , while regex treats pattern as a regular expression and replace as a substitution template that can reference capture groups (e.g. \1 ). Quote regex patterns with single quotes in YAML so backslashes are preserved. Invalid regex rules are rejected when the configuration is saved. See the configuration example above for more details. |

### Merge Strategy

| Name                                          | Type    | Description                                                                                                                                                                                                                                                                          |
| --------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **name**                                      | String  | Defines the merge strategy to use, the options are "squash", "merge", and "rebase". See the [GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github) for more info.   |
| **use\_separate\_commits\_for\_stack**        | Boolean | If enabled, uses independent commits for stacked PRs. This requires setting upRulesets in GitHub and allow Aviator to bypass branch protection rules. Otherwise GitHub blocks commits from merging without approval and CI completion. Defaults to `false`. |
| **update\_pr\_commits\_before\_stack\_merge** | Boolean | If enabled, force updates the commits in the branch of each stacked PR right before merging the PR, so that the PR can be marked as merged instead of closed. This requires `use_separate_commits_for_stack` config to be enabled. Defaults to `false`.                              |

#### Override Labels

You can specify overrides to the above merge strategy using GitHub Labels. When a PR is flagged with these labels along with the trigger label, Aviator bot will merge the PR using this strategy instead of the default strategy. Leave empty for no overrides.

```
merge_rules:
  labels:
    trigger: "label_name"
  merge_strategy:
    name: "squash"
    override_labels:
      squash: "mq-squash"
      merge: "mq-merge-commit"
      rebase: "mq-rebase"
    use_separate_commits_for_stack: true
    update_pr_commits_before_stack_merge: true
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| squash | String | If marked with this label, the PR will be squashed and merged. |
| merge | String | If marked with this label, the PR will be merged using a merge commit. |
| rebase | String | If marked with this label, the PR will be rebased and merged. |

### Status Comment

Aviator posts a status comment on every open pull request by default. Aviator automatically updates the status comment whenever the pull request is updated.

Custom messages can be specified (`open_message`, `queued_message`, and `blocked_message`) to add information specific to your organization or repository (such as common troubleshooting steps).

```yaml
merge_rules:
  # Configuration for the Aviator status comment.
  # Optional (defaults to publish: "always" with no custom messages).
  status_comment:
    # When to publish the Aviator status comment.
    # Optional. Valid values are "always", "ready", "queued", or "never".
    # Default value is "always".
    #   - "always": Post the status comment whenever the pull request is opened.
    #   - "ready": Publish the status comment when the pull request is ready for review.
    #   - "queued": Post the status comment when the pull request is queued.
    #   - "never": Disable the status comment.
    publish: "always"

    # A message to include in the status comment if the pull request is in the
    # open state. Supports markdown.
    # Optional.
    open_message: "..."

    # A message to include in the status comment if the pull request is in the
    # queued state. Supports markdown.
    # Optional.
    queued_message: "..."

    # A message to include in the Aviator status comment when the
    # pull request is blocked. The same message is also posted in the GitHub
    # comment associated with the failed reason. Supports markdown.
    # Optional.
    blocked_message: "..."
```

**Attributes**
| Name                 | Type   | Description                                                                                              |
| -------------------- | ------ | -------------------------------------------------------------------------------------------------------- |
| **publish**          | String | One of `always`, `ready`, `queued`, or `never`. Defaults to `always`.                                    |
| **open\_message**    | String | An optional message to include in the Aviator status comment when the pull request is open (not queued). |
| **queued\_message**  | String | An optional message to include in the Aviator status comment when the pull request is queued.            |
| **blocked\_message** | String | An optional message to include in the Aviator status comment when the pull request is blocked.           |

Pull requests that are part of a stack always get a status comment when they are opened, since the comment carries the stack information. `publish` does not apply to them.

### Blocked queue sources

There are multiple sources that can trigger a queue action for a pull request. These properties let you block specific sources from enqueuing a PR.

```yaml
merge_rules:
  blocked_queue_sources:
    - label
    - slash_command
    - graphql_api
    - rest_api
    - chrome_extension
    - pilot
```

| Name | Description |
|---|---|
| label | Disables all the trigger label, including skip_line |
| slash_command | Disables enqueuing using /aviator merge |
| graphql_api | Disables enqueuing using GraphQL . Also disables enqueuing from the web app |
| rest_api | Disables enqueuing using the REST API |
| chrome_extension | Disables enqueuing from Chrome extension |
| pilot | Disables enqueuing using Pilot actions |

### Skip blocked label

By default, when a pull request fails to merge, Aviator applies the `blocked` label (configured via `labels.merge_failed`) to the PR. To re-queue the PR, the author must remove the `blocked` label and then re-trigger the queue. Enable `skip_blocked_label` if you prefer to keep the PR in the open state on a merge failure and skip the `blocked` label workflow entirely.

```yaml
merge_rules:
  skip_blocked_label: true
```

| Name | Type | Description |
|---|---|---|
| skip_blocked_label | Boolean | When enabled, Aviator will not add the blocked label to a PR when it fails to merge. The PR is left in the open state (with queue and ready labels removed) and the author is instructed to re-queue the PR to retry. Aviator will still post a GitHub comment describing the reason for the failure, and the PR's status is still recorded as blocked in the Aviator audit trail. Defaults to false . |

### Final gates

Final gates run a GitHub Actions workflow as the last step before a PR is merged, once it reaches the top of the queue and all required checks have passed. See [Final Gates](../concepts/final-gates.md) for the full behavior. Requires [parallel mode](../concepts/parallel-mode/README.md).

```yaml
merge_rules:
  final_gates:
    - workflow: run-migration.yml
      timeout_mins: 10
      label: has-migration
```

| Name | Type | Description |
|---|---|---|
| workflow | String | Required. Filename of the workflow under .github/workflows/ . Either run-migration.yml or .github/workflows/run-migration.yml is accepted; nested paths are not. The workflow must declare workflow_dispatch as a trigger. |
| timeout_mins | Integer | Required. How long to wait for the workflow run before treating the gate as failed. Valid range: 1 to 60 . |
| label | String | Optional. Only run this gate when a PR being merged carries this GitHub label. With batching, the gate applies if any PR in the batch carries the label. Matched case-insensitively. When omitted, the gate runs for every merge. |

Multiple gates run sequentially in the order listed.

### Flaky retry

Investigate a failing check on a draft PR before resetting the queue, and rerun the check when the failure looks transient. See [Flaky test management](../concepts/flaky-test-management.md) for the behavior and [How to configure flaky test management](../how-to-guides/configure-flaky-test-management.md) for the rollout. Beta, off by default, and requires [parallel mode](../concepts/parallel-mode/README.md).

```yaml
merge_rules:
  flaky_retry:
    enabled: true
    shadow_mode: false
    context: |
      All CI runs on self-hosted runners that are occasionally evicted
      mid-build. Runner disconnects are always infrastructure.
    retriable_checks:
      - name: "e2e-*"
        context_file: ".aviator/mergequeue/flake/e2e.md"
      - name: "integration-tests"
```

| Name | Type | Description |
|---|---|---|
| enabled | Boolean | When enabled, Aviator investigates a draft PR CI failure before resetting the queue. A failure classified as unrelated to the change lets the queue spend more look-ahead instead of dequeuing the PR, and the failed check is rerun. Defaults to false . |
| shadow_mode | Boolean | Investigate and record verdicts without acting on them, so they can be reviewed before they are trusted. No failure is exonerated and no check is rerun, so PRs are dequeued exactly as they are with the feature off. Aviator still comments on the draft PR when a verdict would have changed a queue decision. Note that failure handling is still held while a verdict is reached — up to two minutes — so a batch is dequeued slightly later than with the feature off entirely. Defaults to false . |
| retriable_checks | List[String or Object] | The checks eligible for investigation. A failure of a check not listed here always follows the existing dequeue behavior. Glob patterns are supported. Each entry is either the check name as a bare string, or an object with name plus its own context or context_file . Defaults to an empty list, which investigates nothing. |
| context | String | Free-form prose about how CI in this repository typically flakes, used when classifying a failure. Applies to every retriable check, in addition to any per-check context rather than as a fallback for it. Mutually exclusive with context_file . |
| context_file | String | Path to a Markdown file in the repository holding that prose instead. Must be under .aviator/mergequeue/flake/ and end in .md . Synced from your default branch. Mutually exclusive with context . |

Each entry in `retriable_checks` accepts:

| Name | Type | Description |
|---|---|---|
| name | String | Required. The check name as it appears on the pull request. Glob patterns are supported (for example e2e-* ). For GitHub Actions this is the job name; for Buildkite it is typically buildkite/<pipeline>/<step-key> . |
| context | String | Free-form prose about how this specific check typically flakes, and which of its failure modes are always genuine. Mutually exclusive with context_file . |
| context_file | String | Path to a Markdown file holding that prose, under .aviator/mergequeue/flake/ . Mutually exclusive with context . |

### Other

```
merge_rules:
  labels:
    trigger: "label_name"
  update_latest: true
  delete_branch: false
  use_rebase: false
  publish_status_check: "ready"
  enable_comments: true
  ci_timeout_mins: 60
  base_branches:
    - master
    - /release-*/
  command_restrictions:
    - commands:
        - skip_line
        - skip_validation
      allowed_actors:
        - "@username"
        - "@org/team-name"
```

**Attributes**

| Name | Type | Description |
|---|---|---|
| update_latest | Boolean | Determines whether Aviator bot will merge the latest base branch into the current branch of your PR before verifying the CI statuses. This is only compatible with the default and no-queue merge modes. Defaults to true . |
| delete_branch | Boolean | Determines whether Aviator bot will delete the branch after merging. Defaults to false . |
| use_rebase | Boolean | Determines if Aviator bot will use rebase to update PRs. This feature is only available in the Pro plan. Please note that you also need to enable update_latest for rebase to work. Defaults to false . |
| publish_status_check | Boolean or String | Determines if Aviator bot will publish a status check back on the PR. This status check represents the current state of PR in the Aviator queue. Possible values: always : Post the status check whenever the pull request is opened. ready : Publish the status check when the pull request is ready for review. queued : Post the status check when the pull request is queued. never : Disable the status check. For backward compatibility this value also supports boolean. true same as ready false same as never Defaults to ready |
| enable_comments | Boolean | Determines if Aviator bot can add comments on the PR to describe the actions performed on the PR by the bot. Aviator bot comments include information such as failure reasons and the position of the PR in the queue. Defaults to true . |
| ci_timeout_mins | Integer | The time before we determine that the CI has timed out. Defaults to 0 that is equivalent to no time out. |
| base_branches | List[String] | These branches are the ones that Aviator will monitor as valid branches to merge into. Defaults to your repository default branch as configured on GitHub. Regexes are allowed. |
| require_all_checks_pass | Boolean | Determines if Aviator will enforce all checks to pass. If true, any single failing test will cause the PR to fail. These checks include the ones we receive status updates for via GitHub. This may work well if your repo has conditional checks. Requires at least one check to be present. Defaults to false . |
| require_skip_line_reason | Boolean | If enabled, a reason is required when marking a PR as skip line. Defaults to false. Provide a reason via Aviator slash command as a GitHub comment: /aviator merge --skip-line=<insert reason for skipping> |
| command_restrictions | List[Object] | Per-command allowlists controlling which GitHub users or teams may run privileged queue commands. Each entry has commands (one or more of skip_line , skip_validation , and dequeue ) and allowed_actors (a list of @username or @org/team-name entries). A command with no matching restriction is unrestricted. Enforced across slash commands and the REST and GraphQL APIs. |
| auto_detect_stacks | Boolean | If enabled, Aviator will automatically detect stacked PRs, this could be useful if you are using a thirdparty tool to stack PRs. This is not needed when using Aviator CLI. Defaults to false . Apply the built-in av-ignore-stack label to a PR to exclude it from automatic stack detection. |
