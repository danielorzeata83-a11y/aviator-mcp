# Aviator REST API — reference

Base URL `https://api.aviator.co` · auth header `Authorization: Bearer <token>` · JSON bodies unless noted.
Generated from docs.aviator.co (MIT). `*` = required.

## Repository

### `POST /api/v1/repo`
Pause / unpause the merging of PRs on a repository

| name | in | type | req | description |
|---|---|---|---|---|
| org | body | String | * | Name of the GitHub organization. |
| name | body | String | * | Name of the repository in the GitHub organization. |
| paused | body | Boolean | * | Whether to pause or unpause the queue |

**200** OK Success
```
{
  "org": "ankitjaindce",
  "name": "testrepo",
  "paused": false
}
```

### `GET /api/v1/repo`
Fetch the list of repositories along with their pause and active status · paginated (10/page)

| name | in | type | req | description |
|---|---|---|---|---|
| page | query | Integer |  | page number. Defaults to 1. |

**200** OK
```
[
    {
        "active": false,
        "name": "public-test",
        "org": "aviator-co",
        "paused": false
    },
    {
        "active": true,
        "name": "testrepo",
        "org": "aviator-co",
        "paused": false
    }
]
```

## Branches

### `POST /api/v1/branches`
Pause / unpause the merging of PRs for specific base branches

| name | in | type | req | description |
|---|---|---|---|---|
| repository | body | Object | * | Repository object associated with the branch |
| repository.org | body | String | * | Organization associated with the repository |
| repository.name | body | String | * | Name of the repository |
| pattern | body | String | * | Glob pattern representing the base branch. E.g. `master` or `release-*` |
| paused | body | Boolean | * | Whether to pause or unpause the queue |
| paused_message | body | String |  | A customized message to post on the top PR when this branch is paused. |

**200** OK
```
{
    "pattern": "release-*",
    "repository": {
      "org": "aviator",
      "name": "av-demo-release"
    },
    "paused": true
}
```

### `GET /api/v1/branches`
Get base branches and their statuses (paused / unpaused)

| name | in | type | req | description |
|---|---|---|---|---|
| repository | query | Object | * | Repository object associated with the branch |
| repository.org | query | String | * | Organization associated with the repository |
| repository.name | query | String | * | Name of the repository |
| pattern | query | String |  | Glob pattern representing the base branch. E.g. `master` or `release-*` |

**200** OK Success
```
{
    "branches": [
        {
            "pattern": "release-*",
            "paused": true
            "paused_message": "This branch is currently paused for the release"
        }
    ],
    "repository": {
        "name": "av-demo-release"
        "org": "aviator"
    }
}
```

## PullRequest

### `POST /api/v1/pull_request`
Queue, Dequeue, Refresh, or Sync a Pull Request

