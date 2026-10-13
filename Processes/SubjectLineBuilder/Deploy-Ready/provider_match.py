"""Provider and adjuster search matching for the standalone Subject Line Builder (rrs_ui).

CANDIDATE FOR REMOVAL: the address/phone helpers below are a verbatim copy of
src/fcm_intake/legacy/legacy_providerresultchecker.py, kept here only so the PyInstaller
build stays self-contained. Once the standalone app can import that module directly
(or the legacy module is retired), delete the copied section and import it instead.
The name-matching / choose_row logic at the bottom is ported from legacy_steps.py
(_click_first_row_if_any) without the Google picker.
"""
import difflib
import re
from typing import Optional
 
USPS_SUFFIX_LONG = {
    'ALLEE': 'Alley', 'ALLEY': 'Alley', 'ALLY': 'Alley', 'ALY': 'Alley',
    'ANEX': 'Annex', 'ANNEX': 'Annex', 'ANNX': 'Annex', 'ANX': 'Annex',
    'ARC': 'Arcade', 'ARCADE': 'Arcade',
    'AV': 'Avenue', 'AVE': 'Avenue', 'AVEN': 'Avenue', 'AVENU': 'Avenue', 'AVENUE': 'Avenue', 'AVN': 'Avenue', 'AVNUE': 'Avenue',
    'BAYOO': 'Bayoo', 'BAYOU': 'Bayoo',
    'BCH': 'Beach', 'BEACH': 'Beach',
    'BEND': 'Bend', 'BND': 'Bend',
    'BLF': 'Bluff', 'BLFS': 'Bluffs', 'BLUF': 'Bluff', 'BLUFF': 'Bluff', 'BLUFFS': 'Bluffs',
    'BOT': 'Bottom', 'BOTTM': 'Bottom', 'BOTTOM': 'Bottom', 'BTM': 'Bottom',
    'BLVD': 'Boulevard', 'BOUL': 'Boulevard', 'BOULEVARD': 'Boulevard', 'BOULV': 'Boulevard',
    'BR': 'Branch', 'BRANCH': 'Branch', 'BRNCH': 'Branch',
    'BRDGE': 'Bridge', 'BRG': 'Bridge', 'BRIDGE': 'Bridge',
    'BRK': 'Brook', 'BROOK': 'Brook', 'BRKS': 'Brooks', 'BROOKS': 'Brooks',
    'BURG': 'Burg', 'BG': 'Burg', 'BURGS': 'Burgs', 'BGS': 'Burgs',
    'BYP': 'Bypass', 'BYPA': 'Bypass', 'BYPAS': 'Bypass', 'BYPASS': 'Bypass', 'BYPS': 'Bypass',
    'CAMP': 'Camp', 'CMP': 'Camp', 'CP': 'Camp',
    'CANYN': 'Canyon', 'CANYON': 'Canyon', 'CNYN': 'Canyon', 'CYN': 'Canyon',
    'CAPE': 'Cape', 'CPE': 'Cape',
    'CAUSEWAY': 'Causeway', 'CAUSWAY': 'Causeway', 'CSWY': 'Causeway',
    'CEN': 'Center', 'CENT': 'Center', 'CENTER': 'Center', 'CENTR': 'Center', 'CENTRE': 'Center',
    'CNTER': 'Center', 'CNTR': 'Center', 'CTR': 'Center',
    'CENTERS': 'Centers', 'CTRS': 'Centers',
    'CIR': 'Circle', 'CIRC': 'Circle', 'CIRCL': 'Circle', 'CIRCLE': 'Circle', 'CRCL': 'Circle', 'CRCLE': 'Circle',
    'CIRCLES': 'Circles', 'CIRS': 'Circles',
    'CLF': 'Cliff', 'CLIFF': 'Cliff', 'CLFS': 'Cliffs', 'CLIFFS': 'Cliffs',
    'CLB': 'Club', 'CLUB': 'Club',
    'COMMON': 'Common', 'CMN': 'Common',
    'COR': 'Corner', 'CORNER': 'Corner', 'CORNERS': 'Corners', 'CORS': 'Corners',
    'COURSE': 'Course', 'CRSE': 'Course',
    'COURT': 'Court', 'CRT': 'Court', 'CT': 'Court',
    'COURTS': 'Courts', 'CTS': 'Courts',
    'COVE': 'Cove', 'CV': 'Cove', 'COVES': 'Coves', 'CVS': 'Coves',
    'CK': 'Creek', 'CR': 'Creek', 'CREEK': 'Creek', 'CRK': 'Creek',
    'CRECENT': 'Crescent', 'CRES': 'Crescent', 'CRESCENT': 'Crescent', 'CRESENT': 'Crescent', 'CRSCNT': 'Crescent',
    'CRSENT': 'Crescent', 'CRSNT': 'Crescent',
    'CREST': 'Crest', 'CRST': 'Crest',
    'CROSSING': 'Crossing', 'CRSSING': 'Crossing', 'CRSSNG': 'Crossing', 'XING': 'Crossing',
    'CROSSROAD': 'Crossroad', 'XRD': 'Crossroad',
    'CURVE': 'Curve', 'CURV': 'Curve',
    'DALE': 'Dale', 'DL': 'Dale',
    'DAM': 'Dam', 'DM': 'Dam',
    'DIV': 'Divide', 'DIVIDE': 'Divide', 'DV': 'Divide', 'DVD': 'Divide',
    'DR': 'Drive', 'DRIV': 'Drive', 'DRIVE': 'Drive', 'DRV': 'Drive',
    'DRIVES': 'Drives', 'DRS': 'Drives',
    'EST': 'Estate', 'ESTATE': 'Estate', 'ESTATES': 'Estates', 'ESTS': 'Estates',
    'EXP': 'Expressway', 'EXPR': 'Expressway', 'EXPRESS': 'Expressway', 'EXPRESSWAY': 'Expressway', 'EXPW': 'Expressway', 'EXPY': 'Expressway',
    'EXT': 'Extension', 'EXTENSION': 'Extension', 'EXTN': 'Extension', 'EXTNSN': 'Extension',
    'EXTENSIONS': 'Extensions', 'EXTS': 'Extensions',
    'FALL': 'Fall', 'FALLS': 'Falls', 'FLS': 'Falls',
    'FERRY': 'Ferry', 'FRRY': 'Ferry', 'FRY': 'Ferry',
    'FIELD': 'Field', 'FLD': 'Field', 'FIELDS': 'Fields', 'FLDS': 'Fields',
    'FLAT': 'Flat', 'FLT': 'Flat', 'FLATS': 'Flats', 'FLTS': 'Flats',
    'FORD': 'Ford', 'FRD': 'Ford', 'FORDS': 'Fords', 'FRDS': 'Fords',
    'FOREST': 'Forest', 'FORESTS': 'Forest', 'FRST': 'Forest',
    'FORG': 'Forge', 'FORGE': 'Forge', 'FRG': 'Forge', 'FORGES': 'Forges', 'FRGS': 'Forges',
    'FORK': 'Fork', 'FRK': 'Fork', 'FORKS': 'Forks', 'FRKS': 'Forks',
    'FORT': 'Fort', 'FRT': 'Fort', 'FT': 'Fort',
    'FREEWAY': 'Freeway', 'FREEWY': 'Freeway', 'FRWAY': 'Freeway', 'FRWY': 'Freeway', 'FWY': 'Freeway',
    'GARDEN': 'Garden', 'GARDN': 'Garden', 'GDN': 'Garden', 'GRDEN': 'Garden', 'GRDN': 'Garden',
    'GARDENS': 'Gardens', 'GDNS': 'Gardens', 'GRDNS': 'Gardens',
    'GATEWAY': 'Gateway', 'GATEWY': 'Gateway', 'GATWAY': 'Gateway', 'GTWAY': 'Gateway', 'GTWY': 'Gateway',
    'GLEN': 'Glen', 'GLN': 'Glen', 'GLENS': 'Glens', 'GLNS': 'Glens',
    'GREEN': 'Green', 'GRN': 'Green', 'GREENS': 'Greens', 'GRNS': 'Greens',
    'GROV': 'Grove', 'GROVE': 'Grove', 'GRV': 'Grove', 'GROVES': 'Groves', 'GRVS': 'Groves',
    'HARB': 'Harbor', 'HARBOR': 'Harbor', 'HBR': 'Harbor', 'HRBOR': 'Harbor',
    'HARBORS': 'Harbors', 'HBRS': 'Harbors',
    'HAVEN': 'Haven', 'HVN': 'Haven',
    'HEIGHTS': 'Heights', 'HT': 'Heights', 'HTS': 'Heights',
    'HIGHWAY': 'Highway', 'HIGHWY': 'Highway', 'HIWAY': 'Highway', 'HIWY': 'Highway', 'HWAY': 'Highway', 'HWY': 'Highway',
    'HILL': 'Hill', 'HL': 'Hill', 'HILLS': 'Hills', 'HLS': 'Hills',
    'HLLW': 'Hollow', 'HOLLOW': 'Hollow', 'HOLLOWS': 'Hollow', 'HOLW': 'Hollow',
    'INLET': 'Inlet', 'INLT': 'Inlet',
    'IS': 'Island', 'ISLAND': 'Island', 'ISLND': 'Island',
    'ISS': 'Islands', 'ISLANDS': 'Islands', 'ISLNDS': 'Islands',
    'JCT': 'Junction', 'JCTION': 'Junction', 'JCTN': 'Junction', 'JUNCTION': 'Junction', 'JUNCTN': 'Junction', 'JUNCTON': 'Junction',
    'JCTS': 'Junctions', 'JUNCTIONS': 'Junctions',
    'KEY': 'Key', 'KY': 'Key', 'KEYS': 'Keys', 'KYS': 'Keys',
    'KNL': 'Knoll', 'KNOL': 'Knoll', 'KNOLL': 'Knoll',
    'KNLS': 'Knolls', 'KNOLLS': 'Knolls',
    'LAKE': 'Lake', 'LK': 'Lake', 'LAKES': 'Lakes', 'LKS': 'Lakes',
    'LAND': 'Land', 'LND': 'Land',
    'LANDING': 'Landing', 'LNDG': 'Landing', 'LNDNG': 'Landing',
    'LANE': 'Lane', 'LN': 'Lane',
    'LGT': 'Light', 'LIGHT': 'Light', 'LGTS': 'Lights', 'LIGHTS': 'Lights',
    'LOAF': 'Loaf', 'LF': 'Loaf',
    'LOCK': 'Lock', 'LCK': 'Lock', 'LOCKS': 'Locks', 'LCKS': 'Locks',
    'LDG': 'Lodge', 'LODG': 'Lodge', 'LODGE': 'Lodge',
    'LOOPS': 'Loops',
    'MALL': 'Mall',
    'MANOR': 'Manor', 'MNR': 'Manor', 'MANORS': 'Manors', 'MNRS': 'Manors',
    'MEADOW': 'Meadow', 'MDW': 'Meadow', 'MEADOWS': 'Meadows', 'MDWS': 'Meadows',
    'MEWS': 'Mews',
    'MILL': 'Mill', 'ML': 'Mill', 'MILLS': 'Mills', 'MLS': 'Mills',
    'MISSION': 'Mission', 'MISSN': 'Mission', 'MSN': 'Mission',
    'MOTORWAY': 'Motorway', 'MTWY': 'Motorway',
    'MOUNT': 'Mount', 'MT': 'Mount',
    'MNTAIN': 'Mountain', 'MNTN': 'Mountain', 'MOUNTAIN': 'Mountain', 'MOUNTIN': 'Mountain', 'MTIN': 'Mountain', 'MTN': 'Mountain',
    'MNTNS': 'Mountains', 'MOUNTAINS': 'Mountains',
    'NCK': 'Neck', 'NECK': 'Neck',
    'ORCH': 'Orchard', 'ORCHARD': 'Orchard', 'ORCHRD': 'Orchard',
    'OVAL': 'Oval',
    'OVERPASS': 'Overpass', 'OPAS': 'Overpass',
    'PARK': 'Park', 'PRK': 'Park', 'PARKS': 'Parks',
    'PARKWAY': 'Parkway', 'PARKWY': 'Parkway', 'PKWAY': 'Parkway', 'PKWY': 'Parkway', 'PKY': 'Parkway',
    'PARKWAYS': 'Parkways', 'PKWYS': 'Parkways',
    'PASS': 'Pass', 'PSS': 'Pass',
    'PASSAGE': 'Passage', 'PSGE': 'Passage',
    'PATH': 'Path', 'PATHS': 'Paths',
    'PIKE': 'Pike', 'PIKES': 'Pikes',
    'PINE': 'Pine', 'PNE': 'Pine', 'PINES': 'Pines', 'PNES': 'Pines',
    'PL': 'Place', 'PLACE': 'Place',
    'PLAIN': 'Plain', 'PLN': 'Plain', 'PLAINS': 'Plains', 'PLNS': 'Plains',
    'PLAZA': 'Plaza', 'PLZ': 'Plaza', 'PLZA': 'Plaza',
    'POINT': 'Point', 'PT': 'Point', 'POINTS': 'Points', 'PTS': 'Points',
    'PORT': 'Port', 'PRT': 'Port', 'PORTS': 'Ports', 'PRTS': 'Ports',
    'PRAIRIE': 'Prairie', 'PR': 'Prairie', 'PRR': 'Prairie',
    'RAD': 'Radial', 'RADIAL': 'Radial', 'RADIEL': 'Radial', 'RADL': 'Radial',
    'RAMP': 'Ramp',
    'RANCH': 'Ranch', 'RANCHES': 'Ranch', 'RNCH': 'Ranch', 'RNCHS': 'Ranch',
    'RAPID': 'Rapid', 'RPD': 'Rapid', 'RAPIDS': 'Rapids', 'RPDS': 'Rapids',
    'REST': 'Rest', 'RST': 'Rest',
    'RDG': 'Ridge', 'RDGE': 'Ridge', 'RIDGE': 'Ridge', 'RDGS': 'Ridges', 'RIDGES': 'Ridges',
    'RIV': 'River', 'RIVER': 'River', 'RIVR': 'River', 'RVR': 'River',
    'RD': 'Road', 'ROAD': 'Road', 'RDS': 'Roads', 'ROADS': 'Roads',
    'ROUTE': 'Route', 'RTE': 'Route',
    'ROW': 'Row', 'RUE': 'Rue', 'RUN': 'Run',
    'SHL': 'Shoal', 'SHOAL': 'Shoal', 'SHLS': 'Shoals', 'SHOALS': 'Shoals',
    'SHOAR': 'Shore', 'SHORE': 'Shore', 'SHR': 'Shore',
    'SHOARS': 'Shores', 'SHORES': 'Shores', 'SHRS': 'Shores',
    'SKYWAY': 'Skyway', 'SKWY': 'Skyway',
    'SPG': 'Spring', 'SPNG': 'Spring', 'SPRING': 'Spring', 'SPRNG': 'Spring',
    'SPGS': 'Springs', 'SPNGS': 'Springs', 'SPRINGS': 'Springs', 'SPRNGS': 'Springs',
    'SPUR': 'Spur', 'SPURS': 'Spur',
    'SQ': 'Square', 'SQR': 'Square', 'SQRE': 'Square', 'SQU': 'Square', 'SQUARE': 'Square',
    'SQRS': 'Squares', 'SQUARES': 'Squares', 'SQS': 'Squares',
    'STA': 'Station', 'STATION': 'Station', 'STATN': 'Station', 'STN': 'Station',
    'STRA': 'Stravenue', 'STRAV': 'Stravenue', 'STRAVE': 'Stravenue', 'STRAVEN': 'Stravenue', 'STRAVENUE': 'Stravenue',
    'STRAVN': 'Stravenue', 'STRVN': 'Stravenue', 'STRVNUE': 'Stravenue',
    'STREAM': 'Stream', 'STREME': 'Stream', 'STRM': 'Stream',
    'ST': 'Street', 'STR': 'Street', 'STREET': 'Street', 'STRT': 'Street',
    'STS': 'Streets', 'STREETS': 'Streets',
    'SMT': 'Summit', 'SUMIT': 'Summit', 'SUMITT': 'Summit', 'SUMMIT': 'Summit',
    'TER': 'Terrace', 'TERR': 'Terrace', 'TERRACE': 'Terrace',
    'THROUGHWAY': 'Throughway', 'TRWY': 'Throughway',
    'TRACE': 'Trace', 'TRACES': 'Trace', 'TRCE': 'Trace',
    'TRACK': 'Track', 'TRACKS': 'Track', 'TRAK': 'Track', 'TRK': 'Track', 'TRKS': 'Track',
    'TRAFFICWAY': 'Trafficway', 'TRFY': 'Trafficway',
    'TR': 'Trail', 'TRAIL': 'Trail', 'TRAILS': 'Trail', 'TRL': 'Trail', 'TRLS': 'Trail',
    'TUNEL': 'Tunnel', 'TUNL': 'Tunnel', 'TUNLS': 'Tunnel', 'TUNNEL': 'Tunnel', 'TUNNELS': 'Tunnel', 'TUNNL': 'Tunnel',
    'TPK': 'Turnpike', 'TPKE': 'Turnpike', 'TRNPK': 'Turnpike', 'TRPK': 'Turnpike', 'TURNPIKE': 'Turnpike', 'TURNPK': 'Turnpike',
    'UNDERPASS': 'Underpass', 'UPAS': 'Underpass',
    'UN': 'Union', 'UNION': 'Union', 'UNIONS': 'Unions', 'UNS': 'Unions',
    'VALLEY': 'Valley', 'VALLY': 'Valley', 'VLLY': 'Valley', 'VLY': 'Valley',
    'VALLEYS': 'Valleys', 'VLYS': 'Valleys',
    'VDCT': 'Viaduct', 'IA': 'Viaduct', 'VIA': 'Viaduct', 'VIADCT': 'Viaduct', 'VIADUCT': 'Viaduct',
    'VIEW': 'View', 'VW': 'View', 'VIEWS': 'Views', 'VWS': 'Views',
    'VILL': 'Village', 'VILLAG': 'Village', 'VILLAGE': 'Village', 'VILLG': 'Village', 'VILLIAGE': 'Village', 'VLG': 'Village',
    'VILLAGES': 'Villages', 'VLGS': 'Villages',
    'VILLE': 'Ville', 'VL': 'Ville',
    'VIS': 'Vista', 'VIST': 'Vista', 'VISTA': 'Vista', 'VST': 'Vista', 'VSTA': 'Vista',
    'WALK': 'Walk', 'WALKS': 'Walks', 'WALL': 'Wall',
    'WAY': 'Way', 'WY': 'Way', 'WAYS': 'Ways',
    'WELL': 'Well', 'WL': 'Well',
    'WELLS': 'Wells', 'WLS': 'Wells'
}
 
