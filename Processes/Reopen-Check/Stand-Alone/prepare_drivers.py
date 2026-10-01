"""Fetch the pinned official IE-mode driver for a reproducible standalone build."""
import hashlib
from pathlib import Path
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = 'IEDriverServer_Win32_4.14.0.zip'
URL = 'https://github.com/SeleniumHQ/selenium/releases/download/selenium-4.14.0/' + ARCHIVE
SHA256 = '542547970163c91080b6908cd223840743a4ac18f8197a44ea41be7cf1d41e48'


def prepare():
    archive = ROOT / 'dist' / ARCHIVE
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        with urlopen(URL, timeout=60) as response:
            data = response.read()
    else:
        data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('IE driver archive checksum mismatch; remove the cached archive and retry.')
    archive.write_bytes(data)
    destination = ROOT / 'dist' / 'browser-drivers'
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        (destination / 'IEDriverServer.exe').write_bytes(bundle.read('IEDriverServer.exe'))
    print('Verified and prepared IEDriverServer 4.14.0 (32-bit, usable on 64-bit Windows).')


if __name__ == '__main__':
    prepare()
