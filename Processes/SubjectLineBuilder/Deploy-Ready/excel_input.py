"""Standalone workbook contract: one referral and one provider per row."""
from datetime import date, datetime, time
from pathlib import Path
import re

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from manual_flow import GROUPS, CHOICES, defaults, validate

SHEET = 'Subject Line Input'
PREFIXES = ['Claim', 'Claimant', 'Provider', 'Adjuster', 'Attorney']
COLUMNS = [(field[0], f'{prefix} - {field[1]}', len(field) > 2 and field[2])
           for prefix, (_, fields) in zip(PREFIXES, GROUPS) for field in fields]


def create_template(path):
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET
    sheet.append([label for _, label, _ in COLUMNS])
    sheet.freeze_panes = 'C2'
    sheet.auto_filter.ref = f'A1:{get_column_letter(len(COLUMNS))}501'
    sheet.row_dimensions[1].height = 44
    for index, (key, label, required) in enumerate(COLUMNS, 1):
        header = sheet.cell(1, index)
        header.font = Font(color='FFFFFF', bold=True)
        header.fill = PatternFill('solid', fgColor='2563EB' if required else '475569')
        header.alignment = Alignment(wrap_text=True, vertical='center')
        header.comment = Comment('Required before starting.' if required else 'Optional. Enter a facility or doctor name for the provider.', 'FCM')
        sheet.column_dimensions[get_column_letter(index)].width = 25
        for row in range(2, 502):
            sheet.cell(row, index).number_format = '@'
        if key in CHOICES:
            rule = DataValidation(type='list', formula1='"' + ','.join(v for v in CHOICES[key] if v) + '"', allow_blank=True)
            rule.errorTitle = 'Choose a listed value'
            rule.error = 'Use the dropdown choices.'
            rule.showErrorMessage = True
            sheet.add_data_validation(rule)
            rule.add(f'{get_column_letter(index)}2:{get_column_letter(index)}501')
    guide = book.create_sheet('Instructions')
    notes = [
        'Subject Line Builder Excel input',
        'Fill Subject Line Input, starting on row 2. One referral and one provider per row.',
        'Blue headers are required before starting. A facility or doctor name is also required.',
        'Blank market defaults to Liberty Mutual Commercial Market; blank referral type to Full Case Management; blank referral source to Adjuster. Review these defaults.',
        'Dates: MM/DD/YYYY. Appointment time is optional (example 08:30 AM). Use two-letter US states.',
        'Identifiers, ZIP codes and phones are text to preserve leading zeros. Do not use formulas.',
        'Leave unknown optional values blank. Incomplete rows can be loaded and corrected in the app.',
        'Open Excel in the app, choose a row, then Load row. Loading replaces the current form but never starts RRS.',
        'This is the standalone input template; AI PDF Reader daily workbooks use a different schema.',
        'Save as .xlsx. Keep the sheet name and column headers. No sample patient data is included.',
    ]
    for note in notes:
        guide.append([note])
        guide.cell(guide.max_row, 1).alignment = Alignment(wrap_text=True, vertical='top')
        guide.row_dimensions[guide.max_row].height = 42
    guide.column_dimensions['A'].width = 115
    guide['A1'].font = Font(size=16, bold=True, color='2563EB')
    book.save(path)
    book.close()
    return str(path)


def _text(cell):
    value = cell.value
    if value is None:
        return ''
    if cell.data_type in ('f', 'e'):
        raise ValueError(f'{cell.coordinate}: replace formulas or Excel errors with plain values.')
    if isinstance(value, (datetime, date)):
        return value.strftime('%m/%d/%Y')
    if isinstance(value, time):
        return value.strftime('%I:%M %p')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if re.fullmatch(r'0+', cell.number_format) and float(value).is_integer():
            return str(int(value)).zfill(len(cell.number_format))
        if float(value).is_integer():
            return str(int(value))
    return str(value).strip()


def read_workbook(path):
    if Path(path).suffix.lower() != '.xlsx':
        raise ValueError('Choose an .xlsx workbook made from the Subject Line Builder template.')
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        if SHEET not in book.sheetnames:
            raise ValueError(f'Missing "{SHEET}" sheet. Use the Subject Line Builder template.')
        sheet = book[SHEET]
        if sheet.max_row > 10001 or sheet.max_column > 200:
            raise ValueError('Use a workbook with up to 10,000 input rows and 200 columns.')
        rows = sheet.iter_rows()
        headers = [str(c.value or '').strip() for c in next(rows, [])]
        known = {label.casefold(): key for key, label, _ in COLUMNS}
        mapping = {}
        for index, label in enumerate(headers):
            key = known.get(label.casefold())
            if key:
                if key in mapping.values():
                    raise ValueError(f'Duplicate column: {label}')
                mapping[index] = key
        if not mapping:
            raise ValueError('No recognized columns. Use the Subject Line Builder template.')
        records = []
        for number, row in enumerate(rows, 2):
            supplied = {key: _text(row[index]) for index, key in mapping.items()}
            if not any(supplied.values()):
                continue
            data = defaults()
            data.update({key: value for key, value in supplied.items() if value})
            try:
                validate(data)
                warning = ''
            except ValueError as error:
                warning = str(error)
            name = ' '.join(filter(None, [data['claimantFirst'], data['claimantLast']])) or 'Unnamed claimant'
            records.append({'row': number, 'label': f"Row {number} | {name} | {data['claimNumber'] or 'No claim number'}",
                            'data': data, 'warning': warning})
        if not records:
            raise ValueError('No filled rows found. Enter referral details starting on row 2, save, then reopen the workbook.')
        return records
    finally:
        book.close()