_PUNCT_TRIM = ".,;:"
_UNIT_MARKERS = {"APT", "UNIT", "STE", "SUITE", "#", "FL", "FLOOR", "RM", "ROOM", "BLDG", "BUILDING", "LOT"}
 
# Direction expansion
_DIRECTION_LONG = {
    "N": "North",
    "S": "South",
    "E": "East",
    "W": "West",
    "NE": "Northeast",
    "NW": "Northwest",
    "SE": "Southeast",
    "SW": "Southwest",
}
 
# Replace commas/periods with spaces
_RE_PUNCT_TO_SPACE = re.compile(r"[.,]+")
_RE_MULTI_SPACE = re.compile(r"\s+")
 
# --- NEW: if address has "#" but no "Suite"/"Ste", convert "#123" -> "Suite 123" ---
 
_SUITE_PRESENT_RE = re.compile(r"\b(?:SUITE|STE)\b", re.IGNORECASE)
_HASH_UNIT_RE = re.compile(r"#\s*([A-Za-z0-9-]+)")
 
def _ensure_suite_for_hash(address: str) -> str:
    """
    If address contains '#' and does NOT already mention Suite/Ste,
    replace patterns like '#100' or '# 100' with 'Suite 100'.
    """
    if not address or "#" not in address:
        return address
 
    # already has Suite/Ste -> leave as-is
    if _SUITE_PRESENT_RE.search(address):
        return address
 
    # replace '#123' with ' Suite 123'
    return _HASH_UNIT_RE.sub(r" Suite \1", address)
 
