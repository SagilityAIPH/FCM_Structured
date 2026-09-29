"""Desktop executable entry point; CLI remains available through run.py."""
import multiprocessing
from pathlib import Path
import sys


def self_test(report):
    import json
    import tempfile
    import time
    import tkinter as tk
    import desktop
    from AI import referral_schema as schema
    from AI.daily_output import save_daily_output
    from fcm_intake import config
    from fcm_intake.workflows import reopen_check, customer_checker
    # CEM creates its browser at import time; verify bundled source without
    # executing that side effect during an offline test.
    compile(config.CEM_SCRIPT.read_text(encoding="utf-8-sig"), str(config.CEM_SCRIPT), "exec")
    root = tk.Tk()
    root.withdraw()
    app = desktop.App(root)
    try:
        assert config.REOPENCHECK_SCRIPT.is_file()
        assert config.CUSTOMERCHECKER_SCRIPT.is_file()
        assert desktop.load_core().run_flow
        with tempfile.TemporaryDirectory() as folder:
            raw = {key: "Not found" for key in schema.REQUIRED_FIELDS if key not in schema.PROVIDER_FIELDS}
            raw.update({"Claim Number": "000123", "First Name": "Jane", "Last Name": "Doe"})
            raw["Provider Information"] = []
            fields = schema.parse_field_block(json.dumps(raw))
            path, rid = save_daily_output(fields, "synthetic.pdf", directory=folder)
            assert desktop.workbook_records(path) == [rid]
            app.filename.set(str(path))
            app.record.set(rid)
            app.load_record()
            assert app.inputs["claimNumber"].get() == "000123"
            assert app.assessment.get().startswith("NEXT STEP: Failed")
            app.mode.set("Live CMS")
            try:
                app.request()
                raise AssertionError("Failed workbook must block live processing")
            except ValueError as error:
                assert "Failed" in str(error)
            app.mode.set("Offline scenario")
            for scenario, expected in [("happy-path.json", "completed"), ("decline.json", "stopped")]:
                app.scenario.set(scenario)
                app.start()
                deadline = time.monotonic() + 45
                while app.worker is not None and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.05)
                assert app.worker is None, "Worker timed out"
                assert app.result["result"]["status"] == expected, app.result
        Path(report).write_text("PASS: desktop UI, bundled legacy imports, daily Excel input, Failed guard, isolated worker, completion and cancellation; no live CMS calls.\n", encoding="utf-8")
    finally:
        if app.worker is not None:
            app.worker.terminate()
            app.worker.join(timeout=5)
        root.destroy()


def main():
    multiprocessing.freeze_support()
    if "--self-test-report" in sys.argv:
        index = sys.argv.index("--self-test-report")
        report = sys.argv[index + 1]
        try:
            self_test(report)
        except Exception:
            import traceback
            Path(report).write_text(traceback.format_exc(), encoding="utf-8")
            return 1
        return 0
    import tkinter as tk
    from desktop import App
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
