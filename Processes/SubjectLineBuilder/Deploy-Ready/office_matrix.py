"""Claims Office Matrix lookup for the standalone Subject Line Builder adjuster search.

CANDIDATE FOR REMOVAL: formataddrSearchStr, parse_address and extract_physical_address below are
verbatim copies from src/fcm_intake/legacy/legacy_fcm.py (lines ~245-371 and ~887-993). legacy_fcm
cannot be imported here (it binds to RRS and the database at import time). Once those helpers move
to an importable module, delete the copies and import them instead.
"""
import os
import re
import sys
from pathlib import Path

import openpyxl

MATRIX_NAME = "Liberty Mutual Claims Office Matrix_08-29-19.xlsx"


def formataddrSearchStr (s: str) -> str:
    # your existing formatter – placeholder
    return " ".join(str(s).split())

def parse_address(full_address: str):
    text = full_address.strip()
    text = re.sub(r"\s+", " ", text)           # normalize spaces
    text = re.sub(r",\s*,+", ",", text)        # collapse double commas: ",," -> ","
    text = text.replace(" ,", ",")             # normalize " ,"

    # ---------- 1) ZIP ----------
    zip_match = re.search(r"(\d{5})(?:-\d{4})?\s*,?\s*$", text)
    zipcode = zip_match.group(1) if zip_match else ""
    if zipcode:
        text = text[:zip_match.start()].rstrip(" ,")

    # ---------- 2) STATE ----------
    state = ""
    state_codes = {
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
        "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
        "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
    }
    full_to_abbr = {
        "ALABAMA":"AL","ALASKA":"AK","ARIZONA":"AZ","ARKANSAS":"AR","CALIFORNIA":"CA",
        "COLORADO":"CO","CONNECTICUT":"CT","DELAWARE":"DE","FLORIDA":"FL","GEORGIA":"GA",
        "HAWAII":"HI","IDAHO":"ID","ILLINOIS":"IL","INDIANA":"IN","IOWA":"IA","KANSAS":"KS",
        "KENTUCKY":"KY","LOUISIANA":"LA","MAINE":"ME","MARYLAND":"MD","MASSACHUSETTS":"MA",
        "MICHIGAN":"MI","MINNESOTA":"MN","MISSISSIPPI":"MS","MISSOURI":"MO","MONTANA":"MT",
        "NEBRASKA":"NE","NEVADA":"NV","NEW HAMPSHIRE":"NH","NEW JERSEY":"NJ",
        "NEW MEXICO":"NM","NEW YORK":"NY","NORTH CAROLINA":"NC","NORTH DAKOTA":"ND",
        "OHIO":"OH","OKLAHOMA":"OK","OREGON":"OR","PENNSYLVANIA":"PA","RHODE ISLAND":"RI",
        "SOUTH CAROLINA":"SC","SOUTH DAKOTA":"SD","TENNESSEE":"TN","TEXAS":"TX",
        "UTAH":"UT","VERMONT":"VT","VIRGINIA":"VA","WASHINGTON":"WA","WEST VIRGINIA":"WV",
        "WISCONSIN":"WI","WYOMING":"WY","DISTRICT OF COLUMBIA":"DC"
    }

    m2 = re.search(r",\s*([A-Za-z]{2,})\s*$", text)
    if m2:
        cand = m2.group(1)
        up = cand.upper()
        if up in state_codes:
            state = up
        elif up in full_to_abbr:
            state = full_to_abbr[up]
        if state:
            text = text[:m2.start()].rstrip(" ,")
    else:
        tokens = text.replace(",", " ").split()
        for tok in reversed(tokens):
            up = tok.upper()
            if up in state_codes or up in full_to_abbr:
                state = up if up in state_codes else full_to_abbr[up]
                idx = text.upper().rfind(tok.upper())
                text = (text[:idx] + text[idx+len(tok):]).rstrip(" ,")
                break

    # ---------- 3) Remaining text: addr1 / addr2 / city ----------
    addr1 = addr2 = city = ""
    addr2_keywords = {
        "suite","ste","apt","apartment","bldg","building",
        "unit","fl","floor","#","po","p.o.","po box","p.o. box","rm","room"
    }

    def split_with_commas(s):
        nonlocal addr1, addr2, city
        parts = [p.strip(" ,") for p in s.split(",") if p.strip(" ,")]
        if not parts:
            return True
        if len(parts) == 1:
            return False

        addr1 = parts[0]
        if len(parts) >= 3:
            addr2 = parts[1]
            city = " ".join(parts[2:])
        else:
            second = parts[1]
            tokens2 = second.split()
            if tokens2 and tokens2[0].lower() in addr2_keywords:
                i = 1
                # allow digits, #, and short suite letters like "B", "2B", "B1"
                while i < len(tokens2) and (
                    any(c.isdigit() for c in tokens2[i]) or
                    tokens2[i].startswith("#") or
                    re.fullmatch(r"[A-Za-z]{1,2}\d{0,2}", tokens2[i]) is not None
                ):
                    i += 1
                addr2 = " ".join(tokens2[:i])
                city = " ".join(tokens2[i:])
            else:
                city = second
        return True

    used_commas = split_with_commas(text)

    if not used_commas:
        tokens = text.replace(",", " ").split()
        if not tokens:
            return "", "", "", state, zipcode

        kw_idx = None
        for i, t in enumerate(tokens):
            if t.replace(".", "").lower() in addr2_keywords:
                kw_idx = i
                break

        if kw_idx is None:
            if len(tokens) == 1:
                addr1 = tokens[0]
            else:
                addr1 = " ".join(tokens[:-1])
                city = tokens[-1]
        else:
            j = kw_idx + 1
            while j < len(tokens) and (
                any(c.isdigit() for c in tokens[j]) or
                tokens[j].startswith("#") or
                re.fullmatch(r"[A-Za-z]{1,2}\d{0,2}", tokens[j]) is not None  # <-- captures "B"
            ):
                j += 1
            addr1 = " ".join(tokens[:kw_idx])
            addr2 = " ".join(tokens[kw_idx:j])
            city = " ".join(tokens[j:])

    return addr1, addr2, city, state, zipcode



