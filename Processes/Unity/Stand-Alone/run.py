"""Run just this process. Defaults to an offline fixture; use --live for Unity."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
HERE = ROOT / "Processes" / "Unity" / "Stand-Alone"
CORE_PATH = HERE.parent / "Deploy-Ready" / "unity_flow.py"


def load_core():
    spec = importlib.util.spec_from_file_location("standalone_unity_flow", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ask_yes_no(title, message):
    while True:
        answer = input(f"{title}: {message}\n[y/n]: ").strip().lower()
        if answer in {"y", "yes", "n", "no"}:
            return answer in {"y", "yes"}


def _preflight_tracking():
    """Presence check only; never connects to the database."""
    sys.path.insert(0, str(ROOT / "src"))
    from fcm_intake.config import get_rrs_db_connection
    get_rrs_db_connection()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="UnityAssignment", description=__doc__)
    parser.add_argument("--stage", choices=["all", "unity", "assign"], default="all")
    parser.add_argument("--scenario", type=Path, default=HERE / "scenarios" / "happy-path.json")
    parser.add_argument("--all-scenarios", action="store_true",
                        help="Run every scenario in scenarios/ and summarise the outcomes.")
    parser.add_argument("--live", action="store_true",
                        help="Use the real Unity portal, database and RRS; requires Windows and configured dependencies.")
    parser.add_argument("--desktop", action="store_true", help="Open the Unity desktop form (live wiring).")
    parser.add_argument("--self-test", action="store_true", help="Run the synthetic desktop smoke check.")
    parser.add_argument("--report", type=Path, help="Write self-test output to this UTF-8 file.")
    parser.add_argument("--claim-number")
    parser.add_argument("--customer")
    parser.add_argument("--claimant-first")
    parser.add_argument("--claimant-last")
    parser.add_argument("--record-attempt-on-failure", choices=["yes", "no"], default="yes",
                        help="Legacy writes the tracking row even when Unity fails. Default yes preserves that.")
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            from contextlib import redirect_stdout, redirect_stderr
            from io import StringIO
            import traceback
            import tempfile
            report = args.report or Path(tempfile.gettempdir()) / "UnityAssignment-self-test.txt"
            captured = StringIO()
            with redirect_stdout(captured), redirect_stderr(captured):
                try:
                    from smoke import main as smoke
                    code = smoke()
                except BaseException:
                    traceback.print_exc()
                    code = 1
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(captured.getvalue(), encoding="utf-8")
            if sys.stdout is not None:
                print(captured.getvalue(), end="")
            return code
        if args.desktop:
            from launcher import main as launch
            launch()
            return 0
        core = load_core()
        if args.all_scenarios:
            rows = []
            for path in sorted((HERE / "scenarios").glob("*.json")):
                rows.append((path.name, run_scenario(core, path, args.stage)))
            width = max(len(name) for name, _ in rows)
            for name, outcome in rows:
                print(f"{name.ljust(width)}  {outcome['status']:<9} {outcome['reason'] or '-'}")
            return 0 if all(r["status"] == "completed" for _, r in rows) else 2

        if not args.live:
            result = run_scenario(core, args.scenario, args.stage)
        else:
            data = {"claimNumber": args.claim_number or "", "customer": args.customer or "",
                    "claimantFirst": args.claimant_first or "", "claimantLast": args.claimant_last or ""}
            sys.path.insert(0, str(ROOT))
            sys.path.insert(0, str(ROOT / "src"))
            if args.stage != "assign":
                _preflight_tracking()
            from fcm_intake.config import ATTACHMENT_FOLDER
            from fcm_intake.legacy_loader import load_module_from_path
            from fcm_intake.config import UNITY_SCRIPT
            unity = load_module_from_path("standalone_legacy_unity", UNITY_SCRIPT)
            folder = Path(ATTACHMENT_FOLDER)
            result = core.run_flow(
                data, stage=args.stage,
                list_attachments=lambda: sorted(p for p in folder.glob("*") if p.is_file()),
                run_unity=unity.main,
                record_assignment=lambda claimant, claim: _record_live(ROOT, claimant, claim),
                notify=lambda title, message: print(f"[{title}]\n{message}"),
                confirm=ask_yes_no,
                complete_assignment=lambda claim: _complete_live(ROOT, claim, confirm_unity_login=ask_yes_no),
                record_attempt_on_failure=args.record_attempt_on_failure == "yes",
            )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["status"] == "completed" else 2
    except Exception as error:
        print(f"Process failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


def run_scenario(core, path, stage):
    """Offline execution. Touches no browser, database or desktop."""
    scenario = json.loads(Path(path).read_text(encoding="utf-8"))

    def run_unity(customer, claimant_full, data):
        if scenario.get("unity_error"):
            raise RuntimeError(scenario["unity_error"])

    def record_assignment(claimant_full, claim_number):
        if scenario.get("record_error"):
            raise RuntimeError(scenario["record_error"])
        print(f"[record] {claimant_full} / {claim_number}")

    def complete_assignment(claim_number):
        if scenario.get("assignment_error"):
            raise RuntimeError(scenario["assignment_error"])
        print(f"[assign] {claim_number}")

    return core.run_flow(
        scenario["input"], stage=stage,
        list_attachments=lambda: scenario.get("attachments", []),
        run_unity=run_unity,
        record_assignment=record_assignment,
        notify=lambda title, message: print(f"[{title}]\n{message}"),
        confirm=lambda *_: scenario.get("icasemanager_approved", False),
        complete_assignment=complete_assignment,
        record_attempt_on_failure=scenario.get("record_attempt_on_failure", True),
    )


def _record_live(root, claimant_full, claim_number):
    from fcm_intake.config import FCM_SCRIPT
    from fcm_intake.legacy_loader import load_module_from_path
    legacy = load_module_from_path("standalone_legacy_fcm", FCM_SCRIPT)
    legacy.InsertIntoTable(claimant_full, claim_number)


def _complete_live(root, claim_number, *, confirm_unity_login=None):
    from fcm_intake.config import FCM_SCRIPT
    from fcm_intake.legacy_loader import load_module_from_path
    legacy = load_module_from_path("standalone_legacy_fcm", FCM_SCRIPT)
    if confirm_unity_login is None:
        legacy.CompleteAssignment(claim_number)
    else:
        legacy.CompleteAssignment(claim_number, confirm_unity_login=confirm_unity_login)


if __name__ == "__main__":
    raise SystemExit(main())
