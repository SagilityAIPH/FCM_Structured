"""Body part text -> item in the RRS body part dropdown (e.g. "Right ring finger" -> "Finger(s)").

CANDIDATE FOR REMOVAL: rule table copied from src/fcm_intake/legacy/legacy_fcm.py
resolve_body_part (~line 3184) because the standalone exe cannot import the legacy module.
"""
import re

RULES = [
    (r"\bskull\b|head\s*injury|concussion",                           "Head"),
    (r"\bhead\b",                                                     "Multiple Head Injury"),
    (r"\bsoft\s*tissue\b.*head|\bhead\b.*soft\s*tissue",              "Soft Tissue - Head"),
    (r"\bface|facial\s*bones",                                        "Facial Bones"),
    (r"\beye\b|eyes\b|ocular",                                        "Eye(s)"),
    (r"\bear\b|ears\b|otitis|tympanic",                               "Ear(s)"),
    (r"\btooth|teeth|dental",                                         "Teeth"),
    (r"\bmouth|oral\b",                                               "Mouth"),
    (r"\bnose|nasal\b",                                               "Nose"),
    (r"\bneck\b|cervical",                                            "Neck"),
    (r"\bupper\s*back\b|thoracic\b",                                  "Upper Back Area (Thoracic Area)"),
    (r"\blow\s*back\b|lumbar\b",                                      "Low Back Area (Lumbar and Lumbo-Sacral)"),
    (r"\bsacrum\b|coccyx",                                            "Sacrum and Coccyx"),
    (r"\bvertebrae\b.*(lumbar|sacral)|\blumbar\b.*vertebrae|\bsacral\b.*vertebrae",
                                                                      "Lumbar &/or Sacral Vertebrae (Vertebra NOC Trunk)"),
    (r"\bspinal\s*cord\b.*(neck|cervical)",                           "Spinal Cord - Neck"),
    (r"\bspinal\s*cord\b",                                            "Spinal Cord - Trunk"),
    (r"\bchest\b|ribs\b|sternum|soft\s*tissue.*chest",                "Chest  (Ribs, Sternum, Soft Tissue)"),
    (r"\babdomen\b|groin",                                            "Abdomen (including groin)"),
    (r"\bpelvis\b",                                                   "Pelvis"),
    (r"\binternal\s*organs\b",                                        "Internal Organs"),
    (r"\bbody\s*systems\b|multiple\s*body\s*systems",                 "Body Systems and Multiple Body Systems"),
    (r"\bmultiple\s*(upper|lower|head|trunk|extremities)\b",          "Multiple Body Parts"),
    (r"\bshoulder\b|rotator\s*cuff",                                  "Shoulder(s)"),
    (r"\bupper\s*arm\b",                                              "Upper Arm"),
    (r"\blower\s*arm\b|forearm",                                      "Lower Arm"),
    (r"\belbow\b",                                                    "Elbow"),
    (r"\bwrist\b",                                                    "Wrist"),
    (r"\bhand\b",                                                     "Hand"),
    (r"\bfinger",                                                     "Finger(s)"),
    (r"\bthumb\b",                                                    "Thumb"),
    (r"\bhip\b",                                                      "Hip"),
    (r"\bupper\s*leg\b|thigh",                                        "Upper Leg"),
    (r"\blower\s*leg\b|shin|calf",                                    "Lower Leg"),
    (r"\bknee\b|meniscus|patella",                                    "Knee"),
    (r"\bankle\b|achilles",                                           "Ankle"),
    (r"\bfoot\b|plantar|metatars",                                    "Foot"),
    (r"\btoe",                                                        "Toe(s)"),
    (r"\bbuttock(s)?\b",                                              "Buttocks"),
    (r"\bdisc\b.*neck",                                               "Disc - Neck"),
    (r"\bdisc\b.*(trunk|back)",                                       "Disc - Trunk"),
    (r"\blarynx\b|trachea\b",                                         "Larynx"),
    (r"\bno\s*physical\s*injury\b",                                   "No Physical Injury  (Mental Disorder)"),
]
UNCLASSIFIED = "Insufficient Info to Properly Identify - Unclassified"


def resolve_body_part(text):
    """Legacy rule: one match -> that part, several -> Multiple Body Parts, none -> Unclassified."""
    text = (text or '').strip()
    if not text:
        return ''
    found = {value for pattern, value in RULES if re.search(pattern, text, re.I)}
    if len(found) > 1:
        return "Multiple Body Parts"
    return next(iter(found)) if found else UNCLASSIFIED


def _norm(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9&/()\- ]', ' ', (text or '').lower())).strip()


def _key(text):
    # Letters/digits only: "BlackLung" == "Black Lung", "Utensil; Not" == "Utensil, Not".
    return re.sub(r'[^a-z0-9]', '', (text or '').lower())


def _words(text):
    # "Finger(s)" -> finger; "Eye(s)" -> eye; plural "toes" -> toe.
    words = re.findall(r'[a-z]+', (text or '').lower().replace('(s)', ''))
    return {w[:-1] if len(w) > 3 and w.endswith('s') and not w.endswith('ss') else w for w in words}


SIDE_WORDS = {'left', 'right', 'bilateral', 'both', 'l', 'r', 'lt', 'rt', 'and', 'the', 'of', 'a', 'ring',
              'index', 'middle', 'little', 'pinky', 'small'}
# Legacy rule values that are not items in the RRS dropdown.
ALIASES = {'Head': 'Skull', 'Neck': 'Multiple Neck Injury'}


def match_item(text, options, resolver, aliases=None):
    """Pick the dropdown item for free text, or None when nothing fits.

    1. The text already is a dropdown item (ignoring case, spacing and punctuation).
    2. One item contains every meaningful word of the text, preferring an item with exactly
       those words ("left wrist and hand" -> "Wrist(s) & Hand(s)", "sprain" -> "Sprain or Tear").
    3. The legacy rule value for the text (resolver), with aliases for values the dropdown names
       differently; unrecognised text gets the legacy default value.
    """
    options = [o for o in options if (o or '').strip()]
    if not (text or '').strip() or not options:
        return None
    by_key = {_key(o): o for o in options}
    if _key(text) in by_key:
        return by_key[_key(text)]
    words = _words(text) - SIDE_WORDS
    if words:
        covering = [o for o in options if words <= _words(o)]
        exact = [o for o in covering if _words(o) == words]
        if len(exact) == 1:
            return exact[0]
        if len(covering) == 1:
            return covering[0]
    resolved = resolver(text)
    resolved = (aliases or {}).get(resolved, resolved)
    return by_key.get(_key(resolved))


def match_option(text, options):
    """Body part dropdown item ("Right ring finger" -> "Finger(s)")."""
    return match_item(text, options,
                      lambda t: resolve_body_part(re.sub(r'(?i)\blower\s+back\b', 'low back', t)), ALIASES)
