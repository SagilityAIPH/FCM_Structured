# AI-FCM current logic flowchart

Open **AI-FCM-Current-Logic.vdx** in Microsoft Visio using File > Open.
It contains editable text, shapes and arrow paths on four pages. To use the
modern Visio format, choose Save As > Visio Drawing (*.vsdx). Arrow paths are
editable geometry; reposition them when moving nodes (they are not auto-routed).

- Page 1: document input, Bedrock extraction, malformed-output retry and results.
- Page 2: primary-section precedence and permitted Special Instructions fallback.
- Page 3: provider cleanup, deduplication, compatible-record merging and sorting.
- Page 4: NEXT STEP completeness, optional fields, Passed and Failed.

`AI-FCM-Current-Logic.html` previews all pages in a browser using the accompanying
SVG files. `AI-FCM-Current-Logic.pdf` provides a portable four-page copy.

Based on release v1.3.0, commit b019403, and the current files:
`AI/bedrock_core.py`, `AI/referral_schema.py`, `AI/launch_bedrock.py`,
`AI/ai_fcm_bedrock.py`, and `AI/ai_fcm_bedrock_runtime.py`.
Source separation is requested from the model; Python operates on those
returned values, not independently proven document provenance. Completeness
does not measure accuracy, and Passed does not start CMS automatically.

The Visio XML was generated and checked for well-formedness, page/shape IDs,
and matching source logic. SVG previews were visually inspected. Microsoft
Visio is not installed on the authoring machine, so native opening was not
verified here.

Regenerate Visio XML and SVG/HTML previews from this repository:

```powershell
rtk proxy python docs/diagrams/build_ai_flowchart.py
```
