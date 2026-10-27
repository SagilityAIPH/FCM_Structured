"""Value-free failure boundaries for Unity UI stages."""


class UnityNCMAssignmentError(RuntimeError):
    def __init__(self, stage):
        self.stage = stage
        super().__init__(
            f"Unity NCM assignment failed while {stage}. Automated work stopped. "
            "Task changes are unconfirmed; inspect before retrying."
        )


class UnityTaskCompletionError(RuntimeError):
    def __init__(self, stage):
        self.stage = stage
        super().__init__(
            f"Unity Complete Task failed while {stage}. Automated work stopped. "
            "Task completion is unconfirmed; do not blindly retry."
        )


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


class UnityEmployerFieldsError(RuntimeError):
    def __init__(self, stage):
        self.stage = stage
        self.browser_left_open = False
        self.service_release_failed = False
        super().__init__(
            f"Unity Employer Defined Fields failed while {stage}. Automated work stopped."
        )

    def __str__(self):
        message = super().__str__()
        if self.browser_left_open:
            message += (" Browser left open for manual recovery. Inspect Employer Defined "
                        "Fields before taking further action. Close the browser manually "
                        "when finished.")
            if self.service_release_failed:
                message += " Browser automation service release could not be confirmed."
        return message


class UnityCustomerFieldsError(RuntimeError):
    def __init__(self, stage):
        self.stage = stage
        self.browser_left_open = False
        self.service_release_failed = False
        super().__init__(
            f"Unity Customer Defined Fields failed while {stage}. Automated work stopped."
        )

    def __str__(self):
        message = super().__str__()
        if self.browser_left_open:
            message += (" Browser left open for manual recovery. Inspect Customer Defined "
                        "Fields before taking further action. Close the browser manually "
                        "when finished.")
            if self.service_release_failed:
                message += " Browser automation service release could not be confirmed."
        return message
