"""Independent CEM operator runner: synthetic unless desktop --live is explicit."""
import argparse
from dataclasses import fields
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]
HERE = ROOT / 'Processes/CEM/Stand-Alone'
CORE = HERE.parent / 'Deploy-Ready'
SCENARIO_COUNT = 17


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_contract():
    return _load('_cem_standalone_contract', CORE / 'contract.py')


def load_core():
    return _load('_cem_standalone_flow', CORE / 'cem_flow.py')


def load_live(settings):
    """Only invoked from the explicitly started live worker."""
    return _load('_cem_standalone_steps', CORE / 'cem_steps.py').open_live_session(settings)


def request_from_form(form, contract=None):
    contract = contract or load_contract()
    if not isinstance(form, dict):
        raise ValueError('Supply a CEM form.')
    return contract.CEMRequest(**{f.name: form.get(f.name, f.default) for f in fields(contract.CEMRequest)})


def live_settings():
    """Use the shared local-settings convention, with env overrides; no URL defaults."""
    sys.path.insert(0, str(ROOT / 'src'))
    from fcm_intake.config import get_local_setting
    def setting(section, key, *env_names):
        try:
            return get_local_setting(section, key, *env_names)
        except KeyError:
            # CEM keys are intentionally absent from the shared built-in defaults.
            return ''
    environment = setting('cem', 'environment', 'FCM_CEM_ENVIRONMENT').strip().lower() or 'uat'
    placeholder = setting('cem', 'allow_placeholder_address', 'FCM_CEM_ALLOW_PLACEHOLDER_ADDRESS').strip().lower()
    if placeholder not in ('', 'false', '0', 'no', 'true', '1', 'yes'):
        raise ValueError('Invalid CEM placeholder policy setting.')
    return load_contract().CEMSettings(
        environment=environment,
        employer_search_url=setting('cem', 'employer_search_url', 'FCM_CEM_EMPLOYER_SEARCH_URL'),
        employer_add_url=setting('cem', 'employer_add_url', 'FCM_CEM_EMPLOYER_ADD_URL'),
        cem_log_path=setting('cem', 'cem_log_path', 'FCM_CEM_LOG_PATH'),
        allow_placeholder_address=placeholder in ('true', '1', 'yes'),
        edge_driver_path=setting('browser', 'edge_driver_path', 'FCM_EDGE_DRIVER_PATH', 'EDGE_DRIVER_PATH'))


def synthetic_settings(fixture=None, contract=None):
    contract = contract or load_contract()
    fixture = fixture or {}
    missing = fixture.get('config_required', False)
    return contract.CEMSettings(environment='uat', employer_search_url='' if missing else 'https://synthetic.invalid/search',
        employer_add_url='https://synthetic.invalid/add', cem_log_path='SYNTHETIC-NO-WRITE',
        allow_placeholder_address=fixture.get('allow_placeholder_address', False))


def synthetic_stages(contract, fixture=None):
    """Callback data are invented; no browser, workbook or live adapter imported."""
    fixture = fixture or {}
    def fail(stage):
        if fixture.get('raise_at') == stage:
            raise SystemExit('synthetic exit')
    def search(request, settings):
        fail('search')
        return fixture.get('search', {'state': 'no_results', 'names': []})
    calls = [0]
    def duplicate(request, settings):
        calls[0] += 1
        fail('duplicate')
        return fixture.get('duplicate_at') == calls[0]
    def fill(request, address, settings):
        fail('fill')
        rules = _load('_cem_standalone_rules', CORE / 'cem_rules.py')
        return dict(address, employer_name=request.employer_name,
                    bill_to_name=rules.BILL_TO_NAME,
                    bill_to_code='' if fixture.get('bill_to_unverified') else rules.BILL_TO_CODE)
    def submit(request, settings):
        fail('submit')
        return not fixture.get('submit_uncertain', False)
    def receipt(request, settings):
        fail('receipt')
        return None if fixture.get('receipt_not_found') else dict(
            reference='SYN-REQUEST-001', employer_name=request.employer_name,
            claim_number=request.claim_number, status='submitted', unique=True)
    def track(request, reference, settings):
        fail('track')
        return {'status': 'failed'} if fixture.get('tracking_failed') else {'status': 'written', 'row': 2}
    return contract.CEMStages(search_employer=search, find_existing_request=duplicate,
        fill_form=fill, review=lambda *args: fixture.get('approve', True),
        confirm_submit=lambda *args: fixture.get('confirm_submit', True),
        submit=submit, read_back_request=receipt, record=track,
        find_log_duplicate=lambda *args: False)


def run_scenario(path):
    fixture = json.loads(Path(path).read_text(encoding='utf-8'))
    contract = load_contract()
    return load_core().run(request_from_form(fixture['request'], contract),
        stages=synthetic_stages(contract, fixture), settings=synthetic_settings(fixture, contract))


def scenario_rows():
    rows = []
    for path in sorted((HERE / 'scenarios').glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        actual = run_scenario(path)
        expected = fixture['expected']
        rows.append((path.stem, expected, actual,
                     (actual['outcome'], actual['reason']) == (expected['outcome'], expected['reason'])))
    return rows


def report_rows(rows):
    lines = ['CEM synthetic scenarios', 'name | expected outcome/reason | actual outcome/reason | result']
    for name, expected, actual, passed in rows:
        lines.append(f"{name} | {expected['outcome']}/{expected['reason']} | {actual['outcome']}/{actual['reason']} | {'PASS' if passed else 'FAIL'}")
    lines.append(f"Scenarios: {sum(row[3] for row in rows)}/{len(rows)} passed")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog='CEMRequest', description=__doc__)
    parser.add_argument('--scenario')
    parser.add_argument('--all-scenarios', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--desktop', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args(argv)
    if args.live and not args.desktop:
        parser.error('--live requires --desktop')
    if args.desktop:
        name = '_cem_standalone_desktop_launcher'
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, HERE / 'launcher.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        sys.modules[name].main(live=args.live)
        return 0
    if args.self_test or args.all_scenarios:
        try:
            rows = scenario_rows()
            lines = report_rows(rows)
            if args.self_test:
                name = '_cem_standalone_smoke'
                smoke = _load(name, HERE / 'smoke.py').main
                try:
                    lines += ['Smoke: ' + smoke()]
                except (Exception, SystemExit) as exc:
                    lines += ['Smoke: FAIL (' + type(exc).__name__ + ')']
        except (Exception, SystemExit) as exc:
            rows, lines = [], ['Scenarios: FAIL (' + type(exc).__name__ + ')']
        if len(rows) != SCENARIO_COUNT:
            lines.append(f'Scenario inventory mismatch: expected {SCENARIO_COUNT}; found {len(rows)}')
        text = '\n'.join(lines) + '\n'
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding='utf-8')
        if sys.stdout is not None:
            print(text, end='')
        return 0 if len(rows) == SCENARIO_COUNT and all(row[3] for row in rows) and (not args.self_test or any(line.startswith('Smoke: PASS') for line in lines)) else 1
    name = args.scenario or 'request-submitted'
    if name in ('', '.', '..') or '/' in name or '\\' in name:
        parser.error('Use a fixture name, not a path.')
    path = HERE / 'scenarios' / (name.removesuffix('.json') + '.json')
    if not path.is_file():
        parser.error('Unknown scenario: ' + name)
    result = run_scenario(path)
    print(json.dumps(result, indent=2))
    return 0 if result['outcome'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
