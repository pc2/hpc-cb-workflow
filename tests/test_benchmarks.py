import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import benchmark_support as benchmark
import hpc_command
import embed_helpers
import pr_integration


class BenchmarkTests(unittest.TestCase):
    def test_api_failures_include_github_validation_details_without_credentials(self):
        cases = [
            ('gh: Resource not accessible by personal access token (HTTP 403)',
             {'message': 'Resource not accessible by personal access token'}),
            ('gh: Validation Failed (HTTP 422)',
             {'message': 'Validation Failed', 'errors': [{'field': 'head', 'code': 'invalid'}]}),
        ]
        env = dict(GH_TOKEN='automatic-secret', CB_TEST_TOKEN='personal-secret')
        for stderr, body in cases:
            result = subprocess.CompletedProcess([], 1, json.dumps(body),
                                                 stderr + '\nautomatic-secret personal-secret')
            with self.subTest(body=body), patch.dict(os.environ, env), \
                 patch.object(pr_integration.subprocess, 'run', return_value=result):
                with self.assertRaises(RuntimeError) as error:
                    pr_integration.api('repos/pc2/test/pulls', {'head': 'fixture'}, token='personal-secret')
                message = str(error.exception)
                self.assertIn('POST repos/pc2/test/pulls', message)
                self.assertIn(stderr, message)
                self.assertIn(json.dumps(body), message)
                self.assertNotIn('automatic-secret', message)
                self.assertNotIn('personal-secret', message)

    def test_api_success_preserves_json_and_empty_responses(self):
        for response, expected in [(' {"number": 7}', {'number': 7}), ('', None)]:
            with self.subTest(response=response), patch.dict(os.environ, {'GH_TOKEN': 'test-token'}), \
                 patch.object(pr_integration.subprocess, 'run',
                              return_value=subprocess.CompletedProcess([], 0, response, '')):
                self.assertEqual(pr_integration.api('repos/pc2/test/pulls'), expected)

    def test_custom_measurements_reject_duplicate_names_and_invalid_values(self):
        measurement = dict(name='solve', unit='seconds', value=1)
        self.assertEqual(benchmark.validate_results([measurement]), [measurement])
        for data in ([], [measurement, measurement], [dict(measurement, value=float('nan'))],
                     [dict(measurement, value=-1)], [dict(measurement, value=True)]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                benchmark.validate_results(data)

    def test_archive_paths_cannot_escape_the_artifact_directory(self):
        for path in ('/etc/passwd', '../result.json', 'results/../../file', 'a\\b', ''):
            with self.subTest(path=path), self.assertRaises(ValueError):
                benchmark.relative_path(path)

    def test_test_account_is_restricted_to_generated_prs(self):
        pr = dict(user=dict(login='user'), title='HPC integration test pass',
                  head=dict(repo=dict(full_name='pc2/test'), ref='hpc-test/12-1/pass'))
        self.assertTrue(hpc_command.authorized_test_pr(pr, 'user', 'user', 'pc2/test'))
        self.assertFalse(hpc_command.authorized_test_pr(pr, 'other', 'user', 'pc2/test'))
        self.assertFalse(hpc_command.authorized_test_pr(pr, 'user', '', 'pc2/test'))
        self.assertTrue(hpc_command.authorized_test_pr(pr, 'USER', 'User', 'pc2/test'))
        for author in ('other', 'github-actions[bot]'):
            self.assertFalse(hpc_command.authorized_test_pr(pr | {'user': {'login': author}},
                                                          'user', 'user', 'pc2/test'))
        pr['head']['ref'] = 'unreviewed'
        self.assertFalse(hpc_command.authorized_test_pr(pr, 'user', 'user', 'pc2/test'))

    def command(self, body, commits, role='maintain', fail_dispatch_after=None, reject=None,
                permission='write', test_actor=False):
        head = commits[-1]
        pr = dict(state='open', head=dict(sha=head, ref='feature', repo=dict(full_name='pc2/test')),
                  user=dict(login='author'), title='Feature')
        if test_actor:
            pr.update(user=dict(login='maintainer'), title='HPC integration test pass')
            pr['head']['ref'] = 'hpc-test/12-1/pass'
        calls = []

        def api(path, data=None):
            calls.append((path, data))
            if path.endswith('/pulls/7'):
                return pr
            if '/pulls/7/commits' in path:
                page = int(path.rsplit('page=', 1)[1])
                return [dict(sha=sha) for sha in commits[(page - 1) * 100:page * 100]]
            if path.endswith('/permission'):
                return dict(role_name=role, permission=permission)
            if '/pulls/7/files' in path:
                return [dict(filename='benchmarks/pr-fixture.json')]
            if path.endswith('/dispatches'):
                dispatched = sum(call[0].endswith('/dispatches') for call in calls)
                if reject and dispatched > reject[0]:
                    raise subprocess.CalledProcessError(1, 'gh', stderr=reject[1])
                if fail_dispatch_after is not None and dispatched > fail_dispatch_after:
                    raise RuntimeError('dispatch failed')
                return dict(workflow_run_id=dispatched)
            return {}

        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / 'event.json'
            event.write_text(json.dumps(dict(
                issue=dict(number=7, pull_request={}), repository=dict(default_branch='main'),
                comment=dict(id=99, body=body, user=dict(login='maintainer')))))
            env = dict(GITHUB_EVENT_PATH=str(event), GITHUB_REPOSITORY='pc2/test',
                       CB_TEST_ACTOR='maintainer' if test_actor else '')
            error = None
            with patch.dict(os.environ, env), patch.object(hpc_command, 'api', side_effect=api):
                try:
                    hpc_command.main()
                except (ValueError, RuntimeError, subprocess.CalledProcessError) as raised:
                    error = raised
        self.inputs = [data['inputs'] for path, data in calls if path.endswith('/dispatches')]
        rejected = reject[0] if reject else len(self.inputs)
        dispatched = [inputs['source_sha'] for inputs in self.inputs[:rejected]]
        replies = [data['body'] for path, data in calls if path.endswith('/issues/7/comments')]
        return dispatched, replies, error

    def test_command_options_reach_every_dispatch_as_inputs(self):
        commits = ['a' * 40, 'c' * 40]
        dispatched, replies, error = self.command(f'/hpc suite=gpu {"a" * 7} {"c" * 7} threads=4', commits)
        self.assertIsNone(error)
        self.assertEqual(dispatched, commits)
        self.assertTrue(all(inputs['suite'] == 'gpu' and inputs['threads'] == '4' for inputs in self.inputs))
        self.assertTrue(all(inputs['command_comment'] == '99' for inputs in self.inputs))
        self.assertEqual(replies[0].count('with suite=gpu threads=4'), 2)

    def test_command_refuses_invalid_options_without_dispatching(self):
        for body, reason in [(f'/hpc {"c" * 7} source_sha={"d" * 40}', 'set by the command itself'),
                             (f'/hpc {"c" * 7} context_run_id=5', 'set by the command itself'),
                             (f'/hpc {"c" * 7} command_comment=5', 'set by the command itself'),
                             (f'/hpc {"c" * 7} suite=cpu suite=gpu', 'given twice'),
                             (f'/hpc {"c" * 7} suite=a;b', 'name=value'), (f'/hpc {"c" * 7} 1suite=a', 'name=value'),
                             (f'/hpc {"c" * 7} suite=', 'name=value'), ('/hpc suite=gpu', 'Name the reviewed commits')]:
            with self.subTest(body=body):
                dispatched, replies, error = self.command(body, ['c' * 40])
                self.assertIsInstance(error, ValueError)
                self.assertEqual(self.inputs, [])
                self.assertIn('Not dispatched', replies[0])
                self.assertIn(reason, replies[0])
                self.assertNotIn(';', replies[0])

    def test_command_relays_a_rejection_of_the_first_dispatch(self):
        dispatched, replies, error = self.command(
            f'/hpc {"a" * 7} {"c" * 7} undeclared=1', ['a' * 40, 'c' * 40],
            reject=(0, 'gh: Unexpected inputs provided: ["undeclared"] (HTTP 422)\n'))
        self.assertIsInstance(error, ValueError)
        self.assertEqual(dispatched, [])
        self.assertEqual(len(self.inputs), 1)
        self.assertEqual(len(replies), 1)
        self.assertIn('Not dispatched', replies[0])
        self.assertIn('Unexpected inputs provided', replies[0])

    def test_command_announces_started_runs_when_a_later_dispatch_is_rejected(self):
        dispatched, replies, error = self.command(f'/hpc {"a" * 7} {"c" * 7}', ['a' * 40, 'c' * 40],
                                                  reject=(1, 'gh: Server Error (HTTP 500)'))
        self.assertIsInstance(error, subprocess.CalledProcessError)
        self.assertEqual(dispatched, ['a' * 40])
        self.assertEqual(len(replies), 1)
        self.assertIn(f'Authorized commit {"a" * 40}', replies[0])
        self.assertNotIn('Not dispatched', replies[0])

    def test_command_dispatches_each_named_commit_of_the_pr(self):
        commits = ['a' * 40, 'b' * 40, 'c' * 40]
        for body, expected in [(f'/hpc {"c" * 7}', ['c' * 40]), (f'  /hpc {"c" * 40}\n', ['c' * 40]),
                               (f'/hpc {"a" * 7} {"c" * 12} {"a" * 9}', ['a' * 40, 'c' * 40])]:
            with self.subTest(body=body):
                dispatched, replies, error = self.command(body, commits)
                self.assertIsNone(error)
                self.assertEqual(dispatched, expected)
                self.assertEqual(len(replies), 1)
                self.assertTrue(replies[0].startswith('<!-- hpc-command:99 -->'))
                for sha in expected:
                    self.assertIn(f'Authorized commit {sha}', replies[0])

    def test_command_refuses_commits_outside_the_pr_without_dispatching_any(self):
        commits = ['a' * 40, 'a' * 7 + 'b' * 33, 'd' * 40]
        for body, reason in [(f'/hpc {"d" * 7} {"e" * 7}', 'matches no commit'),
                             (f'/hpc {"a" * 7}', 'matches several commits'),
                             ('/hpc', 'Name the reviewed commits'), ('/hpc please', 'seven hex characters')]:
            with self.subTest(body=body):
                dispatched, replies, error = self.command(body, commits)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(dispatched, [])
                self.assertEqual(len(replies), 1)
                self.assertIn('Not dispatched', replies[0])
                self.assertIn(reason, replies[0])
                self.assertNotIn('please', replies[0])

    def test_command_searches_all_pages_of_pr_commits(self):
        commits = [f'{index:040x}' for index in range(1, 231)]
        dispatched, _, error = self.command(f'/hpc {commits[0]}', commits)
        self.assertIsNone(error)
        self.assertEqual(dispatched, [commits[0]])

    def test_command_announces_started_runs_when_a_later_dispatch_fails(self):
        commits = ['a' * 40, 'b' * 40]
        dispatched, replies, error = self.command(f'/hpc {"a" * 7} {"b" * 7}', commits, fail_dispatch_after=1)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(len(replies), 1)
        self.assertIn(f'Authorized commit {"a" * 40}', replies[0])
        self.assertNotIn('b' * 40, replies[0])

    def test_command_ignores_other_comments(self):
        for body in ('/hpcfoo', 'please run /hpc'):
            with self.subTest(body=body):
                dispatched, replies, error = self.command(body, ['c' * 40])
                self.assertEqual(dispatched, [])
                self.assertEqual(replies, [])
                self.assertIsNone(error)

    def test_command_accepts_repository_writers_regardless_of_role_name(self):
        for role, permission in [('write', 'write'), ('maintain', 'write'), ('admin', 'admin'),
                                 ('custom_writer', 'write')]:
            with self.subTest(role=role):
                dispatched, _, error = self.command(f'/hpc {"c" * 40}', ['c' * 40],
                                                    role=role, permission=permission)
                self.assertIsNone(error)
                self.assertEqual(dispatched, ['c' * 40])

    def test_command_rejects_users_without_write_access_including_the_test_actor(self):
        for role, permission in [('read', 'read'), ('triage', 'read'), ('none', 'none'),
                                 ('custom_reader', 'read'), ('admin', None)]:
            for test_actor in (False, True):
                with self.subTest(role=role, test_actor=test_actor):
                    dispatched, replies, error = self.command(f'/hpc {"c" * 40}', ['c' * 40],
                                                            role=role, permission=permission,
                                                            test_actor=test_actor)
                    self.assertEqual(dispatched, [])
                    self.assertEqual(replies, [])
                    self.assertRegex(str(error), 'needs repository write access')

    def test_waiting_tolerates_a_job_list_that_lags_behind_the_completed_run(self):
        run = dict(id=5, status='completed', conclusion='failure', run_attempt=2, html_url='run')
        report = 'hpc / benchmark (fixture) / report'
        lists = iter([[dict(name=report, status='in_progress', conclusion=None, run_attempt=2)],
                      [dict(name=report, status='completed', conclusion='failure', run_attempt=1)],
                      [dict(name=report, status='completed', conclusion='failure', run_attempt=2)]])
        with patch.object(pr_integration, 'api', return_value=run), \
             patch.object(pr_integration, 'items', side_effect=lambda *args: next(lists)), \
             patch.object(pr_integration.time, 'sleep') as sleep:
            self.assertEqual(pr_integration.wait_run('pc2/test', 5, 'failure', 2), run)
        self.assertEqual(sleep.call_count, 2)

    def test_pr_creation_uses_the_test_token_without_granting_it_branch_access(self):
        class CreatedPR(Exception):
            pass

        requests = []
        def api(path, body=None, method=None, token=None):
            requests.append((path, token))
            if path == 'user':
                return {'login': 'user'}
            if path == 'repos/pc2/test':
                return {'default_branch': 'main'}
            if path.endswith('/dispatches'):
                return {'workflow_run_id': 1}
            if path.endswith('/git/ref/heads/hpc-test-results'):
                return {'object': {'sha': 'baseline'}}
            if '/git/commits/' in path:
                return {'tree': {'sha': 'tree'}}
            if path.endswith(('/git/trees', '/git/commits')):
                return {'sha': 'fixture'}
            if path.endswith('/git/refs'):
                return {}
            if path.endswith('/pulls'):
                raise CreatedPR()
            self.fail(f'Unexpected request {path}.')

        env = dict(CB_TEST_TOKEN='test-token', CB_TEST_ACTOR='user',
                   GITHUB_REPOSITORY='pc2/test', GITHUB_SHA='a' * 40,
                   GITHUB_RUN_ID='12', GITHUB_RUN_ATTEMPT='1')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, env), \
             patch.object(pr_integration, 'api', side_effect=api), patch.object(pr_integration, 'wait_run'):
            with self.assertRaises(CreatedPR):
                pr_integration.run(Path(directory) / 'state.json')
        self.assertIn(('repos/pc2/test/pulls', 'test-token'), requests)
        self.assertTrue(all(token is None for path, token in requests if '/git/' in path))

    def test_reusable_workflows_embed_the_tested_helpers(self):
        for template in (embed_helpers.ROOT / '.github/templates').glob('*.yml'):
            self.assertEqual(embed_helpers.render(template),
                             (embed_helpers.ROOT / '.github/workflows' / template.name).read_text())

    def test_recording_retry_preserves_verdict_without_writing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = dict(context=dict(sha='a' * 40), suite=dict(name='CPU'), record=True,
                         key='1/2/CPU', previous=dict(verdict='failure', summary='Recorded regression.'))
            (root / 'benchmark-state.json').write_text(json.dumps(state))
            env = dict(RUNNER_TEMP=str(root), GITHUB_OUTPUT=str(root / 'output'),
                       GITHUB_STEP_SUMMARY=str(root / 'summary'), OUTCOME='skipped')
            with patch.dict(os.environ, env), patch.object(benchmark, 'command') as command, \
                 patch.object(benchmark, 'report') as report:
                benchmark.finish()
                command.assert_not_called()
                report.assert_called_once_with(state['context'], state['suite'], 'failure', 'Recorded regression.')
                self.assertIn('verdict=failure', (root / 'output').read_text())

    def test_fresh_measurement_requires_the_action_to_attribute_the_correct_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for entries, recorded in [(0, 'a'), (1, 'b'), (2, 'b')]:
                with self.subTest(entries=entries, recorded=recorded):
                    state = dict(context=dict(sha='b' * 40), suite=dict(name='CPU'), record=True,
                                 directory=str(root), previous=None, entries=entries)
                    (root / 'benchmark-state.json').write_text(json.dumps(state))
                    history = [dict(commit=dict(id='b' * 40))] * (entries - 1) + [dict(commit=dict(id=recorded * 40))]
                    data = dict(entries={'CPU': history})
                    (root / 'data.js').write_text('window.BENCHMARK_DATA = ' + json.dumps(data))
                    with patch.dict(os.environ, dict(RUNNER_TEMP=str(root), OUTCOME='failure')), \
                         patch.object(benchmark, 'command') as command:
                        with self.assertRaisesRegex(ValueError, 'expected measurement'):
                            benchmark.finish()
                        command.assert_not_called()

    def test_prepare_selects_a_comparable_baseline_and_blocks_missing_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = Path.cwd()
            os.chdir(root)
            try:
                (root / 'bench').mkdir()
                context = dict(sha='b' * 40, pull_request='7', project_id=1, pipeline_id=2, ref='main')
                (root / 'context.json').write_text(json.dumps(context))
                measurement = dict(name='solve', unit='seconds', value=110)
                with zipfile.ZipFile(root / 'job.zip', 'w') as archive:
                    archive.writestr('results.json', json.dumps([measurement]))
                history = dict(entries={'CPU': [dict(commit=dict(id='a' * 40), tool='customSmallerIsBetter', benches=[measurement])]})
                (root / 'bench/data.js').write_text('window.BENCHMARK_DATA = ' + json.dumps(history))
                env = dict(CONFIG='{}', SUITE=json.dumps(dict(name='CPU', archive='job.zip', file='results.json')),
                           CONTEXT=str(root / 'context.json'), ARTIFACTS=str(root), DEFAULT_BRANCH='main',
                           RUNNER_TEMP=str(root), GITHUB_OUTPUT=str(root / 'output'),
                           GITHUB_REPOSITORY='pc2/test', GITHUB_RUN_ID='10')
                with patch.dict(os.environ, env), patch.object(benchmark, 'command', return_value='exists'), \
                     patch.object(benchmark, 'api', return_value={'artifacts': []}):
                    benchmark.prepare()
                    state = json.loads((root / 'benchmark-state.json').read_text())
                    self.assertFalse(state['record'])
                    self.assertEqual(state['baseline'], 'a' * 40)
                    history['entries']['CPU'][0]['benches'][0]['name'] = 'different'
                    (root / 'bench/data.js').write_text('window.BENCHMARK_DATA = ' + json.dumps(history))
                    with self.assertRaisesRegex(ValueError, 'names and units'):
                        benchmark.prepare()
            finally:
                os.chdir(old)

    def test_recording_resolves_the_default_branch_when_the_event_lacks_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = Path.cwd()
            os.chdir(root)
            try:
                context = dict(sha='b' * 40, pull_request='', project_id=1, pipeline_id=2, ref='trunk')
                (root / 'context.json').write_text(json.dumps(context))
                with zipfile.ZipFile(root / 'job.zip', 'w') as archive:
                    archive.writestr('results.json', json.dumps([dict(name='solve', unit='seconds', value=1)]))
                env = dict(CONFIG='{}', SUITE=json.dumps(dict(name='CPU', archive='job.zip', file='results.json')),
                           CONTEXT=str(root / 'context.json'), ARTIFACTS=str(root), DEFAULT_BRANCH='',
                           RUNNER_TEMP=str(root), GITHUB_OUTPUT=str(root / 'output'),
                           GITHUB_REPOSITORY='pc2/test', GITHUB_RUN_ID='10')
                for default, allowed in [('main', False), ('trunk', True)]:
                    with self.subTest(default=default), patch.dict(os.environ, env), \
                         patch.object(benchmark, 'command', return_value=''), \
                         patch.object(benchmark, 'api', return_value=dict(default_branch=default)) as api:
                        if allowed:
                            benchmark.prepare()
                            self.assertTrue(json.loads((root / 'benchmark-state.json').read_text())['record'])
                        else:
                            with self.assertRaisesRegex(ValueError, 'Only the default branch'):
                                benchmark.prepare()
                        api.assert_called_once_with('repos/pc2/test')
            finally:
                os.chdir(old)


if __name__ == '__main__':
    unittest.main()
