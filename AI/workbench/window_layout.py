"""Windows-only sizing for the narrow, vertically resizable Reader window."""

WINDOW_WIDTH = 480
WINDOW_HEIGHT = 900
MIN_HEIGHT = 600
# Edge e2e measurement: header 53 + dock 37.5 = 90.5 CSS px.
# WinForms probe at 96 DPI: Height - ClientSize.Height = 39 px.
# 129.5 px content + chrome, rounded up to 140 for 10.5 px clearance.
# e2e/compact.spec.ts verifies both elements fit the 101 px client area.
COMPACT_HEIGHT = 140


def set_compact(window, value):
    """Headless APIs have no window; live controllers marshal onto the UI thread."""
    if window is None:
        return
    controller = getattr(window, "_set_compact_layout", None)
    if controller is None:
        raise RuntimeError("Window layout is not ready.")
    controller(value)


def constrain_window(window):
    """Set native limits on the UI thread, including on DPI/work-area changes."""
    from System import Action
    from System.Drawing import Size
    from System.Windows.Forms import Screen

    form = window.native
    compact = False
    normal_height = WINDOW_HEIGHT

    def apply(initial=False, restore=False):
        # WinForms reports physical sizes; preserve a 480px logical width at 96 DPI.
        scale = form.DeviceDpi / 96.0
        width = round(WINDOW_WIDTH * scale)
        area = Screen.FromControl(form).WorkingArea
        maximum = area.Height
        minimum = min(round((COMPACT_HEIGHT if compact else MIN_HEIGHT) * scale), maximum)
        if compact:
            maximum = minimum
            height = minimum
        else:
            target = WINDOW_HEIGHT if initial else normal_height if restore else form.Height / scale
            height = min(round(target * scale), maximum)
        # Release old limits first so changing monitor DPI cannot clamp the new size.
        form.MinimumSize = Size(0, 0)
        form.MaximumSize = Size(0, 0)
        form.MinimumSize = Size(width, minimum)
        form.MaximumSize = Size(width, maximum)
        form.Size = Size(width, max(minimum, height))
        form.MaximizeBox = False
        form.Left = max(area.Left, min(form.Left, area.Right - width))
        form.Top = max(area.Top, min(form.Top, area.Bottom - form.Height))

    def change_compact(value):
        def change():
            nonlocal compact, normal_height
            if value == compact:
                return
            if value:
                normal_height = form.Height / (form.DeviceDpi / 96.0)
            compact = value
            apply(restore=not value)
        if form.InvokeRequired:
            form.Invoke(Action(change))
        else:
            change()

    def configure():
        apply(initial=True)
        window._set_compact_layout = change_compact
        form.DpiChanged += lambda *_: form.BeginInvoke(Action(apply))
        form.ResizeEnd += lambda *_: apply()

    if form.InvokeRequired:
        form.Invoke(Action(configure))
    else:
        configure()
