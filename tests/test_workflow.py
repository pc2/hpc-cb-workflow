import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
task = root / '.tmp'
task.mkdir(exist_ok=True)
action = Path(os.environ.get('GITHUB2LAB_SOURCE', task / 'github2lab_action')).resolve()
workflow = yaml.load((root / '.github/workflows/hpc-pipeline.yml').read_text(), Loader=yaml.BaseLoader)
caller = yaml.load((root / 'examples/manual.yml').read_text(), Loader=yaml.BaseLoader)
checks = yaml.load((root / '.github/workflows/test.yml').read_text(), Loader=yaml.BaseLoader)
integration = yaml.load((root / '.github/workflows/integration.yml').read_text(), Loader=yaml.BaseLoader)
suite = yaml.load((root / '.github/workflows/integration-suite.yml').read_text(), Loader=yaml.BaseLoader)
history = yaml.load((root / '.github/workflows/benchmark-history.yml').read_text(), Loader=yaml.BaseLoader)
gitlab_ci = yaml.load((root / '.gitlab-ci.yml').read_text(), Loader=yaml.BaseLoader)
jobs = workflow['jobs']
assert set(jobs) == {'start', 'wait', 'collect', 'benchmark', 'pages'}
steps = [step for job in jobs.values() for step in job.get('steps', [])]
by_name = {step['name']: step for step in steps}
action_revisions = {step['uses'].split('@')[1] for step in steps
                    if step.get('uses', '').startswith('pc2/github2lab_action@')}
assert len(action_revisions) == 1
action_revision = action_revisions.pop()
assert subprocess.check_output(['git', '-C', str(action), 'rev-parse', 'HEAD'], text=True).strip() == action_revision
for definition in (workflow, checks, integration, suite, history):
    for job in definition['jobs'].values():
        for step in job.get('steps', []):
            if 'uses' in step:
                assert re.search(r'@[0-9a-f]{40}$', step['uses']), step['uses']
for step in checks['jobs']['workflow']['steps']:
    if step.get('with', {}).get('repository') == 'pc2/github2lab_action':
        assert step['with']['ref'] == action_revision
for step in steps:
    if 'run' in step:
        subprocess.run(['bash', '-n'], input=step['run'], text=True, check=True)
assert set(caller['on']) == {'workflow_dispatch'}
assert 'workflow_call' in workflow['on']
assert caller['permissions'] == workflow['permissions']
assert 'statuses' not in caller['permissions']
assert 'pipeline_variables' not in caller['jobs']['hpc']['with']
assert set(caller['on']['workflow_dispatch']['inputs']) == {'context_run_id', 'pull_request', 'source_sha', 'command_comment'}
command = yaml.load((root / '.github/workflows/hpc-command.yml').read_text(), Loader=yaml.BaseLoader)
assert set(command['on']) == {'workflow_call'}
assert command['on']['workflow_call']['inputs']['workflow']['required'] == 'true'
assert command['jobs']['dispatch']['steps'][0]['env']['CB_COMMAND_WORKFLOW'] == '${{ inputs.workflow }}'
for stub_path, target, workflow_file in [('.github/workflows/pr-command.yml', './.github/workflows/hpc-command.yml', 'hpc-pr.yml'),
                                         ('examples/command.yml', 'pc2/hpc-cb-workflow/.github/workflows/hpc-command.yml@REVIEWED_COMMIT', 'hpc.yml')]:
    stub = yaml.load((root / stub_path).read_text(), Loader=yaml.BaseLoader)
    assert stub['on'] == {'issue_comment': {'types': ['created']}}, stub_path
    assert stub['permissions'] == command['permissions'], stub_path
    assert stub['jobs']['hpc']['uses'] == target and stub['jobs']['hpc']['with'] == {'workflow': workflow_file}
    assert stub['jobs']['hpc']['if'] == "github.event.issue.pull_request && startsWith(github.event.comment.body, '/hpc')"
for example in ('manual', 'benchmark'):
    forwarded = yaml.load((root / f'examples/{example}.yml').read_text(), Loader=yaml.BaseLoader)['jobs']['hpc']['with']
    assert not {'context_run_id', 'pull_request', 'source_sha', 'command_comment'} & set(forwarded), example
assert 'if' not in caller['jobs']['hpc']
assert caller['jobs']['hpc']['uses'].endswith('@REVIEWED_COMMIT')
assert workflow['on']['workflow_call']['secrets']['GITLAB_TRIGGER_TOKEN']['required'] == 'false'
assert workflow['on']['workflow_call']['inputs']['max_wait_minutes']['default'] == '330'
assert workflow['on']['workflow_call']['inputs']['expected_pipeline_status']['default'] == 'success'
assert workflow['on']['workflow_call']['outputs']['pipeline_status']['value'] == '${{ jobs.collect.outputs.pipeline_status }}'
assert jobs['benchmark']['if'].find("needs.collect.outputs.pipeline_status == 'success'") >= 0
assert "needs.benchmark.result == 'failure'" in jobs['pages']['if'] and "needs.wait.outputs.pull_request == ''" in jobs['pages']['if']


def test_integration_suite_covers_all_scenarios_and_verifies_without_write_access():
    assert set(integration['on']) == {'workflow_dispatch'}
    assert set(suite['on']) == {'push', 'workflow_dispatch', 'schedule'}
    assert suite['on']['push'] == {'branches': ['main']}
    assert suite['jobs']['scenarios']['strategy']['matrix']['scenario'] == ['success', 'failure', 'handover', 'handover_failure']
    assert set(integration['on']['workflow_dispatch']['inputs']) == {'scenario', 'pull_request', 'context_run_id'}
    assert integration['on']['workflow_dispatch']['inputs']['scenario']['options'] == ['success', 'failure', 'handover', 'handover_failure', 'benchmark']
    assert integration['permissions'] == workflow['permissions']
    assert integration['concurrency']['cancel-in-progress'] == 'false'
    hpc = integration['jobs']['hpc']
    assert hpc['uses'] == './.github/workflows/hpc-pipeline.yml'
    assert hpc['if'] == "vars.GITLAB_PROJECT_ID != ''"
    assert set(hpc['with']) <= set(workflow['on']['workflow_call']['inputs'])
    assert 'context_run_id' not in hpc['with'] and 'pull_request' not in hpc['with']
    assert 'EXPECTED_COMMIT_SHA' not in hpc['with']['pipeline_variables']
    assert hpc['secrets'] == {'GITLAB_TOKEN': '${{ secrets.GITLAB_TOKEN }}',
                              'GITLAB_TRIGGER_TOKEN': '${{ secrets.GITLAB_TRIGGER_TOKEN }}'}
    verify = integration['jobs']['verify']
    assert verify['needs'] == 'hpc'
    assert set(verify['permissions'].values()) == {'read'}
    for step in verify['steps']:
        if 'run' in step:
            subprocess.run(['bash', '-n'], input=step['run'], text=True, check=True)
        assert tokens & step.get('env', {}).keys() <= {'GITLAB_TOKEN', 'GH_TOKEN'}, step['name']
    assert verify['steps'][1]['env']['GITLAB_TOKEN'] == '${{ secrets.GITLAB_TOKEN }}'
    assert sum('GITLAB_TOKEN' in step.get('env', {}) for step in verify['steps']) == 1
    rule = gitlab_ci['workflow']['rules'][0]['if']
    assert '$CI_PIPELINE_SOURCE == "trigger"' in rule and '$EXPECTED_COMMIT_SHA == $CI_COMMIT_SHA' in rule
    assert gitlab_ci['fail']['rules'] == [{'if': '$SCENARIO == "failure"'}]
    assert gitlab_ci['slow']['rules'] == [{'if': '$SCENARIO == "handover" || $SCENARIO == "handover_failure"'}]
    assert gitlab_ci['slow']['artifacts']['when'] == 'always'
    assert gitlab_ci['benchmark']['rules'] == [{'if': '$SCENARIO == "benchmark"'}]
    assert set(history['on']) == {'push', 'schedule', 'workflow_dispatch'}
    assert history['on']['push'] == {'branches': ['main']}
    assert history['jobs']['benchmark']['uses'] == './.github/workflows/hpc-pipeline.yml'
    assert json.loads(history['jobs']['benchmark']['with']['benchmark'])['mode'] == 'pages'
    assert 'results/' in gitlab_ci['quick']['artifacts']['paths']
assert jobs['wait']['timeout-minutes'] == '345'
assert jobs['collect']['timeout-minutes'] == '${{ fromJSON(inputs.collect_timeout_minutes) }}'
assert workflow['on']['workflow_call']['inputs']['collect_timeout_minutes']['default'] == '60'
assert by_name['Upload GitLab artifacts']['with']['compression-level'] == '0'
assert "(inputs.context_run_id || github.event.inputs.context_run_id) == ''" in jobs['start']['if']
assert "(inputs.context_run_id || github.event.inputs.context_run_id) != ''" in jobs['wait']['if']
assert "inputs.gitlab_project_id != '' || !github.event.repository.fork" in jobs['start']['if']
assert jobs['wait']['needs'] == 'start'
assert jobs['collect']['needs'] == 'wait'

