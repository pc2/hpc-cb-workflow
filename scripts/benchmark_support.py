"""Prepare collected measurements and report benchmark action results."""

import argparse
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def api(path, body=None, method=None):
    args = ['gh', 'api', '-H', 'X-GitHub-Api-Version: 2026-03-10', path]
    if body is not None:
        args += ['--method', method or 'POST', '--input', '-']
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                            text=True, capture_output=True, check=True, timeout=60)
    return json.loads(result.stdout) if result.stdout.strip() else None


def relative_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '.git' in path.parts or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValueError('Expected a relative artifact path.')
    return value


def validate_results(data):
    if not isinstance(data, list) or not data:
        raise ValueError('The benchmark result must be a nonempty array.')
    names = set()
    for item in data:
        for key in ('name', 'unit'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f'Missing benchmark {key}.')
        if item['name'] in names:
            raise ValueError('Duplicate benchmark name.')
        names.add(item['name'])
        value = item.get('value')
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Benchmark values must be finite and nonnegative.')
    return data


def output(**values):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        for key, value in values.items():
            stream.write(f'{key}={value}\n')


def prepare():
    config = json.loads(os.environ['CONFIG'])
    suite = json.loads(os.environ['SUITE'])
    context = json.loads(Path(os.environ['CONTEXT']).read_text())
    branch = config.get('branch', 'hpc-results')
    command('git', 'check-ref-format', '--branch', branch)
    mode = config.get('mode', 'history')
    if mode not in ('history', 'pages', 'compare'):
        raise ValueError('Unknown publication mode.')
    record = mode != 'compare' and not context['pull_request']
    # Some event payloads lack the repository, the API knows the default branch.
    default_branch = os.environ.get('DEFAULT_BRANCH') or api(f'repos/{os.environ["GITHUB_REPOSITORY"]}')['default_branch']
    if record and context['ref'] != default_branch:
        raise ValueError('Only the default branch can update benchmark history.')
    tool = suite.get('tool', 'customSmallerIsBetter')
    if tool not in ('customSmallerIsBetter', 'customBiggerIsBetter', 'julia'):
        raise ValueError('Unsupported benchmark format.')
    directory = relative_path(suite.get('directory', 'bench'))
    for key in ('name', 'archive', 'file'):
        if not isinstance(suite.get(key), str) or not suite[key]:
            raise ValueError(f'Missing suite {key}.')
    archive = relative_path(suite['archive'])
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,100}', suite['name']):
        raise ValueError('Invalid suite name.')
    member = relative_path(suite['file'])
    with zipfile.ZipFile(Path(os.environ['ARTIFACTS']) / archive) as source:
        info = source.getinfo(member)
        if info.file_size > 20_000_000:
            raise ValueError('Benchmark output exceeds twenty megabytes.')
        raw = source.read(info)
    if tool.startswith('custom'):
        validate_results(json.loads(raw))
    result = Path(os.environ['RUNNER_TEMP']) / 'benchmark-input.json'
    result.write_bytes(raw)
    warning = suite.get('alert_threshold', '115%')
    failure = suite.get('fail_threshold', '150%')
    if any(not re.fullmatch(r'[1-9][0-9]*(?:\.[0-9]+)?%', value) for value in (warning, failure)):
        raise ValueError('Thresholds must be positive percentages.')
    if not 100 <= float(warning[:-1]) <= float(failure[:-1]):
        raise ValueError('Thresholds must satisfy 100 <= warning <= failure.')
    command('git', 'config', 'user.name', 'github-actions[bot]')
    command('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    exists = command('git', 'ls-remote', '--heads', 'origin', f'refs/heads/{branch}')
    if exists:
        command('git', 'fetch', '--depth=1', 'origin', f'refs/heads/{branch}')
        command('git', 'checkout', '-B', branch, 'FETCH_HEAD')
    elif record:
        command('git', 'checkout', '--orphan', branch)
        command('git', 'rm', '-rf', '--ignore-unmatch', '.')
        command('git', 'commit', '--allow-empty', '-m', 'Initialize benchmark history.')
    else:
        raise ValueError('No recorded baseline exists for this comparison.')
    ledger_path = Path(directory) / '.hpc-runs.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    key = f'{context["project_id"]}/{context["pipeline_id"]}/{suite["name"]}'
    previous = ledger.get(key)
    receipt_name = f'benchmark-receipt-{context["project_id"]}-{context["pipeline_id"]}-{suite["name"]}'
    if not record:
        repo = os.environ['GITHUB_REPOSITORY']
        run = os.environ['GITHUB_RUN_ID']
        artifacts = api(f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100')['artifacts']
        receipt = next((a for a in artifacts if a['name'] == receipt_name and not a['expired']), None)
        if receipt:
            response = subprocess.run(['gh', 'api', f'repos/{repo}/actions/artifacts/{receipt["id"]}/zip'],
                                      capture_output=True, check=True, timeout=60)
            with zipfile.ZipFile(io.BytesIO(response.stdout)) as saved:
                previous = json.loads(saved.read('receipt.json'))
            if previous['key'] != key or previous['sha'] != context['sha']:
                raise ValueError('The comparison receipt belongs to another measurement.')
    data_path = Path(directory) / 'data.js'
    history = {}
    if data_path.exists():
        contents = data_path.read_text()
        prefix = 'window.BENCHMARK_DATA = '
        if not contents.startswith(prefix):
            raise ValueError('Unexpected benchmark history format.')
        history = json.loads(contents[len(prefix):].strip().rstrip(';'))
    entries = history.get('entries', {}).get(suite['name'], [])
    baseline = next((entry for entry in reversed(entries) if entry['commit']['id'] != context['sha']), None)
    if not record and not previous and baseline is None:
        raise ValueError('No comparable baseline with a different commit exists.')
    if baseline and baseline.get('tool') != tool:
        raise ValueError('The benchmark format differs from the baseline.')
    if baseline and not previous and tool.startswith('custom'):
        old = {entry['name']: entry for entry in baseline['benches']}
        for item in json.loads(raw):
            if item['name'] not in old or old[item['name']]['unit'] != item['unit']:
                raise ValueError('Benchmark names and units must match the baseline.')
    state = dict(context=context, config=config, suite=suite, branch=branch, directory=directory,
                 record=record, key=key, ledger=ledger, previous=previous,
                 receipt_name=receipt_name, baseline_data=baseline, entries=len(entries),
                 baseline=baseline['commit']['id'] if baseline else None)
    (Path(os.environ['RUNNER_TEMP']) / 'benchmark-state.json').write_text(json.dumps(state))
    output(tool=tool, name=suite['name'], file=result, directory=directory,
           warning=warning, failure=failure, sha=context['sha'],
           duplicate=str(previous is not None).lower(), branch=branch,
           receipt=receipt_name,
           baseline=state['baseline'] or 'none')


def finish():
    state = json.loads((Path(os.environ['RUNNER_TEMP']) / 'benchmark-state.json').read_text())
    context, suite = state['context'], state['suite']
    verdict = state['previous']['verdict'] if state['previous'] else os.environ['OUTCOME']
    if verdict not in ('success', 'failure'):
        raise ValueError('Benchmark action did not complete.')
    if state['previous']:
        summary = state['previous']['summary']
    else:
        generated = (Path(state['directory']) / 'data.js').read_text()
        data = json.loads(generated.removeprefix('window.BENCHMARK_DATA = ').strip().rstrip(';'))
        entries = data['entries'][suite['name']]
        current = entries[-1]
        # An earlier entry of the same commit must not pass as this measurement.
        if len(entries) != state['entries'] + 1 or current['commit']['id'] != context['sha']:
            raise ValueError('The benchmark action did not produce the expected measurement.')
        previous = {b['name']: b for b in (state['baseline_data'] or {}).get('benches', [])}
        if previous and any(b['name'] not in previous or previous[b['name']]['unit'] != b['unit']
                            for b in current['benches']):
            raise ValueError('The generated measurements do not match the baseline.')
        def cell(value):
            return str(value).replace('|', '\\|').replace('\n', ' ')
        summary = f'Benchmark suite {suite["name"]}.\n\n| Measurement | Current | Baseline | Unit | Ratio |\n| --- | --- | --- | --- | --- |\n'
        for item in current['benches']:
            baseline = previous.get(item['name'], {}).get('value', 'unavailable')
            ratio = 'unavailable'
            if type(baseline) in (int, float):
                numerator, denominator = item['value'], baseline
                if current['tool'] == 'customBiggerIsBetter':
                    numerator, denominator = denominator, numerator
                ratio = f'{numerator / denominator:.3f}' if denominator else ('1.000' if numerator == 0 else 'infinite')
            summary += f'| {cell(item["name"])} | {item["value"]} | {baseline} | {cell(item["unit"])} | {ratio} |\n'
        summary += f'\nBaseline commit {state["baseline"] or "none, initial measurement"}.\n'
        summary += f'\nMeasured commit {context["sha"]}, benchmark result {verdict}.\n'
        summary += f'\nWarning threshold {suite.get("alert_threshold", "115%")}, failure threshold {suite.get("fail_threshold", "150%")}.\n'
    if state['record'] and not state['previous']:
        state['ledger'][state['key']] = dict(verdict=verdict, summary=summary)
        ledger = Path(state['directory']) / '.hpc-runs.json'
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(json.dumps(state['ledger'], indent=2) + '\n')
        command('git', 'add', str(ledger))
        command('git', 'commit', '-m', f'Record pipeline {context["pipeline_id"]}.')
        command('git', 'push', 'origin', f'HEAD:refs/heads/{state["branch"]}')
    report(context, suite, verdict, summary)
    receipt = Path(os.environ['RUNNER_TEMP']) / 'receipt.json'
    receipt.write_text(json.dumps(dict(key=state['key'], sha=context['sha'], verdict=verdict, summary=summary)))
    output(verdict=verdict, recorded=str(state['record']).lower())
    Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(summary)


def report(context, suite, verdict, summary):
    repo = os.environ['GITHUB_REPOSITORY']
    marker = f'<!-- hpc-benchmark:{context["project_id"]}:{context["pipeline_id"]}:{suite["name"]} -->'
    if context['pull_request']:
        path = f'repos/{repo}/issues/{context["pull_request"]}/comments'
        comments = json.loads(command('gh', 'api', '--paginate', '--slurp', path))
        existing = next((c for page in comments for c in page if
                         c['user']['login'] == 'github-actions[bot]' and c['body'].startswith(marker)), None)
        body = marker + '\n\n' + summary[-50000:]
        if existing:
            api(f'repos/{repo}/issues/comments/{existing["id"]}', {'body': body}, 'PATCH')
        else:
            api(path, {'body': body})
    check_name = f'HPC benchmark / {suite["name"]}'
    pages = json.loads(command('gh', 'api', '--paginate', '--slurp',
                              f'repos/{repo}/commits/{context["sha"]}/check-runs?filter=all&per_page=100'))
    checks = [check for page in pages for check in page['check_runs']]
    identity = f'{context["project_id"]}/{context["pipeline_id"]}/{suite["name"]}'
    existing = next((c for c in checks if c.get('external_id') == identity and
                     c['app']['slug'] == 'github-actions'), None)
    check = dict(name=check_name, status='completed', conclusion=verdict,
                 external_id=identity, output=dict(title=f'Benchmark {verdict}', summary=summary[-50000:]))
    if existing:
        api(f'repos/{repo}/check-runs/{existing["id"]}', check, 'PATCH')
    else:
        api(f'repos/{repo}/check-runs', dict(check, head_sha=context['sha']))


def unavailable():
    context = json.loads(Path(os.environ['CONTEXT']).read_text())
    suite = json.loads(os.environ['SUITE'])
    url = f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'
    summary = f'Benchmark comparison unavailable for commit {context["sha"]}.\nSee the [workflow failure]({url}) for the configuration, baseline or processing error.\n'
    report(context, suite, 'failure', summary)
    Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['prepare', 'finish', 'unavailable'])
    args = parser.parse_args()
    globals()[args.operation]()
