"""RRS Body Part / Injury Type / Injury Cause classification for the AI PDF Reader.

The AI PDF Reader owns this logic. It runs after extraction (parse_field_block):
1. Bedrock picks one item from each RRS dropdown list in the same extraction call.
2. Python accepts that answer only when it is an item of the list.
3. The legacy rules (copied verbatim from legacy_fcm.py resolve_body_part /
   resolve_injury_type / resolve_cause) are the fallback and a cross-check;
   a disagreement is flagged for review.

Pure ``re``/``json`` module: the Subject Line Builder re-exports the rules and matcher from here.
The RRS dropdown lists come from ``rrs_dropdowns.json`` (written by export_rrs_dropdowns.py
from the live RRS Subject Line Builder). Without that file, a provisional list built from the
rule values is used.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

# ----------------------------------------------------------------------------- Body Part
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


# ----------------------------------------------------------------------------- Injury Type
TYPE_RULES = [
    (r"\bamputat",                                   "Amputation"),
    (r"\bfractur",                                   "Fracture"),
    (r"\bdislocat",                                  "Dislocation"),
    (r"\blacerat|\bcut\b|\bincis",                   "Laceration"),
    (r"\bcontusion|\bbruise",                        "Contusion"),
    (r"\bsprain\b|\btear\b|\brotator\s*cuff\s*tear", "Sprain or Tear"),
    (r"\bstrain\b|\bpulled\s+muscle",                "Strain"),
    (r"\bconcuss|\btbi\b",                           "Concussion"),
    (r"\bburn\b|thermal|scald",                      "Burn"),
    (r"\bpuncture|\bstab\b",                         "Puncture"),
    (r"\bcrush|\bcrushing",                          "Crushing"),
    (r"\bforeign\s*body|\bsplinter|\bshard",         "Foreign Body"),
    (r"\binfect|\bcellulitis|\bsepsis",              "Infection"),
    (r"\binflamm|\btendinitis|\btenosynov|\bbursitis", "Inflammation"),
    (r"\bhernia\b",                                  "Hernia"),
    (r"\bdermatitis|\brash\b|\beczema",              "Dermatitis"),
    (r"\bpoison|\bintoxicat|\btoxic\b",              "Poisoning - General (Not OD or Cumulative Injury)"),
    (r"\bchemical\s+exposure|\bfume|\bgas|\bvapor",  "Respiratory Disorders (Gas, Fumes, Chems)"),
    (r"\bradiation",                                 "Radiation"),
    (r"\bheat\s+prostration|\bheat\s+exhaustion|\bheat\s+stroke", "Heat Prostration"),
    (r"\bfreez|\bfrostbite",                         "Freezing"),
    (r"\belectric\s+shock|\belectrocution",          "Electric Shock"),
    (r"\bsyncope|\bfaint",                           "Syncope (Fainting)"),
    (r"\bcarpal\s+tunnel",                           "Carpal Tunnel Syndrome"),
    (r"\bhearing\s+loss|\bimpairment\s*\(traumatic only\)", "Hearing Loss or Impairment (Traumatic Only)"),
    (r"\bmyocardial\s+infarction|\bheart\s+attack",  "Myocardial Infarction (Heart Attack)"),
    (r"\bblack\s*lung",                              "Black Lung"),
    (r"\basbest",                                    "Asbestosis"),
    (r"\bpandemic|\bcovid",                          "Pandemic"),
    (r"\bmultiple\s+injur|\bpolytrauma",             "Multiple Physical Injuries Only"),
    (r"\bno\s*physical\s*injury\b",                  "No Physical Injury"),
    (r"\bvdt|\brepetitive\s+motion|\bcumulative\s+trauma", "All Other Cumulative Injury, NOC"),
]
PSYCH = (r"\b(mental\s+stress|mental\s+disorder|ptsd|anxiety|"
         r"depress(ion|ed)?|panic|psych(ological)?|psychiatr(ic|y)?)\b")
TYPE_DEFAULT = "All Other Specific Injuries, NOC"


def resolve_injury_type(text):
    text = (text or '').lower()
    if not text.strip():
        return ''
    psych = bool(re.search(PSYCH, text, re.I))
    phys = set()
    for pattern, value in TYPE_RULES:
        if re.search(pattern, text, re.I):
            if value == "No Physical Injury":
                phys = {value}
                break
            phys.add(value)
    if psych and phys:
        return "Multiple Injuries (Including Both Phys and Psych)"
    if psych:
        return "Mental Stress"
    if len(phys) > 1:
        return "Multiple Physical Injuries Only"
    return next(iter(phys)) if phys else TYPE_DEFAULT


# ----------------------------------------------------------------------------- Injury Cause
FALL_VALUES = ["Slip or Trip, Did Not Fall", "Fall/Slip/Trip Injury - On Ice or Snow",
               "Fall/Slip/Trip Injury - On Stairs", "Fall/Slip/Trip Injury - From Ladder or Scaffolding",
               "Fall/Slip/Trip Injury - From Liquid/Grease Spills", "Fall/Slip/Trip Injury - Into Openings",
               "Fall/Slip/Trip Injury - From Different Level", "Fall/Slip/Trip Injury - On Same Level"]


def _fall(text):
    if not re.search(r"\b(slip(ped)?|trip(ped)?|fell|fall|falling)\b", text):
        return None
    if re.search(r"\b(no\s+fall|did\s+not\s+fall)\b", text):
        return "Slip or Trip, Did Not Fall"
    if re.search(r"\b(ice|icy|snow|snowy)\b", text):
        return "Fall/Slip/Trip Injury - On Ice or Snow"
    if re.search(r"\bstair(s)?\b|\bstep(s)?\b", text):
        return "Fall/Slip/Trip Injury - On Stairs"
    if re.search(r"\bladder\b|\bscaffold(ing)?\b", text):
        return "Fall/Slip/Trip Injury - From Ladder or Scaffolding"
    if re.search(r"\b(spill(ed|ing)?|spillage|grease|oil|liquid|wet floor)\b", text):
        return "Fall/Slip/Trip Injury - From Liquid/Grease Spills"
    if re.search(r"\bhole\b|\bpit\b|\btrench\b|\bmanhole\b|\bopening\b|\bshaft\b", text):
        return "Fall/Slip/Trip Injury - Into Openings"
    if re.search(r"\b(from|off)\b.*\b(level|roof|platform|dock|loading\s+dock|second floor|balcony)\b", text):
        return "Fall/Slip/Trip Injury - From Different Level"
    return "Fall/Slip/Trip Injury - On Same Level"


CAUSE_RULES = [
    (r"\babnormal\s+air\s+pressure\b|\bdecompression\b|\bbarotrauma\b", "Abnormal Air Pressure"),
    (r"\banimal(s)?\b|\bdog\b|\b(dog\s*bite)\b|"
     r"\b(cat|insect|bee|wasp|hornet|spider|mosquito\w*|tick|ant|rodent|rat|mouse)\b", "Animal or Insect"),
    (r"\bbroken\s+glass\b|\bglass\s+cut\b|\bcut\b.*\bglass\b|\bglass\b.*\bcut\b", "Broken Glass"),
    (r"\bcaught\s+in\b|\bcaught\s+under\b|\bcaught\s+between\b|\bpinch(ing)?\b|entrap", "Caught In, Under or Between, NOC"),
    (r"\bchemical(s)?\b|\bsolvent(s)?\b|\bbleach\b|\bacid\b|\bcaustic\b", "Chemicals"),
    (r"\bdust\b|\bfume(s)?\b|\bgas(es)?\b|\bvapor(s)?\b|\binhalation\b", "Dust, Gases, Fumes or Vapors"),
    (r"\bcold\b.*\bobject\b|\bobject\b.*\bcold\b|\bfrozen\b|\bice\b(?!\s*or snow)", "Cold Objects or Substances"),
    (r"\bcollapse(d|s|)\b.*\b(trench|dirt|earth|wall|soil)\b|\bcave-?in\b|\blandslide\b", "Collapsing Materials (Sides of Earth)"),
    (r"\bcontact\b.*\b(with|by)\b", "Contact With, NOC"),
    (r"\bcovid\b|\bcoronavirus\b|\bsars\-?cov\-?2\b", "COVID-19"),
    (r"\bcrash\b.*\b(plane|aircraft|airplane)\b", "Crash of Airplane"),
    (r"\bcrash\b.*\b(train|rail|locomotive)\b", "Crash of Rail Vehicle"),
    (r"\bcrash\b.*\b(boat|ship|vessel|barge)\b", "Crash of Water Vehicle"),
    (r"\b(upset\b|\boverturned\b|\brollover\b)\b.*\b(vehicle|truck|car)\b", "Vehicle Upset"),
    (r"\b(collid(ed|e|ing)?|sideswipe(d)?)\b.*\b(vehicle|car|truck|forklift)\b", "Collision or Sideswipe with Another Vehicle"),
    (r"\b(collid(ed|e|ing)?|hit\b|struck\b)\b.*\b(pole|guardrail|barrier|wall|tree|building|door|fixed object)\b", "Collision with a Fixed Object"),
    (r"\bmotor\s+vehicle\b|\bauto\b|\bcar\b|\btruck\b|\bvan\b", "Motor Vehicle, NOC"),
    (r"\b(cut|puncture|scrape|laceration)\b", "Cut, Puncture, Scrape, NOC"),
    (r"\bobject\b.*\b(cut|puncture|scrape)\b|\b(cut|puncture|scrape)\b.*\bobject\b", "Object Handled - Cut/Puncture/Scrape"),
    (r"\beye\b.*\b(foreign\s+body|debris|dust|dirt|metal|object|particle)\b", "Foreign Matter (Body) in Eyes(s)"),
    (r"\belectric(al)?\s+shock\b|\belectrocute(d|ion)?\b|\bcontact\b.*\bpower\s+line\b", "Electrical Current"),
    (r"\bexplosion\b|\bexploded\b|\bflare\-?back\b|\bblast\b", "Explosion or Flare Back"),
    (r"\bfire\b|\bflame(s)?\b|\bburned\b|\bburning\b", "Fire or Flame"),
    (r"\bsteam\b|\bhot\s+fluid(s)?\b|\bboiling\b", "Steam or Hot Fluids"),
    (r"\bhot\b.*\b(object|surface|metal|pipe)\b", "Hot Object or Substances"),
    (r"\b(hand\s+tool|utensil)\b(?!\s*powered)", "Hand Tool, Utensil, Not Powered"),
    (r"\b(powered\s+hand\s+tool|power\s+tool|saw\b|drill\b|grinder\b)\b", "Powered Hand Tool, Appliance"),
    (r"\bmachine\b|\bmachinery\b|\bconveyor\b|\bpress\b", "Machine or Machinery"),
    (r"\busing\b.*\b(tool|machinery|machine)\b", "Using Tool or Machinery"),
    (r"\blift(ing|ed)?\b", "Lifting"),
    (r"\b(pushing|pulling|push(ed|ing)?|pull(ed|ing)?)\b", "Pushing or Pulling"),
    (r"\bholding\b|\bcarrying\b|\bcarried\b", "Strain/Injury By - From Holding or Carrying"),
    (r"\brepetitive\b|\brepetition\b", "Strain/Injury By - Repetitive Motion"),
    (r"\breach(ing)?\b|\bstretched\b", "Reaching"),
    (r"\btwist(ed|ing)?\b|\btwisting\b", "Twisting"),
    (r"\bstrain\b|\boverexert(ion|ed|ing)\b|\bmuscle\b.*\b(pulled|strain)\b", "Strain or Injury by, NOC"),
    (r"\brubb(ed|ing)?\b|\babrasion\b|\bchafe(d|ing)?\b", "Rubbed or Abraded, NOC"),
    (r"\brubb(ed|ing)?\b.*\brepetitive\b|\babrasion\b.*\brepetitive\b", "Rubbed/Abraded By - Repetitive Motion"),
    (r"\bstruck\b.*\bagainst\b.*\b(stationary|fixed)\s+object\b|\bran\s+into\b", "Stationary Object"),
    (r"\bstepp(ed|ing)?\b.*\b(nail|screw|sharp|tack|glass)\b", "Stepping on Sharp Object"),
    (r"\bstepp(ed|ing)?\b|\bstruck\b.*\bagainst\b", "Striking Against or Stepping On, NOC"),
    (r"\bstruck\b.*\b(falling|flying)\b|\bfalling\b.*\bobject\b|\bflying\b.*\bobject\b", "Struck/Injured By - Falling or Flying Object"),
    (r"\bstruck\b|\bhit\b|\binjured\b.*\bby\b.*\b(co-worker|coworker|fellow worker|patient)\b", "Struck/Injured By - Fellow Worker, Patient"),
    (r"\bstruck\b|\bhit\b|\binjured\b.*\bby\b.*\b(hand\s+tool|machine\s+in\s+use|power\s+tool)\b", "Struck/Injured By - Hand Tool or Machine in Use"),
    (r"\bstruck\b|\bhit\b|\binjured\b.*\bby\b.*\b(vehicle|car|truck|forklift)\b", "Struck/Injured By - Motor Vehicle"),
    (r"\bstruck\b|\bhit\b|\binjured\b.*\bby\b.*\b(moving\s+part(s)?\b.*\bmachine)\b", "Struck/Injured By - Moving Parts of Machine"),
    (r"\bstruck\b|\bhit\b|\binjured\b.*\bby\b.*\b(object\b.*handled\b.*other(s)?|object\b.*another\b.*worker)\b", "Struck/Injured By - Object Handled by Others"),
    (r"\bstruck\b|\bhit\b|\binjured\b.*\bby\b", "Struck/Injured, NOC"),
    (r"\bheat\s+exhaustion\b|\bheat\s+stroke\b|\bheat\s+stress\b|\bextreme\s+heat\b|\bextreme\s+cold\b|\btemperature\s+extreme(s)?\b", "Temperature Extremes"),
    (r"\bradiation\b|\bx-ray(s)?\b|\bxray(s)?\b", "Radiation"),
    (r"\bmold\b|\bmould\b", "Mold"),
    (r"\bearthquake\b|\btornado\b|\bhurricane\b|\bflood\b|\btsunami\b", "Natural Disasters"),
    (r"\bterroris(m|t)\b|\bactive\s+shooter\b|\bbomb\b", "Terrorism"),
    (r"\bassault\b|\brobbery\b|\bcrime\b|\barmed\b\s+robbery\b", "Person in Act of a Crime"),
    (r"\bgunshot\b|\bshot\b.*\bgun\b|\bfirearm\b", "Gunshot"),
    (r"\bsanding\b|\bscrap(ing|e)\b|\bcleaning\b.*\boperation\b", "Sanding, Scraping, Cleaning Operation"),
    (r"\bcumulative\b", "Cumulative, NOC"),
    (r"\bmental\b|\bstress\b|\bpsycho(logical)?\b", "Other Than Physical Cause of Injury"),
]
CAUSE_DEFAULT = "Other - Miscellaneous, NOC"


def resolve_cause(text):
    text = (text or '').lower()
    if not text.strip():
        return ''
    found = _fall(text)
    if found:
        return found
    for pattern, value in CAUSE_RULES:
        if re.search(pattern, text):
            return value
    return CAUSE_DEFAULT


# ----------------------------------------------------------------------------- Dropdown matching
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
# Legacy rule values whose RRS item is named differently (punctuation/spacing is already ignored).
BODY_ALIASES = {'Head': 'Skull', 'Neck': 'Multiple Neck Injury'}
CAUSE_ALIASES = {
    "Fall/Slip/Trip Injury - On Stairs": "Fall/Slip/Trip = On Stairs",
    "Fall/Slip/Trip Injury - On Ice or Snow": "Fall/SlipTrip - On Ice or Snow",
    "Collapsing Materials (Sides of Earth)": "Collapsing Materials (Slides of Earth)",
    "Object Handled - Cut/Puncture/Scrape": "Object Lifted or Handled - Cut/Puncture/Scrape",
    "Strain/Injury By - From Holding or Carrying": "Holding or Carrying",
}


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


def _body_resolver(text):
    return resolve_body_part(re.sub(r'(?i)\blower\s+back\b', 'low back', text))


def match_body_part(text, options):
    """Body part dropdown item ("Right ring finger" -> "Finger(s)")."""
    return match_item(text, options, _body_resolver, BODY_ALIASES)


def match_injury_type(text, options):
    return match_item(text, options, resolve_injury_type)


def match_injury_cause(text, options):
    return match_item(text, options, resolve_cause, CAUSE_ALIASES)


# ----------------------------------------------------------------------------- RRS lists
FIELDS = ("Body Part", "Injury Type", "Injury Cause")
OPTIONS_FILE = Path(__file__).resolve().with_name('rrs_dropdowns.json')
# Rule values that only mean "the rules found nothing specific".
RULE_DEFAULTS = {"Body Part": UNCLASSIFIED, "Injury Type": TYPE_DEFAULT, "Injury Cause": CAUSE_DEFAULT}


def _unique(values):
    return list(dict.fromkeys(v for v in values if (v or '').strip()))


def provisional_options():
    """Every value the legacy rules can produce, renamed to known RRS items."""
    body = [BODY_ALIASES.get(v, v) for _, v in RULES] + ["Multiple Body Parts", UNCLASSIFIED]
    types = [v for _, v in TYPE_RULES] + ["Mental Stress", "Multiple Injuries (Including Both Phys and Psych)",
                                          "Multiple Physical Injuries Only", TYPE_DEFAULT]
    causes = [CAUSE_ALIASES.get(v, v) for v in FALL_VALUES + [v for _, v in CAUSE_RULES] + [CAUSE_DEFAULT]]
    return {"Body Part": _unique(body), "Injury Type": _unique(types), "Injury Cause": _unique(causes)}


@lru_cache(maxsize=None)
def load_options(path=None):
    """{'Body Part': [...], 'Injury Type': [...], 'Injury Cause': [...], 'provisional': bool}."""
    path = Path(path) if path else OPTIONS_FILE
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf-8'))
        lists = {field: _unique(str(v).strip() for v in data.get(field, []) if str(v).strip().casefold() != 'none')
                 for field in FIELDS}
        if all(lists.values()):
            return {**lists, 'provisional': False}
    return {**provisional_options(), 'provisional': True}


def list_item(value, options):
    """The exact list item for a value (case/spacing/punctuation-insensitive), else None."""
    by_key = {_key(o): o for o in options}
    return by_key.get(_key(value)) if (value or '').strip() else None


# ----------------------------------------------------------------------------- Post-extraction step
def _text(fields, key):
    value = str(fields.get(key) or '').strip()
    return '' if value.casefold() == 'not found' else value


def rule_values(fields, options):
    """Legacy inputs: body part from Accident + Injury Description + Special Instructions together;
    injury type and cause from Accident + Injury Description, Special Instructions only as fallback."""
    accident, injury = _text(fields, 'Accident Description'), _text(fields, 'Injury Description')
    special = _text(fields, 'Special Instructions')
    core = ' '.join(filter(None, [accident, injury]))
    blend = ' '.join(filter(None, [accident, injury, special]))
    result = {"Body Part": match_body_part(blend, options["Body Part"]) if blend else None}
    for field, resolver, aliases in (("Injury Type", resolve_injury_type, None),
                                     ("Injury Cause", resolve_cause, CAUSE_ALIASES)):
        value = resolver(core) if core else ''
        if (not value or value == RULE_DEFAULTS[field]) and special:
            value = resolver(special)
        value = (aliases or {}).get(value, value)
        result[field] = list_item(value, options[field]) if value else None
    return result


def classify(fields, ai_values=None, manual=None, options=None):
    """Set Body Part / Injury Type / Injury Cause on ``fields`` and return the per-field detail.

    ai_values: the model's raw answers. manual: {field: value} edited by the operator; those win.
    """
    options = options or load_options()
    ai_values = {field: str((ai_values or {}).get(field) or '').strip() for field in FIELDS}
    manual = manual or {}
    rules = rule_values(fields, options)
    detail = []
    for field in FIELDS:
        raw_ai = ai_values[field]
        ai = list_item(raw_ai, options[field])
        rule = rules[field]
        review = ''
        if field in manual:
            value, source = manual[field], 'Manual'
            if value != 'Not found' and not list_item(value, options[field]):
                review = 'Manual value is not an item in the RRS list.'
        elif ai:
            value, source = ai, 'AI'
            if rule and rule != ai and rule != list_item(RULE_DEFAULTS[field], options[field]):
                review = f'AI chose {ai}; legacy rules suggest {rule}.'
        elif rule:
            value, source = rule, 'Rules'
            if raw_ai and raw_ai.casefold() != 'not found':
                review = f'AI answer "{raw_ai}" is not an item in the RRS list; legacy rules used.'
        else:
            value, source = 'Not found', 'None'
        fields[field] = value
        detail.append({'field': field, 'value': value, 'source': source, 'ai_value': raw_ai or 'Not found',
                       'rule_value': rule or 'Not found', 'review': review,
                       'list': 'provisional' if options.get('provisional') else 'RRS'})
    return detail


def prompt_lists(options=None):
    options = options or load_options()
    return '\n'.join(f'  Allowed {field} items: ' + ' | '.join(options[field]) for field in FIELDS)
