"""Re-open/customer flow, independent of browsers, databases and desktop UI.

Dependencies are passed as callables so the same process can run in the intake
app, the standalone runner, or offline tests. No session is opened on import.
"""


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
        cases = search_cases(data["claimNumber"])
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
        if not selected or not str(selected).strip():
            result.update(status="stopped", reason="customer_unresolved_or_cem")
            return result
        result["customer"] = str(selected).strip()
    return result