def job_runs(name, event, attempt, context='', start_result='skipped', canceled=False,
             ref='refs/heads/main', default='main', project='42', fork=False):
    expression = jobs[name]['if'].replace("format('refs/heads/{0}', github.event.repository.default_branch)",
                                          repr(f'refs/heads/{default}'))
    for key, value in {'github.event.repository.fork': fork, 'inputs.gitlab_project_id': project,
                       'github.event_name': event, 'github.run_attempt': attempt, 'github.ref': ref,
                       '(inputs.context_run_id || github.event.inputs.context_run_id)': context, 'needs.start.result': start_result,
                       'cancelled()': canceled}.items():
        expression = expression.replace(key, repr(value))
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', 'not ', expression)
    return eval(expression.strip(), {'__builtins__': {}})


def test_retries_monitor_saved_context_without_starting_pipelines():
    for event in ('workflow_dispatch', 'schedule', 'push'):
        assert job_runs('start', event, 1)
        assert not job_runs('wait', event, 1, start_result='failure')
        assert job_runs('wait', event, 1, start_result='success')
        for attempt in (2, 3):
            assert not job_runs('start', event, attempt)
            assert job_runs('wait', event, attempt)
        assert not job_runs('start', event, 1, context='900')
        assert job_runs('wait', event, 1, context='900')
        assert not job_runs('wait', event, 2, canceled=True)
    # Unsupported events start the job, its authorization step then fails with a message.
    for event in ('pull_request', 'pull_request_target'):
        assert job_runs('start', event, 1)
        for attempt in (1, 2):
            assert not job_runs('wait', event, attempt)
    for ref in ('refs/heads/feature', 'refs/tags/main'):
        assert job_runs('start', 'push', 1, ref=ref)
        for attempt in (1, 2):
            assert not job_runs('wait', 'push', attempt, ref=ref)
    # Forks without a GitLab project skip the run, a missing project elsewhere fails in validation.
    assert not job_runs('start', 'push', 1, project='', fork=True)
    assert job_runs('start', 'push', 1, project='', fork=False)
    assert job_runs('start', 'push', 1, project='42', fork=True)


test_retries_monitor_saved_context_without_starting_pipelines()
assert "needs.wait.outputs.finished == 'true'" in jobs['collect']['if']
assert jobs['wait']['permissions'] == {'actions': 'write', 'checks': 'write'}
assert jobs['collect']['permissions'] == {'contents': 'read', 'actions': 'read', 'pull-requests': 'write'}
assert jobs['collect']['concurrency']['cancel-in-progress'] == 'false'
assert 'needs.wait.outputs.pipeline_id' in jobs['collect']['concurrency']['group']
for environment in [workflow['env'], *(job.get('env', {}) for job in jobs.values())]:
    assert not {'GITLAB_TOKEN', 'GITLAB_TRIGGER_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN'} & environment.keys()
prepare = by_name['Prepare artifact download']
assert prepare['working-directory'] == '${{ runner.temp }}'
assert 'python3 -I -m venv ' in prepare['run']
assert ' -I -m pip install --require-hashes --only-binary :all: ' in prepare['run']
requirements = prepare['run'].split("<<'EOF'\n")[1].split('\nEOF\n')[0].replace(' \\\n', ' ').splitlines()
assert requirements and all(re.fullmatch(r'[a-z0-9-]+==[0-9.]+ +--hash=sha256:[0-9a-f]{64}', line) for line in requirements), requirements
assert any(line.startswith('requests==') for line in requirements)
assert 'env' not in prepare
token_scopes = {
    'Authorize the run': {'GH_TOKEN'},
    'Check continuation': {'GH_TOKEN'},
    'Report a failed run to the PR': {'GH_TOKEN'},
    'Validate configuration': {'GITLAB_TOKEN', 'GITLAB_TRIGGER_TOKEN'},
    'Push the selected commit to GitLab': {'GITLAB_TOKEN'},
    'Start GitLab pipeline': {'GITLAB_TRIGGER_TOKEN'},
    'Verify PR commit': {'GH_TOKEN'},
    'Save pipeline context': {'GITLAB_TOKEN', 'GH_TOKEN'},
    'Verify context source': {'GH_TOKEN'},
    'Verify pipeline identity': {'GITLAB_TOKEN'},
    'Follow GitLab jobs': {'GITLAB_TOKEN', 'GITHUB_TOKEN'},
    'Continue monitoring': {'GH_TOKEN'},
    'Verify completed pipeline': {'GITLAB_TOKEN'},
    'Collect GitLab artifacts': {'GITLAB_TOKEN'},
    'Report to the PR': {'GH_TOKEN'},
}
tokens = {'GITLAB_TOKEN', 'GITLAB_TRIGGER_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN'}
for step in steps:
    actual = tokens & step.get('env', {}).keys()
    assert actual == token_scopes.get(step['name'], set()), step['name']
    for token in actual:
        expected = '${{ github.token }}' if token in {'GITHUB_TOKEN', 'GH_TOKEN'} else '${{ secrets.' + token + ' }}'
        assert step['env'][token] == expected
assert by_name['Store pipeline context']['with']['name'] == 'hpc-context'
assert 'overwrite' not in by_name['Store pipeline context']['with']
assert by_name['Download pipeline context']['with']['run-id'] == '${{ env.CONTEXT_RUN_ID }}'
assert by_name['Upload GitLab artifacts']['with']['overwrite'] == 'true'
assert by_name['Upload GitLab artifacts']['with']['if-no-files-found'] == 'warn'
assert by_name['Store pipeline context']['with']['if-no-files-found'] == 'error'
assert jobs['collect']['env']['PR'] == '${{ needs.wait.outputs.pull_request }}'
assert "always()" in by_name['Upload GitLab artifacts']['if']
assert "always()" in by_name['Report to the PR']['if']
assert "steps.identity.outcome == 'success'" in by_name['Report to the PR']['if']
assert by_name['Follow GitLab jobs']['continue-on-error'] == 'true'
assert by_name['Follow GitLab jobs']['env']['MAX_WAIT_MINUTES'] == '${{ inputs.max_wait_minutes }}'
assert by_name['Verify context source']['env']['MAX_WAIT_MINUTES'] == '${{ inputs.max_wait_minutes }}'
assert by_name['Collect GitLab artifacts']['env']['PIPELINE_ID'] == '${{ env.PIPELINE_ID }}'
assert by_name['Follow GitLab jobs']['env']['TARGET_SHA'] == '${{ steps.identity.outputs.sha }}'
assert by_name['Follow GitLab jobs']['env']['CHECK_PREFIX'] == 'HPC ${{ steps.identity.outputs.pipeline_id }} / '
assert by_name['Follow GitLab jobs']['env']['SET_STATUS'] == 'false'
assert by_name['Follow GitLab jobs']['env']['STOP_ON_MANUAL'] == 'true'
checkout = by_name['Check out the selected commit']
mirror = by_name['Push the selected commit to GitLab']
assert checkout in jobs['start']['steps'] and mirror in jobs['start']['steps']
assert checkout['with'] == {'ref': '${{ env.HPC_SOURCE_SHA || github.sha }}', 'fetch-depth': '0',
                            'persist-credentials': 'false'}
assert mirror['env'] == {'MODE': 'mirror', 'GITLAB_TOKEN': '${{ secrets.GITLAB_TOKEN }}',
                         'MIRROR_SHA': '${{ env.HPC_SOURCE_SHA || github.sha }}',
                         'MIRROR_BRANCH': "${{ env.HPC_SOURCE_SHA && format('hpc-pr-{0}-{1}', env.HPC_PULL_REQUEST, env.HPC_SOURCE_SHA) || github.ref_name }}",
                         'MIRROR_ONLY': 'true', 'FORCE_PUSH': 'true'}
assert steps.index(checkout) < steps.index(mirror) < steps.index(by_name['Start GitLab pipeline'])
assert 'MIRROR_WAIT_MINUTES' not in by_name['Start GitLab pipeline']['env']

