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
            state = dict(context=dict(sha='b' * 40), suite=dict(name='CPU'), record=True,
                         directory=str(root), previous=None)
            (root / 'benchmark-state.json').write_text(json.dumps(state))
            data = dict(entries={'CPU': [dict(commit=dict(id='a' * 40))]})
            (root / 'data.js').write_text('window.BENCHMARK_DATA = ' + json.dumps(data))
            with patch.dict(os.environ, dict(RUNNER_TEMP=str(root), OUTCOME='success')), \
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


if __name__ == '__main__':
    unittest.main()
