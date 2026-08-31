"""Batch regression workflow for the AI-FCM sample PDFs.

The Streamlit application is intentionally not imported here.  Instead, this
module loads its literal prompt/constants and pure post-processing functions
from ``ai_fcm_bedrock_runtime.py``.  That keeps batch results aligned with the
application without executing Streamlit UI code.

All output defaults to ``AI/.sample_runs``.  Both that directory and the
sample source directory are gitignored because they can contain PHI.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests

try:
    import pymupdf
except ImportError as exc:  # pragma: no cover - exercised by CLI installations
    raise SystemExit(
        "PyMuPDF is required. Install the AI dependencies with: "
        "python -m pip install -e .[ai]"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES_DIR = PROJECT_ROOT / "Samples for AI"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / ".sample_runs"
DEFAULT_CORE_PATH = Path(__file__).resolve().parent / "ai_fcm_bedrock_runtime.py"
DEFAULT_REGION = "us-east-2"
DEFAULT_MODEL = "openai.gpt-oss-120b-1:0"
EXPECTED_PREFIX = "expected__"
PREDICTED_PREFIX = "predicted__"


def _document_id(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:16]


def extract_pdf(path: Path) -> tuple[str, int]:
    """Return text with stable page markers plus the page count."""
    parts: list[str] = []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            parts.append(f"===== PAGE {page_number} =====\n{text}")
        return "\n\n".join(parts).strip(), len(document)


def discover_samples(samples_dir: Path) -> list[Path]:
    if not samples_dir.is_dir():
        raise FileNotFoundError(f"Sample directory does not exist: {samples_dir}")
    samples = sorted(samples_dir.glob("*.pdf"), key=lambda item: item.name.casefold())
    if not samples:
        raise FileNotFoundError(f"No PDF samples found in: {samples_dir}")
    return samples


def scan_samples(samples_dir: Path) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    for path in discover_samples(samples_dir):
        text, pages = extract_pdf(path)
        documents.append(
            {
                "document_id": _document_id(path),
                "source_file": path.name,
                "pages": pages,
                "text_chars": len(text),
                "text_readable": len(text.strip()) >= 50,
            }
        )

    char_counts = sorted(item["text_chars"] for item in documents)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples_dir": str(samples_dir.resolve()),
        "document_count": len(documents),
        "page_count": sum(item["pages"] for item in documents),
        "readable_count": sum(item["text_readable"] for item in documents),
        "text_chars_total": sum(char_counts),
        "text_chars_min": min(char_counts),
        "text_chars_median": char_counts[len(char_counts) // 2],
        "text_chars_max": max(char_counts),
        "documents": documents,
    }


def _is_literal_assignment(node: ast.stmt) -> bool:
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return False
    value = node.value
    if value is None:
        return False
    try:
        ast.literal_eval(value)
    except (ValueError, TypeError):
        return False
    return True


def load_extraction_core(core_path: Path = DEFAULT_CORE_PATH) -> dict[str, Any]:
    """Load app prompt/validators without importing Streamlit or Boto3.

    Only literal module assignments and function definitions are compiled.
    UI calls and side effects are never included.
    """
    source = core_path.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(core_path))
    selected: list[ast.stmt] = [
        ast.ImportFrom(module="__future__", names=[ast.alias("annotations")], level=0)
    ]
    for node in parsed.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            selected.append(node)
        elif _is_literal_assignment(node):
            selected.append(node)

    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    namespace: dict[str, Any] = {
        "__name__": "ai_fcm_batch_core",
        "json": json,
        "os": os,
        "re": re,
        "time": time,
    }
    exec(compile(module, str(core_path), "exec"), namespace)

    required = {"FIELD_ONLY_PROMPT", "REQUIRED_FIELDS", "run_reasoning"}
    missing = required.difference(namespace)
    if missing:
        raise RuntimeError(f"AI core is missing required definitions: {sorted(missing)}")
    return namespace


class BedrockClient:
    """Use Boto3 credentials when available, otherwise a Bedrock bearer token."""

    def __init__(self, region: str, bearer_token: str = "", timeout: float = 180.0):
        self.region = region
        self.timeout = timeout
        self.bearer_token = bearer_token.strip()
        self._boto_client: Any | None = None

        if not self.bearer_token:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise RuntimeError(
                    "No AWS_BEARER_TOKEN_BEDROCK is set and Boto3 is unavailable. "
                    "Install with 'python -m pip install -e .[ai]' or set a Bedrock bearer token."
                ) from exc
            self._boto_client = boto3.client(
                "bedrock-runtime",
                region_name=region,
                config=Config(
                    connect_timeout=30,
                    read_timeout=timeout,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )

    def converse(self, **payload: Any) -> dict[str, Any]:
        if self._boto_client is not None:
            return self._boto_client.converse(**payload)

        model_id = str(payload.pop("modelId"))
        endpoint = (
            f"https://bedrock-runtime.{self.region}.amazonaws.com/model/"
            f"{quote(model_id, safe='')}/converse"
        )
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


def _existing_successes(results_path: Path) -> set[str]:
    successes: set[str] = set()
    if not results_path.exists():
        return successes
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("status") == "ok":
            successes.add(str(record.get("document_id", "")))
    return successes


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _extract_bedrock_text(response: dict[str, Any]) -> str:
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    return "\n".join(
        str(block.get("text", "")).strip()
        for block in blocks
        if isinstance(block, dict) and block.get("text")
    ).strip()


def _make_llm_call():
    def call_llm_once(
        client: BedrockClient,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        response = client.converse(
            modelId=model_id,
            system=[
                {
                    "text": (
                        "You are a strict document field extraction engine. "
                        "Return only the requested completed field list. "
                        "Do not explain. Do not provide reasoning. "
                        "Do not copy blank templates."
                    )
                }
            ],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": 0.4,
            },
        )
        return _extract_bedrock_text(response)

    return call_llm_once


def run_samples(
    samples_dir: Path,
    output_dir: Path,
    region: str,
    model: str,
    limit: int | None = None,
    max_doc_chars: int = 100_000,
    max_tokens: int = 768,
    force: bool = False,
) -> dict[str, Any]:
    core = load_extraction_core()
    core["call_llm_once"] = _make_llm_call()
    required_fields: list[str] = core["REQUIRED_FIELDS"]
    token = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
    client = BedrockClient(region=region, bearer_token=token)

    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.jsonl"
    completed = set() if force else _existing_successes(results_path)
    samples = discover_samples(samples_dir)
    if limit is not None:
        samples = samples[:limit]

    attempted = succeeded = failed = skipped = 0
    missing_by_field: Counter[str] = Counter()
    for path in samples:
        document_id = _document_id(path)
        if document_id in completed:
            skipped += 1
            continue

        attempted += 1
        text, pages = extract_pdf(path)
        text_for_model = text[:max_doc_chars]
        started = time.time()
        try:
            final_text, fields, raw_cleaned, elapsed = core["run_reasoning"](
                client=client,
                model_id=model,
                full_document_text=text_for_model,
                validation_source_text=text,
                max_tokens=max_tokens,
                temperature=0.0,
            )
            missing = [
                field
                for field in required_fields
                if str(fields.get(field, "")).strip().casefold() in {"", "not found"}
            ]
            missing_by_field.update(missing)
            record = {
                "status": "ok",
                "document_id": document_id,
                "source_file": path.name,
                "pages": pages,
                "text_chars": len(text),
                "model_chars": len(text_for_model),
                "model": model,
                "region": region,
                "elapsed_seconds": elapsed,
                "fields": fields,
                "missing_fields": missing,
                "final_text": final_text,
                "raw_cleaned": raw_cleaned,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            succeeded += 1
        except Exception as exc:  # continue so long runs are resumable
            record = {
                "status": "error",
                "document_id": document_id,
                "source_file": path.name,
                "pages": pages,
                "text_chars": len(text),
                "model": model,
                "region": region,
                "elapsed_seconds": round(time.time() - started, 2),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            failed += 1
        _append_jsonl(results_path, record)
        print(f"{document_id}  {record['status']}", flush=True)

    summary = {
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "skipped_existing": skipped,
        "missing_by_field": dict(missing_by_field),
        "results_path": str(results_path.resolve()),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def _latest_success_records(results_path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "ok":
            records[str(record["document_id"])] = record
    return records


def export_review(results_path: Path, review_path: Path) -> int:
    core = load_extraction_core()
    fields: list[str] = core["REQUIRED_FIELDS"]
    records = _latest_success_records(results_path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["document_id", "source_file", "reviewed"]
    columns += [PREDICTED_PREFIX + field for field in fields]
    columns += [EXPECTED_PREFIX + field for field in fields]

    with review_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records.values():
            row: dict[str, Any] = {
                "document_id": record["document_id"],
                "source_file": record["source_file"],
                "reviewed": "no",
            }
            for field in fields:
                predicted = str(record.get("fields", {}).get(field, "Not found"))
                row[PREDICTED_PREFIX + field] = predicted
                row[EXPECTED_PREFIX + field] = predicted
            writer.writerow(row)
    return len(records)


def _normalize_score_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def score_review(review_path: Path) -> dict[str, Any]:
    core = load_extraction_core()
    fields: list[str] = core["REQUIRED_FIELDS"]
    correct: Counter[str] = Counter()
    total: Counter[str] = Counter()
    reviewed_documents = 0

    with review_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("reviewed", "")).strip().casefold() not in {"yes", "y", "true", "1"}:
                continue
            reviewed_documents += 1
            for field in fields:
                expected = str(row.get(EXPECTED_PREFIX + field, ""))
                predicted = str(row.get(PREDICTED_PREFIX + field, ""))
                if not expected.strip():
                    continue
                total[field] += 1
                if _normalize_score_value(expected) == _normalize_score_value(predicted):
                    correct[field] += 1

    per_field = {
        field: {
            "correct": correct[field],
            "total": total[field],
            "accuracy": round(correct[field] / total[field], 4) if total[field] else None,
        }
        for field in fields
    }
    all_correct = sum(correct.values())
    all_total = sum(total.values())
    return {
        "reviewed_documents": reviewed_documents,
        "field_values_scored": all_total,
        "exact_match_accuracy": round(all_correct / all_total, 4) if all_total else None,
        "per_field": per_field,
    }


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan, run, and score the local AI-FCM PDF sample set."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Validate PDFs locally; no network calls.")
    scan.add_argument("--samples", type=_path, default=DEFAULT_SAMPLES_DIR)
    scan.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)

    run = subparsers.add_parser("run", help="Run samples through Amazon Bedrock.")
    run.add_argument("--samples", type=_path, default=DEFAULT_SAMPLES_DIR)
    run.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)
    run.add_argument("--region", default=os.getenv("AWS_REGION", DEFAULT_REGION))
    run.add_argument("--model", default=os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL))
    run.add_argument("--limit", type=int)
    run.add_argument("--max-doc-chars", type=int, default=100_000)
    run.add_argument("--max-tokens", type=int, default=768)
    run.add_argument("--force", action="store_true")

    review = subparsers.add_parser("export-review", help="Create a human-review CSV.")
    review.add_argument("--results", type=_path, default=DEFAULT_OUTPUT_DIR / "results.jsonl")
    review.add_argument("--review", type=_path, default=DEFAULT_OUTPUT_DIR / "review.csv")

    score = subparsers.add_parser("score", help="Score rows marked reviewed=yes.")
    score.add_argument("--review", type=_path, default=DEFAULT_OUTPUT_DIR / "review.csv")
    score.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR / "score.json")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "scan":
        report = scan_samples(args.samples)
        args.output.mkdir(parents=True, exist_ok=True)
        report_path = args.output / "scan.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            f"Scanned {report['document_count']} PDFs / {report['page_count']} pages; "
            f"{report['readable_count']} text-readable."
        )
        print(f"Report: {report_path.resolve()}")
        return 0 if report["readable_count"] == report["document_count"] else 1

    if args.command == "run":
        summary = run_samples(
            samples_dir=args.samples,
            output_dir=args.output,
            region=args.region,
            model=args.model,
            limit=args.limit,
            max_doc_chars=args.max_doc_chars,
            max_tokens=args.max_tokens,
            force=args.force,
        )
        print(json.dumps(summary, indent=2))
        return 0 if summary["failed"] == 0 else 1

    if args.command == "export-review":
        count = export_review(args.results, args.review)
        print(f"Exported {count} results to: {args.review}")
        return 0

    if args.command == "score":
        score = score_review(args.review)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(score, indent=2), encoding="utf-8")
        print(json.dumps(score, indent=2))
        return 0 if score["reviewed_documents"] else 2

    return 2


if __name__ == "__main__":
    sys.exit(main())
