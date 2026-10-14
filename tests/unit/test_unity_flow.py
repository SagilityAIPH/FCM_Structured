"""Collect the standard-library Unity contract suite in the main unit gate."""
import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "Processes/Unity/Stand-Alone/test_flow.py"
spec = importlib.util.spec_from_file_location("unity_contract_tests", SOURCE)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FlowTests = module.FlowTests
