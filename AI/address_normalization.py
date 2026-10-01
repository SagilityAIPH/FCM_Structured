"""Split documented address components; never supply guessed address values."""
import re


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
