"""Scenario and controller-spec tests; unique module import names."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_cms_registration_scenario_test_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ScenarioTests(unittest.TestCase):
    def test_every_fixture_expected_outcome_and_reason(self):
        rows = runner.scenario_rows()
        self.assertEqual(len(rows), 14)
        self.assertTrue(all(row[3] for row in rows), [(name, expected, actual['outcome'], actual['reason']) for name, expected, actual, ok in rows if not ok])

    def test_result_shape_and_callback_order(self):
        contract = runner.load_contract()
        core = runner.load_core()
        stages_seen, steps_seen = [], []
        result = core.run_flow(contract.RegistrationRequest('SYN-0001', 'Testy', 'Example', 'Medical'),
            stages=contract.RegistrationStages(
                lambda req: [contract.CaseCandidate('SYN-CASE-1', '2026-01-01', 'Medical')],
                lambda req, case: {'cem_employer_request': False},
                lambda req, case, data: True,
                lambda req, case, data, cb: [contract.StepResult('synthetic_setup', 'manual')],
                lambda req, case, cem: {'option': '3', 'case_id_entered': True, 'readback': case.case_id}),
            on_stage=stages_seen.append, on_step=steps_seen.append)
        self.assertEqual(set(result), {'outcome', 'reason', 'stage', 'stages', 'case_id', 'candidates', 'steps', 'registration', 'cem', 'problems', 'error'})
        self.assertEqual(stages_seen, list(contract.STAGES))
        self.assertEqual((result['outcome'], result['reason']), ('completed', 'registered'))

    def test_no_registration_after_cms_failure(self):
        contract, core = runner.load_contract(), runner.load_core()
        complete = Mock()
        result = core.run_flow(contract.RegistrationRequest('SYN-0001', 'Testy', 'Example', 'Medical'),
            stages=contract.RegistrationStages(
                lambda _: [contract.CaseCandidate('SYN-CASE-1', '2026-01-01', 'Medical')],
                lambda *_: {'cem_employer_request': False}, lambda *_: True,
                lambda *args: [contract.StepResult('synthetic_setup', 'failed')], complete))
        self.assertEqual((result['outcome'], result['reason']), ('failed', 'cms_step_failed'))
        complete.assert_not_called()

    def test_cli_all_and_self_test_exit(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with redirect_stdout(StringIO()):
            self.assertEqual(runner.main(['--all-scenarios']), 0)

    def test_explicit_offline_self_test_runs_outside_repo_without_pythonpath(self):
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        result = subprocess.run(
            [sys.executable, str(HERE / 'run.py'), '--self-test'],
            cwd=HERE, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Scenarios: 14/14 passed', result.stdout)
        self.assertIn('Smoke: PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
