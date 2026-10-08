"""Open the manual SubjectLineBuilder desktop; --scenario checks the legacy controller offline."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CORE = Path(__file__).resolve().parents[1] / 'Deploy-Ready' / 'subject_line_flow.py'


def load_core():
    spec = importlib.util.spec_from_file_location('standalone_subject_line_flow', CORE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def simulated_steps(app=None):
    global botStop, data
    if scenario == 'failure':
        raise RuntimeError('Synthetic builder failure')
    if scenario == 'stopped':
        return
    data = {'claimNumber': 'SYNTHETIC-001'}
    botStop = False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['completed', 'stopped', 'failure'])
    args = parser.parse_args(argv)
    try:
        if not args.scenario:
            from launcher import main as launch
            launch()
            return 0
        else:
            result = load_core().run_flow({'scenario': args.scenario or 'completed'}, steps=simulated_steps)
        # Data remains available to the application; do not dump claim PHI to CLI.
        summary = {key: value for key, value in result.items() if key != 'data'}
        summary['mode'] = 'offline simulation'
        print(json.dumps(summary, indent=2))
        return {'completed': 0, 'stopped': 2, 'failed': 1}[result['status']]
    except Exception as error:
        print(f'Unable to start SubjectLineBuilder: {type(error).__name__}: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
