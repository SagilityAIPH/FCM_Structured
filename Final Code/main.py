"""Entry point for the FCM Final Code attended referral intake.

    python "Final Code/main.py"              open the window and run one referral
    python "Final Code/main.py" --self-test  drive the chain with synthetic data

Final Code contains a space and cannot be a module name, so this shim puts its
directory on sys.path and hands over to the finalcode package.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
# The legacy modules import each other by top-level name and fcm_intake lives
# under src, so all three entries must exist before finalcode is imported.
for _entry in (str(_ROOT), str(_ROOT / "src"), str(_HERE)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from finalcode.app import main  # noqa: E402 - sys.path must be set first

if __name__ == "__main__":
    sys.exit(main())