with tempfile.TemporaryDirectory(prefix='workflow.', dir=task) as directory:
    fixture = Path(directory)
    assert fixture.resolve().parent == task.resolve()
    bin_dir = fixture / 'bin'
    bin_dir.mkdir()
    curl = bin_dir / 'curl'
    curl.write_text(f'#!{sys.executable}\n' + '''
import json
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse
args = sys.argv[1:]
url = args[-1]
method = args[args.index('--request') + 1] if '--request' in args else 'GET'
body = json.loads(args[args.index('--data') + 1]) if '--data' in args else None
with open(os.environ['REQUEST_LOG'], 'a') as log:
    log.write(json.dumps({'url': url, 'method': method, 'body': body}) + '\\n')
if url.endswith('/trigger/pipeline'):
    if 'MOCK_TRIGGER_RESPONSE' in os.environ:
        print(os.environ['MOCK_TRIGGER_RESPONSE'])
        sys.exit(0)
    attempts = sum('/trigger/pipeline' in line for line in Path(os.environ['REQUEST_LOG']).read_text().splitlines())
    if attempts <= int(os.environ.get('MOCK_TRIGGER_MISSING', '0')):
        print('{"message":{"base":["Reference not found"]}}')
        sys.exit(0)
    print(Path(os.environ['PIPELINE_RESPONSE']).read_text())
elif '/repository/commits/' in url:
    print('{}')
elif '/pipelines/' in url and '/jobs?' not in url and '/bridges?' not in url:
    count_file = Path(os.environ['PIPELINE_READ_COUNT'])
    count = int(count_file.read_text()) if count_file.exists() else 0
    count_file.write_text(str(count + 1))
    if 0 < count <= int(os.environ.get('MOCK_POLL_FAILURES', '0')):
        print('curl: (22) The requested URL returned error: 502', file=sys.stderr)
        sys.exit(22)
    if count and 'MOCK_POLL_RESPONSE' in os.environ:
        print(os.environ['MOCK_POLL_RESPONSE'])
        sys.exit(int(os.environ.get('MOCK_POLL_EXIT', '0')))
    print(Path(os.environ['PIPELINE_RESPONSE']).read_text())
elif '/bridges?' in url:
    page = int(parse_qs(urlparse(url).query).get('page', ['1'])[0])
    parent = '/pipelines/123/' in url
    bridges = [{'name': 'child', 'downstream_pipeline': {'id': 456, 'project_id': 42}},
               {'name': 'other', 'downstream_pipeline': {'id': 789, 'project_id': 7}}]
    print(json.dumps(bridges if parent and page == 1 and os.environ.get('MOCK_CHILD') == 'true' else []))
elif '/jobs?' in url:
    page = int(parse_qs(urlparse(url).query).get('page', ['1'])[0])
    names = ['tests'] + [f'matrix {index}' for index in range(1, int(os.environ.get('MOCK_JOB_COUNT', '1')))]
    if '/pipelines/456/' in url:
        names = ['tests']
    jobs = [{'id': index + 1, 'name': name, 'status': os.environ['MOCK_STATUS'],
             'allow_failure': os.environ.get('MOCK_ALLOW_FAILURE') == 'true',
             'stage': 'check', 'web_url': f'https://git.example/jobs/{index + 1}', 'duration': 60}
            for index, name in enumerate(names)]
    print(json.dumps(jobs[(page - 1) * 100:page * 100]))
elif '/check-runs' in url and method == 'GET':
    print(json.dumps({'check_runs': [{'id': 999, 'name': 'gitlab/42/other/tests'}]}))
elif '/check-runs' in url:
    print('{"id": 111}')
elif url.endswith('/projects/42'):
    print('{"http_url_to_repo": "https://git.example/example/project.git"}')
else:
    print('{}')
''')
    curl.chmod(0o755)
    date = bin_dir / 'date'
    date.write_text('#!/usr/bin/env bash\nvalue=$(cat "$DATE_CALLED" 2>/dev/null || echo 0)\nvalue=$((value + 100))\necho "$value" > "$DATE_CALLED"\necho "$value"\n')
    date.chmod(0o755)
    sleep = bin_dir / 'sleep'
    sleep.write_text('#!/usr/bin/env bash\nexit 0\n')
    sleep.chmod(0o755)
    git = bin_dir / 'git'
    git.write_text(f'#!{sys.executable}\n' + '''
import json
import os
from pathlib import Path
import sys
with open(os.environ['GIT_ARGUMENT_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'push':
    pushes = sum(json.loads(line)[0] == 'push' for line in Path(os.environ['GIT_ARGUMENT_LOG']).read_text().splitlines())
    if pushes <= int(os.environ.get('MOCK_PUSH_LOCKED', '0')):
        print("remote: error: cannot lock ref 'refs/heads/main': is at " + 'b' * 40 + ' but expected ' + 'c' * 40)
        sys.exit(1)
    print('Everything up-to-date')
    sys.exit(int(os.environ.get('MOCK_PUSH_EXIT', '0')))
''')
    git.chmod(0o755)
    gh = bin_dir / 'gh'
    gh.write_text(f'#!{sys.executable}\n' + '''
import json
import os
from pathlib import Path
import sys
args = sys.argv[1:]
with open(os.environ['GH_REQUEST_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
if args[:2] == ['workflow', 'run']:
    dispatches = sum(json.loads(line)[:2] == ['workflow', 'run'] for line in Path(os.environ['GH_REQUEST_LOG']).read_text().splitlines())
    if dispatches <= int(os.environ.get('MOCK_DISPATCH_FAILURES', '0')):
        sys.exit(1)
    sys.exit(int(os.environ.get('MOCK_DISPATCH_EXIT', '0')))
assert args[0] == 'api', args
endpoint = next(arg for arg in args if arg.startswith('repos/'))
method = args[args.index('--method') + 1] if '--method' in args else 'GET'
if method != 'GET':
    assert method in ('POST', 'PATCH')
    sys.exit(0)
if endpoint == f"repos/{os.environ['GITHUB_REPOSITORY']}":
    value = {'default_branch': os.environ['MOCK_DEFAULT_BRANCH']}
elif '/collaborators/' in endpoint:
    permissions = json.loads(os.environ.get('MOCK_PERMISSIONS', '{}'))
    login = endpoint.split('/collaborators/')[1].split('/')[0]
    if login not in permissions:
        print('gh: Not Found (HTTP 404)', file=sys.stderr)
        sys.exit(1)
    value = {'permission': permissions[login]}
elif '/issues/comments/' in endpoint:
    value = json.loads(os.environ['MOCK_COMMENT'])
elif '/contents/' in endpoint:
    if 'MOCK_CALLER' not in os.environ:
        print('gh: Not Found (HTTP 404)', file=sys.stderr)
        sys.exit(1)
    import base64
    value = {'content': base64.b64encode(os.environ['MOCK_CALLER'].encode()).decode()}
elif '/attempts/' in endpoint and '/jobs' in endpoint:
    value = json.loads(os.environ['MOCK_JOBS'])
elif '/actions/runs/' in endpoint:
    value = {'workflow_id': 88} if endpoint.endswith('/901') else json.loads(Path(os.environ['ORIGIN_RESPONSE']).read_text())
elif endpoint.endswith('/commits') and '/pulls/' in endpoint:
    pr = json.loads(Path(os.environ['PR_RESPONSE']).read_text())
    for sha in [pr['head']['sha']] + os.environ.get('MOCK_PR_COMMITS', '').split():
        print(sha)
    sys.exit(0)
elif '/pulls/' in endpoint:
    value = json.loads(Path(os.environ['PR_RESPONSE']).read_text())
elif endpoint.endswith('/comments'):
    for page in json.loads(Path(os.environ['COMMENTS_RESPONSE']).read_text()):
        print(json.dumps(page))
    sys.exit(0)
else:
    raise AssertionError(endpoint)
print(value[args[args.index('--jq') + 1].lstrip('.')] if '--jq' in args else json.dumps(value))
''')
    gh.chmod(0o755)
    pipeline_file = fixture / 'pipeline.json'
    origin_file = fixture / 'origin.json'
    pr_file = fixture / 'pr.json'
    comments_file = fixture / 'comments.json'
    gh_log = fixture / 'gh.jsonl'
    origin = {'id': 900, 'repository': {'full_name': 'example/project'},
              'head_repository': {'full_name': 'example/project'},
              'workflow_id': 88, 'head_sha': 'a' * 40, 'head_branch': 'main', 'path': '.github/workflows/hpc.yml',
              'event': 'workflow_dispatch'}
    pr = {'state': 'open', 'head': {'sha': 'a' * 40},
          'base': {'repo': {'full_name': 'example/project'}}}
    origin_file.write_text(json.dumps(origin))
    pr_file.write_text(json.dumps(pr))
    comments_file.write_text('[[]]')
    output = fixture / 'output'
    summary = fixture / 'summary'
    request_log = fixture / 'requests'
    pipeline = {'id': 123, 'project_id': 42, 'sha': 'a' * 40, 'ref': 'main',
                'source': 'trigger', 'status': 'success', 'web_url': 'https://git.example/pipelines/123'}
    environment = os.environ | {
        'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'PIPELINE_RESPONSE': str(pipeline_file),
        'REQUEST_LOG': str(request_log), 'TMPDIR': str(fixture), 'TMP': str(fixture), 'TEMP': str(fixture),
        'GITLAB_HOSTNAME': 'git.example', 'GITLAB_PROJECT_ID': '42', 'GITLAB_TOKEN': 'read-token',
        'GITLAB_TRIGGER_TOKEN': 'trigger-token', 'GITHUB_TOKEN': 'github-token',
        'SELECTED_SHA': 'a' * 40, 'SOURCE_SHA': 'a' * 40, 'SOURCE_REF': 'main', 'BENCHMARK': '{}',
        'GITHUB_SHA': 'a' * 40, 'GITHUB_REF_NAME': 'main', 'GITHUB_REF': 'refs/heads/main',
        'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REPOSITORY': 'example/project',
        'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_RUN_ID': '900',
        'CONTEXT_RUN_ID': '900', 'WORKFLOW_ID': '88', 'ORIGIN_SHA': 'a' * 40,
        'ORIGIN_REF': 'main', 'PIPELINE_REF': 'main', 'MOCK_DEFAULT_BRANCH': 'main',
        'PR': '7', 'GH_REQUEST_LOG': str(gh_log), 'ORIGIN_RESPONSE': str(origin_file),
        'PR_RESPONSE': str(pr_file), 'COMMENTS_RESPONSE': str(comments_file),
        'STARTED_AT': '100', 'DOWNLOAD_OUTCOME': 'success', 'UPLOAD_OUTCOME': 'success',
        'STATUS': 'success', 'WEB_URL': 'https://git.example/pipelines/123',
        'EXPECTED_PIPELINE_STATUS': 'success',
        'GITHUB_OUTPUT': str(output), 'GITHUB_STEP_SUMMARY': str(summary),
        'RESUME_ID': '', 'RESUME_SHA': '', 'PIPELINE_ID': '123', 'EXPECTED_SHA': 'a' * 40,
        'POLL_TIMEOUT': '0', 'MAX_WAIT_MINUTES': '0', 'CHECK_RUNS': 'true', 'SUMMARY': 'true',
        'LOG_TRACES': 'false', 'CHECK_PREFIX': 'gitlab/42/123/', 'STATUS_CONTEXT': 'gitlab-ci/123',
        'RUNNER_TEMP': str(fixture), 'MOCK_STATUS': 'success', 'DATE_CALLED': str(fixture / 'date'),
        'SET_STATUS': 'false', 'VARIABLE_PATTERNS': '', 'COLLECT_TIMEOUT_MINUTES': '60',
        'PIPELINE_READ_COUNT': str(fixture / 'pipeline-reads'),
        'GIT_ARGUMENT_LOG': str(fixture / 'git.jsonl'),
    }
    def run(script, overrides=None):
        output.write_text('')
        summary.write_text('')
        request_log.write_text('')
        gh_log.write_text('')
        (fixture / 'git.jsonl').write_text('')
        (fixture / 'pipeline-reads').write_text('0')
        pipeline_file.write_text(json.dumps(pipeline))
        result = subprocess.run(['bash'], input=script, text=True,
                                cwd=fixture, env=environment | (overrides or {}),
                                capture_output=True, timeout=30, check=False)
        return result

    marker = fixture / 'untrusted-python-module'
    for module in ('venv', 'pip'):
        (fixture / f'{module}.py').write_text(
            f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n')
    isolated = fixture / 'isolated-python'
    subprocess.run([sys.executable, '-m', 'venv', str(isolated)],
                   cwd=fixture, env=environment, check=True, capture_output=True, timeout=30)
    assert marker.exists()
    marker.unlink()
    subprocess.run([sys.executable, '-I', '-m', 'venv', '--without-pip', str(isolated)],
                   cwd=fixture, env=environment, check=True, capture_output=True, timeout=30)
    result = subprocess.run([str(isolated / 'bin/python'), '-I', '-m', 'pip', '--version'],
                            cwd=fixture, env=environment, capture_output=True, timeout=30,
                            check=False)
    assert result.returncode != 0
    assert not marker.exists()

    def test_callers_may_omit_dispatch_inputs_but_not_change_them():
        check = by_name['Check caller inputs']['run']
        sha = 'a' * 40
        cases = [({}, {'pull_request': '7', 'source_sha': sha}, True), ({'pull_request': '7'}, {'pull_request': '7'}, True),
                 ({'pull_request': '7'}, None, True), ({'pull_request': '7'}, {'pull_request': ''}, True),
                 ({'pull_request': '8'}, {'pull_request': '7'}, False), ({'source_sha': sha}, {'source_sha': 'b' * 40}, False),
                 ({'command_comment': '1'}, {'command_comment': '2'}, False)]
        for passed, dispatched, accepted in cases:
            result = run(check, {'PASSED': json.dumps(passed | {'benchmark': '{}'}), 'DISPATCHED': json.dumps(dispatched)})
            assert (result.returncode == 0) == accepted, (passed, dispatched, result.stdout)
        assert workflow['env']['HPC_PULL_REQUEST'] == '${{ inputs.pull_request || github.event.inputs.pull_request }}'
        assert workflow['env']['HPC_CONTEXT_RUN_ID'] == '${{ inputs.context_run_id || github.event.inputs.context_run_id }}'
        assert jobs['start']['steps'][0]['name'] == 'Check caller inputs'

    test_callers_may_omit_dispatch_inputs_but_not_change_them()

    def test_only_repository_writers_authorize_prs_and_other_branches():
        authorize = by_name['Authorize the run']['run']
        sha = 'a' * 40
        base = {'EVENT': 'workflow_dispatch', 'ACTOR': 'maintainer', 'PR': '7',
                'COMMENT': '', 'SELECTED_SHA': sha, 'GITHUB_API_URL': 'https://api.github.com',
                'MOCK_PERMISSIONS': json.dumps({'maintainer': 'write', 'owner': 'admin', 'writer': 'write',
                                                'reader': 'read', 'triager': 'read', 'outsider': 'none',
                                                'missing': None})}
        def comment(body, author='maintainer', issue=7):
            return {'COMMENT': '99', 'ACTOR': 'github-actions[bot]', 'MOCK_COMMENT': json.dumps(
                {'body': body, 'user': {'login': author},
                 'issue_url': f'https://api.github.com/repos/example/project/issues/{issue}'})}
        accepted = [{'EVENT': 'push', 'ACTOR': 'anyone'}, {'EVENT': 'schedule', 'ACTOR': 'anyone'},
                    {'PR': '', 'ACTOR': 'github-actions[bot]'}, {'ACTOR': 'maintainer'}, {'ACTOR': 'owner'},
                    {'ACTOR': 'writer'}, {'PR': '', 'ACTOR': 'writer', 'GITHUB_REF': 'refs/heads/feature'},
                    comment(f'/hpc {sha}', author='writer'),
                    comment(f'/hpc {sha}'), comment(f'/hpc {"b" * 40} {sha} checks=gpu'),
                    comment(f'/hpc\n{sha}\n', author='owner')]
        refused = [{'ACTOR': 'stranger'}, {'ACTOR': 'github-actions[bot]'},
                   comment(f'/hpc {"b" * 40}'),
                   comment(f'/hpc {sha}', issue=8), comment(f'please /hpc {sha}'),
                   comment(f'/hpc {sha[:6]}'), comment(f'/hpc checks={sha}')]
        for actor in ('reader', 'triager', 'outsider', 'missing', 'stranger'):
            refused += [{'ACTOR': actor},
                        {'PR': '', 'ACTOR': actor, 'GITHUB_REF': 'refs/heads/feature'},
                        comment(f'/hpc {sha}', author=actor)]
        for overrides in accepted:
            result = run(authorize, base | overrides)
            assert result.returncode == 0, (overrides, result.stdout, result.stderr)
        for overrides in refused:
            result = run(authorize, base | overrides)
            assert result.returncode != 0, (overrides, result.stdout)
        run(authorize, base | {'EVENT': 'push'})
        assert [json.loads(line)[:2] for line in gh_log.read_text().splitlines()] == [['api', 'repos/example/project']]
        for overrides in ({'EVENT': 'pull_request'}, {'EVENT': 'push', 'GITHUB_REF': 'refs/heads/feature'},
                          {'EVENT': 'push', 'GITHUB_REF': 'refs/tags/main'}):
            result = run(authorize, base | overrides)
            assert result.returncode != 0 and 'runs on pushes to main' in result.stdout, (overrides, result.stdout)

    test_only_repository_writers_authorize_prs_and_other_branches()

    def test_command_authorization_requires_the_full_selected_commit_hash():
        reviewed = 'b12dfc7bc9e9ee2b5c37be4e2b40f58b0c8e7630'
        replacement = 'b12dfc7ea13956dab968787fcf9db88b3f524adc'
        base = {'EVENT': 'workflow_dispatch', 'ACTOR': 'github-actions[bot]', 'PR': '7', 'COMMENT': '99',
                'GITHUB_API_URL': 'https://api.github.com', 'MOCK_PERMISSIONS': '{"writer": "write"}'}
        cases = [(reviewed, reviewed, True), (replacement, reviewed, False),
                 (replacement, replacement + 'a', False)]
        cases += [(replacement, replacement[:length], False) for length in (7, 12, 39)]
        for selected, named, accepted in cases:
            comment = {'body': f'/hpc {named}', 'user': {'login': 'writer'},
                       'issue_url': 'https://api.github.com/repos/example/project/issues/7'}
            result = run(by_name['Authorize the run']['run'], base | {
                'SELECTED_SHA': selected, 'MOCK_COMMENT': json.dumps(comment)})
            assert (result.returncode == 0) == accepted, (selected, named, result.stdout, result.stderr)

    test_command_authorization_requires_the_full_selected_commit_hash()

    def test_the_workflow_sets_the_expected_commit_and_checks_caller_variables():
        compose = by_name['Compose pipeline variables']['run']
        sha = 'a' * 40
        def composed(variables, selected=sha):
            result = run(compose, {'PIPELINE_VARIABLES': variables, 'SELECTED_SHA': selected})
            if result.returncode:
                return None, result.stdout
            text = output.read_text()
            delimiter = text.splitlines()[0].removeprefix('lines<<')
            return text.split('\n', 1)[1].split(delimiter)[0].splitlines(), result.stdout
        assert composed('')[0] == [f'EXPECTED_COMMIT_SHA={sha}']
        assert composed(f'SUITE=gpu\n\nNOTE=a=b c\nEXPECTED_COMMIT_SHA={sha}')[0] == [
            f'EXPECTED_COMMIT_SHA={sha}', 'SUITE=gpu', 'NOTE=a=b c']
        for variables, message in [(f'EXPECTED_COMMIT_SHA={"b" * 40}', 'Omit EXPECTED_COMMIT_SHA'),
                                   ('SUITE=cpu\nSUITE=gpu', 'set twice'), ('invalid line', 'KEY=VALUE'),
                                   ('1SUITE=gpu', 'KEY=VALUE')]:
            lines, stdout = composed(variables)
            assert lines is None and message in stdout, (variables, stdout)
        assert composed('', selected='main')[0] is None
        start = jobs['start']['steps']
        names = [step['name'] for step in start]
        assert names.index('Compose pipeline variables') < names.index('Push the selected commit to GitLab')
        assert by_name['Start GitLab pipeline']['env']['PIPELINE_VARIABLES'] == '${{ steps.variables.outputs.lines }}'

    test_the_workflow_sets_the_expected_commit_and_checks_caller_variables()

    def test_variable_patterns_restrict_the_values_reaching_gitlab():
        compose = by_name['Compose pipeline variables']['run']
        patterns = 'HPC_CHECKS=(all|cpu|mpi|gpu)(\\+(all|cpu|mpi|gpu))*\nHPC_JULIA=(all|1\\.10|1\\.13)(\\+(all|1\\.10|1\\.13))*\n'
        def check(variables, patterns=patterns):
            return run(compose, {'PIPELINE_VARIABLES': variables, 'VARIABLE_PATTERNS': patterns, 'SELECTED_SHA': 'a' * 40})
        for variables in ('HPC_CHECKS=all\nHPC_JULIA=all', 'HPC_CHECKS=cpu+gpu\nHPC_JULIA=1.10+1.13'):
            result = check(variables)
            assert result.returncode == 0, (variables, result.stdout)
        for variables, extra, message in [
                ('HPC_CHECKS=gpus\nHPC_JULIA=all', None, 'does not match'),
                ('HPC_CHECKS=all\nHPC_JULIA=1x10', None, 'does not match'),
                ('HPC_CHECKS=all;id\nHPC_JULIA=all', None, 'does not match'),
                ('HPC_CHECKS=all', None, 'does not set'),
                ('HPC_CHECKS=all', 'HPC_CHECKS=(all', 'not a valid'),
                ('HPC_CHECKS=all', 'HPC_CHECKS=', 'NAME=REGEX'),
                ('HPC_CHECKS=all', 'EXPECTED_COMMIT_SHA=.*', 'does not set')]:
            result = check(variables, extra if extra is not None else patterns)
            assert result.returncode != 0 and message in result.stdout, (variables, extra, result.stdout)
        assert check('SUITE=gpu', '').returncode == 0

    test_variable_patterns_restrict_the_values_reaching_gitlab()

    def test_configuration_errors_name_the_input_to_fix():
        validate = by_name['Validate configuration']['run']
        for overrides, message in [({'GITLAB_PROJECT_ID': 'group/project'}, 'gitlab_project_id'),
                                   ({'GITLAB_HOSTNAME': 'https://git.example'}, 'gitlab_hostname'),
                                   ({'GITLAB_TOKEN': ''}, 'GITLAB_TOKEN'), ({'PR': 'seven'}, 'pull_request must'),
                                   ({'PR': '', 'SELECTED_SHA': 'a' * 40}, 'source_sha needs pull_request'),
                                   ({'SELECTED_SHA': 'a' * 7}, 'full 40 character'), ({'BENCHMARK': '[]'}, 'benchmark must'),
                                   ({'EXPECTED_PIPELINE_STATUS': 'canceled'}, 'expected_pipeline_status'),
                                   ({'COLLECT_TIMEOUT_MINUTES': '361'}, 'collect_timeout_minutes'),
                                   ({'COLLECT_TIMEOUT_MINUTES': 'long'}, 'collect_timeout_minutes')]:
            result = run(validate, {'SELECTED_SHA': ''} | overrides)
            assert result.returncode != 0 and f'::error::' in result.stdout and message in result.stdout, (overrides, result.stdout)
        final = by_name['Set final result']['run']
        for overrides, message in [({'STATUS': 'failed'}, 'finished with failed'), ({'DOWNLOAD_OUTCOME': 'failure'}, 'Downloading'),
                                   ({'UPLOAD_OUTCOME': 'failure'}, 'Uploading')]:
            result = run(final, overrides)
            assert result.returncode != 0 and message in result.stdout, (overrides, result.stdout)

    test_configuration_errors_name_the_input_to_fix()

    def test_continuation_problems_are_reported_at_start():
        check = by_name['Check continuation']['run']
        good = 'on:\n  workflow_dispatch:\n    inputs:\n      context_run_id:\n        type: string\n'
        for overrides, warning in [({'MOCK_CALLER': good}, None), ({}, 'is missing on main'),
                                   ({'MOCK_CALLER': 'on:\n  workflow_dispatch:\n'}, 'lacks the workflow_dispatch input'),
                                   ({'MOCK_CALLER': 'on:\n  push:\n'}, 'lacks the workflow_dispatch input')]:
            result = run(check, overrides)
            assert result.returncode == 0, (overrides, result.stdout, result.stderr)
            assert ('::warning::' in result.stdout) == bool(warning) and (not warning or warning in result.stdout), result.stdout
        calls = [json.loads(line) for line in gh_log.read_text().splitlines()]
        assert any(call[1] == 'repos/example/project/contents/.github/workflows/hpc.yml?ref=main' for call in calls)

    test_continuation_problems_are_reported_at_start()

    def test_runs_failing_before_collection_are_reported_to_the_pr():
        collect = jobs['collect']
        assert "needs.wait.outputs.finished == 'true' ||" in collect['if']
        assert "failure()" in collect['if'] and 'github.event.inputs.pull_request' in collect['if']
        assert collect['permissions'] == {'contents': 'read', 'actions': 'read', 'pull-requests': 'write'}
        assert collect['concurrency']['group'].endswith("${{ needs.wait.outputs.pipeline_id || github.run_id }}")
        guarded = {step['name']: step['if'] for step in collect['steps']}
        for name in ('Verify completed pipeline', 'Prepare artifact download', 'Collect GitLab artifacts'):
            assert guarded[name] == "env.FINISHED == 'true'", name
        assert guarded['Report a failed run to the PR'] == "env.FINISHED != 'true'"
        assert collect['steps'][-1]['name'] == 'Report a failed run to the PR'
        comment = by_name['Report a failed run to the PR']['run']
        failed_jobs = {'jobs': [{'name': 'hpc / Start on GitLab', 'conclusion': 'failure',
                                 'steps': [{'name': 'Validate configuration', 'conclusion': 'success'},
                                           {'name': 'Verify PR commit', 'conclusion': 'failure'}]}]}
        result = run(comment, {'PR': '7', 'GITHUB_RUN_ATTEMPT': '1', 'MOCK_JOBS': json.dumps(failed_jobs)})
        assert result.returncode == 0, (result.stdout, result.stderr)
        posts = [call for call in map(json.loads, gh_log.read_text().splitlines()) if '--method' in call]
        assert len(posts) == 1 and posts[0][posts[0].index('--method') + 1] == 'POST'
        body = next(arg for arg in posts[0] if arg.startswith('body='))
        assert 'hpc / Start on GitLab, step Verify PR commit' in body and 'a' * 40 in body and '/actions/runs/900' in body
        assert run(comment, {'PR': '', 'MOCK_JOBS': json.dumps(failed_jobs)}).returncode == 0
        assert not any('--method' in call for call in map(json.loads, gh_log.read_text().splitlines()))

    test_runs_failing_before_collection_are_reported_to_the_pr()

    validate = by_name['Validate configuration']['run']
    assert run(validate).returncode == 0
    for overrides in ({'PR': 'bad'}, {'GITLAB_TOKEN': ''}, {'GITLAB_TRIGGER_TOKEN': ''},
                      {'GITLAB_PROJECT_ID': 'bad'}, {'GITLAB_HOSTNAME': 'bad/path'}):
        assert run(validate, overrides).returncode != 0, overrides

    verify_pr = by_name['Verify PR commit']['run']
    assert run(verify_pr).returncode == 0
    for key, value in [('state', 'closed'), ('head', {'sha': 'b' * 40}),
                       ('base', {'repo': {'full_name': 'other/project'}})]:
        changed = pr | {key: value}
        pr_file.write_text(json.dumps(changed))
        assert run(verify_pr).returncode != 0, key
        assert not request_log.read_text()
    pr_file.write_text(json.dumps(pr | {'head': {'sha': 'b' * 40}}))
    assert run(verify_pr, {'MOCK_PR_COMMITS': 'a' * 40}).returncode == 0
    assert run(verify_pr, {'MOCK_PR_COMMITS': 'c' * 40}).returncode != 0
    pr_file.write_text(json.dumps(pr))

    saved = run(by_name['Save pipeline context']['run'])
    assert saved.returncode == 0, (saved.stderr, saved.stdout)
    context_file = fixture / 'hpc-context/context.json'
    context = json.loads(context_file.read_text())
    assert context['pipeline_id'] == 123 and context['sha'] == 'a' * 40
    assert context['pull_request'] == '7' and context['run_id'] == 900
    assert context['expected_pipeline_status'] == 'success'
    assert not any('token' in key.lower() for key in context)

    verify_origin = by_name['Verify context source']['run']
    monitoring = {'MAX_WAIT_MINUTES': '330'}
    assert run(verify_origin, monitoring).returncode == 0
    for key, value in [('event', 'pull_request'), ('workflow_id', 99),
                       ('repository', {'full_name': 'other/project'}),
                       ('head_repository', {'full_name': 'other/project'})]:
        origin_file.write_text(json.dumps(origin | {key: value}))
        assert run(verify_origin, monitoring | {'GITHUB_RUN_ID': '901'}).returncode != 0, key
        assert not output.read_text()
    origin_file.write_text(json.dumps(origin))
    assert run(verify_origin, monitoring | {'CONTEXT_RUN_ID': 'bad'}).returncode != 0
    origin_file.write_text(json.dumps(origin | {'event': 'push'}))
    assert run(verify_origin, monitoring).returncode == 0
    origin_file.write_text(json.dumps(origin | {'event': 'push', 'head_branch': 'feature'}))
    assert run(verify_origin, monitoring).returncode != 0
    origin_file.write_text(json.dumps(origin | {'event': 'push', 'head_branch': 'trunk'}))
    assert run(verify_origin, monitoring | {'MOCK_DEFAULT_BRANCH': 'trunk'}).returncode == 0
    assert run(verify_origin, monitoring).returncode != 0
    origin_file.write_text(json.dumps(origin))
    for minutes in ('0', '331', 'bad', ''):
        assert run(verify_origin, {'MAX_WAIT_MINUTES': minutes}).returncode != 0, minutes
    assert run(verify_origin, {'MAX_WAIT_MINUTES': '1'}).returncode == 0
    assert run(verify_origin, monitoring | {'GITHUB_REF_NAME': 'other', 'GITHUB_RUN_ID': '901'}).returncode == 0

    identity = by_name['Verify pipeline identity']['run']
    assert run(identity).returncode == 0
    assert f'sha={"a" * 40}' in output.read_text()
    assert run(identity, {'GITHUB_RUN_ID': '901', 'GITHUB_SHA': 'c' * 40,
                          'GITHUB_REF_NAME': 'other', 'GITLAB_TRIGGER_TOKEN': '',
                          'PR': '8'}).returncode == 0
    assert 'pull_request=7' in output.read_text()
    def test_expected_status_is_preserved_across_continuation_and_defaults_for_older_contexts():
        saved = run(by_name['Save pipeline context']['run'], {'EXPECTED_PIPELINE_STATUS': 'failed'})
        assert saved.returncode == 0, saved.stderr
        assert json.loads(context_file.read_text())['expected_pipeline_status'] == 'failed'
        assert run(identity, {'EXPECTED_PIPELINE_STATUS': 'success', 'GITHUB_RUN_ID': '901'}).returncode == 0
        assert 'expected_pipeline_status=failed' in output.read_text()
        legacy = {key: value for key, value in context.items() if key != 'expected_pipeline_status'}
        context_file.write_text(json.dumps(legacy))
        assert run(identity, {'EXPECTED_PIPELINE_STATUS': 'failed'}).returncode == 0
        assert 'expected_pipeline_status=success' in output.read_text()
        for invalid in ('canceled', '', True, False, None):
            context_file.write_text(json.dumps(context | {'expected_pipeline_status': invalid}))
            assert run(identity).returncode != 0
        context_file.write_text(json.dumps(context))
    test_expected_status_is_preserved_across_continuation_and_defaults_for_older_contexts()
    selected = context | {'sha': 'b' * 40, 'ref': 'hpc-pr-7-' + 'b' * 40,
                          'benchmark': {'mode': 'compare', 'suites': [{'name': 'CPU'}]}}
    context_file.write_text(json.dumps(selected))
    original_pipeline = pipeline.copy()
    pipeline.update(sha=selected['sha'], ref=selected['ref'])
    assert run(identity).returncode == 0
    assert f'sha={"b" * 40}' in output.read_text()
    assert '"mode":"compare"' in output.read_text()
    pipeline.clear()
    pipeline.update(original_pipeline)
    context_file.write_text(json.dumps(context))
    for key, value in [('repository', 'other/project'), ('hostname', 'other.invalid'),
                       ('project_id', 43), ('run_id', 901), ('workflow_id', 99),
                       ('workflow_sha', 'b' * 40), ('workflow_ref', 'other'), ('pipeline_id', 'bad'),
                       ('pull_request', 'bad'), ('started_at', -1)]:
        context_file.write_text(json.dumps(context | {key: value}))
        assert run(identity).returncode != 0, key
        assert not request_log.read_text()
        assert not output.read_text()
    context_file.write_text(json.dumps(context))
    for key, value in [('id', 124), ('project_id', 1), ('sha', 'b' * 40),
                       ('ref', 'other'), ('source', 'push')]:
        original = pipeline[key]
        pipeline[key] = value
        assert run(identity).returncode != 0, key
        assert not output.read_text()
        pipeline[key] = original

    resume = by_name['Continue monitoring']['run']
    assert run(resume, {'GITHUB_RUN_ID': '901', 'GITHUB_SHA': 'c' * 40,
                        'GITHUB_REF_NAME': 'unreviewed-branch'}).returncode == 0
    calls = [json.loads(line) for line in gh_log.read_text().splitlines()]
    assert calls == [['api', 'repos/example/project', '--jq', '.default_branch'],
                     ['workflow', 'run', '88', '--repo', 'example/project',
                      '--ref', 'main', '--field', 'context_run_id=900']]
    assert not request_log.read_text()
    assert run(resume, {'MOCK_DEFAULT_BRANCH': 'trunk'}).returncode == 0
    assert ['--ref', 'trunk'] == [json.loads(line) for line in gh_log.read_text().splitlines()][-1][5:7]
    assert run(resume, {'MOCK_DEFAULT_BRANCH': ''}).returncode != 0
    assert not any(call[0] == 'workflow' for call in map(json.loads, gh_log.read_text().splitlines()))
    assert run(resume, {'MOCK_DISPATCH_EXIT': '1'}).returncode != 0
    assert sum(call[:2] == ['workflow', 'run'] for call in map(json.loads, gh_log.read_text().splitlines())) == 5

    def test_continuation_dispatch_survives_transient_api_errors():
        result = run(resume, {'MOCK_DISPATCH_FAILURES': '2'})
        assert result.returncode == 0, result.stdout
        calls = [json.loads(line) for line in gh_log.read_text().splitlines()]
        assert sum(call[:2] == ['workflow', 'run'] for call in calls) == 3
        assert 'continue monitoring' in summary.read_text()

    test_continuation_dispatch_survives_transient_api_errors()
    (fixture / 'date').write_text('604800')
    assert run(resume).returncode != 0
    assert not any(call[0] == 'workflow' for call in map(json.loads, gh_log.read_text().splitlines()))
    (fixture / 'date').write_text('0')

    completed = by_name['Verify completed pipeline']['run']
    assert run(completed, {'GITHUB_REF_NAME': 'other'}).returncode == 0
    pipeline['status'] = 'manual'
    assert run(completed).returncode == 0 and 'status=manual' in output.read_text()
    pipeline['status'] = 'success'
    for key, value in [('status', 'running'), ('sha', 'b' * 40),
                       ('project_id', 1), ('id', 124), ('ref', 'other'), ('source', 'push')]:
        original = pipeline[key]
        pipeline[key] = value
        assert run(completed).returncode != 0, key
        assert not output.read_text()
        pipeline[key] = original

    report = by_name['Report to the PR']['run']
    pr_file.write_text(json.dumps(pr | {'head': {'sha': 'c' * 40}}))
    assert run(report, {'GITHUB_SHA': 'c' * 40, 'GITHUB_RUN_ID': '901'}).returncode == 0
    calls = [json.loads(line) for line in gh_log.read_text().splitlines()]
    writes = [call for call in calls if '--method' in call]
    assert len(writes) == 1 and 'POST' in writes[0]
    assert 'repos/example/project/issues/7/comments' in writes[0]
    body = next(arg for arg in writes[0] if arg.startswith('body='))
    assert 'a' * 40 in body and 'c' * 40 not in body
    assert '<!-- hpc-cb:42:123 -->' in body
    comments_file.write_text(json.dumps([
        [{'id': 11, 'user': {'login': 'someone'}, 'body': '<!-- hpc-cb:42:123 -->'}],
        [{'id': 12, 'user': {'login': 'github-actions[bot]'}, 'body': '<!-- hpc-cb:42:123 -->'}],
    ]))
    assert run(report, {'STATUS': 'failed', 'UPLOAD_OUTCOME': 'failure'}).returncode == 0
    calls = [json.loads(line) for line in gh_log.read_text().splitlines()]
    writes = [call for call in calls if '--method' in call]
    assert len(writes) == 1 and 'PATCH' in writes[0]
    assert 'repos/example/project/issues/comments/12' in writes[0]
    assert any('**failed**' in arg and '**failure**' in arg for arg in writes[0])
    pr_file.write_text(json.dumps(pr | {'base': {'repo': {'full_name': 'other/project'}}}))
    assert run(report).returncode != 0
    assert not any('--method' in json.loads(line) for line in gh_log.read_text().splitlines())
    pr_file.write_text(json.dumps(pr))

    final = by_name['Set final result']['run']
    assert run(final).returncode == 0
    assert 'Collected 0 GitLab job archives.' in summary.read_text()
    (fixture / 'hpc-artifacts').mkdir(exist_ok=True)
    (fixture / 'hpc-artifacts' / 'tests.zip').write_bytes(b'zip')
    assert run(final).returncode == 0
    assert 'Collected 1 GitLab job archives.' in summary.read_text()
    for overrides in ({'STATUS': 'failed'}, {'STATUS': 'canceled'}, {'STATUS': 'manual'},
                      {'DOWNLOAD_OUTCOME': 'failure'}, {'UPLOAD_OUTCOME': 'failure'}):
        assert run(final, overrides).returncode != 0, overrides
    def test_expected_failure_does_not_hide_artifact_errors_or_unexpected_success():
        expected_failure = {'STATUS': 'failed', 'EXPECTED_PIPELINE_STATUS': 'failed'}
        assert run(final, expected_failure).returncode == 0
        for override in ({'STATUS': 'success'}, {'STATUS': 'canceled'}, {'STATUS': 'skipped'}, {'STATUS': 'manual'},
                         {'DOWNLOAD_OUTCOME': 'failure'}, {'UPLOAD_OUTCOME': 'failure'},
                         {'EXPECTED_PIPELINE_STATUS': 'canceled'}):
            assert run(final, expected_failure | override).returncode != 0, override
    test_expected_failure_does_not_hide_artifact_errors_or_unexpected_success()
    def test_integration_verifies_the_raw_pipeline_status_and_requires_a_successful_workflow():
        verify = next(step['run'] for step in integration['jobs']['verify']['steps']
                      if step.get('name') == 'Verify the GitHub result')
        expected = {'SCENARIO': 'handover_failure', 'COLLECTED': 'true',
                    'HPC_RESULT': 'success', 'PIPELINE_STATUS': 'failed'}
        assert run(verify, expected).returncode == 0
        for override in ({'HPC_RESULT': 'failure'}, {'PIPELINE_STATUS': 'success'},
                         {'PIPELINE_STATUS': ''}):
            assert run(verify, expected | override).returncode != 0
        assert run(verify, expected | {'COLLECTED': 'false', 'PIPELINE_STATUS': ''}).returncode == 0
    test_integration_verifies_the_raw_pipeline_status_and_requires_a_successful_workflow()
    result_check = by_name['Verify monitoring result']['run']
    assert run(result_check, {'FINISHED': ''}).returncode != 0
    assert run(result_check, {'FINISHED': 'false'}).returncode == 0
    assert run(result_check, {'FINISHED': 'true'}).returncode == 0

    mirror_script = (action / 'mirror.sh').read_text()
    assert run(mirror_script, {'MIRROR_SHA': 'a' * 40, 'MIRROR_BRANCH': 'main',
                               'MIRROR_ONLY': 'true', 'FORCE_PUSH': 'true'}).returncode == 0
    arguments = [json.loads(line) for line in (fixture / 'git.jsonl').read_text().splitlines()]
    assert ['push', '--force', 'gitlab', 'a' * 40 + ':refs/heads/main'] in arguments
    assert not any(args[0] in ('fetch', 'checkout', 'pull') for args in arguments)
    assert not any(json.loads(line)['method'] == 'POST' for line in request_log.read_text().splitlines())
    assert run(mirror_script, {'MIRROR_SHA': 'a' * 40, 'MIRROR_ONLY': 'true',
                               'MOCK_PUSH_EXIT': '1'}).returncode != 0
    arguments = [json.loads(line) for line in (fixture / 'git.jsonl').read_text().splitlines()]
    assert sum(args[0] == 'push' for args in arguments) == 1

    def test_mirror_retries_pushes_rejected_by_a_locked_branch():
        for locked, expected, pushes in [('1', 0, 2), ('9', 1, 5)]:
            result = run(mirror_script, {'MIRROR_SHA': 'a' * 40, 'MIRROR_BRANCH': 'main',
                                         'MIRROR_ONLY': 'true', 'FORCE_PUSH': 'true',
                                         'MOCK_PUSH_LOCKED': locked})
            assert (result.returncode != 0) == bool(expected), result.stdout
            arguments = [json.loads(line) for line in (fixture / 'git.jsonl').read_text().splitlines()]
            assert sum(args[0] == 'push' for args in arguments) == pushes

    test_mirror_retries_pushes_rejected_by_a_locked_branch()

    def test_mirror_preserves_the_optional_unchanged_branch_trigger():
        for mirror_only in ('', 'false', 'true'):
            result = run(mirror_script, {'MIRROR_SHA': 'a' * 40,
                                         'MIRROR_ONLY': mirror_only})
            assert result.returncode == 0, result.stderr
            requests = [json.loads(line) for line in request_log.read_text().splitlines()]
            triggers = [r for r in requests if r['method'] == 'POST']
            assert len(triggers) == (0 if mirror_only == 'true' else 1)
            assert all(r['url'].endswith('/projects/42/pipeline') for r in triggers)

    test_mirror_preserves_the_optional_unchanged_branch_trigger()

    trigger = (action / 'trigger.sh').read_text()
    assert run(trigger, {'PIPELINE_REF': 'main',
                         'PIPELINE_VARIABLES': f'EXPECTED_COMMIT_SHA={"a" * 40}'}).returncode == 0
    requests = [json.loads(line) for line in request_log.read_text().splitlines()]
    assert sum(request['method'] == 'POST' for request in requests) == 1
    assert 'pipeline_id=123' in output.read_text()
    assert run(trigger, {'PIPELINE_VARIABLES': 'invalid line'}).returncode != 0
    assert not request_log.read_text()

    def test_trigger_retries_until_gitlab_knows_the_pushed_ref():
        result = run(trigger, {'PIPELINE_REF': 'main', 'MOCK_TRIGGER_MISSING': '1'})
        assert result.returncode == 0, result.stderr
        requests = [json.loads(line) for line in request_log.read_text().splitlines()]
        assert sum(request['method'] == 'POST' for request in requests) == 2
        assert 'pipeline_id=123' in output.read_text()
        result = run(trigger, {'PIPELINE_REF': 'main', 'MOCK_TRIGGER_MISSING': '99'})
        assert result.returncode != 0
        assert 'Reference not found' in result.stdout
        assert 'pipeline_id=' not in output.read_text()
        result = run(trigger, {'PIPELINE_REF': 'main', 'MOCK_TRIGGER_RESPONSE': '{"message":"401 Unauthorized"}'})
        assert result.returncode != 0
        requests = [json.loads(line) for line in request_log.read_text().splitlines()]
        assert sum(request['method'] == 'POST' for request in requests) == 1

    test_trigger_retries_until_gitlab_knows_the_pushed_ref()

    poll = (action / 'get_ci_state.sh').read_text()
    for status, expected in [('success', 0), ('failed', 1), ('canceled', 1), ('skipped', 1)]:
        pipeline['status'] = status
        result = run(poll, {'MOCK_STATUS': status})
        assert result.returncode == expected, (status, result.stderr, result.stdout)
        assert 'finished=true' in output.read_text()
        assert f'status={status}' in output.read_text()
        requests = [json.loads(line) for line in request_log.read_text().splitlines()]
        assert not any('/statuses/' in request['url'] for request in requests)
        check_requests = [r for r in requests if '/check-runs' in r['url'] and r['method'] != 'GET']
        assert len(check_requests) == 2
        assert all(r['method'] == 'POST' for r in check_requests)
        assert all(r['body']['name'].startswith('gitlab/42/123/') for r in check_requests)
        assert all(r['body']['head_sha'] == 'a' * 40 for r in check_requests)
        assert 'tests' in summary.read_text()

    def test_waiting_pipelines_resume_without_completed_checks():
        for status in ('created', 'preparing', 'pending', 'running', 'waiting_for_resource',
                       'waiting_for_callback', 'manual', 'scheduled', 'canceling'):
            pipeline['status'] = status
            result = run(poll, {'MOCK_STATUS': status, 'MAX_WAIT_MINUTES': '1'})
            assert result.returncode == 0, (status, result.stderr, result.stdout)
            assert 'finished=false' in output.read_text(), status
            assert f'status={status}' in output.read_text()
            requests = [json.loads(line) for line in request_log.read_text().splitlines()]
            assert not any('/trigger/pipeline' in r['url'] for r in requests)
            checks = [r['body'] for r in requests if '/check-runs' in r['url'] and r['method'] != 'GET']
            assert checks and all(c['status'] != 'completed' for c in checks), status

    def test_optional_manual_jobs_are_skipped_on_successful_pipelines():
        pipeline['status'] = 'success'
        result = run(poll, {'MOCK_STATUS': 'manual', 'MOCK_ALLOW_FAILURE': 'true'})
        assert result.returncode == 0, result.stderr
        requests = [json.loads(line) for line in request_log.read_text().splitlines()]
        checks = [r['body'] for r in requests if '/check-runs' in r['url'] and r['method'] != 'GET']
        assert next(c for c in checks if c['name'].endswith('/tests'))['conclusion'] == 'skipped'
        assert next(c for c in checks if c['name'].endswith('/pipeline'))['conclusion'] == 'success'

    def test_waiting_pipelines_complete_when_the_next_poll_finishes():
        for status in ('waiting_for_resource', 'waiting_for_callback', 'manual', 'scheduled', 'canceling'):
            pipeline['status'] = status
            response = json.dumps(pipeline | {'status': 'success'})
            result = run(poll, {'MOCK_STATUS': 'success', 'MOCK_POLL_RESPONSE': response})
            assert result.returncode == 0, (status, result.stderr, result.stdout)
            assert 'finished=true' in output.read_text()
            assert 'status=success' in output.read_text()

    def test_invalid_poll_responses_never_report_completion():
        for status in (None, 'unknown'):
            pipeline['status'] = status
            result = run(poll, {'MOCK_STATUS': 'pending'})
            assert result.returncode != 0, status
            assert 'finished=true' not in output.read_text()
        pipeline['status'] = 'pending'
        for response in ('{}', '{"status": "unknown"}', 'invalid JSON'):
            result = run(poll, {'MOCK_STATUS': 'pending', 'MOCK_POLL_RESPONSE': response})
            assert result.returncode != 0, response
            assert 'finished=true' not in output.read_text()
        result = run(poll, {'MOCK_STATUS': 'pending', 'MOCK_POLL_RESPONSE': '{}', 'MOCK_POLL_EXIT': '22'})
        assert result.returncode != 0
        assert 'finished=true' not in output.read_text()

    def test_monitoring_survives_a_gitlab_outage_and_hands_over_at_the_deadline():
        pipeline['status'] = 'pending'
        response = json.dumps(pipeline | {'status': 'success'})
        result = run(poll, {'MOCK_STATUS': 'success', 'MOCK_POLL_RESPONSE': response, 'MOCK_POLL_FAILURES': '3'})
        assert result.returncode == 0, (result.stderr, result.stdout)
        assert 'finished=true' in output.read_text() and 'status=success' in output.read_text()
        assert 'retrying' in result.stdout
        result = run(poll, {'MOCK_STATUS': 'pending', 'MOCK_POLL_RESPONSE': response,
                            'MOCK_POLL_FAILURES': '1000', 'MAX_WAIT_MINUTES': '30'})
        assert result.returncode == 0, (result.stderr, result.stdout)
        assert 'finished=false' in output.read_text()
        result = run(poll, {'MOCK_STATUS': 'pending', 'MOCK_POLL_RESPONSE': response,
                            'MOCK_POLL_FAILURES': '1000', 'MAX_WAIT_MINUTES': '0'})
        assert result.returncode != 0
        assert 'finished=' not in output.read_text()
        assert 'for 30 minutes' in result.stdout
        pipeline['status'] = 'unknown'
        result = run(poll, {'MOCK_STATUS': 'pending', 'MAX_WAIT_MINUTES': '30'})
        pipeline['status'] = 'pending'
        assert result.returncode == 0, (result.stderr, result.stdout)
        assert 'finished=false' in output.read_text()
        assert not any('/check-runs' in json.loads(line)['url'] for line in request_log.read_text().splitlines())

    def test_job_checks_cover_all_pages_and_child_pipelines():
        pipeline['status'] = 'success'
        result = run(poll, {'MOCK_STATUS': 'success', 'MOCK_JOB_COUNT': '150', 'MOCK_CHILD': 'true'})
        assert result.returncode == 0, (result.stderr, result.stdout)
        requests = [json.loads(line) for line in request_log.read_text().splitlines()]
        names = {r['body']['name'] for r in requests if '/check-runs' in r['url'] and r['method'] != 'GET'}
        assert len(names) == 152, len(names)
        assert {'gitlab/42/123/matrix 149', 'gitlab/42/123/child/tests', 'gitlab/42/123/pipeline'} <= names
        assert not any('/pipelines/789/' in r['url'] for r in requests)
        assert 'child/tests' in summary.read_text()

    test_monitoring_survives_a_gitlab_outage_and_hands_over_at_the_deadline()
    test_job_checks_cover_all_pages_and_child_pipelines()

    def test_artifact_collection_covers_all_pages_and_child_pipelines():
        import importlib.util
        import types

        class Response:
            def __init__(self, payload=None, broken=False):
                self.payload, self.broken = payload, broken
            def json(self):
                return self.payload
            def raise_for_status(self):
                pass
            def iter_content(self, chunk_size):
                yield b'partial'
                if self.broken:
                    raise ConnectionError('transfer interrupted')
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        archive = [{'file_type': 'archive', 'file_format': 'zip'}]
        broken = set()
        def get(url, headers=None, params=None, stream=False, timeout=None):
            assert timeout, url
            page = (params or {}).get('page', 1)
            if url.endswith('/pipelines/123/jobs'):
                jobs = [{'id': index, 'name': f'job {index}', 'stage': 'check', 'artifacts': archive} for index in range(150)]
                return Response(jobs[(page - 1) * 100:page * 100])
            if url.endswith('/pipelines/456/jobs'):
                return Response([{'id': 1000, 'name': 'job 0', 'stage': 'check', 'artifacts': archive}] if page == 1 else [])
            if url.endswith('/pipelines/123/bridges'):
                return Response([{'name': 'child', 'downstream_pipeline': {'id': 456, 'project_id': 42}},
                                 {'name': 'other', 'downstream_pipeline': {'id': 789, 'project_id': 7}}] if page == 1 else [])
            if url.endswith('/bridges'):
                return Response([])
            assert url.endswith('/artifacts') and stream, url
            return Response(broken=url.split('/')[-2] in broken)

        fake = types.ModuleType('requests')
        fake.get = get
        directory = fixture / 'collected'
        settings = {'GITLAB_HOSTNAME': 'git.example', 'GITLAB_PROJECT_ID': '42', 'GITLAB_TOKEN': 'read-token',
                    'PIPELINE_ID': '123', 'ARTIFACT_DIR': str(directory)}
        saved_environment, saved_requests = dict(os.environ), sys.modules.get('requests')
        os.environ.update(settings)
        sys.modules['requests'] = fake
        sys.dont_write_bytecode = True
        try:
            spec = importlib.util.spec_from_file_location('get_artifact', action / 'get_artifact.py')
            collector = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(collector)
            jobs = collector.get_job_list()
            assert len(jobs) == 151 and jobs[-1]['name'] == 'child/job 0'
            collector.download_artifacts(jobs)
            files = {path.name for path in directory.iterdir()}
            assert len(files) == 151 and {'job_149.zip', 'child_job_0.zip'} <= files
            for path in directory.iterdir():
                path.unlink()
            broken.add('7')
            try:
                collector.download_artifacts(jobs)
            except ConnectionError:
                pass
            else:
                raise AssertionError('An interrupted transfer must fail the collection.')
            assert not (directory / 'job_7.zip').exists()
            try:
                collector.download_artifacts([jobs[0], jobs[0]])
            except ValueError as error:
                assert 'share the artifact name' in str(error)
            else:
                raise AssertionError('Colliding artifact names must fail the collection.')
        finally:
            os.environ.clear()
            os.environ.update(saved_environment)
            if saved_requests is None:
                sys.modules.pop('requests', None)
            else:
                sys.modules['requests'] = saved_requests

    test_artifact_collection_covers_all_pages_and_child_pipelines()
    test_waiting_pipelines_resume_without_completed_checks()
    test_optional_manual_jobs_are_skipped_on_successful_pipelines()
    test_waiting_pipelines_complete_when_the_next_poll_finishes()
    test_invalid_poll_responses_never_report_completion()

test_integration_suite_covers_all_scenarios_and_verifies_without_write_access()
print('Workflow Bash parses and the caller preserves the commit and explicit permissions.')
print('The integration workflow runs on main pushes and verifies with read access.')
print('Main pushes, manual and scheduled callers execute and Python setup ignores checkout modules.')
print('Retries reuse saved context without starting another pipeline.')
print('Context ownership and pipeline identity reject mismatched repositories, workflows and commits.')
print('Identity verification rejects mismatched projects, pipelines, branches, commits and sources.')
print('Mirroring pushes the exact commit without an API trigger and triggering starts one pipeline.')
print('Automatic continuation preserves the original context and fails after seven days.')
print('PR reports update one bot comment per pipeline and preserve the original commit.')
print('Failed pipelines and missing artifacts fail the final collection result.')
print('Checks remain isolated by pipeline and target the original commit after the branch advances.')
print('Waiting pipelines resume monitoring and invalid pipeline responses never report completion.')
print('Blocking manual checks remain queued and optional manual checks are skipped.')
