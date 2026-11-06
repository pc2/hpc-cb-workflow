# Changelog

## Unreleased

Optional benchmark suites use github-action-benchmark for history and regression checks.
Reviewed PR commits can run through the trusted default branch caller.
The command integration test verifies PR creation, comments, continuation and reporting retries.
The CB_TEST_TOKEN secret and CB_TEST_ACTOR variable configure command testing.

The integration suite verifies success, failure and both handover outcomes.
A Julia measurement follows the GitLab artifact path into GitHub Pages history.
Pushes, manual runs and weekly runs contribute to the benchmark history.
Publication retries reuse the saved measurement without creating another point.
Pages are redeployed after a failing suite, since its point is already recorded.
A failed benchmark action can no longer report an earlier measurement of the same commit.
The `/hpc` command accepts surrounding whitespace.
The manual example accepts `source_sha` and can serve as the PR command target.

The reusable workflow mirrors commits and verifies pipeline identity.
It reports individual job checks and collects artifacts after failures.
Start, wait and collect run as separate jobs with scoped credentials.
Monitoring continues automatically using the original run's context artifact.
Retries reuse saved context without starting another pipeline.
Waiting pipelines remain monitored until completion or the polling deadline.
PR comments report the tested commit, pipeline result and artifact outcomes.
Callers can shorten the monitoring time of one run with `max_wait_minutes`.
Continuation looks up the default branch through the API, so scheduled runs continue.
Monitoring fails after seven days instead of ending successfully.
The artifact download dependencies are pinned by hash.
The integration workflow verifies success, failure and handover against a GitLab project.
