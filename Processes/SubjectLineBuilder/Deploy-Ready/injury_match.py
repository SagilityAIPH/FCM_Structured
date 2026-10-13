"""Injury type / injury cause text -> item in the RRS dropdowns (e.g. "lifted a box" -> "Lifting").

The rules and matcher now live in the AI PDF Reader (AI/injury_classification.py); this module
re-exports them so rrs_ui and the standalone tests keep their existing imports.
"""
from body_part import _rules

TYPE_RULES = _rules.TYPE_RULES
PSYCH = _rules.PSYCH
CAUSE_RULES = _rules.CAUSE_RULES
CAUSE_ALIASES = _rules.CAUSE_ALIASES
resolve_injury_type = _rules.resolve_injury_type
resolve_cause = _rules.resolve_cause
_fall = _rules._fall
match_item = _rules.match_item
match_injury_type = _rules.match_injury_type
match_injury_cause = _rules.match_injury_cause
