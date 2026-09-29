"""Daily Excel interchange for the AI reader and standalone processes.

One Referrals row per extraction; Providers rows preserve repeated records.
All field cells are written as literal text, including identifiers and formulas.
"""
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

try:
    from .referral_schema import REQUIRED_FIELDS, PROVIDER_FIELDS, ReferralFields, completeness
except ImportError:
    from referral_schema import REQUIRED_FIELDS, PROVIDER_FIELDS, ReferralFields, completeness

VERSION = "1"
HEADERS = ["Record ID", "Extracted At", "Source File", "NEXT STEP", "Missing Required Fields"] + REQUIRED_FIELDS
PROVIDER_HEADERS = ["Record ID", "Provider Index"] + PROVIDER_FIELDS


def output_directory():
    configured = os.getenv("FCM_AI_OUTPUT_DIR", "").strip()
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    return Path(configured).expanduser().resolve() if configured else base / "Output" / "AI"


@contextmanager
def workbook_lock(path):
    lock = path.with_suffix(".xlsx.lock")
    deadline = time.monotonic() + 5
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise OSError("Daily workbook is busy. Retry after the other writer finishes.")
            time.sleep(.1)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def append_text(sheet, values):
    row = sheet.max_row + 1 if sheet.cell(1, 1).value is not None else 1
    for column, value in enumerate(values, 1):
        text = str(value if value is not None else "")
        if len(text) > 32767:
            raise ValueError("An output value exceeds Excel's 32,767-character cell limit; workbook was not changed.")
        cell = sheet.cell(row, column, text)
        cell.data_type = "s"
        cell.number_format = "@"


def check_layout(book):
    if "Schema" not in book or book["Schema"]["B1"].value != VERSION:
        raise ValueError("Unsupported daily workbook schema.")
    for name, headers in [("Referrals", HEADERS), ("Providers", PROVIDER_HEADERS)]:
        if name not in book or [c.value for c in book[name][1]] != headers:
            raise ValueError(f"Unexpected {name} columns; use the AI daily output workbook without renaming headers.")


def save_daily_output(fields, source_file, *, directory=None, record_id=None, extracted_at=None):
    timestamp = extracted_at or datetime.now().astimezone()
    record_id = record_id or str(uuid.uuid4())
    folder = Path(directory) if directory is not None else output_directory()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"AI-FCM-Output-{timestamp:%Y-%m-%d}.xlsx"
    providers = getattr(fields, "providers", None)
    if providers is None:
        raise ValueError("Saving requires structured extraction results, including provider records.")
    assessment = completeness(fields)
    with workbook_lock(path):
        book = load_workbook(path) if path.exists() else Workbook()
        temp_path = None
        try:
            if path.exists():
                check_layout(book)
            else:
                book.active.title = "Referrals"
                append_text(book.active, HEADERS)
                append_text(book.create_sheet("Providers"), PROVIDER_HEADERS)
                append_text(book.create_sheet("Schema"), ["Version", VERSION])
            # Retrying a save of the same extraction never appends a duplicate.
            existing = [row[0] for row in book["Referrals"].iter_rows(min_row=2, values_only=True)]
            if record_id in existing:
                return path, record_id
            append_text(book["Referrals"], [record_id, timestamp.isoformat(), Path(source_file).name,
                        assessment["status"], "\n".join(assessment["missing_fields"])]
                        + [fields.get(key, "Not found") for key in REQUIRED_FIELDS])
            for index, provider in enumerate(providers, 1):
                append_text(book["Providers"], [record_id, index] + [provider.get(k, "Not found") for k in PROVIDER_FIELDS])
            for name in ["Referrals", "Providers"]:
                sheet = book[name]
                sheet.freeze_panes = "A2"
                sheet.auto_filter.ref = sheet.dimensions
                for cell in sheet[1]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="24486C")
                    sheet.column_dimensions[cell.column_letter].width = min(45, max(20, len(str(cell.value)) + 2))
            with tempfile.NamedTemporaryFile(dir=folder, suffix=".xlsx", delete=False) as temp:
                temp_path = Path(temp.name)
            book.save(temp_path)
            os.replace(temp_path, path)
        finally:
            book.close()
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    return path, record_id


def read_record(path, record_id):
    """Shared standalone reader; never executes Excel formulas."""
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        check_layout(book)
        rows = []
        for cells in book["Referrals"].iter_rows(min_row=2):
            if cells[0].value == record_id:
                if any(cell.data_type == "f" for cell in cells):
                    raise ValueError("Formula cells are not supported in process input.")
                rows.append(dict(zip(HEADERS, [cell.value for cell in cells])))
        if len(rows) != 1:
            raise ValueError("Record ID must identify exactly one Referrals row.")
        record = rows[0]
        providers = []
        for cells in book["Providers"].iter_rows(min_row=2):
            if cells[0].value == record_id:
                if any(cell.data_type == "f" for cell in cells):
                    raise ValueError("Formula cells are not supported in provider input.")
                providers.append(dict(zip(PROVIDER_FIELDS, [c.value or "Not found" for c in cells[2:]])))
        fields = ReferralFields({key: record.get(key) or "Not found" for key in REQUIRED_FIELDS}, providers)
        return fields, completeness(fields)
    finally:
        book.close()


def reopen_input(fields):
    def value(key):
        text = str(fields.get(key) or "").strip()
        return "" if text.casefold() == "not found" else text
    return {"claimNumber": value("Claim Number"), "customer": value("Employer Name"),
            "claimID": value("Claim ID"), "claimantFull": " ".join(filter(None, [value("First Name"), value("Last Name")])),
            "referralType": value("Referral Type")}
