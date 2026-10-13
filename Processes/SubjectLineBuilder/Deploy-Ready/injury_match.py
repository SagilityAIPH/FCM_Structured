"""Injury type / injury cause text -> item in the RRS dropdowns (e.g. "lifted a box" -> "Lifting").

CANDIDATE FOR REMOVAL: rule tables copied from src/fcm_intake/legacy/legacy_fcm.py
resolve_injury_type (~line 3239) and resolve_cause (~line 3360) because the standalone exe cannot
import the legacy module. Each resolver gets the single input field as its text.
"""
import re

from body_part import match_item

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
    return next(iter(phys)) if phys else "All Other Specific Injuries, NOC"


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
    return "Other - Miscellaneous, NOC"


# Legacy values whose RRS item is worded differently (punctuation/spacing is already ignored).
CAUSE_ALIASES = {
    "Fall/Slip/Trip Injury - On Stairs": "Fall/Slip/Trip = On Stairs",
    "Fall/Slip/Trip Injury - On Ice or Snow": "Fall/SlipTrip - On Ice or Snow",
    "Collapsing Materials (Sides of Earth)": "Collapsing Materials (Slides of Earth)",
    "Object Handled - Cut/Puncture/Scrape": "Object Lifted or Handled - Cut/Puncture/Scrape",
    "Strain/Injury By - From Holding or Carrying": "Holding or Carrying",
}


def match_injury_type(text, options):
    return match_item(text, options, resolve_injury_type)


def match_injury_cause(text, options):
    return match_item(text, options, resolve_cause, CAUSE_ALIASES)
