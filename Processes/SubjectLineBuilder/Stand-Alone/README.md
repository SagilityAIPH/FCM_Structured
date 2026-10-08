# Manual desktop runner

Launch `run.py` or `launcher.py` for Excel input or manual entry. Fill the included
`SubjectLineBuilder-Input.xlsx`, then Open Excel, choose a row and Load row.
The form remains editable. Save template creates a blank workbook from the app.
Build with `build.ps1` to create the EXE and template in `dist`:
`dist/SubjectLineBuilder.exe`. Uses the AI PDF Reader theme and native dimensions.
No upstream PDF, AI or CMS stages are called.

See [process instructions](../README.md) for the operator flow, requirements,
verification commands and live-testing limits.
