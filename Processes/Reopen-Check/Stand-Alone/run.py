"""Run just this process. Defaults to an offline fixture; use --live for CMS."""
import argparse
from getpass import getpass
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
HERE = ROOT / "Processes" / "Reopen-Check" / "Stand-Alone"
CORE_PATH = HERE.parent / "Deploy-Ready" / "reopen_flow.py"


def load_core():
    spec = importlib.util.spec_from_file_location("standalone_reopen_flow", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConsolePrompts:
    def ask_yes_no(self, title, message):
        while True:
            answer = input(f"{title}: {message}\n[y/n]: ").strip().lower()
            if answer in {"y", "yes", "n", "no"}:
                return answer in {"y", "yes"}

    def ask_text(self, title, message):
        return input(f"{title}: {message}\n> ").strip()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="CMSCustomerSearch", description=__doc__)
    parser.add_argument("--stage", choices=["all", "reopen", "customer"], default="all")
    parser.add_argument("--scenario", type=Path, default=HERE / "scenarios" / "happy-path.json")
    parser.add_argument("--live", action="store_true", help="Use real CMS; requires Windows and configured dependencies.")
    parser.add_argument("--excel", type=Path, help="Daily AI output workbook; without --live, preview the mapped input only.")
    parser.add_argument("--record-id", help="Record ID from the Referrals sheet.")
    parser.add_argument("--claim-number")
    parser.add_argument("--customer")
    parser.add_argument("--claim-id")
    parser.add_argument("--claimant")
    parser.add_argument("--referral-type", default="")
    args = parser.parse_args(argv)
    try:
        workbook_data = None
        if args.excel or args.record_id:
            if not args.excel or not args.record_id:
                raise ValueError("Use --excel and --record-id together.")
            if any([args.claim_number, args.customer, args.claim_id, args.claimant, args.referral_type]):
                raise ValueError("Use either Excel input or direct input arguments, not both.")
            sys.path.insert(0, str(ROOT))
            from AI.daily_output import read_record, reopen_input
            fields, assessment = read_record(args.excel, args.record_id)
            workbook_data = reopen_input(fields)
            if not args.live:
                print(json.dumps({"record_id": args.record_id, "input": workbook_data, "next_step": assessment}, indent=2))
                return 0
            if assessment["status"] != "Passed":
                raise ValueError("This record has missing required information. Review the AI output before live processing.")
        if not args.live:
            scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
            result = load_core().run_flow(
                scenario["input"], stage=args.stage,
                search_cases=lambda _: scenario.get("cases", []),
                check_customer=lambda *_: scenario.get("selected_customer"),
                notify=lambda title, message: print(f"[{title}]\n{message}"),
                confirm=lambda *_: scenario.get("proceed", False),
            )
        else:
            # Live runs never fall back to synthetic fixture inputs.
            data = workbook_data or {"claimNumber": args.claim_number or "", "customer": args.customer or "",
                    "claimID": args.claim_id or "", "claimantFull": args.claimant or "",
                    "referralType": args.referral_type}
            required = (["claimNumber"] if args.stage in {"all", "reopen"} else [])
            required += (["customer", "claimID", "claimantFull"] if args.stage in {"all", "customer"} else [])
            missing = [key for key in required if not data[key].strip()]
            if missing:
                raise ValueError("Missing live inputs: " + ", ".join(missing))
            sys.path.insert(0, str(ROOT / "src"))
            from fcm_intake.cms import session
            from fcm_intake.workflows.reopen_flow import run_live
            prompts = ConsolePrompts()
            username = os.getenv("FCM_CMS_USERNAME") or input("CMS username: ").strip()
            password = os.getenv("FCM_CMS_PASSWORD") or getpass("CMS password: ")
            session.set_credentials(username, password)
            try:
                result = run_live(data, stage=args.stage, app=prompts,
                                  notify=lambda title, message: print(f"[{title}]\n{message}"),
                                  confirm=prompts.ask_yes_no)
            finally:
                session.close_shared_driver()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["status"] == "completed" else 2
    except Exception as error:
        print(f"Process failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
