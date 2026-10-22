"""Unity assignment flow, independent of browsers, databases and desktop UI.

Dependencies are passed as callables so the same process can run in the intake
app, the standalone runner, or offline tests. No session is opened on import.

This controller is a boundary around the legacy stage, not a rewrite. The live
work still lives in `legacy_unity.validate_and_complete_task`, roughly 1,280
lines welded to the Unity portal's DOM; the same reasoning that kept
`CreateSubjectLineBuilder` whole applies here.

Two deliberate differences from legacy `OpenUnity`:

1. Legacy loses the outcome. `legacy_unity.main` catches every exception, prints
   it and returns None, so a failed assignment is indistinguishable from a
   successful one. Here the stage reports completed, stopped or failed, with a
   business stop kept distinct from a technical failure.

2. Legacy trusts `glob.glob(ATTACHMENT_FOLDER + "/*")[0]`, which is filesystem
   order rather than newest-first, so a folder holding a previous referral's
   export uploads the WRONG DOCUMENT to the claim - and the failure is swallowed
   by a bare `except` that only prints. This controller resolves the attachment
   BEFORE the stage runs and stops when the folder does not hold exactly one
   file, so that upload cannot happen silently.

PRESERVED ON PURPOSE: legacy records the assignment from a `finally`, so the row
is written even when Unity raised. That is preserved by default, because
silently changing what reaches a production table belongs to the process owner
rather than to a port. Pass record_attempt_on_failure=False to record only
successful runs.
"""

STAGES = ("all", "unity", "assign")


def run_flow(data, *, list_attachments, run_unity, record_assignment, notify, confirm,
             complete_assignment, stage="all", record_attempt_on_failure=True):
    """Run the Unity assignment boundary; return completed, stopped or failed.

    list_attachments() returns the candidate export files for this referral.
    run_unity(customer, claimant_full, data) drives the portal.
    record_assignment(claimant_full, claim_number) writes the tracking row.
    complete_assignment(claim_number) finishes the assignment back in RRS.
    confirm(title, message) owns the iCaseManager approval gate.
    """
    if stage not in STAGES:
        raise ValueError("stage must be all, unity or assign")
    required = []
    if stage in {"all", "unity"}:
        required += ["customer", "claimantFirst", "claimantLast"]
    required += ["claimNumber"]
    missing = [key for key in dict.fromkeys(required) if not str(data.get(key) or "").strip()]
    if missing:
        raise ValueError("Missing process inputs: " + ", ".join(missing))

    claimant_full = f"{str(data.get('claimantFirst', '')).strip()} {str(data.get('claimantLast', '')).strip()}".strip()
    claim_number = str(data["claimNumber"]).strip()
    result = {"status": "completed", "reason": "", "claimantFull": claimant_full,
              "attachment": "", "steps": [], "error": {}}

    def fail(step, error):
        result.update(status="failed", reason=f"{step}_failed",
                      error={"stage": step, "type": type(error).__name__, "message": str(error)})
        if isinstance(error, SystemExit):
            result["error"]["exit_code"] = error.code
        return result

    if stage in {"all", "unity"}:
        # Resolve the attachment first: an ambiguous folder must never reach the
        # legacy uploader, which would silently take whichever file glob listed.
        result["steps"].append("resolve_attachment")
        try:
            attachments = list(list_attachments() or [])
        except (Exception, SystemExit) as error:
            return fail("resolve_attachment", error)
        if not attachments:
            notify("Unity Attachment", "No referral document was found. Select a local referral PDF "
                                       "or use RRS Complete Triage to export the attachment before Unity runs.")
            result.update(status="stopped", reason="attachment_missing")
            return result
        if len(attachments) > 1:
            notify("Unity Attachment", f"{len(attachments)} files are waiting in the export folder, so the "
                                       "correct document cannot be identified. Select a local referral PDF or clear the folder and re-export "
                                       "this referral before continuing.")
            result.update(status="stopped", reason="attachment_ambiguous")
            return result
        result["attachment"] = str(attachments[0])

        result["steps"].append("run_unity")
        unity_error = None
        try:
            run_unity(data["customer"], claimant_full, data)
        except SystemExit as error:
            unity_error = error
        except Exception as error:
            unity_error = error

        if unity_error is None or record_attempt_on_failure:
            result["steps"].append("record_assignment")
            try:
                record_assignment(claimant_full, claim_number)
            except (Exception, SystemExit) as error:
                if unity_error is None:
                    return fail("record_assignment", error)
        if unity_error is not None:
            return fail("run_unity", unity_error)

    if stage in {"all", "assign"}:
        result["steps"].append("await_icasemanager_approval")
        try:
            approved = confirm("Complete Assignment Stopper",
                               "Click Yes once the referral is approved in iCaseManager to proceed with "
                               "Complete Assignment.\nClick No to stop here.")
        except (Exception, SystemExit) as error:
            return fail("await_icasemanager_approval", error)
        if not approved:
            result.update(status="stopped", reason="icasemanager_declined")
            return result

        result["steps"].append("complete_assignment")
        try:
            complete_assignment(claim_number)
        except SystemExit as error:
            return fail("complete_assignment", error)
        except Exception as error:
            return fail("complete_assignment", error)

    return result
