"""Value-free failure boundary for Unity's missing-appointment-time flag."""


class UnityFlagError(RuntimeError):
    def __init__(self, stage):
        self.stage = stage
        self.browser_left_open = False
        self.service_release_failed = False
        super().__init__(f"Unity flagging failed while {stage}. Automated work stopped.")

    def __str__(self):
        message = super().__str__()
        if self.browser_left_open:
            message += (" Browser left open for manual recovery. Inspect the flag status "
                        "before taking further action; do not blindly retry submission. "
                        "Close the browser manually when finished.")
            if self.service_release_failed:
                message += " Browser automation service release could not be confirmed."
        return message
