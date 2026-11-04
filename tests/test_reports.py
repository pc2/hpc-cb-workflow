import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import benchmark_report
import integration_suite


class IntegrationResultTests(unittest.TestCase):
    def record(self, collected=True):
        return dict(scenario='handover_failure', sha='a' * 40, context_run_id=10,
                    pipeline_id=20, collected=collected, next_run_id=0 if collected else 11,
                    result='failure' if collected else 'success')

    def test_expected_failure_requires_a_verified_matching_pipeline(self):
        record = self.record()
        integration_suite.validate_result(record, 'handover_failure', 'a' * 40, 10, 20, 'failure')
        for key, value in [('pipeline_id', 21), ('context_run_id', 12), ('sha', 'b' * 40),
                           ('scenario', 'success'), ('result', 'success'), ('next_run_id', 11)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                integration_suite.validate_result(record | {key: value}, 'handover_failure', 'a' * 40, 10, 20, 'failure')

    def test_handover_requires_another_run(self):
        record = self.record(False)
        integration_suite.validate_result(record, 'handover_failure', 'a' * 40, 10, 20, 'success')
        with self.assertRaises(ValueError):
            integration_suite.validate_result(record | {'next_run_id': 0}, 'handover_failure', 'a' * 40, 10, 20, 'success')

    def test_dispatch_failure_is_not_accepted_as_an_expected_pipeline_failure(self):
        with self.assertRaises(ValueError):
            integration_suite.validate_result(self.record(False), 'handover_failure', 'a' * 40, 10, 20, 'failure')

    def test_suite_follows_handover_and_accepts_only_the_verified_failure(self):
        def fake_api(path, body=None):
            if path.endswith('/dispatches'):
                self.assertEqual(body['inputs']['scenario'], 'handover_failure')
                self.assertTrue(body['return_run_details'])
                return {'workflow_run_id': 10}
            run_id = int(path.rsplit('/', 1)[-1])
            return dict(status='completed', head_sha='a' * 40,
                        conclusion='success' if run_id == 10 else 'failure', html_url=f'https://example/{run_id}')

        def fake_artifact(repo, run_id, name):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive:
                archive.writestr('result.json', json.dumps(self.record(run_id != 10)))
            return zipfile.ZipFile(stream)

        root = Path(__file__).resolve().parents[1] / '.tmp'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            output = Path(directory) / 'result.json'
            summary = Path(directory) / 'summary'
            with patch.object(integration_suite, 'api', side_effect=fake_api), \
                 patch.object(integration_suite, 'items', return_value=[{'name': 'Verify integration', 'conclusion': 'success'}]), \
                 patch.object(integration_suite, 'artifact', side_effect=fake_artifact), \
                 patch.dict('os.environ', {'GITHUB_STEP_SUMMARY': str(summary)}):
                result = integration_suite.run_scenario('example/project', 'main', 'a' * 40, 'handover_failure', output)
            self.assertEqual(result['run_id'], 11)
            self.assertEqual(result['pipeline_id'], 20)
            self.assertEqual(json.loads(output.read_text())['result'], 'failure')


class BenchmarkReportTests(unittest.TestCase):
    def record(self):
        return dict(schema=1, name='julia_linear_solve_512', unit='seconds', value=0.004,
                    samples=[0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007], residual=1e-15,
                    sha='a' * 40, julia_version='1.10.12', threads=1, blas_threads=1,
                    cpu='test', blas='OpenBLAS', date='2026-11-04T12:00:00Z',
                    run_id=10, pipeline_id=20, project_id=42)

    def test_custom_measurement_is_accepted_without_a_benchmark_parser(self):
        record = self.record()
        self.assertEqual(benchmark_report.validate_measurement(record, 'a' * 40), record)

    def test_invalid_or_misattributed_measurements_are_rejected(self):
        for key, value in [('value', float('nan')), ('value', 0.003), ('sha', 'b' * 40),
                           ('residual', 1.0), ('threads', 2), ('blas_threads', 2),
                           ('samples', [0.1]), ('unit', 'ms'), ('cpu', '')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                benchmark_report.validate_measurement(self.record() | {key: value}, 'a' * 40)


if __name__ == '__main__':
    unittest.main()
