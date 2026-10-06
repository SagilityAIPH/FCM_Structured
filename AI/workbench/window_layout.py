"""Windows-only sizing for the narrow, vertically resizable Reader window."""

WINDOW_WIDTH = 480
WINDOW_HEIGHT = 900
MIN_HEIGHT = 600


def constrain_window(window):
    """Set native limits on the UI thread, including on DPI/work-area changes."""
    from System import Action
    from System.Drawing import Size
    from System.Windows.Forms import Screen

    form = window.native

    def apply(initial=False):
        # WinForms reports physical sizes; preserve a 480px logical width at 96 DPI.
        scale = form.DeviceDpi / 96.0
        width = round(WINDOW_WIDTH * scale)
        area = Screen.FromControl(form).WorkingArea
        maximum = area.Height
        minimum = min(round(MIN_HEIGHT * scale), maximum)
        height = min(round(WINDOW_HEIGHT * scale) if initial else form.Height, maximum)
        # Release old limits first so changing monitor DPI cannot clamp the new size.
        form.MinimumSize = Size(0, 0)
        form.MaximumSize = Size(0, 0)
        form.MinimumSize = Size(width, minimum)
        form.MaximumSize = Size(width, maximum)
        form.Size = Size(width, max(minimum, height))
        form.MaximizeBox = False
        form.Left = max(area.Left, min(form.Left, area.Right - width))
        form.Top = max(area.Top, min(form.Top, area.Bottom - form.Height))

    def configure():
        apply(initial=True)
        form.DpiChanged += lambda *_: form.BeginInvoke(Action(apply))
        form.ResizeEnd += lambda *_: apply()

    if form.InvokeRequired:
        form.Invoke(Action(configure))
    else:
        configure()
