from pathlib import Path


def test_v3_source_does_not_reference_v2_path():
    root = Path(__file__).resolve().parents[2]
    offenders = []
    for path in (root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "FCM-Intake-V2" in text:
            offenders.append(path.relative_to(root).as_posix())

    assert offenders == []
