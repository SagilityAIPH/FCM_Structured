"""Authoritative page-one referral identifier from a printed form label."""
import re

_LABEL = re.compile(r'^[ \t]*Referral[ \t]*(?:Number|No\.?|#)[ \t]*:[ \t]*(.*)$', re.I)
_PAGE = re.compile(r'(?i)^\s*(?:=+\s*)?PAGE\s+(\d+)\b')
_CLAIMANT = re.compile(r'^\s*Claimant\s+Information\s*$', re.I)


def read_referral_number(source):
    """Return first valid header label, then first valid page-one label, else Not found.

    An invalid/blank label does not authorize borrowing a neighbouring field.
    """
    lines = source.splitlines()
    first_page = []
    for line in lines:
        marker = _PAGE.match(line)
        if marker:
            if marker[1] != '1':
                break
            continue
        first_page.append(line)
    # Without a page-one marker, the initial text is the first page. A later
    # page marker still bounds it above. Never search later numbered pages.
    boundary = next((i for i, line in enumerate(first_page) if _CLAIMANT.fullmatch(line)), len(first_page))
    matches = []
    for i, line in enumerate(first_page):
        label = _LABEL.fullmatch(line)
        if not label:
            continue
        candidate = label[1].strip()
        if not candidate:
            candidate = next((other.strip() for other in first_page[i + 1:] if other.strip()), '')
        if re.fullmatch(r'[0-9]+', candidate):
            matches.append((i, candidate))
    return next((value for i, value in matches if i < boundary),
                matches[0][1] if matches else 'Not found')
