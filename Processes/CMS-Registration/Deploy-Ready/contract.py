"""Phase 0 shared CMS Registration interface; no portal or database side effects.

Phase 1 implements cms_registration_flow.run_flow(request, *, stages,
on_stage=None, on_step=None, preview_only=False) -> dict and cms_steps.open_live_session(settings)
-> LiveSession. Phase 2 consumes both in its independent operator app.

The controller result dict always has ``outcome`` (one of OUTCOMES), ``reason``
(one of REASONS), ``stage`` (current/final stage name), ``stages`` (completed
stage names), ``case_id`` (confirmed CMS case ID), ``candidates`` (CaseCandidate
dicts), ``steps`` (StepResult dicts), ``registration`` (completion dict or None),
``cem`` (bool or None), ``problems`` (input validation messages), and ``error``
(a dict containing stage, type and message, or None). Completion is not proven
merely by invoking a callback: live adapters must verify identities and
readback before reporting success.

``preview_only=True`` stops with ``stopped / preview_only`` after REVIEW,
without invoking CMS_SETUP or COMPLETE_REG; it does not fill CMS fields.
"""

from dataclasses import dataclass
from typing import Callable


STAGES = ("START", "CASE", "DATA", "REVIEW", "CMS_SETUP", "COMPLETE_REG")
OUTCOMES = ("completed", "stopped", "cancelled", "failed")
REASONS = (
    "invalid_request", "case_not_confirmed", "no_matching_case", "case_ambiguous",
    "cem_status_unknown", "operator_cancelled", "cms_step_failed",
    "registration_not_verified", "exception", "registered", "preview_only",
)


@dataclass(frozen=True)
class RegistrationRequest:
    claim_number: str
    claimant_first_name: str
    claimant_last_name: str
    referral_type: str
    cms_case_id: str = ""
    referral_number: str = ""
    cem_employer_request: bool | None = None
    record_id: str = ""

    def validate(self) -> list[str]:
        """Return human-readable input problems without modifying the request."""
        problems = []
        if not self.claim_number or not self.claim_number.strip():
            problems.append("Claim number is required.")
        if not self.claimant_first_name or not self.claimant_first_name.strip():
            problems.append("Claimant first name is required.")
        if not self.claimant_last_name or not self.claimant_last_name.strip():
            problems.append("Claimant last name is required.")
        if self.referral_type not in ("Medical", "Vocational"):
            problems.append("Referral type must be 'Medical' or 'Vocational'.")
        return problems


@dataclass(frozen=True)
class CaseCandidate:
    case_id: str
    assigned_date: str  # ISO date or '' when unavailable
    referral_type: str
    status: str = ""
    source: str = "cms_search"


@dataclass(frozen=True)
class StepResult:
    step: str
    status: str  # 'done', 'skipped', 'manual', or 'failed'
    detail: str = ""


@dataclass(frozen=True)
class RegistrationStages:
    find_cases: Callable[[RegistrationRequest], list[CaseCandidate]]
    load_data: Callable[[RegistrationRequest, CaseCandidate], dict]
    review: Callable[[RegistrationRequest, CaseCandidate, dict], bool]
    setup_cms: Callable[[RegistrationRequest, CaseCandidate, dict, Callable[[StepResult], None]], list[StepResult]]
    complete_registration: Callable[[RegistrationRequest, CaseCandidate, bool], dict]
    # completion dict: {'option': '3' or '10', 'case_id_entered': bool,
    #                   'readback': str}
