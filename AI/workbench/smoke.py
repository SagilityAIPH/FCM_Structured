"""Hidden WebView2 smoke test with a synthetic PDF and offline inference fixture."""
import argparse
from contextlib import nullcontext
import json
import sys
from pathlib import Path
import tempfile
import time
import traceback
from unittest.mock import patch

import fitz
import webview

from AI.workbench.backend import WorkbenchAPI
from AI.workbench.window_layout import WINDOW_WIDTH, WINDOW_HEIGHT, MIN_HEIGHT, constrain_window
from AI import bedrock_runtime as core
from AI.referral_schema import PROVIDER_FIELDS, REQUIRED_FIELDS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fcm-workbench-smoke-') as directory:
        folder = Path(directory)
        source = folder / 'SYNTHETIC,REFERRAL.pdf'
        with fitz.open() as pdf:
            pdf.new_page().insert_text((40, 60), 'Synthetic referral for native UI smoke test.')
            pdf.save(source)
        api = WorkbenchAPI(folder / 'output')
        api._key = 'offline-fixture'
        identifier = api._import_paths([source])[0]
        data = {key: 'Not found' for key in REQUIRED_FIELDS if key not in PROVIDER_FIELDS}
        data['Provider Information'] = [{key: 'Not found' for key in PROVIDER_FIELDS}]
        data.update({'First Name': 'Synthetic', 'Last Name': 'Example'})
        result, fields = core.force_exact_field_output(json.dumps(data))
        index = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'frontend/dist/index.html'
        window = webview.create_window('FCM Workbench smoke', str(index.resolve()), js_api=api,
                                        hidden=True, width=WINDOW_WIDTH, height=WINDOW_HEIGHT,
                                        min_size=(WINDOW_WIDTH, MIN_HEIGHT), resizable=True)
        window.events.before_show += lambda: constrain_window(window)
        api._window = window
        outcome = {'passed': False}
        def verify():
            try:
                window.events.loaded.wait(20)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    ready = window.evaluate_js("Boolean(document.querySelector('input[aria-label=\"Claimant Information / First Name\"]'))")
                    if ready:
                        break
                    time.sleep(.25)
                else:
                    raise RuntimeError('React form did not load through the native bridge: ' + str(window.evaluate_js('document.body.innerText')))
                assert window.evaluate_js("document.querySelector('input[aria-label=\"Claimant Information / First Name\"]').value") == 'Synthetic'
                assert window.evaluate_js("document.querySelectorAll('[role=tab]').length") == 0
                assert not window.evaluate_js("document.body.innerText.includes('Synthetic preview')")
                from System import Action
                from System.Drawing import Size
                def verify_size():
                    form = window.native
                    width = round(WINDOW_WIDTH * form.DeviceDpi / 96.0)
                    assert form.MinimumSize.Width == form.MaximumSize.Width == width
                    assert form.Width == width
                    assert not form.MaximizeBox
                    original = form.Height
                    form.Size = Size(width + 200, form.MinimumSize.Height)
                    assert form.Width == width and form.Height == form.MinimumSize.Height
                    form.Size = Size(width - 100, original)
                    assert form.Width == width and form.Height == original
                window.native.Invoke(Action(verify_size))
                assert window.evaluate_js("document.querySelector('[aria-label=\"Form navigation\"]') !== null")
                assert window.evaluate_js("document.querySelector('[aria-label=\"Processing progress\"]') !== null")
                window.evaluate_js("document.querySelector('nav button[aria-controls=\"group-PDF\"]').click()")
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if window.evaluate_js("Boolean(document.querySelector('.pdf-page')?.naturalWidth)"):
                        break
                    time.sleep(.25)
                else:
                    raise RuntimeError('PDF preview did not render through the native bridge.')
                assert list((folder / 'output').glob('*.xlsx'))
                outcome['passed'] = True
                args.report.write_text('PASS: hidden WebView2 window, fixed 480 logical pixel width, vertical resize, React/Python bridge, appended PDF preview, single scrollable form, bottom navigation and progress, daily workbook. No live Bedrock or Census calls.', encoding='utf-8')
            except Exception:
                args.report.write_text(traceback.format_exc(), encoding='utf-8')
            finally:
                window.destroy()
        with patch.object(core, 'create_bedrock_client', return_value=nullcontext(None)), \
             patch.object(core, 'run_reasoning', return_value=(result, fields, json.dumps(data), .1)), \
             patch('AI.address_enrichment.census_lookup', return_value=[]):
            api._queue_pending()
            webview.start(verify, gui='edgechromium', http_server=True, private_mode=True)
        if not outcome['passed']:
            raise SystemExit(args.report.read_text(encoding='utf-8'))
        print(args.report.read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