def extract_physical_address(filename: str, target_id) -> tuple[str | None, str]:
    target_id_up = str(target_id).strip().upper()
    physAddress: str | None = None
    mailAddress: str = ""  # only populated from Sheet 1; otherwise stays blank

    wb = openpyxl.load_workbook(filename, data_only=True)
    try:
        # 1) Sheet: "Liberty and Middle Market"
        try:
            ws1 = wb["Liberty and Middle Market"]
            max_row = ws1.max_row

            collecting = False
            physical_lines: list[str] = []
            mailing_lines: list[str] = []

            for i in range(6, max_row + 1):  # starts row 6
                cell_id = ws1.cell(row=i, column=1).value  # col A

                # New ID starts
                if cell_id not in (None, ""):
                    # if we were collecting and a new ID starts, stop
                    if collecting:
                        break

                    current_id = str(cell_id).strip()
                    collecting = target_id_up in current_id.upper()

                    if collecting:
                        physical_lines = []
                        mailing_lines = []

                if collecting:
                    # Physical address (col G)
                    physical1 = ws1.cell(row=i, column=7).value
                    if physical1 not in (None, ""):
                        physical_lines.append(str(physical1).strip())

                    # Mailing address (col H)
                    mailing1 = ws1.cell(row=i, column=8).value
                    if mailing1 not in (None, ""):
                        mailing_lines.append(str(mailing1).strip())

            if physical_lines:
                physAddress = formataddrSearchStr(" ".join(physical_lines))
            if mailing_lines:
                mailAddress = formataddrSearchStr(" ".join(mailing_lines))

        except KeyError:
            # sheet not present, just skip
            pass

        if physAddress:
            return physAddress, mailAddress  # mailAddress filled ONLY from sheet 1 (or blank)

        # 2) Sheet: "LM Physical Address"  (mailAddress stays blank)
        try:
            ws2 = wb["LM Physical Address"]
            max_row2 = ws2.max_row

            for i in range(2, max_row2 + 1):  # starts row 2
                cell_id = ws2.cell(row=i, column=1).value  # ID in col A
                if cell_id is None:
                    continue

                if target_id_up in str(cell_id).strip().upper():
                    addr_value = ws2.cell(row=i, column=6).value  # address in col F
                    if addr_value:
                        physAddress = formataddrSearchStr(str(addr_value))
                    break
        except KeyError:
            pass

        if physAddress:
            return physAddress, ""  # mailing blank (only from sheet 1)

        # 3) Sheet: "Manual Tracking LM Claim Office"  (mailAddress stays blank)
        try:
            ws3 = wb["Manual Tracking LM Claim Office"]
            max_row3 = ws3.max_row

            for i in range(1, max_row3 + 1):  # starts row 1
                cell_val = ws3.cell(row=i, column=1).value  # ID + address in col A
                if not cell_val:
                    continue

                text = str(cell_val).strip()
                text = text.replace("–", "-").replace("—", "-")

                if "-" not in text:
                    continue

                id_part, addr_part = text.split("-", 1)

                if target_id_up in id_part.strip().upper():
                    physAddress = formataddrSearchStr(addr_part.strip())
                    break
        except KeyError:
            pass

        if not physAddress:
            print(f"No physical address found for ID {target_id}")

        return physAddress, ""  # always blank mailing unless sheet 1 matched

    finally:
        wb.close()


