import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile


def api(path, body=None):
    command = ['gh', 'api', '-H', 'X-GitHub-Api-Version: 2026-03-10', path]
    if body is not None:
        command += ['--method', 'POST', '--input', '-']
    result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                            text=True, capture_output=True, check=True, timeout=60)
    return json.loads(result.stdout)


def items(path, key):
    separator = '&' if '?' in path else '?'
    for page in range(1, 101):
        batch = api(f'{path}{separator}per_page=100&page={page}')[key]
        yield from batch
        if len(batch) < 100:
            return
    raise RuntimeError('API pagination exceeded the supported limit.')


def artifact(repo, run_id, name):
    matches = [a for a in items(f'repos/{repo}/actions/runs/{run_id}/artifacts', 'artifacts')
               if a['name'] == name and not a['expired']]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one {name} artifact in run {run_id}.')
    result = subprocess.run(['gh', 'api', f'repos/{repo}/actions/artifacts/{matches[0]["id"]}/zip'],
                            capture_output=True, check=True, timeout=120)
    return zipfile.ZipFile(io.BytesIO(result.stdout))


def validate_result(record, scenario, sha, origin, pipeline, conclusion):
    if (record['scenario'], record['sha'], record['context_run_id']) != (scenario, sha, origin):
        raise ValueError('The verification report belongs to another test.')
    if pipeline is not None and record['pipeline_id'] != pipeline:
        raise ValueError('Continuation started a different pipeline.')
    if type(record['pipeline_id']) is not int or record['pipeline_id'] <= 0:
        raise ValueError('Invalid pipeline ID.')
    if type(record['collected']) is not bool:
        raise ValueError('Invalid collection state.')
    expected = 'failure' if record['collected'] and scenario in ('failure', 'handover_failure') else 'success'
    if record['result'] != expected or conclusion != expected:
        raise ValueError('The run did not have the expected outcome.')
    if record['collected']:
        if record['next_run_id'] != 0:
            raise ValueError('A completed pipeline dispatched another run.')
    elif not scenario.startswith('handover') or type(record['next_run_id']) is not int or record['next_run_id'] <= 0:
        raise ValueError('An unfinished pipeline needs a continuation run.')


def run_scenario(repo, ref, sha, scenario, output):
    response = api(f'repos/{repo}/actions/workflows/integration.yml/dispatches',
                   {'ref': ref, 'inputs': {'scenario': scenario}, 'return_run_details': True})
    origin = run_id = response['workflow_run_id']
    pipeline = None
    visited = set()
    deadline = time.monotonic() + 3600
    while time.monotonic() < deadline:
        run = api(f'repos/{repo}/actions/runs/{run_id}')
        if run['status'] != 'completed':
            time.sleep(15)
            continue
        if run_id == origin and run['head_sha'] != sha:
            raise RuntimeError('The selected branch advanced before dispatch.')
        if run_id in visited or len(visited) >= 5:
            raise RuntimeError('Unexpected continuation chain.')
        visited.add(run_id)
        jobs = list(items(f'repos/{repo}/actions/runs/{run_id}/jobs', 'jobs'))
        if not any(j['name'] == 'Verify integration' and j['conclusion'] == 'success' for j in jobs):
            raise RuntimeError(f'Integration verification failed in {run["html_url"]}.')
        with artifact(repo, run_id, 'integration-result') as archive:
            record = json.loads(archive.read('result.json'))
        validate_result(record, scenario, sha, origin, pipeline, run['conclusion'])
        pipeline = record['pipeline_id']
        if record['collected']:
            if scenario.startswith('handover') and len(visited) < 2:
                raise RuntimeError('The handover test did not continue in another run.')
            record.update(run_id=run_id, run_url=run['html_url'])
            output.write_text(json.dumps(record, indent=2) + '\n')
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write(f'Passed {scenario}, [verified run]({run["html_url"]}), pipeline {pipeline}.\n')
            print(f'PASS: {scenario}, pipeline {pipeline}.')
            return record
        run_id = record['next_run_id']
    raise TimeoutError(f'Integration did not finish within one hour, original run {origin}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', required=True,
                        choices=['success', 'failure', 'handover', 'handover_failure', 'benchmark'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run_scenario(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_REF_NAME'],
                 os.environ['GITHUB_SHA'], args.scenario, args.output)