def expand_suffix_long(address: str, suffix_map: dict[str, str] = USPS_SUFFIX_LONG) -> str:
    if not address or not address.strip():
        return address
 
    # normalize "#" to Suite if needed
    address = _ensure_suite_for_hash(address)
 
    # ALWAYS remove commas & periods
    cleaned = _RE_PUNCT_TO_SPACE.sub(" ", address)
    cleaned = _RE_MULTI_SPACE.sub(" ", cleaned).strip()
 
    tokens = cleaned.split()
    if not tokens:
        return cleaned
 
    upper_tokens = [t.strip(_PUNCT_TRIM).upper() for t in tokens]
 
    # Stop before unit marker (Suite/Apt/#/etc.)
    stop_idx = len(tokens)
    for i, ut in enumerate(upper_tokens):
        if ut in _UNIT_MARKERS:
            stop_idx = i
            break
 
    # If tail looks like "... City State Zip", avoid matching suffix/direction in that tail
    street_end = stop_idx
    if street_end >= 1 and re.fullmatch(r"\d{5}(?:-\d{4})?", tokens[street_end - 1] or ""):
        if street_end >= 2 and re.fullmatch(r"[A-Z]{2}", upper_tokens[street_end - 2] or ""):
            street_end = max(0, street_end - 3)  # CITY(>=1 token) + STATE + ZIP
 
    # Expand directions in street portion only
    for i in range(street_end):
        ut = upper_tokens[i]
        if ut in _DIRECTION_LONG:
            tokens[i] = _DIRECTION_LONG[ut]
            upper_tokens[i] = tokens[i].upper()
 
    # Replace last matching suffix token before unit marker / before tail
    replace_idx = None
    for i in range(street_end - 1, -1, -1):
        ut = upper_tokens[i]
        if ut in suffix_map:
            replace_idx = i
            break
 
    if replace_idx is not None:
        core = tokens[replace_idx].strip(_PUNCT_TRIM).upper()
        tokens[replace_idx] = suffix_map[core]
 
    return " ".join(tokens)
 
