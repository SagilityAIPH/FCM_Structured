from pathlib import Path

import pytest

from fcm_intake.automation.legacy_loader import load_module_from_path


def test_load_module_from_path_loads_temp_module(tmp_path: Path):
    module_path = tmp_path / "sample_module.py"
    module_path.write_text("VALUE = 42\n", encoding="utf-8")

    module = load_module_from_path("sample_module_for_test", module_path)

    assert module.VALUE == 42


def test_load_module_from_path_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_module_from_path("missing_module_for_test", tmp_path / "missing.py")
