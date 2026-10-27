"""Synthetic smoke checks: bridge callbacks and frozen resource presence only."""
from pathlib import Path
import importlib.util
import sys
import threading
import time


def main():
    from backend import CMSRegistrationAPI
    from run import HERE, ROOT
    if getattr(sys, 'frozen', False):
        required = [HERE / 'frontend/dist/index.html', HERE / 'run.py', HERE / 'scenarios/registered-normal.json',
                    HERE.parent / 'Deploy-Ready/contract.py', HERE.parent / 'Deploy-Ready/cms_registration_flow.py',
                    HERE.parent / 'Deploy-Ready/cms_steps.py', ROOT / 'src/fcm_intake/legacy/CMS.py',
                    ROOT / 'drivers/IEDriverServer.exe']
        for item in required:
            assert item.is_file(), f'Missing packaged resource: {item.name}'
        for name in ('selenium', 'pywinauto', 'pyodbc', 'openpyxl'):
            assert importlib.util.find_spec(name) is not None, f'Missing frozen import: {name}'
        import pyodbc  # importability only; never connect
        import pythoncom
        import selenium
        import pywinauto
        import webview
    api = CMSRegistrationAPI()
    assert api.get_state()['status'] == 'idle'
    assert not api.get_state()['busy']
    outcome = []
    thread = threading.Thread(target=lambda: outcome.append(api.confirm('Synthetic confirmation', 'Proceed?')))
    thread.start()
    deadline = time.monotonic() + 5
    while not api.get_state()['prompt']:
        assert time.monotonic() < deadline, 'Synthetic prompt timed out'
        time.sleep(.01)
    prompt = api.get_state()['prompt']
    assert api.answer_prompt(prompt['id'], True)['ok']
    thread.join(5)
    assert outcome == [True] and api.get_state()['prompt'] is None
    assert not api.answer_prompt(prompt['id'], True)['ok']
    return ['Idle until operator Start: OK', 'Threaded prompt round-trip and stale ID rejection: OK',
            'Frozen resource and import presence: OK' if getattr(sys, 'frozen', False) else 'Source-only resources: OK']


if __name__ == '__main__':
    for line in main():
        print(line)
