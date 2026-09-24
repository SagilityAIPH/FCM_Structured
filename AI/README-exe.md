# Native AI-FCM Bedrock application

Double-click `dist/AI-FCM-Bedrock.exe` on 64-bit Windows. This opens a native
desktop window. Python is bundled; Streamlit, a browser, and a local web
server are not used. No Python installation commands are needed on the client.

1. Enter your AWS region, model, and Bedrock API key.
2. Choose **Test connection** to check inference access.
3. Choose **Open document** for a selectable PDF, DOCX, or TXT.
4. Review **Document text** and **Text sent to Bedrock**.
5. Choose **Extract fields**, then save CSV, JSON, or TXT results.

Network access to `https://bedrock-mantle.<region>.api.aws/v1` and access to
the selected model are required. Extraction sends document text to Bedrock.
Scanned PDFs need OCR first. Closing the window exits the application.
First launch can take a little time while the single-file EXE extracts itself.

No keys or sample documents are bundled. The key can be entered in the window,
provided as `OPENAI_API_KEY`, or placed in a `.env` beside the EXE.
Keys entered in the window are not saved by the application.

## Build and validate

On 64-bit Windows with Python 3.14 and RTK installed:

```powershell
rtk proxy powershell -ExecutionPolicy Bypass -File AI/build_bedrock.ps1
rtk proxy python AI/smoke_bedrock.py
```

The build uses `.venv-bedrock` and writes `dist/AI-FCM-Bedrock.exe`.
The smoke test runs the executable outside the repository, creates the native
window hidden, reads synthetic PDF/DOCX/TXT, exercises background extraction
with a mock model, and checks CSV/JSON/TXT exports without contacting Bedrock.

`bedrock_core.py` contains the shared extraction logic used by both the native
launcher and the original `ai_fcm_bedrock.py` Streamlit interface.
