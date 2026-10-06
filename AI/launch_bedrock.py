"""Native Windows interface for the shared Bedrock extraction engine."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import queue
import sys
import threading
from datetime import datetime
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from dotenv import load_dotenv
import bedrock_runtime as core
from daily_output import save_daily_output, output_directory
from address_enrichment import suggest_addresses, apply_suggestions
from appointment_rules import appointment_checks, confirm_appointments


class BedrockApp:
    def __init__(self, root):
        self.root = root
        root.title("AI-FCM Bedrock Runtime")
        root.geometry("1050x760")
        root.minsize(800, 580)
        self.events = queue.Queue()
        self.busy = False
        self.full_text = ""
        self.fields = None
        self.daily_directory = output_directory()
        self.record_id = None
        self.extracted_at = None
        self.result = ""
        self.address_report = []
        self.daily_update = False
        self.controls = []
        body = ttk.Frame(root, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="AI-FCM Bedrock Runtime", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(body, text="Read a PDF, Word document, or text file, then extract fields with Amazon Bedrock.").pack(anchor="w", pady=(4, 12))
        settings = ttk.LabelFrame(body, text="Bedrock settings", padding=10)
        settings.pack(fill="x")
        self.region = tk.StringVar(value=core.DEFAULT_BEDROCK_REGION)
        self.model = tk.StringVar(value=core.DEFAULT_BEDROCK_MODEL)
        self.key = tk.StringVar(value=core.resolve_bedrock_api_key())
        self.tokens = tk.StringVar(value=str(core.DEFAULT_MAX_TOKENS))
        self.temperature = tk.StringVar(value=str(core.DEFAULT_TEMP))
        self.limit = tk.StringVar(value=str(core.DEFAULT_MAX_DOC_CHARS))
        for row, (label, variable) in enumerate((("AWS region", self.region), ("Model", self.model), ("API key", self.key))):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
            entry = ttk.Entry(settings, textvariable=variable, show="*" if variable is self.key else "")
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self.controls.append(entry)
        settings.columnconfigure(1, weight=1)
        options = ttk.Frame(settings)
        options.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        for label, variable in (("Output tokens", self.tokens), ("Temperature", self.temperature), ("Document character limit", self.limit)):
            ttk.Label(options, text=label).pack(side="left", padx=(0, 5))
            entry = ttk.Entry(options, textvariable=variable, width=9)
            entry.pack(side="left", padx=(0, 15))
            self.controls.append(entry)
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=12)
        for label, command in (("1. Open document", self.open_document), ("Test connection", self.test_connection), ("2. Extract fields", self.extract)):
            button = ttk.Button(actions, text=label, command=command)
            button.pack(side="left", padx=(0, 8))
            self.controls.append(button)
        self.filename = tk.StringVar(value="No document selected")
        address_actions = ttk.Frame(body)
        address_actions.pack(fill="x")
        for label, command in (("3. Look up missing address fields", self.lookup_addresses), ("4. Review and apply address suggestions", self.review_addresses)):
            button = ttk.Button(address_actions, text=label, command=command)
            button.pack(side="left", padx=(0, 8))
            self.controls.append(button)
        ttk.Label(body, text="Address lookup sends only partial addresses to the U.S. Census service. Review suggestions before applying.").pack(anchor="w")
        ttk.Label(body, textvariable=self.filename).pack(anchor="w")
        button = ttk.Button(body, text='Review and confirm appointments', command=self.review_appointments)
        button.pack(anchor='w', pady=4)
        self.controls.append(button)
        tabs = ttk.Notebook(body)
        tabs.pack(fill="both", expand=True, pady=8)
        self.views = {}
        for title in ("Document text", "Text sent to Bedrock", "Extracted fields", "NEXT STEP", "Address Review", "JSON", "Raw output"):
            widget = ScrolledText(tabs, wrap="word", font=("Consolas", 10), state="disabled")
            tabs.add(widget, text=title)
            self.views[title] = widget
        self.tabs = tabs
        footer = ttk.Frame(body)
        footer.pack(fill="x")
        for label, kind in (("Save CSV", "csv"), ("Save JSON", "json"), ("Save results TXT", "txt"), ("Save document text", "document")):
            ttk.Button(footer, text=label, command=lambda k=kind: self.save(k)).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="Save daily Excel / Retry", command=self.save_daily).pack(side="left")
        self.status = tk.StringVar(value="Ready. Document text is sent to Bedrock only when you choose Extract fields.")
        self.next_step = tk.StringVar(value="NEXT STEP: Awaiting extraction")
        ttk.Label(body, textvariable=self.next_step, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(8, 0))
        ttk.Label(body, textvariable=self.status, wraplength=950).pack(anchor="w", pady=(10, 0))
        self.limit.trace_add("write", lambda *_: self.preview())
        root.after(100, self.poll)

    def set_view(self, name, text):
        widget = self.views[name]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def preview(self):
        try:
            limit = int(self.limit.get())
        except ValueError:
            return
        self.set_view("Text sent to Bedrock", self.full_text[:max(0, limit)])

    def run_task(self, message, work, done):
        if self.busy:
            return
        self.busy = True
        self.status.set(message)
        for control in self.controls:
            control.configure(state="disabled")
        def worker():
            try:
                self.events.put((done, work(), None))
            except Exception as error:
                self.events.put((done, None, error))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            done, result, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            for control in self.controls:
                control.configure(state="normal")
            if error:
                self.status.set("Operation failed.")
                messagebox.showerror("AI-FCM Bedrock", str(error), parent=self.root)
            else:
                done(result)
        self.root.after(100, self.poll)

    def clear_results(self):
        self.fields = None
        self.record_id = None
        self.extracted_at = None
        self.result = ""
        self.address_report = []
        self.daily_update = False
        self.next_step.set("NEXT STEP: Awaiting extraction")
        for name in ("Extracted fields", "NEXT STEP", "Address Review", "JSON", "Raw output"):
            self.set_view(name, "")

    def load_document(self, path):
        self.clear_results()
        self.full_text = ""
        self.set_view("Document text", "")
        self.preview()
        self.filename.set(str(path))
        def work():
            with Path(path).open("rb") as document:
                return core.join_pages(core.extract_document_pages(document))
        def done(text):
            self.full_text = text
            self.set_view("Document text", text)
            self.preview()
            self.tabs.select(self.views["Document text"])
            self.status.set(f"Read {len(text):,} characters. Review text before extraction." if text.strip() else "No text found. Scanned PDFs require OCR; use a selectable PDF, DOCX, or TXT.")
        self.run_task("Reading document...", work, done)

    def open_document(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Supported documents", "*.pdf *.docx *.txt")])
        if path:
            self.load_document(path)

    def settings(self):
        region, model, key = self.region.get().strip(), self.model.get().strip(), self.key.get().strip()
        if not region or not model or not key:
            raise ValueError("Enter an AWS region, model, and Bedrock API key.")
        return region, model, key

    def test_connection(self):
        try:
            region, model, key = self.settings()
        except ValueError as error:
            messagebox.showerror("Settings", str(error), parent=self.root)
            return
        def work():
            with core.create_bedrock_client(key, core.build_bedrock_base_url(region)) as client:
                return core.test_bedrock_connection(client, model)
        self.run_task("Testing Bedrock inference access...", work,
                      lambda result: self.status.set("Bedrock responded: " + (result[:200] or "[empty response]")))

    def extract(self):
        try:
            region, model, key = self.settings()
            tokens, temperature, limit = int(self.tokens.get()), float(self.temperature.get()), int(self.limit.get())
            if not (128 <= tokens <= core.MAX_OUTPUT_TOKENS and 0 <= temperature <= 0.5 and 5000 <= limit <= 400000):
                raise ValueError(f"Use 128–{core.MAX_OUTPUT_TOKENS:,} tokens, temperature 0–0.5, and 5,000–400,000 document characters.")
            if not self.full_text.strip():
                raise ValueError("Open a document containing selectable text first.")
        except ValueError as error:
            messagebox.showerror("Cannot extract", str(error), parent=self.root)
            return
        full_text = self.full_text
        self.clear_results()
        def work():
            with core.create_bedrock_client(key, core.build_bedrock_base_url(region)) as client:
                return core.run_reasoning(client, model, full_text[:limit], full_text, tokens, temperature)
        def done(result):
            self.result, self.fields, raw, elapsed = result
            self.record_id = str(uuid.uuid4())
            self.extracted_at = datetime.now().astimezone()
            readiness = core.completeness(self.fields)
            self.next_step.set("NEXT STEP: " + readiness["status"])
            self.set_view("NEXT STEP", core.next_step_text(self.fields))
            self.set_view("Extracted fields", self.result)
            self.set_view("JSON", json.dumps(core.export_payload(self.fields), indent=2, ensure_ascii=False))
            self.set_view("Raw output", raw)
            self.tabs.select(self.views["Extracted fields"])
            self.status.set(f"Completed in {elapsed}s using {model}. Sent {min(len(full_text), limit):,} of {len(full_text):,} characters.")
            self.save_daily()
        self.run_task(f"Sending {min(len(full_text), limit):,} of {len(full_text):,} characters to Bedrock...", work, done)

    def lookup_addresses(self):
        if self.fields is None or self.busy:
            return
        def done(report):
            self.address_report = report
            self.set_view("Address Review", json.dumps(report, indent=2) if report else "No partial addresses to look up.")
            self.tabs.select(self.views["Address Review"])
            self.status.set("Lookup finished. Suggestions have not changed the extraction or NEXT STEP.")
        self.run_task("Looking up partial addresses with the U.S. Census service...", lambda: suggest_addresses(self.fields), done)

    def review_addresses(self):
        if self.fields is None or self.busy:
            return
        selected = []
        for index, item in enumerate(self.address_report):
            if item["status"] == "suggested":
                details = "\n".join(f"{key}: {value['original']} -> {value['suggested']}" for key, value in item["changes"].items())
                if messagebox.askyesno("Apply address suggestion: " + item["target"],
                    details + "\n\n" + item["source"] + "\n" + item["reason"] + "\n\nApply to this record and daily Excel?", parent=self.root):
                    selected.append(index)
        if not selected:
            return
        self.fields = apply_suggestions(self.fields, self.address_report, selected)
        for index in selected:
            self.address_report[index]["status"] = "accepted"
        self.result = core.format_field_block(self.fields)
        self.set_view("Extracted fields", self.result)
        self.set_view("JSON", json.dumps(core.export_payload(self.fields), indent=2))
        self.set_view("Address Review", json.dumps(self.fields.address_review, indent=2))
        self.set_view("NEXT STEP", core.next_step_text(self.fields))
        self.next_step.set("NEXT STEP: " + core.completeness(self.fields)["status"])
        self.daily_update = True
        self.save_daily()

    def save_daily(self):
        if self.fields is None or self.record_id is None:
            messagebox.showinfo("Daily Excel", "Extract fields first.", parent=self.root)
            return
        try:
            path, record_id = save_daily_output(self.fields, self.filename.get(), directory=self.daily_directory,
                                               record_id=self.record_id, extracted_at=self.extracted_at, update_existing=self.daily_update)
            self.daily_update = False
            self.status.set(f"Daily Excel saved: {path} | Record ID: {record_id}")
        except Exception as error:
            self.status.set("Extraction is ready, but daily Excel was not saved. Use Save daily Excel / Retry.")
            messagebox.showerror("Daily Excel not saved", f"{error}\nClose the workbook in Excel and retry saving.", parent=self.root)

    def review_appointments(self):
        if self.fields is None or self.busy:
            return
        selected = []
        for item in appointment_checks(self.fields):
            if item['can_confirm'] and not item['confirmed']:
                provider = self.fields.providers[item['provider_index'] - 1]
                identity = ' / '.join(provider.get(k, 'Not found') for k in
                    ('Provider Name (First Name / Last Name)', 'Doctor First Name', 'Doctor Last Name'))
                detail = (f"Provider {item['provider_index']}: {identity}\n"
                          f"Date: {item['appointment_date']}\nTime: {provider.get('Appointment Time', 'Not found')}\n\n"
                          + '\n'.join(item['reasons']) + '\n\nHave you verified and confirmed this appointment?')
                if messagebox.askyesno('Confirm appointment', detail, parent=self.root):
                    selected.append(item['provider_index'])
        if not selected:
            self.set_view('NEXT STEP', core.next_step_text(self.fields))
            self.tabs.select(self.views['NEXT STEP'])
            return
        self.fields = confirm_appointments(self.fields, selected)
        self.result = core.format_field_block(self.fields)
        self.set_view('Extracted fields', self.result)
        self.set_view('JSON', json.dumps(core.export_payload(self.fields), indent=2))
        self.set_view('NEXT STEP', core.next_step_text(self.fields))
        self.next_step.set('NEXT STEP: ' + core.completeness(self.fields)['status'])
        self.daily_update = True
        self.save_daily()

    def export_content(self, kind):
        if kind == "document":
            if not self.full_text:
                raise ValueError("Open a document first.")
            return self.full_text
        if self.fields is None:
            raise ValueError("Extract fields first.")
        if kind == "csv":
            return core.table_df_to_csv_text(core.fields_to_table_df(self.fields))
        if kind == "json":
            return json.dumps(core.export_payload(self.fields), indent=2, ensure_ascii=False)
        return self.result

    def save(self, kind):
        try:
            content = self.export_content(kind)
            extension = "txt" if kind == "document" else kind
            path = filedialog.asksaveasfilename(parent=self.root, defaultextension="." + extension,
                initialfile="fcm_" + kind + "." + extension, filetypes=[(extension.upper(), "*." + extension)])
            if path:
                Path(path).write_text(content, encoding="utf-8-sig" if kind == "csv" else "utf-8")
                self.status.set("Saved " + path)
        except (ValueError, OSError) as error:
            messagebox.showerror("Cannot save", str(error), parent=self.root)


def self_test(root, app):
    """No network calls: exercise the native window and production processing."""
    from types import SimpleNamespace
    import tempfile
    import time
    with core.fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Portable PDF test")
        assert "Portable PDF test" in core.join_pages(core.extract_pages_from_pdf(document.tobytes()))
    document = core.Document()
    document.add_paragraph("Portable Word test")
    buffer = BytesIO()
    document.save(buffer)
    assert "Portable Word test" in core.join_pages(core.extract_pages_from_docx(buffer.getvalue()))
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "sample.txt"
        path.write_text("Provider Phone: 212-555-1234", encoding="utf-8")
        app.load_document(path)
        deadline = time.monotonic() + 20
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        assert not app.busy and "212-555-1234" in app.full_text
    payload = {field: "Not found" for field in core.REQUIRED_FIELDS if field not in core.PROVIDER_FIELDS}
    provider = {field: "Not found" for field in core.PROVIDER_FIELDS}
    provider["Provider Phone"] = "212-555-1234"
    payload["Provider Information"] = [provider]
    response = json.dumps(payload)
    class MockClient:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=response))])))
    original = core.create_bedrock_client
    test_output = tempfile.TemporaryDirectory()
    app.daily_directory = Path(test_output.name)
    core.create_bedrock_client = lambda *args: MockClient()
    try:
        app.key.set("local-test-placeholder")
        app.extract()
        deadline = time.monotonic() + 20
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        assert not app.busy and app.fields is not None
        assert "212" in json.loads(app.export_content("json"))["Provider Information"][0]["Phone Number"]
        assert "Provider Information" in app.export_content("csv")
        assert "Provider Information" in app.export_content("txt")
        assert app.next_step.get() == "NEXT STEP: Failed"
        assert len(list(app.daily_directory.glob("*.xlsx"))) == 1
        # Exercise review/apply and same-row Excel update without external calls.
        app.fields["Address-line-1"] = "123 Summer St"
        app.fields["City"] = "Worcester"
        match = {"matchedAddress": "123 SUMMER ST, WORCESTER, MA, 01608",
                 "addressComponents": {"city": "WORCESTER", "state": "MA", "zip": "01608"}}
        app.address_report = suggest_addresses(app.fields, lookup=lambda _: [match])
        original_confirm = messagebox.askyesno
        messagebox.askyesno = lambda *args, **kwargs: True
        try:
            app.review_addresses()
        finally:
            messagebox.askyesno = original_confirm
        assert app.fields["State"] == "MA" and app.fields["Zip"] == "01608"
        assert "Address Review" in json.loads(app.export_content("json"))
        from daily_output import read_record
        saved, _ = read_record(next(app.daily_directory.glob("*.xlsx")), app.record_id)
        assert saved["Zip"] == "01608" and saved.address_review
        app.fields.providers[0]['Appointment Date'] = '2020-07-04'
        app.fields.providers[0]['Appointment Time'] = 'Not found'
        app.fields['Appointment Date'] = '2020-07-04'
        app.fields['Appointment Time'] = 'Not found'
        messagebox.askyesno = lambda *args, **kwargs: False
        try:
            app.review_appointments()
            assert not getattr(app.fields, 'appointment_review', [])
            messagebox.askyesno = lambda *args, **kwargs: True
            app.review_appointments()
        finally:
            messagebox.askyesno = original_confirm
        assert app.fields.appointment_review[0]['status'] == 'confirmed'
        saved, assessment = read_record(next(app.daily_directory.glob('*.xlsx')), app.record_id)
        assert saved.appointment_review and not assessment['confirmation_required']
        assert json.loads(app.export_content('json'))['Provider Information'][0]['Date Only']
        assert "streamlit" not in sys.modules
    finally:
        core.create_bedrock_client = original
        test_output.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test-report", type=Path)
    args = parser.parse_args()
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    if not args.self_test_report:
        load_dotenv(base / ".env")
    root = tk.Tk()
    if args.self_test_report:
        root.withdraw()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        app = BedrockApp(root)
        if args.self_test_report:
            self_test(root, app)
            args.self_test_report.write_text("PASS: native UI, PDF/DOCX/TXT, background extraction, CSV/JSON/TXT exports; no Streamlit or network calls.", encoding="utf-8")
            root.destroy()
        else:
            root.mainloop()
    except Exception:
        import traceback
        details = traceback.format_exc()
        if args.self_test_report:
            args.self_test_report.write_text(details, encoding="utf-8")
        else:
            messagebox.showerror("AI-FCM Runtime startup failed", details)
        raise


if __name__ == "__main__":
    main()
