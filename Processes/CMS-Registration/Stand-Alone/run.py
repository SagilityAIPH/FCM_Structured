"""CMS Registration: attended desktop window (live by default) or offline synthetic runner."""
import argparse
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = ROOT / 'Processes/CMS-Registration/Stand-Alone'
CORE = HERE.parent / 'Deploy-Ready'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve module names when creating types
    spec.loader.exec_module(module)
    return module


def load_contract():
    return _load('_cms_registration_standalone_contract', CORE / 'contract.py')


def load_core():
    return _load('_cms_registration_standalone_flow', CORE / 'cms_registration_flow.py')


def load_live(settings):
    """Import the portal adapter only after an attended live Start."""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT / 'src/fcm_intake'))  # legacy CMS uses top-level legacy imports
    adapter = _load('_cms_registration_standalone_steps', CORE / 'cms_steps.py')
    return adapter.open_live_session(settings)


def request_from_form(form, contract=None):
    contract = contract or load_contract()
    cem = form.get('cem_employer_request', None)
    if cem in ('auto', '', None):
        cem = None
    elif cem in ('yes', True):
        cem = True
    elif cem in ('no', False):
        cem = False
    else:
        raise ValueError('CEM must be auto, yes or no.')
    return contract.RegistrationRequest(
        claim_number=form.get('claim_number', ''),
        claimant_first_name=form.get('claimant_first_name', ''),
        claimant_last_name=form.get('claimant_last_name', ''),
        referral_type=form.get('referral_type', ''),
        cms_case_id=form.get('cms_case_id', ''),
        referral_number=form.get('referral_number', ''),
        cem_employer_request=cem,
    )


def run_scenario(path, *, flow=None, contract=None):
    """All callbacks are synthetic. No live adapter is imported."""
    flow = flow or load_core().run_flow
    contract = contract or load_contract()
    fixture = json.loads(Path(path).read_text(encoding='utf-8'))
    request = request_from_form(fixture['request'], contract)
    candidates = [contract.CaseCandidate(**item) for item in fixture.get('candidates', [])]
    steps = [contract.StepResult(**item) for item in fixture.get('steps', [{'step': 'synthetic_setup', 'status': 'done'}])]
    def fail(stage):
        if fixture.get('raise_at') == stage:
            raise SystemExit('synthetic stage exit')
    def find_cases(req):
        fail('CASE')
        return candidates
    def load_data(req, case):
        fail('DATA')
        return fixture.get('data', {'cem_employer_request': False, 'synthetic': 'Testy Example'})
    def review(req, case, data):
        fail('REVIEW')
        return fixture.get('approve', True)
    def setup(req, case, data, on_step):
        fail('CMS_SETUP')
        for step in steps:
            on_step(step)
        return steps
    def complete(req, case, cem):
        fail('COMPLETE_REG')
        return fixture.get('registration', {'option': '10' if cem else '3', 'case_id_entered': True, 'readback': case.case_id})
    stages = contract.RegistrationStages(find_cases, load_data, review, setup, complete)
    return flow(request, stages=stages)


def scenario_rows():
    rows = []
    for path in sorted((HERE / 'scenarios').glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        result = run_scenario(path)
        expected = fixture['expected']
        rows.append((path.stem, expected, result, (result['outcome'], result['reason']) == (expected['outcome'], expected['reason'])))
    return rows


def report_rows(rows):
    lines = ['CMS Registration synthetic scenarios', 'name | expected outcome/reason | actual outcome/reason | result']
    for name, expected, actual, passed in rows:
        lines.append(f"{name} | {expected['outcome']}/{expected['reason']} | {actual['outcome']}/{actual['reason']} | {'PASS' if passed else 'FAIL'}")
    lines.append(f"Scenarios: {sum(row[3] for row in rows)}/{len(rows)} passed")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog='CMSRegistration', description=__doc__)
    parser.add_argument('--scenario', help='Fixture name in scenarios/ (without .json)')
    parser.add_argument('--all-scenarios', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--desktop', action='store_true')
    parser.add_argument('--live', action='store_true', help='Attended desktop live mode (default for --desktop); never starts on its own.')
    parser.add_argument('--offline', action='store_true', help='Desktop with the synthetic fixture instead of the live portal.')
    args = parser.parse_args(argv)
    if args.live and args.offline:
        parser.error('--live and --offline are mutually exclusive.')
    if not (args.scenario or args.all_scenarios or args.self_test):
        args.desktop = True
    if (args.live or args.offline) and not args.desktop:
        parser.error('--live/--offline require --desktop; scenarios are always offline.')
    if args.desktop:
        from launcher import main as desktop
        desktop(live=not args.offline)
        return 0
    if args.self_test or args.all_scenarios:
        try:
            rows = scenario_rows()
            lines = report_rows(rows)
            if args.self_test:
                from smoke import main as smoke
                try:
                    smoke_lines = smoke()
                    lines += ['Smoke: PASS', *smoke_lines]
                except (Exception, SystemExit) as error:
                    lines += [f'Smoke: FAIL ({type(error).__name__})']
        except (Exception, SystemExit) as error:
            lines = [f'Scenarios: FAIL ({type(error).__name__})']
            rows = []
        if len(rows) != 14:
            lines.append(f'Scenario inventory mismatch: expected 14; found {len(rows)}')
        text = '\n'.join(lines) + '\n'
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding='utf-8')
        if sys.stdout is not None:
            print(text, end='')
        return 0 if len(rows) == 14 and all(row[3] for row in rows) and (not args.self_test or 'Smoke: PASS' in lines) else 1
    name = args.scenario or 'registered-normal'
    if '/' in name or '\\' in name or name in ('', '.', '..'):
        parser.error('Use a scenario name, not a path.')
    path = HERE / 'scenarios' / (name.removesuffix('.json') + '.json')
    if not path.is_file():
        parser.error(f'Unknown scenario: {name}')
    result = run_scenario(path)
    print(json.dumps(result, indent=2))
    return 0 if result['outcome'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
