"""Authorize a reviewed PR commit and dispatch its HPC caller."""

import json
import os
import re
import subprocess


def api(path, body=None):
    args = ['gh', 'api', '-H', 'X-GitHub-Api-Version: 2026-03-10', path]
    if body is not None:
        args += ['--method', 'POST', '--input', '-']
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                            text=True, capture_output=True, check=True, timeout=60)
    return json.loads(result.stdout) if result.stdout else None


def authorized_test_pr(pr, login, expected_login, repo):
    return bool(expected_login and login.lower() == expected_login.lower() and
                pr['user']['login'].lower() == expected_login.lower() and
                pr['head']['repo']['full_name'] == repo and
                re.fullmatch(r'hpc-test/[0-9]+-[0-9]+/(pass|fail)', pr['head']['ref']) and
                pr['title'].startswith('HPC integration test '))


def pr_commits(repo, number):
    commits = []
    # GitHub lists at most 250 commits of a PR.
    for page in (1, 2, 3):
        chunk = api(f'repos/{repo}/pulls/{number}/commits?per_page=100&page={page}')
        commits += [commit['sha'] for commit in chunk]
        if len(chunk) < 100:
            break
    return commits


# Options become workflow dispatch inputs of the caller, these inputs are set by the command itself.
RESERVED_INPUTS = {'pull_request', 'source_sha', 'context_run_id', 'command_comment'}


def parse_options(words):
    """Returns the name=value options of the command and the reasons for refusing them."""
    options, reasons = {}, []
    for word in words:
        name, _, value = word.partition('=')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,99}', name) or \
                not re.fullmatch(r'[A-Za-z0-9._:/+-]{1,100}', value):
            reasons.append('Options are written as name=value with letters, digits and ._:/+- in the value.')
        elif name in RESERVED_INPUTS:
            reasons.append(f'The option {name} is set by the command itself.')
        elif name in options:
            reasons.append(f'The option {name} is given twice.')
        else:
            options[name] = value
    return options, reasons


def select_commits(body, commits, head):
    """Returns the PR commits and options named in the command and the reasons for refusing the command."""
    words = body.split()[1:]
    options, reasons = parse_options([word for word in words if '=' in word])
    names = [word for word in words if '=' not in word]
    if not names:
        return [], {}, ['Name the reviewed commits, for example `/hpc ' + head + '`.'] + reasons
    selected = []
    for name in names:
        if not re.fullmatch(r'[0-9a-f]{40}', name):
            reasons.append('Commits require their full 40 character hexadecimal hash.')
            continue
        if name not in commits:
            reasons.append(f'{name} matches no commit of this PR.')
        elif name not in selected:
            selected.append(name)
    return (selected, options, []) if not reasons else ([], {}, reasons)


def main():
    event = json.load(open(os.environ['GITHUB_EVENT_PATH']))
    body = event['comment']['body'].strip()
    if 'pull_request' not in event['issue'] or not re.fullmatch(r'/hpc(\s.*)?', body, re.DOTALL):
        return
    repo = os.environ['GITHUB_REPOSITORY']
    number = event['issue']['number']
    login = event['comment']['user']['login']
    marker = f'<!-- hpc-command:{event["comment"]["id"]} -->'
    pr = api(f'repos/{repo}/pulls/{number}')
    if pr['state'] != 'open':
        raise ValueError('The PR is not open.')
    permission = api(f'repos/{repo}/collaborators/{login}/permission').get('permission')
    if permission not in ('write', 'admin'):
        raise ValueError('The commenter needs repository write access to authorize cluster execution.')
    test = authorized_test_pr(pr, login, os.environ.get('CB_TEST_ACTOR', ''), repo)
    if test:
        files = api(f'repos/{repo}/pulls/{number}/files?per_page=100')
        if len(files) != 1 or files[0]['filename'] != 'benchmarks/pr-fixture.json':
            raise ValueError('The integration PR changed files outside its fixture.')
    # The comment names the reviewed commits, the PR may have received others since the review.
    commits = pr_commits(repo, number)
    if not all(re.fullmatch(r'[0-9a-f]{40}', sha) for sha in commits + [pr['head']['sha']]):
        raise ValueError('Invalid PR commit.')
    selected, options, reasons = select_commits(body, commits, pr['head']['sha'])

    def refuse(reasons):
        api(f'repos/{repo}/issues/{number}/comments',
            dict(body=f'{marker}\n\nNot dispatched.\n\n' + '\n'.join(f'- {reason}' for reason in reasons)))
        raise ValueError(' '.join(reasons))

    if reasons:
        refuse(reasons)
    workflow = os.environ.get('CB_COMMAND_WORKFLOW') or 'hpc-pr.yml'
    described = ''.join(f' {name}={value}' for name, value in options.items())
    lines = []
    try:
        for sha in selected:
            try:
                result = api(f'repos/{repo}/actions/workflows/{workflow}/dispatches',
                             dict(ref=event['repository']['default_branch'], return_run_details=True,
                                  inputs=dict(options, pull_request=str(number), source_sha=sha,
                                              command_comment=str(event['comment']['id']))))
            except subprocess.CalledProcessError as error:
                # GitHub validates the options against the caller's inputs, the first dispatch reports a rejection.
                if lines:
                    raise
                message = ' '.join((error.stderr or '').split())[:300] or 'no details'
                refuse([f'GitHub rejected the dispatch: {message}'])
            lines.append(f'Authorized commit {sha}{described and " with" + described}.\n'
                         f'[HPC run](https://github.com/{repo}/actions/runs/{result["workflow_run_id"]}).')
    finally:
        # Announce every started run, also when a later dispatch fails.
        if lines:
            api(f'repos/{repo}/issues/{number}/comments', dict(body=f'{marker}\n\n' + '\n\n'.join(lines)))


if __name__ == '__main__':
    main()
