"""Pure, attended CMS Registration controller; no live imports or auto-start.

Load by importlib from this hyphenated directory. Stage adapters own all I/O.
"""
from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys


def _load_rules():
    name = "_cms_registration_pure_rules"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("cms_rules.py"))
        if spec is None or spec.loader is None:
            raise ImportError("CMS rules module unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


select_case = _load_rules().select_case


def run_flow(request, *, stages, on_stage=None, on_step=None) -> dict:
    """Run START→CASE→DATA→REVIEW→CMS_SETUP→COMPLETE_REG, returning all result keys.

    Exception and SystemExit, including callback failures, become structured
    failure at the active stage. KeyboardInterrupt is deliberately not caught.
    """
    result: dict = dict(outcome="failed", reason="", stage="START", stages=[], case_id="",
                  candidates=[], steps=[], registration=None, cem=None, error=None, problems=[])

    def begin(name):
        result["stage"] = name
        if on_stage is not None:
            on_stage(name)

    def finished():
        result["stages"].append(result["stage"])

    try:
        begin("START")
        problems = request.validate()
        if problems:
            result.update(outcome="stopped", reason="invalid_request", problems=list(problems))
            return result
        finished()

        begin("CASE")
        candidates = stages.find_cases(request)
        result["candidates"] = [asdict(candidate) for candidate in candidates]
        case, reason = select_case(candidates, request)
        if reason:
            result.update(outcome="stopped", reason=reason)
            return result
        result["case_id"] = case.case_id
        finished()

        begin("DATA")
        data = stages.load_data(request, case)
        if not isinstance(data, dict):
            raise TypeError("load_data must return a dict")
        cem = request.cem_employer_request
        if cem is None:
            cem = data.get("cem_employer_request")
        if not isinstance(cem, bool):
            result.update(outcome="stopped", reason="cem_status_unknown")
            return result
        result["cem"] = cem
        finished()

        begin("REVIEW")
        if stages.review(request, case, data) is False:
            result.update(outcome="cancelled", reason="operator_cancelled")
            return result
        finished()

        begin("CMS_SETUP")
        def forward(step):
            if on_step is not None:
                on_step(step)

        steps = stages.setup_cms(request, case, data, forward)
        result["steps"] = [asdict(step) for step in steps]
        if any(step.status == "failed" for step in steps):
            result.update(outcome="failed", reason="cms_step_failed")
            return result
        finished()

        begin("COMPLETE_REG")
        registration = stages.complete_registration(request, case, cem)
        result["registration"] = registration
        if (isinstance(registration, dict)
                and registration.get("option") == ("10" if cem else "3")
                and registration.get("case_id_entered") is True
                and isinstance(registration.get("readback"), str)
                and registration["readback"].strip() == case.case_id):
            finished()
            result.update(outcome="completed", reason="registered")
        else:
            result.update(outcome="failed", reason="registration_not_verified")
        return result
    except (Exception, SystemExit) as exc:
        result.update(outcome="failed", reason="exception",
                      error=dict(stage=result["stage"], type=type(exc).__name__,
                                 message=str(exc)[:300]))
        return result
