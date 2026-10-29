"""Deterministic FY2027 ICD-10-CM code membership; never correct extracted values."""
from functools import lru_cache
from pathlib import Path
import sys

YEAR = 'FY2027'
FILENAME = 'icd10cm_2027.txt'


def _list_path():
    # Source: alongside this module. Frozen: same repo-relative AI/data layout
    # used by the other PyInstaller-bundled AI resources.
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return base / 'AI' / 'data' / FILENAME


@lru_cache(maxsize=1)
def _codes():
    codes = {}
    for line in _list_path().read_text(encoding='ascii').splitlines():
        if line.startswith('#'):
            continue
        code, flag = line.split()
        if flag not in ('0', '1') or code in codes:
            raise ValueError('Invalid ICD-10-CM list')
        codes[code] = flag
    if not codes:
        raise ValueError('Empty ICD-10-CM list')
    return codes


def check(code):
    """Return valid, incomplete, invalid, or unchecked if the list is unavailable."""
    try:
        codes = _codes()
    except (OSError, UnicodeError, ValueError):
        return 'unchecked'
    if not isinstance(code, str):
        return 'invalid'
    normalized = ''.join(code.upper().split())
    if len(normalized) > 3 and normalized[3] == '.':
        normalized = normalized[:3] + normalized[4:]
    flag = codes.get(normalized)
    return 'valid' if flag == '1' else 'incomplete' if flag == '0' else 'invalid'
