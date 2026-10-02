"""Preserve verbatim referral sections across PDF page boundaries."""
import re


_START = re.compile(r'^[ \t]*Special[ \t]+Instructions[ \t]*(?::[ \t]*|(?=\n|$))', re.I | re.M)
_END = re.compile(r'\bReferrer[ \t]+Name[ \t]*:|^[ \t]*Referrer[ \t]+Name[ \t]*(?=\n|$)', re.I | re.M)
_PAGINATION = re.compile(r'(?:Page\s+\d+\s+(?:of|/)\s+\d+|=+\s*PAGE\s+\d+\s*=+)', re.I)


def clean_special_instructions(text):
    """Remove pagination lines, retaining clinical wording and line breaks."""
    if text is None:
        return 'Not found'
    if not isinstance(text, str):
        raise ValueError('Field values must be strings.')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    end = _END.search(text)
    if end:
        text = text[:end.start()]
    lines, after_page = [], False
    for line in text.splitlines():
        if _PAGINATION.fullmatch(line.strip()):
            while lines and not lines[-1].strip():
                lines.pop()
            after_page = True
            continue
        if after_page and not line.strip():
            continue
        lines.append(line.rstrip())
        after_page = False
    result = '\n'.join(lines).strip()
    missing = {'', 'not found', 'n/a', 'null', 'none', 'unknown', 'unknown time', 'not provided', 'not available', 'tbd'}
    return 'Not found' if result.casefold() in missing else result


def extract_special_instructions(source_text):
    """Return None when the source has no recognizable section heading."""
    source_text = source_text.replace('\r\n', '\n').replace('\r', '\n')
    start = _START.search(source_text)
    if start is None:
        return None
    return clean_special_instructions(source_text[start.end():])
