"""Capture the RRS Body Part / Injury Type / Injury Cause dropdown lists for the AI PDF Reader.

Run once (and again whenever RRS changes these lists) with one RRS Subject Line Builder
window open, from the repository root:

    .venv-bedrock/Scripts/python.exe -m AI.export_rrs_dropdowns

Read-only: it expands and collapses the three dropdowns and never selects an item or
changes the referral. The lists are RRS reference values and contain no claim data.
Output: AI/rrs_dropdowns.json, used by injury_classification.py for the Bedrock prompt and
for checking the AI's choices.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

try:
    from .injury_classification import FIELDS, OPTIONS_FILE, _key, load_options, provisional_options
except ImportError:
    from injury_classification import FIELDS, OPTIONS_FILE, _key, load_options, provisional_options

CONTROLS = {"Body Part": "cbBodyPart", "Injury Type": "cbInjuryType", "Injury Cause": "cbInjuryCause"}
BUILDER_TITLE = r'^Subject Line Builder Email Display.*'
DEPLOY_READY = Path(__file__).resolve().parents[1] / 'Processes' / 'SubjectLineBuilder' / 'Deploy-Ready'


def capture(adapter):
    """Read the three dropdowns through the Subject Line Builder's RRS adapter."""
    adapter.builder = adapter.unique(BUILDER_TITLE)
    lists = {}
    for field, ident in CONTROLS.items():
        combo = adapter.control(adapter.builder, ident, 'ComboBox')
        items = [str(item).strip() for item in adapter._combo_options(combo)]
        items = list(dict.fromkeys(item for item in items if item and item.casefold() != 'none'))
        if not items:
            raise RuntimeError(f'No items were read from the RRS {field} dropdown. Keep the builder visible and retry.')
        lists[field] = items
    return lists


def unmapped_rule_values(lists):
    """Legacy rule values with no RRS item: these need an alias in injury_classification.py."""
    return {field: [value for value in provisional_options()[field]
                    if _key(value) not in {_key(item) for item in lists[field]}] for field in FIELDS}


def write(lists, path=OPTIONS_FILE):
    data = {'source': 'RRS Subject Line Builder',
            'captured_at': datetime.now().astimezone().isoformat(timespec='seconds'), **lists}
    path = Path(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    load_options.cache_clear()
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', default=str(OPTIONS_FILE), help='JSON file to write (default: AI/rrs_dropdowns.json)')
    args = parser.parse_args(argv)
    if str(DEPLOY_READY) not in sys.path:
        sys.path.append(str(DEPLOY_READY))
    from rrs_ui import RRSAdapter
    try:
        lists = capture(RRSAdapter())
    except RuntimeError as error:
        print(f'{error}\nOpen exactly one RRS Subject Line Builder window, then run this again.', file=sys.stderr)
        return 1
    path = write(lists, args.output)
    for field in FIELDS:
        print(f'{field}: {len(lists[field])} items')
    for field, values in unmapped_rule_values(lists).items():
        if values:
            print(f'\n{field}: legacy rule values with no RRS item (add an alias in AI/injury_classification.py):')
            print('\n'.join(f'  - {value}' for value in values))
    print(f'\nSaved {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
