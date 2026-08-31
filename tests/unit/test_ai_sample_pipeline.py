import csv
import json

import pymupdf

from AI.batch_samples import (
    EXPECTED_PREFIX,
    PREDICTED_PREFIX,
    export_review,
    load_extraction_core,
    scan_samples,
    score_review,
)


def test_load_core_without_streamlit_or_boto3_imports():
    core = load_extraction_core()

    assert len(core["REQUIRED_FIELDS"]) == 14
    assert "{DOCUMENT_TEXT}" in core["FIELD_ONLY_PROMPT"]
    assert callable(core["run_reasoning"])


def test_loaded_core_runs_production_post_processing_with_stubbed_model():
    core = load_extraction_core()
    fields = core["REQUIRED_FIELDS"]
    values = {field: "Not found" for field in fields}
    values["Provider Phone"] = "555-555-0100"
    values["Provider Name (First Name / Last Name)"] = "Example Clinic"
    values["Determining if Doctor or Provider Name"] = "Facility"
    model_output = "\n".join(f"{field}: {values[field]}" for field in fields)
    core["call_llm_once"] = lambda **_kwargs: model_output

    _final_text, final_fields, _raw, _elapsed = core["run_reasoning"](
        client=object(),
        model_id="stub",
        full_document_text="Provider / Facility Name: Example Clinic\nPhone Number: 555-555-0100",
    )

    assert list(final_fields) == fields
    assert final_fields["Provider Phone"] == "555-555-0100"
    assert final_fields["Determining if Doctor or Provider Name"] == "Facility"


def test_scan_samples_reads_pdf_text(tmp_path):
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Provider Name: Example Clinic\nAppointment Date: 01/02/2026")
    document.save(sample_dir / "sample.pdf")
    document.close()

    report = scan_samples(sample_dir)

    assert report["document_count"] == 1
    assert report["page_count"] == 1
    assert report["readable_count"] == 1
    assert len(report["documents"][0]["document_id"]) == 16


def test_review_export_and_score(tmp_path):
    core = load_extraction_core()
    fields = core["REQUIRED_FIELDS"]
    results = tmp_path / "results.jsonl"
    result = {
        "status": "ok",
        "document_id": "abc123",
        "source_file": "sample.pdf",
        "fields": {field: "Not found" for field in fields},
    }
    results.write_text(json.dumps(result) + "\n", encoding="utf-8")
    review = tmp_path / "review.csv"

    assert export_review(results, review) == 1
    with review.open(newline="", encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))
    row["reviewed"] = "yes"
    row[PREDICTED_PREFIX + fields[0]] = "555-0100"
    row[EXPECTED_PREFIX + fields[0]] = "555-0100"
    row[PREDICTED_PREFIX + fields[1]] = "01/02/2026"
    row[EXPECTED_PREFIX + fields[1]] = "01/03/2026"
    with review.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    score = score_review(review)

    assert score["reviewed_documents"] == 1
    assert score["field_values_scored"] == 14
    assert score["per_field"][fields[0]]["accuracy"] == 1.0
    assert score["per_field"][fields[1]]["accuracy"] == 0.0
