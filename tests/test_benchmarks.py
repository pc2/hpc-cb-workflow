import json
import os
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


class BenchmarkTests(unittest.TestCase):
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
        pr = dict(user=dict(login='github-actions[bot]'), title='HPC integration test pass',
                  head=dict(repo=dict(full_name='pc2/test'), ref='hpc-test/12-1/pass'))
        self.assertTrue(hpc_command.authorized_test_pr(pr, 'user', 'user', 'pc2/test'))
        self.assertFalse(hpc_command.authorized_test_pr(pr, 'other', 'user', 'pc2/test'))
        self.assertFalse(hpc_command.authorized_test_pr(pr, 'user', '', 'pc2/test'))
        pr['head']['ref'] = 'unreviewed'
        self.assertFalse(hpc_command.authorized_test_pr(pr, 'user', 'user', 'pc2/test'))

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
