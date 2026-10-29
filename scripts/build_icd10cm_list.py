"""Build the FY2027 ICD-10-CM list from CMS's official order file.

Source: https://www.cms.gov/files/zip/2027-code-descriptions-tabular-order.zip
Member: Code Descriptions/icd10cm_order_2027.txt (effective 2026-10-01).
Download this ZIP from CMS separately and pass its local path; no network at build time.
"""
import argparse
from pathlib import Path
import re
import zipfile

SOURCE_URL = 'https://www.cms.gov/files/zip/2027-code-descriptions-tabular-order.zip'
MEMBER = 'Code Descriptions/icd10cm_order_2027.txt'
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / 'AI/data/icd10cm_2027.txt'
ROW = re.compile(r'^\d{5} ([A-Z][0-9A-Z]{2,6}) +([01]) ')


def build(source, output=DEFAULT_OUTPUT):
    with zipfile.ZipFile(source) as archive:
        lines = archive.read(MEMBER).decode('latin-1').splitlines()
    codes = {}
    for line in lines:
        match = ROW.match(line)
        if not match:
            raise ValueError(f'Unexpected ICD-10-CM order row: {line[:40]!r}')
        code, billable = match.groups()
        if code in codes:
            raise ValueError(f'Duplicate ICD-10-CM code: {code}')
        codes[code] = billable
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('# FY2027 ICD-10-CM, effective 2026-10-01\n'
                      f'# Source: {SOURCE_URL}\n'
                      f'# Member: {MEMBER}\n'
                      '# Dotless code and billable flag (1=yes, 0=category/header)\n'
                      + ''.join(f'{code} {flag}\n' for code, flag in codes.items()), encoding='ascii')
    return len(codes), sum(flag == '1' for flag in codes.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', type=Path, help='Official CMS FY2027 code-descriptions/tabular-order ZIP')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print('total, billable:', *build(args.zip, args.output))
