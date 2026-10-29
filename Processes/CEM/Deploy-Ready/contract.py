"""Immutable, offline CEM request and injected-stage contract."""
from dataclasses import dataclass
from typing import Callable

STAGES = ("START", "VERIFY_SOURCE", "SEARCH", "REVIEW", "SUBMIT", "VERIFY_RECEIPT", "TRACK")
OUTCOMES = ("completed", "stopped", "cancelled", "failed")
REASONS = ("invalid_request", "configuration_required", "address_required", "already_exists",
           "ambiguous_employer", "search_unverified", "duplicate_request", "bill_to_unverified",
           "form_not_verified", "operator_cancelled", "submit_declined", "submit_uncertain",
           "receipt_not_found", "tracking_failed_after_submit", "exception", "request_submitted")

@dataclass(frozen=True)
class CEMRequest:
    employer_name: str
    claim_number: str
    claim_id: str
    claimant_first_name: str
    claimant_last_name: str
    address1: str = ""
    address2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "USA"
    referral_number: str = ""
    record_id: str = ""

    def validate(self) -> list[str]:
        problems = []
        if not isinstance(self.employer_name, str) or self.employer_name.strip().casefold() in (
            "", "not found", "not given/not applicable", "no employer"
        ):
            problems.append("A valid employer name is required.")
        elif self.employer_name.strip().startswith(("=", "+", "-", "@")) or any(ord(c) < 32 for c in self.employer_name):
            problems.append("Employer name contains unsafe characters.")
        for field, label in (("claim_number", "Claim number"), ("claim_id", "Claim ID"),
                             ("claimant_first_name", "Claimant first name"),
                             ("claimant_last_name", "Claimant last name")):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{label} is required.")
            elif value.strip().startswith(("=", "+", "-", "@")) or any(ord(c) < 32 for c in value):
                problems.append(f"{label} contains unsafe characters.")
        return problems

@dataclass(frozen=True)
class CEMSettings:
    environment: str = "uat"
    employer_search_url: str = ""
    employer_add_url: str = ""
    allow_placeholder_address: bool = False
    cem_log_path: str = ""
    edge_driver_path: str = ""
    timeout_seconds: float = 15.0

@dataclass(frozen=True)
class StepResult:
    step: str
    status: str
    detail: str = ""

@dataclass(frozen=True)
class CEMStages:
    # search_employer returns {'state': 'results'|'no_results'|'loading', 'names': [...]}
    search_employer: Callable
    find_existing_request: Callable
    fill_form: Callable
    review: Callable
    confirm_submit: Callable
    submit: Callable
    read_back_request: Callable
    record: Callable
    find_log_duplicate: Callable


def new_result() -> dict:
    """All keys exist even when validation stops before opening a browser."""
    return dict(outcome="failed", reason="", stage="START", stages=[], steps=[],
                request_status="not_submitted", request_reference="", tracking_status="not_attempted",
                cem_log_row=None, problems=[], error=None, warning="")