# normalize ALL abbreviations to long format (suffix + direction + unit designators)
def normalize_address(addr: str) -> str:
    if not addr:
        return ""

    # normalize "#" to Suite if needed BEFORE stripping it
    addr = _ensure_suite_for_hash(addr)

    # remove punctuation consistently
    s = str(addr).upper().strip()
    s = re.sub(r"[.,#]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""

    # Normalize PO BOX variants: "P.O. Box", "P O Box", etc. -> "PO BOX"
    s = re.sub(r"\bP\s*\.?\s*O\s+BOX\b", "PO BOX", s)

    tokens = s.split()

    # direction -> long (uppercase for comparison)
    dir_map = {
        "N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST",
        "NE": "NORTHEAST", "NW": "NORTHWEST", "SE": "SOUTHEAST", "SW": "SOUTHWEST",
    }

    # unit/secondary designators -> long
    unit_map = {
        "APT": "APARTMENT", "APARTMENT": "APARTMENT",
        "STE": "SUITE", "SUITE": "SUITE",
        "UNIT": "UNIT",
        "BLDG": "BUILDING", "BUILDING": "BUILDING",
        "FL": "FLOOR", "FLOOR": "FLOOR",
        "RM": "ROOM", "ROOM": "ROOM",
        "LOT": "LOT",
        "DEPT": "DEPARTMENT", "DEPARTMENT": "DEPARTMENT",
        "TRLR": "TRAILER", "TRAILER": "TRAILER",
        "HNGR": "HANGAR", "HANGAR": "HANGAR",
        "PIER": "PIER",
        "BSMT": "BASEMENT", "BASEMENT": "BASEMENT",
        "FRNT": "FRONT", "FRONT": "FRONT",
        "LBBY": "LOBBY", "LOBBY": "LOBBY",
        "LOWR": "LOWER", "LOWER": "LOWER",
        "OFC": "OFFICE", "OFFICE": "OFFICE",
        "PH": "PENTHOUSE", "PENTHOUSE": "PENTHOUSE",
        "UPPR": "UPPER", "UPPER": "UPPER",
        "REAR": "REAR", "SIDE": "SIDE",
        "CORP": "CORPORATE",
        "CORPORATION": "CORPORATE",
    }

    out = []
    for t in tokens:
        # ZIP+4 handling: keep only first 5 digits for ANY zip
        # e.g. "91203-1234" -> "91203"
        if re.fullmatch(r"\d{5}(?:-\d{4})?", t):
            t = t[:5]

        if t in dir_map:
            out.append(dir_map[t])
        elif t in unit_map:
            out.append(unit_map[t])
        elif t in USPS_SUFFIX_LONG:
            out.append(USPS_SUFFIX_LONG[t].upper())
        else:
            out.append(t)

    return re.sub(r"\s+", " ", " ".join(out)).strip()
 
def addressMatch(TempAddr: str, RealAddr: str) -> bool:
    # robust comparison using normalized addresses
    Temp = normalize_address(TempAddr)
    Real = normalize_address(RealAddr)
    # print(Temp in Real)
    return Temp in Real or Real in Temp
 
def format_phone_us(phone: str) -> str:
    if phone is None:
        return ""
 
    raw = str(phone).strip()
    if not raw:
        return ""
 
    digits = re.sub(r"\D", "", raw)
 
    # Drop US country code
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
 
    if len(digits) != 10:
        return raw
 
    area, first3, last4 = digits[:3], digits[3:6], digits[6:]
    return f"({area}) {first3}-{last4}"
 
def format_phone_list(text_block: str) -> list[str]:
    out = []
    for line in (text_block or "").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(format_phone_us(line))
    return out

# searchcity
# searchstcd
# name = LocCont




# ---------------------------------------------------------------------------
# Ported from legacy_steps.py (_normalize_name, _*_match, _click_first_row_if_any).
# ---------------------------------------------------------------------------
def normalize_name(value: str) -> str:
    value = re.sub(r'[^A-Z0-9\s]', ' ', (value or '').upper())
    return re.sub(r'\s+', ' ', value).strip()


def facility_strong_match(facility: str, result: str) -> bool:
    fac, res = normalize_name(facility), normalize_name(result)
    return bool(fac and res and fac == res)


def provider_strong_match(first: str, last: str, result: str) -> bool:
    first, last, res = normalize_name(first), normalize_name(last), normalize_name(result)
    if not first or not last or not res:
        return False
    return res in (f'{first} {last}', f'{last} {first}', f'{last}, {first}')


def facility_loose_match(facility: str, result: str) -> bool:
    fac, res = normalize_name(facility), normalize_name(result)
    return bool(fac and res and (fac in res or res in fac))


def provider_loose_match(first: str, last: str, result: str) -> bool:
    first, last, res = normalize_name(first), normalize_name(last), normalize_name(result)
    return bool(res and (first or last) and first in res and last in res)


def facility_search_word(facility: str) -> str:
    """First significant word of the facility name, as the legacy bot searched with."""
    words = re.findall(r'[A-Za-z0-9&]+', ' '.join((facility or '').split()))
    if words and words[0].upper() == 'THE':
        words = words[1:]
    return words[0] if words else ''


def choose_row(rows, kind, data):
    """Return the index of the RRS result row to select, or None.

    rows: list of {'name', 'address', 'phone'} read from dgResults.
    A row qualifies only when its address matches (or is >= 0.76 similar) AND its phone
    matches. Strong name matches win; otherwise a loose name match is accepted
    (the legacy Google confirmation step is intentionally not used).
    """
    real_addr = expand_suffix_long(f"{data['providerAddr']} {data['providerCity']} "
                                   f"{data['providerState']} {data['providerZip']}")
    real_phone = format_phone_us(data['providerPhone'])
    if not real_phone:
        return None
    candidates = []
    for index, row in enumerate(rows):
        addr = expand_suffix_long(row.get('address') or '')
        similarity = difflib.SequenceMatcher(None, (addr or '').lower(), (real_addr or '').lower()).ratio()
        if not (addressMatch(addr, real_addr) or similarity >= 0.76):
            continue
        if format_phone_us(row.get('phone') or '') != real_phone:
            continue
        candidates.append((index, row.get('name') or ''))
    facility, first, last = data['providerName'], data['providerFirst'], data['providerLast']
    if kind == 'fac':
        passes = (lambda n: facility_strong_match(facility, n),
                  lambda n: facility_loose_match(facility, n) or facility_loose_match(facility_search_word(facility), n))
    else:
        passes = (lambda n: provider_strong_match(first, last, n),
                  lambda n: provider_loose_match(first, last, n))
    for matches in passes:
        for index, name in candidates:
            if matches(name):
                return index
    return None


def choose_adjuster_row(physical_addresses, targets):
    """Index of the first adjuster row whose physical address matches any target, or None.

    Ported from legacy_steps (addressMatch on 'Physical Address' vs the Office Matrix physical
    and mailing addresses). Unlike legacy, blank targets never match: addressMatch('', x) is True.
    """
    targets = [expand_suffix_long(t) for t in targets if (t or '').strip()]
    for index, address in enumerate(physical_addresses):
        if address and any(addressMatch(expand_suffix_long(address), t) for t in targets):
            return index
    return None
