# Changelog

## Unreleased

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
