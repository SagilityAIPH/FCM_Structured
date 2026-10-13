"""Split documented address components; never supply guessed address values."""
import re


_ADDRESS_WORDS = dict(zip(
    'st str ave rd blvd ln ct pl pkwy hwy cir ste apt fl bldg rm n s e w ne nw se sw'.split(),
    'street street avenue road boulevard lane court place parkway highway circle suite apartment floor building room north south east west northeast northwest southeast southwest'.split()))


def canonical_address(value):
    """Comparison-only expansion; never infer missing address components."""
    words = re.sub(r'[^\w\s]', ' ', value.casefold().replace('.', '')).split()
    return ' '.join('drive' if word == 'dr' and index > 0 and index == len(words) - 1
                    else _ADDRESS_WORDS.get(word, word) for index, word in enumerate(words))


def split_address(record, street_key, line2_key, city_key, state_key, zip_key):
    street = record.get(street_key, 'Not found')
    if street == 'Not found':
        return
    # A comma explicitly separates the street from the city. Missing components
    # can be copied from that suffix without inferring a street/city boundary.
    match = re.search(r',\s*([A-Za-z][A-Za-z .\'-]+?),?\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*$', street, re.I)
    if match:
        for key, value in zip((city_key, state_key, zip_key), match.groups()):
            if record.get(key, 'Not found') == 'Not found':
                record[key] = value.strip()
    # Remove a suffix only when it agrees with the separately extracted value.
    for key in (zip_key, state_key, city_key):
        value = record.get(key, 'Not found')
        if value != 'Not found':
            street = re.sub(r'(?:[,\s]+)' + re.escape(value) + r'\s*[,]*$', '', street, flags=re.I).strip(' ,')
    unit = re.search(r'(?:,\s*|\s+)((?:apt\.?|apartment|suite|ste\.?|unit|floor|fl\.?)\s+[^,]+|#\s*[^,]+)$', street, re.I)
    if unit and record.get(line2_key, 'Not found') == 'Not found':
        record[line2_key] = unit.group(1).strip()
        street = street[:unit.start()].strip(' ,')
    record[street_key] = street or 'Not found'
