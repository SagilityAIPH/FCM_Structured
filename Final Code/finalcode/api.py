"""Final Code-only bridge for operator-gated attended runs."""

from AI.workbench.backend import WorkbenchAPI, response

from .app import build_live_callables, start_workflow


class FinalCodeAPI(WorkbenchAPI):
    def __init__(self, *, app=None, runtime=None):
        super().__init__(memory_only=True)
        self._attended_app = app
        self._attended_runtime = runtime
        self._attended_reserved = False
        self._external_stage = "Waiting for Start"

    @response
    def get_state(self):
        state = super().get_state()
        if not state["ok"]:
            raise RuntimeError(state["error"])
        with self._lock:
            state["value"]["workflow_active"] = self._workflow_active or self._attended_reserved
        return state["value"]

    def _finish_attended(self):
        with self._lock:
            self._attended_reserved = False

    @response
    def start_attended(self):
        """Reserve one run atomically, then start its worker without holding the state lock."""
        with self._lock:
            if self._workflow_active or self._attended_reserved:
                raise ValueError("The attended run is already active.")
            self._attended_reserved = True
            self._external_stage = "Starting referral intake…"
        try:
            start_workflow(self, lambda: build_live_callables(
                self, app=self._attended_app, runtime=self._attended_runtime),
                on_finished=self._finish_attended)
        except BaseException:
            with self._lock:
                self._attended_reserved = False
                self._external_stage = "Waiting for Start"
            raise
        return True
