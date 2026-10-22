"""Metadata-only validation for an explicitly selected referral document."""
from pathlib import Path


SUPPORTED_EXTENSIONS = ('.pdf', '.msg', '.eml')


def referral_document(path):
    """Return the original absolute path without reading, copying or converting."""
    selected = Path(path).resolve()
    if selected.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError('Choose a referral document in PDF, MSG or EML format.')
    if not selected.is_file():
        raise ValueError('Choose one existing referral document file. The selected file may have moved or been deleted.')
    return selected
