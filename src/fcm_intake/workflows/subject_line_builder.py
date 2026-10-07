"""Thin application adapter for the standalone SubjectLineBuilder process."""
from fcm_intake.config import PROJECT_ROOT, FCM_SCRIPT
from fcm_intake.legacy_loader import load_module_from_path

_core = load_module_from_path(
    'modular_subject_line_builder',
    PROJECT_ROOT / 'processes' / 'SubjectLineBuilder' / 'Deploy-Ready' / 'subject_line_flow.py',
)
run_with_runtime = _core.run_flow


def run_live(*, app=None):
    # Windows/DB/browser imports occur only on explicit live execution.
    legacy = load_module_from_path('standalone_subject_line_runtime', FCM_SCRIPT)
    return run_with_runtime(vars(legacy), app=app)
