"""Re-open/customer flow, independent of browsers, databases and desktop UI.

Dependencies are passed as callables so the same process can run in the intake
app, the standalone runner, or offline tests. No session is opened on import.

check_customer returns the resolved customer string, a falsey value when the
operator declined CEM / nothing resolved (reason customer_unresolved_or_cem,
unchanged), or a needs-CEM marker mapping ({"needs_cem": True, ...}). CEM runs
in the separate operator-started CEMRequest app; this flow only reports the
handoff values (reason needs_cem) and never starts CEM itself.
"""

NEEDS_CEM_INSTRUCTION = "Employer not found in CMS. Start the CEM app (CEMRequest) with these values."


def is_needs_cem(value):
    return isinstance(value, dict) and value.get("needs_cem") is True


def cem_handoff(data):
    """Handoff from the flow inputs; claim_number is never replaced by claim ID."""
    return {"employer_name": str(data.get("customer") or ""),
            "claim_number": str(data.get("claimNumber") or ""),
            "claim_id": str(data.get("claimID") or ""),
            "claimant_full": str(data.get("claimantFull") or "")}


def run_flow(data, *, search_cases, check_customer, notify, confirm, stage="all"):
    if stage not in {"all", "reopen", "customer"}:
        raise ValueError("stage must be all, reopen or customer")
    required = []
    if stage in {"all", "reopen"}:
        required += ["claimNumber"]
    if stage in {"all", "customer"}:
        required += ["customer", "claimID", "claimantFull"]
    missing = [key for key in required if not str(data.get(key) or "").strip()]
    if missing:
        raise ValueError("Missing process inputs: " + ", ".join(missing))

    result = {"status": "completed", "reason": "", "customer": data.get("customer", ""),
              "cases": [], "steps": []}
    if stage in {"all", "reopen"}:
        result["steps"].append("search_cases")
        cases = search_cases(data["claimNumber"], data.get("claimantFull"))
        result["cases"] = cases
        visible = [case for case in cases if case.get("case_status") in {"C", "O"}]
        open_tcm = any(case.get("caseType") == "TCM" and case.get("case_status") == "O" for case in cases)
        customer = str(data.get("customer", "")).lower()
        referral = str(data.get("referralType", "")).lower()
        tire_customer = "goodyear tire" in customer or "cooper tire" in customer
        special_referral = "full case management" in referral or "one-time rn visit" in referral
        if open_tcm and tire_customer and special_referral:
            notify("Goodyear/Cooper Tire Instruction For Open TCM",
                   "For Manual Process Bot Stop. Send an email to Jen.Herbert@enlyte.com and "
                   "richard.castellini@enlyte.com\nRequest assistance to have the Full Med referral "
                   "cancelled and resubmitted by Liberty as a One-Time RN Visit Provider")
            result.update(status="stopped", reason="tire_customer_open_tcm")
            return result
        if visible:
            result["steps"].append("review_cases")
            notify("Open/Closed Cases", "\n\n".join(
                f"{case.get('cms_caseNum', '')}\n{case.get('caseType', '')}\n{case.get('message', '')}"
                for case in visible))
            if not confirm("User Confirmation", "Select Yes if bot would proceed.\nSelect No if bot to stop process."):
                result.update(status="stopped", reason="user_declined")
                return result
        else:
            notify("Case Checker - CMS", "No Open or Closed Cases Found in CMS")
    if stage in {"all", "customer"}:
        result["steps"].append("validate_customer")
        selected = check_customer(data["customer"], data["claimID"], data["claimantFull"])
        if is_needs_cem(selected):
            handoff = cem_handoff(data)
            notify("CEM Required", NEEDS_CEM_INSTRUCTION + "\n\n" + "\n".join(
                f"{label}: {handoff[key]}" for key, label in (
                    ("employer_name", "Employer Name"), ("claim_number", "Claim Number"),
                    ("claim_id", "Claim ID"), ("claimant_full", "Claimant Full Name"))))
            result.update(status="stopped", reason="needs_cem", cem_handoff=handoff,
                          instruction=NEEDS_CEM_INSTRUCTION)
            return result
        # A mapping is never a customer name; only the marker above means needs_cem.
        if isinstance(selected, dict) or not selected or not str(selected).strip():
            result.update(status="stopped", reason="customer_unresolved_or_cem")
            return result
        result["customer"] = str(selected).strip()
    return result
