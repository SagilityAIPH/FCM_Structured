"""Controller shared by the full workflow and the standalone runner.

The UI steps still depend on the legacy runtime's helpers and mutable globals.
FunctionType binds the moved, unchanged function to that SAME namespace rather
than copying global state or duplicating the UI implementation. This bridge is
temporary until the underlying UI stages receive explicit dependencies.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import FunctionType


def _load_steps():
    path = Path(__file__).with_name('legacy_steps.py')
    spec = spec_from_file_location('subject_line_builder_steps', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CreateSubjectLineBuilder


def _failure_details(error, action):
    action_frame = legacy_frame = last_frame = None
    tb = error.__traceback__
    while tb is not None:
        last_frame = tb
        if tb.tb_frame.f_code is action.__code__:
            action_frame = tb
        if Path(tb.tb_frame.f_code.co_filename).name == 'legacy_steps.py':
            legacy_frame = tb
        tb = tb.tb_next
    # Prefer the builder call-site over UIA/library internals; never include locals.
    frame = legacy_frame or action_frame or last_frame
    kind = type(error).__name__
    message = str(error)
    detail = f'{kind}: {message}' if message else kind
    if frame is not None:
        detail += f' ({Path(frame.tb_frame.f_code.co_filename).name}:{frame.tb_lineno})'
    return {'type': kind, 'error': detail}


def run_flow(runtime, *, app=None, steps=None, allData=None, emaiDisplay=None,
             skip_capture=False, skip_cms=False):
    """Run only the builder boundary; return completed/stopped/failed.

    runtime is the existing legacy module dictionary. Never run concurrently
    against the same runtime or desktop. Offline tests inject synthetic steps.
    """
    runtime['botStop'] = True
    # Do not return stale claim data when a new run stops before PDF capture.
    runtime['data'] = {}
    template = steps if steps is not None else _load_steps()
    action = FunctionType(template.__code__, runtime, template.__name__,
                          template.__defaults__, template.__closure__)
    action.__kwdefaults__ = template.__kwdefaults__
    try:
        if allData is None and emaiDisplay is None and not skip_capture and not skip_cms:
            action(app=app)
        else:
            action(app=app, allData=allData, emaiDisplay=emaiDisplay,
                   skip_capture=skip_capture, skip_cms=skip_cms)
    except SystemExit as error:
        runtime['botStop'] = True
        result = {'status': 'failed', 'stage': 'subject_line_builder',
                  'error': 'Legacy builder exited before completion', 'exit_code': error.code}
        if isinstance(error.__context__, Exception):
            result.update(_failure_details(error.__context__, action))
        return result
    except Exception as error:
        runtime['botStop'] = True
        return {'status': 'failed', 'stage': 'subject_line_builder',
                **_failure_details(error, action)}
    return {'status': 'stopped' if runtime['botStop'] else 'completed',
            'stage': 'subject_line_builder', 'data': runtime.get('data', {})}
