"""Body part text -> item in the RRS body part dropdown (e.g. "Right ring finger" -> "Finger(s)").

The rules and matcher now live in the AI PDF Reader (AI/injury_classification.py); this module
re-exports them so rrs_ui and the standalone tests keep their existing imports.
"""
from pathlib import Path
import sys

try:
    import AI.injury_classification as _rules
except ModuleNotFoundError:  # run without the repo root on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    import AI.injury_classification as _rules

RULES = _rules.RULES
UNCLASSIFIED = _rules.UNCLASSIFIED
SIDE_WORDS = _rules.SIDE_WORDS
ALIASES = _rules.BODY_ALIASES
resolve_body_part = _rules.resolve_body_part
match_item = _rules.match_item
match_option = _rules.match_body_part
_norm, _key, _words = _rules._norm, _rules._key, _rules._words
