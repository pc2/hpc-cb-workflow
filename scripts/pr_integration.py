"""Exercise PR commands, continuation, regression reporting and retry cleanup."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote

from integration_suite import artifact, items


def api(path, body=None, method=None, token=None):
    args = ['gh', 'api', '-H', 'X-GitHub-Api-Version: 2026-03-10', path]
    if body is not None:
        args += ['--input', '-']
    if method or body is not None:
        args += ['--method', method or 'POST']
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                            env=dict(os.environ, GH_TOKEN=token or os.environ['GH_TOKEN']),
                            text=True, capture_output=True, timeout=60)
    if result.returncode:
        details = '\n'.join(part.strip() for part in (result.stderr, result.stdout) if part.strip())
        for secret in (token, os.environ.get('GH_TOKEN'), os.environ.get('CB_TEST_TOKEN')):
            if secret:
                details = details.replace(secret, '[redacted]')
        verb = method or ('POST' if body is not None else 'GET')
        raise RuntimeError(f'GitHub API {verb} {path} failed with exit code {result.returncode}.\n{details}')
    return json.loads(result.stdout) if result.stdout.strip() else None


def wait_run(repo, origin, expected, minimum_attempt=1):
    deadline = time.monotonic() + 3600
    run_id = origin
    since = None
    while time.monotonic() < deadline:
        run = api(f'repos/{repo}/actions/runs/{run_id}')
        since = since or run['created_at']
        if run['status'] != 'completed' or run.get('run_attempt', 1) < minimum_attempt:
            time.sleep(15)
            continue
        jobs = list(items(f'repos/{repo}/actions/runs/{run_id}/jobs', 'jobs'))
        # The job list can lag behind the completed run, especially right after a rerun.
        if any(j['status'] != 'completed' or j.get('run_attempt', 1) != run.get('run_attempt', 1) for j in jobs):
            time.sleep(15)
            continue
        report = [j for j in jobs if 'benchmark' in j['name'].lower() and j['conclusion'] in ('success', 'failure')]
        if report:
            if run['conclusion'] != expected:
                raise AssertionError(f'Unexpected conclusion in {run["html_url"]}.')
            return run
        if run['conclusion'] != 'success':
            raise AssertionError(f'Pipeline failed before reporting, {run["html_url"]}.')
        # Continuations start after the original run, so older history need not be listed.
        candidates = items(f'repos/{repo}/actions/workflows/hpc-pr.yml/runs?event=workflow_dispatch'
                           f'&created={quote(">=" + since)}', 'workflow_runs')
        next_run = next((r for r in candidates if r['id'] > run_id and
                         r['display_title'] == f'PR benchmark resume {origin}'), None)
        if next_run:
            run_id = next_run['id']
            minimum_attempt = 1
        else:
            time.sleep(15)
    raise TimeoutError(f'PR benchmark did not finish, original run {origin}.')


def comments(repo, pr):
    pages = subprocess.check_output(['gh', 'api', '--paginate', '--slurp',
                                     f'repos/{repo}/issues/{pr}/comments'], text=True)
    return [entry for page in json.loads(pages) for entry in page]


def verify_report(repo, pr, sha, expected):
    reports = [c for c in comments(repo, pr) if c['user']['login'] == 'github-actions[bot]' and
               c['body'].startswith('<!-- hpc-benchmark:')]
    if len(reports) != 1 or sha not in reports[0]['body'] or f'benchmark result {expected}' not in reports[0]['body']:
        raise AssertionError('Expected one matching PR regression report.')
    ratio = '2.500' if expected == 'failure' else '0.900'
    if f'| {ratio} |' not in reports[0]['body'] or 'Baseline commit ' not in reports[0]['body']:
        raise AssertionError('The regression report did not compare the controlled measurements.')
    checks = api(f'repos/{repo}/commits/{sha}/check-runs?per_page=100')['check_runs']
    matching = [c for c in checks if c['name'] == 'HPC benchmark / Regression fixture']
    if len(matching) != 1 or matching[0]['conclusion'] != expected:
        raise AssertionError('The regression check is missing or has the wrong verdict.')
    return reports[0]['id']


def run_title(repo, run_id):
    """Returns the run name, GitHub shows the bare workflow name until it has evaluated run-name."""
    for _ in range(24):
        title = api(f'repos/{repo}/actions/runs/{run_id}')['display_title']
        if title != 'PR benchmark':
            return title
        time.sleep(5)
    return title


def command(repo, pr, body):
    """Posts an HPC command as the test account and returns the reply without its marker."""
    comment = api(f'repos/{repo}/issues/{pr}/comments', dict(body=body), token=os.environ['CB_TEST_TOKEN'])
    marker = f'<!-- hpc-command:{comment["id"]} -->'
    for _ in range(60):
        replies = [c for c in comments(repo, pr) if c['user']['login'] == 'github-actions[bot]' and
                   c['body'].startswith(marker)]
        if replies:
            return replies[0]['body'].removeprefix(marker).strip()
        time.sleep(10)
    raise AssertionError(f'The command {body} got no reply.')


def verify_benchmark_jobs(repo, run_id, sha):
    """Checks that only the suite with a collected archive started a benchmark job."""
    reports = [j['name'] for j in items(f'repos/{repo}/actions/runs/{run_id}/jobs', 'jobs') if j['name'].endswith('/ report')]
    if len(reports) != 1 or 'Regression fixture' not in reports[0]:
        raise AssertionError(f'Expected one benchmark job for the collected suite: {reports}')
    checks = api(f'repos/{repo}/commits/{sha}/check-runs?per_page=100')['check_runs']
    if any(c['name'] == 'HPC benchmark / Left out' for c in checks):
        raise AssertionError('A suite without a collected archive reported a check.')


def verify_failure_report(repo, pr, sha):
    """Dispatches a commit outside the PR and checks that collection reports the failed start to the PR."""
    run_id = api(f'repos/{repo}/actions/workflows/hpc-pr.yml/dispatches',
                 dict(ref=api(f'repos/{repo}')['default_branch'], return_run_details=True,
                      inputs=dict(pull_request=str(pr), source_sha=sha)))['workflow_run_id']
    deadline = time.monotonic() + 900
    while api(f'repos/{repo}/actions/runs/{run_id}')['status'] != 'completed':
        if time.monotonic() > deadline:
            raise TimeoutError(f'The failing run {run_id} did not finish.')
        time.sleep(15)
    jobs = {j['name'].split(' / ', 1)[-1]: j['conclusion'] for j in items(f'repos/{repo}/actions/runs/{run_id}/jobs', 'jobs')}
    if jobs.get('Start on GitLab') != 'failure' or jobs.get('Monitor GitLab jobs') != 'skipped':
        raise AssertionError(f'The run {run_id} did not fail before reaching GitLab: {jobs}')
    marker = f'<!-- hpc-failure:{run_id}:1 -->'
    for _ in range(30):
        reports = [c for c in comments(repo, pr) if c['user']['login'] == 'github-actions[bot]' and c['body'].startswith(marker)]
        if reports:
            if 'Start on GitLab, step Authorize the run' not in reports[0]['body']:
                raise AssertionError(f'The failure report does not name the failed step: {reports[0]["body"]}')
            return
        time.sleep(10)
    raise AssertionError(f'No failure report for run {run_id}.')


def run(state_path):
    token = os.environ.get('CB_TEST_TOKEN')
    if not token:
        raise ValueError('Configure the CB_TEST_TOKEN Actions secret.')
    if api('user', token=token)['login'].lower() != os.environ['CB_TEST_ACTOR'].lower():
        raise ValueError('CB_TEST_ACTOR does not match the token owner.')
    repo = os.environ['GITHUB_REPOSITORY']
    sha = os.environ['GITHUB_SHA']
    default = api(f'repos/{repo}')['default_branch']
    response = api(f'repos/{repo}/actions/workflows/hpc-pr.yml/dispatches',
                   dict(ref=default, return_run_details=True))
    wait_run(repo, response['workflow_run_id'], 'success')
    baseline = api(f'repos/{repo}/git/ref/heads/hpc-test-results')['object']['sha']
    state = []
    state_path.write_text(json.dumps(state))
    for scenario, value, expected in [('pass', 90, 'success'), ('fail', 250, 'failure')]:
        branch = f'hpc-test/{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}/{scenario}'
        parent = api(f'repos/{repo}/git/commits/{sha}')
        tree = api(f'repos/{repo}/git/trees', dict(base_tree=parent['tree']['sha'], tree=[dict(
            path='benchmarks/pr-fixture.json', mode='100644', type='blob',
            content=json.dumps([dict(name='controlled measurement', unit='seconds', value=value)]) + '\n')]))
        commit = api(f'repos/{repo}/git/commits', dict(message=f'HPC integration test {scenario}.',
                     tree=tree['sha'], parents=[sha]))['sha']
        state.append(dict(branch=branch, pr=None))
        state_path.write_text(json.dumps(state))
        api(f'repos/{repo}/git/refs', dict(ref=f'refs/heads/{branch}', sha=commit))
        pr = api(f'repos/{repo}/pulls', dict(title=f'HPC integration test {scenario}', head=branch,
                  base=default, draft=True, body='Automated regression test, closed after verification.'),
                 token=token)['number']
        state[-1]['pr'] = pr
        state_path.write_text(json.dumps(state))
        if scenario == 'pass':
            # A dispatch without a person and comment fails before GitLab, collection reports it to the PR.
            verify_failure_report(repo, pr, sha)
            # GitHub must reject an option the caller does not declare, before any run starts.
            reply = command(repo, pr, f'/hpc {commit} undeclared=1')
            if not reply.startswith('Not dispatched') or '/actions/runs/' in reply:
                raise AssertionError('An undeclared option was not refused.')
        options = ' label=option-check' if scenario == 'pass' else ''
        reply = command(repo, pr, f'/hpc {commit}{options}')
        match = re.search(r'/actions/runs/([0-9]+)', reply)
        if not match:
            raise AssertionError(f'The comment did not dispatch the HPC workflow: {reply}')
        origin = int(match[1])
        title = run_title(repo, origin)
        if title != f'PR benchmark {pr} {commit} {"option-check" if options else "none"}':
            raise AssertionError(f'The command options did not reach the run: {title}')
        result = wait_run(repo, origin, expected)
        if result['id'] == origin:
            raise AssertionError('The PR test did not exercise continuation.')
        verify_benchmark_jobs(repo, result['id'], commit)
        report_id = verify_report(repo, pr, commit, expected)
        api(f'repos/{repo}/actions/runs/{result["id"]}/rerun', method='POST')
        wait_run(repo, result['id'], expected, result['run_attempt'] + 1)
        if verify_report(repo, pr, commit, expected) != report_id:
            raise AssertionError('Retry created another comment.')
        if api(f'repos/{repo}/git/ref/heads/hpc-test-results')['object']['sha'] != baseline:
            raise AssertionError('PR comparison modified the baseline.')
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(f'Passed PR {pr}, {scenario}, comment dispatch, continuation and retry.\n')


def cleanup(state_path):
    if not state_path.exists():
        return
    repo = os.environ['GITHUB_REPOSITORY']
    for entry in json.loads(state_path.read_text()):
        if not entry['branch'].startswith(f'hpc-test/{os.environ["GITHUB_RUN_ID"]}-'):
            raise ValueError('Cleanup encountered an unrelated branch.')
        if entry['pr']:
            api(f'repos/{repo}/pulls/{entry["pr"]}', dict(state='closed'), 'PATCH')
        api(f'repos/{repo}/git/refs/heads/{entry["branch"]}', method='DELETE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['run', 'cleanup'])
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.operation](args.state)