def matrix_path():
    """FCM_LM_MATRIX env var, next to the exe/module, bundled copy, then the repo docs folder."""
    candidates = [os.environ.get("FCM_LM_MATRIX", "")]
    if getattr(sys, "frozen", False):
        candidates += [Path(sys.executable).parent / MATRIX_NAME, Path(getattr(sys, "_MEIPASS", "")) / MATRIX_NAME]
    here = Path(__file__).resolve().parent
    candidates += [here / MATRIX_NAME] + [p / "docs" / MATRIX_NAME for p in here.parents]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def office_number(data):
    """Claims office number field; if blank, claim number characters 3-5 (as CMS.py).
    One leading zero is dropped, as the legacy referral parser did."""
    office = (data.get("adjOffice") or "").strip()
    if not office:
        claim = (data.get("claimNumber") or "").strip()
        office = claim[2:5] if len(claim) >= 5 else ""
    if office.startswith("0"):
        office = office[1:]
    return office


def adjuster_addresses(data):
    """(physical, mailing) address from the matrix for this claim's office; blanks if unavailable."""
    office, path = office_number(data), matrix_path()
    if not office or not path:
        return "", ""
    try:
        physical, mailing = extract_physical_address(path, office)
    except Exception:
        return "", ""
    return physical or "", mailing or ""


def enrich_adjuster(data):
    """Copy of data with blank adjuster address fields filled from the matrix physical address.
    Also returns the addresses to match RRS 'Physical Address' rows against."""
    physical, mailing = adjuster_addresses(data)
    result = dict(data)
    if physical and not any(result.get(k) for k in ("adjAddr1", "adjAddr2", "adjCity", "adjState", "adjZip")):
        addr1, addr2, city, state, zip_ = parse_address(physical)
        result.update(adjAddr1=addr1 or "", adjAddr2=addr2 or "", adjCity=city or "",
                      adjState=state or "", adjZip=zip_ or "")
    typed = " ".join(filter(None, [data.get(k, "") for k in ("adjAddr1", "adjAddr2", "adjCity", "adjState", "adjZip")])).strip()
    targets = [a for a in (physical, mailing) if a]
    if typed and data.get("adjAddr1", "").strip():
        targets.append(typed)
    return result, targets
