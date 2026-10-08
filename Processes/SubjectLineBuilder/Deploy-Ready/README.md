# Shared implementation

Manual standalone uses `manual_flow.run_manual` with `rrs_ui.RRSAdapter`.
`excel_input.py` generates and reads the standalone Excel input contract.
The main application continues to use `subject_line_flow.run_flow(runtime, app=...)`
and `legacy_steps.py`. The manual runner never calls the legacy PDF/CMS stages.
See the parent README for the two entry points and their boundaries.