| name | in | type | req | description |
|---|---|---|---|---|
| action | body | String | * | Action taken. Valid options: `queue`, `update`, `dequeue`, `refresh`, or `sync` |
| pull_request | body | Object | * | PullRequest object representing the PR that is queued. |
| pull_request.number | body | String | * |  |
| pull_request.repository | body | Object | * | Repository object associated with the PR |
| pull_request.repository.name | body | String | * | Name of the repository |
| pull_request.repository.org | body | String | * | Organization associated with the repository |
| pull_request.head_commit_sha | body | String |  | Representing the commit SHA of the head of the PR. |
| pull_request.affected_targets | body | List[String] |  | Affected targets for the PR. Please see [affected targets](../../mergequeue/concepts/affected-targets/#overview) section for more details |
| pull_request.merge_commit_message | body | Object |  | CommitMessage object |
| pull_request.merge_commit_message.title | body | String |  | Title of merge commit message |
| pull_request.merge_commit_message.body | body | String |  | Body of merge commit message |
| pull_request.skip_line | body | Boolean |  | _Optional_. When `true`, the PR skips to the front of the queue. Only valid with the `queue` action. Requires skip-line authorization. |
| pull_request.skip_line_reason | body | String |  | _Optional_. Reason for skipping the line. Required if the repository has `require_skip_line_reason` enabled. |
| pull_request.skip_validation | body | Boolean |  | _Optional_. When `true`, skips CI validation for the PR. Only valid with the `queue` action. Independent of `skip_line`; requires skip-validation authorization. |
| pull_request.requested_by | body | String |  | _Optional_. GitHub username (e.g. `@octocat`) on whose behalf `skip_line` / `skip_validation` is requested. When set, both the API token's user and this user must be authorized to run the command. |
| pull_request.merge_commit_sha | body | String |  | _Optional_. Represents the SHA associated with the commit on the mainline generated after the PR was merged. |

**200** OK (queue/update/dequeue)
```
{
  "pull_request": {
    "number": 1234,
    "status": "queued",
    "queued": true,
    "title": "[TASK-123] This is a new bug",
    "author": "av_user",
    "head_branch": "av/new_fix",
    "base_branch": "main",
    "repository": {
      "name": "av-demo",
      "org": "aviator-co"
    }
  }
}
```

**202** Accepted (refresh/sync)
```

```

### `POST /api/v1/pull_request/backport`
Request to backport a PR on the specified target branch

| name | in | type | req | description |
|---|---|---|---|---|
| target_branch | body | String | * | Name of the base branch to backport this PR to |
| source_pull | body | Object | * | PullRequest object for the current branch |
| source_pull.number | body | Integer | * | PullRequest number |
| source_pull.repository | body | Object | * | GitHub repository associated with the PullRequest |
| source_pull.repository.org | body | String | * | Organization associated with the repository |
| source_pull.repository.name | body | String |  | Name of the repository |

**200** OK
```
{
    "source_pull": {
      "number": 1234,
      "repository": {
        "org": "aviator",
        "name": "av-demo-release"
      }
    },
    "target_branch": "release-v1",
    "message": "Backporting initiated for 1234 to release-v1. Check comments in the PR #1234 for the status"
}
```

### `GET /api/v1/pull_request`
Fetch information of a PR based on the branch name or number

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | Organization associated with the repository |
| repo | query | String | * | Name of the repository |
| branch | query | String | * | Feature branch associated with PR. One of `branch` or `number` must be present. |
| number | query | Integer | * | PR number to fetch. One of `branch` or `number` must be present. |

**200** OK Success
```
{
    "author": "author-name",
    "base_branch": "master",
    "head_branch": "mq-qa-8440-1",
    "number": 89,
    "queued": true,
    "queued_at": "2022-11-16T17:21:41.350499",
    "merged_at": null,
    "created_at": "2022-11-16T17:20:00.000000",
    "repository": {
        "name": "repo-name",
        "org": "org-name"
    },
    "skip_line": false,
    "status": "queued",
    "title": "mq-qa-8440-1",
    "bot_pull_request": {
        "number": 201,
        "github_url": "https://github.com/org-name/repo-name/pull/201",
        "target_branch": "master",
        "head_commit_sha": "acffa5
…
```

### `GET /api/v1/pull_request/queued`
Fetch information of PRs that are in the queued state

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | Organization associated with the repository |
| repo | query | String | * | Name of the repository |
| base_branch | query | String |  | Target branch to fetch queued PRs for |

**200** OK Success
```
{
    "pull_requests": [
        {
            "author": "ohcnivek",
            "base_branch": "master",
            "head_branch": "mq-qa-8440-1",
            "number": 89,
            "queued": true,
            "queued_at": "2022-11-16T17:21:41.350499",
            "merged_at": null,
            "created_at": "2022-11-16T17:20:00.000000",
            "repository": {
                "name": "kevin-test",
                "org": "ohcnivek"
            },
            "skip_line": false,
            "status": "queued",
            "title": "mq-qa-8440-1"
        },
        {
            "author
…
```

### `GET /api/v1/pull_request/bisection`
Fetch the bisection status of a PR

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | Organization associated with the repository |
| repo | query | String | * | Name of the repository |
| number | query | Integer | * | PR number |

**200** OK Bisecting
```
{
    "pull_request": {
        "number": 1234,
        "stack_top_number": null
    },
    "is_bisecting": true,
    "bisection": {
        "round": 1,
        "current_bot_pull_request": null,
        "last_failed_bot_pull_request": {
            "number": 5678,
            "github_url": "https://github.com/org-name/repo-name/pull/5678",
            "target_branch": "master",
            "head_commit_sha": "acffa575c02f2cf000aabe69f44e8905bc04c25d",
            "head_branch_oid": "acffa575c02f2cf000aabe69f44e8905bc04c25d",
            "codemix_pre_batch_sha": null,
            "failure_reaso
…
```

**200** OK Not bisecting
```
{
    "pull_request": {
        "number": 1234,
        "stack_top_number": null
    },
    "is_bisecting": false,
    "bisection": null
}
```

## BotPullRequest

### `GET /api/v1/bot_pull_request`
Fetch information of PRs associated with a provided Bot PullRequest

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | Organization associated with the repository |
| repo | query | String | * | Name of the repository |
| number | query | Integer | * | PR number associated with the Bot PR |

**200** OK Success
```
{
  "number": 201,
  "github_url": "https://github.com/org-name/repo-name/pull/201",
  "target_branch": "master",
  "head_commit_sha": "acffa575c02f2cf000aabe69f44e8905bc04c25d",
  "head_branch_oid": "acffa575c02f2cf000aabe69f44e8905bc04c25d",
  "codemix_pre_batch_sha": "08d30e0141d9f9253a228dac05173c4f383e1444",
  "pull_requests": [
    {
      "author": "author-name",
      "base_branch": "master",
      "head_branch": "mq-qa-8440-1",
      "number": 89,
      "queued": true,
      "queued_at": "2022-11-16T17:21:41.350499",
      "merged_at": null,
      "created_at": "2022-11-16T17:20:00.00
…
```

## Config

### `GET /api/v1/config`
Fetch the current YAML config associated with the given GitHub repository

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | Organization associated with the GitHub repository. |
| repo | query | String | * | Name of the GitHub repository. |

**200** OK
```
merge_rules:
   labels:
     trigger: "mergequeue"
   merge_mode:
    type: "parallel"
    parallel_mode:
      max_parallel_builds: 10
      override_required_checks:
        - build_and_test
        - 'ci/circleci: build'
```

### `POST /api/v1/config`
Change the YAML config associated with the given GitHub repository

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | Organization associated with a GitHub repository |
| repo | query | String | * | Name of the GitHub repository. |

**200** OK
```
{
  "success": true
}
```

**400** Bad Request
```
{
    "errors": [
        "mergeRules -> mergeMode -> parallelMode -> updateBeforeRequeue: value could not be parsed to a boolean",
        "mergeRules -> mergeMode -> parallelMode -> checkMergeabilityToQueue: value could not be parsed to a boolean"
    ],
    "success": false
}
```

## Config Change

### `GET /api/v1/config/history`
Fetch the history of config changes associated with a given repository · paginated (?/page)

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | Organization associated with the repository |
| repo | query | String | * | Name of the repository |
| start | query | String |  | UTC Start date in _YYYY-MM-DD_ format. Example: 2021-07-21 |
| end | query | String |  | UTC End date in _YYYY-MM-DD_ format. Example: 2021-07-21 |
| page | query | Integer |  | Page number. Defaults to 1. |

**200** OK Success
```
{
  "repository": {
    "name": "mergeit",
    "org": "aviator"
  },
  "history": [{
      "applied_by": {
        "email": "email@email.com",
        "gh_username": "jainankit"
      },
      "applied_at": "2022-11-16T17:21:41.350499Z"
      "commit_sha": "85d419bbca585f04456083fd98b7858c0f1e4d13",
      "diff": "-     publish: \"always\"\n+     publish: \"ready\"",
    },
    {
      ..
    }
  ]
}
```

## Analytics

### `GET /api/v1/analytics`
Get list of analytics objects representing statistics on a daily basis

| name | in | type | req | description |
|---|---|---|---|---|
| start | query | String |  | UTC Start date in YYYY-MM-DD format. Example: 2021-07-21 |
| end | query | String |  | UTC End date in YYYY-MM-DD format. Example: 2021-07-21 |
| repo | query | String | * | Name of the GitHub repo, in the format: orgname/reponame |
| timezone | query | String |  | Standard tz format string. Defaults to account timezone. Example: America/Los_Angeles |

**200** OK Success
```

```

## Queue

### `GET /api/v1/queue/stats`
Get live statistics about the state of the merge queue

| name | in | type | req | description |
|---|---|---|---|---|
| org | query | String | * | The GitHub organization that the repo belongs to. |
| repo | query | String | * | The name of the GitHub repo. |

**200** OK Success
```
{
  // Stats about the current depth of the queue.
  "depth": {
    // The total number of PRs that are in the queue.
    // Excludes PRs that have not been queued yet or that have been
    // marked as blocked.
    "queued": 8,
    // The number of PRs actively being processed.
    // In serial mode, this value is always equal to the "queued" value.
    // In parallel mode, this will be at most the "max_parallel_builds" setting
    // and indicates the numbers of PRs that have draft PRs created.
    "processing": 2,
    // The number of PRs that are queued but not yet being processed.
    // 
…
```

## User actions

### `GET /api/v1/user_actions`
User actions · paginated (?/page) · Enterprise plan only

| name | in | type | req | description |
|---|---|---|---|---|
| entity | query | String |  | Represents the entity type that is changed. Currently supported entities are user , merge_queue , repository , account , billing , integrations and flexreview |
| action | query | String |  | The type of action performed by the user. |
| page | query | Number |  | Page number |
| action | query | String |  | The type of action performed by the user |
| actor | query | String |  | The email address of the user who performed the action |
| entity | query | String |  | The entity type that has changed. |
| target | query | String |  | Optional . Represents the target entity that has changed. It could be null if not applicable. E.g. it will be null for entity type account or integrations |
| timestamp | query | String |  | ISO timestamp representing the time with timezone |

**200**
```
[
    {
        "action": "user_removed",
        "actor": "ankit@aviator.co",
        "entity": "user",
        "target": "heeju@aviator.co",
        "timestamp": "2024-10-02T00:45:05.881726+00:00"
    },
    {
        "action": "queue_config_changed",
        "actor": "ankit+masaya-demo@aviator.co",
        "entity": "merge_queue",
        "target": "aviator-staging-testing/release-testing",
        "timestamp": "2024-10-02T00:31:46.471689+00:00"
    }
]
```
