# Re-open check and customer validation

The standalone desktop app is **CMSCustomerSearch** (`dist/CMSCustomerSearch.exe`).
It offers daily Excel/Record ID selection, manual input, offline scenarios and
live CMS execution. See [desktop setup](Stand-Alone/README.md#windows-desktop-application).
The source folder stays `Reopen-Check` for existing integrations.

This process now has one shared controller used by the intake application and
the standalone runner. You can debug it without starting the full intake bot.

```text
Reopen-Check/
  Deploy-Ready/
    reopen_flow.py       Shared controller; injectable CMS, customer and UI calls
    README.md           Application integration and deployment requirements
  Stand-Alone/
    run.py              Offline scenarios or live CMS execution
    test_flow.py        Tests requiring only Python's standard library
    scenarios/          Synthetic examples, no real claim information
    README.md           Commands and debugging instructions
```

The controller searches cases, displays the existing open/closed-case results,
requests permission to continue, and then validates the customer. It preserves
the Goodyear/Cooper Tire open-TCM manual-processing rule. An unresolved customer
or a handoff to CEM stops the intake flow instead of continuing with an
unvalidated customer.

The CMS search, database eligibility checks, matching and CEM implementations
remain shared repository dependencies. They have not been copied into two
folders. Deploy-Ready is integration source, not an independently packaged EXE.

Current business rules remain: no cases continues to customer validation;
ineligible closed cases are shown with their warnings; multiple customer
matches may be resolved by the existing similarity scorer. The proposed table's
different stop/filter/manual-selection rules and AI customer matching are not
enabled by this reorganization.
