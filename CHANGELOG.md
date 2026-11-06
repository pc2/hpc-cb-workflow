# Changelog

## Unreleased

Optional benchmark suites use github-action-benchmark for history and regression checks.
Reviewed PR commits can run through the trusted default branch caller.
The command integration test verifies PR creation, comments, continuation and reporting retries.
The CB_TEST_TOKEN secret and CB_TEST_ACTOR variable configure command testing, the command treats the test account like any user.

The integration suite verifies success, failure and both handover outcomes.
A Julia measurement follows the GitLab artifact path into GitHub Pages history.
Pushes, manual runs and weekly runs contribute to the benchmark history.
Publication retries reuse the saved measurement without creating another point.
Pages are redeployed after a failing suite, since its point is already recorded.
A failed benchmark action can no longer report an earlier measurement of the same commit.
The `/hpc <commit> [<commit> ...]` command dispatches the named reviewed commits of the PR, earlier commits included.
Approval requires full 40 character commit hashes in the command and start job.
Command options `name=value` set the caller's dispatch inputs, the PR command test verifies a refused and an accepted option.
The command and start job require repository write access for the person authorizing PR runs and runs of other branches.
The workflow sets EXPECTED_COMMIT_SHA itself and rejects malformed or duplicate pipeline variables.
The PR command is a reusable workflow, callers keep a short stub and name their caller in its workflow input.
The workflow reads context_run_id, pull_request, source_sha and command_comment from the caller's dispatch, callers only declare them.
Configuration, PR and resume checks name the input or state to fix, PR runs failing before collection comment on the PR.
The variable_patterns input restricts the values of pipeline variables before anything reaches GitLab.
The start job warns about callers that cannot continue, skips unconfigured forks and fails on unsupported events.
Artifact collection has a configurable time limit and uploads the archives without compressing them again.
Job checks are named HPC <pipeline> / <job> instead of gitlab/<project>/<pipeline>/<job>.
Benchmark reports mark each measurement as ok, warning or failure and count warnings in the check title, the action's duplicate job summary is off.
Pushes to the default branch start pipelines, it no longer has to be named `main`.
GitLab outages are retried during monitoring and continuation dispatches are retried.
Checks and collected artifacts include all jobs and child pipelines.
Pipelines without artifacts pass collection.
A pipeline blocked by a manual job ends monitoring instead of polling for seven days.
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
