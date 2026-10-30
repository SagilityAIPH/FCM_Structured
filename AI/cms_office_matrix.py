"""Pure CMS office-matrix resolution; workbook I/O belongs to the caller."""

SHEETS = ("Liberty and Middle Market", "LM Physical Address",
          "Manual Tracking LM Claim Office")


def office_lookup(rows, office_number):
    """Legacy primary-sheet block algorithm, retained for caller compatibility."""
    physical, mailing, collecting = [], [], False
    for row in rows:
        office = str(row[0] or "").strip() if row else ""
        if office:
            collecting = bool(office_number) and str(office_number).upper() in office.upper()
            if collecting:
                physical, mailing = [], []
        if collecting:
            for column, target in ((6, physical), (7, mailing)):
                if len(row) > column and row[column]:
                    target.append(str(row[column]).strip())
    return (" ".join(physical).lower(), " ".join(mailing).lower())


def _normalized(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Office mapping malformed")
    return " ".join(value.split()).lower()


def resolve_office(sheets, office_number):
    """Return normalized (physical, mailing), using legacy worksheet priority.

    Sheet values include header rows. Literal case-insensitive substring ID
    matching is retained; duplicates stop even when their addresses agree.
    No match, unreadable content or malformed matching records raise value-free
    errors rather than selecting another tier.
    """
    if (not isinstance(office_number, (str, int)) or isinstance(office_number, bool)
            or not str(office_number).strip()):
        raise ValueError("Office identifier unavailable")
    if sheets is None:
        raise ValueError("Office matrix unavailable")
    target = str(office_number).upper()
    try:
        for tier, sheet in enumerate(SHEETS):
            rows = sheets.get(sheet, ())
            matches = []
            if tier == 0:
                rows = rows[5:]
                matches = [row for row in rows if row and row[0]
                           and target in str(row[0]).strip().upper()]
                if len(matches) == 1:
                    # Check types before the compatibility algorithm can coerce
                    # malformed address cells to plausible text.
                    collecting = False
                    for row in rows:
                        if row and row[0] not in (None, ""):
                            collecting = target in str(row[0]).strip().upper()
                        if collecting:
                            for value in row[6:8]:
                                if value not in (None, "") and not isinstance(value, str):
                                    raise ValueError("Office mapping malformed")
                    physical, mailing = office_lookup(rows, office_number)
                    if not physical and not mailing:
                        raise ValueError("Office mapping malformed")
                    return (" ".join(physical.split()), " ".join(mailing.split()))
            else:
                for row in rows[1:] if tier == 1 else rows:
                    if not row or row[0] in (None, ""):
                        continue
                    if tier == 1:
                        identifier = str(row[0]).strip()
                        address = row[5] if len(row) > 5 else None
                    else:
                        text = str(row[0]).strip().replace("–", "-").replace("—", "-")
                        identifier, separator, address = text.partition("-")
                        if not separator:
                            # An identifier-only matching row is malformed;
                            # headers and unrelated rows remain ignorable.
                            if target in identifier.upper():
                                raise ValueError("Office mapping malformed")
                            continue
                    if target in identifier.strip().upper():
                        matches.append(address)
                if len(matches) == 1:
                    address = _normalized(matches[0])
                    return address, address
            if matches:
                raise ValueError("Office mapping ambiguous")
    except (Exception, SystemExit):
        raise ValueError("Office matrix resolution failed") from None
    raise ValueError("Office mapping unresolved")
