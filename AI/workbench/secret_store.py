"""DPAPI protects blobs for the current Windows user, not against malware running as that user.

Only encrypted bytes live in LocalAppData. Another Windows account cannot
normally decrypt the blob; roaming domain profiles and backups may change its
portability. A shared/roaming profile needs its own risk review.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


_PROTECT_UI_FORBIDDEN = 0x1
_NAMES = {"bedrock": "bedrock.dpapi", "cms": "cms.dpapi"}


class SecretStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else Path(os.environ["LOCALAPPDATA"]) / "FCM_Structured" / "credentials"

    def _path(self, name):
        return self.directory / _NAMES[name]

    @staticmethod
    def _crypt(data, *, protect):
        source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        incoming = _Blob(len(data), source)
        outgoing = _Blob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        method = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        method.argtypes = ([ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob),
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
                           if protect else
                           [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob),
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)])
        method.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        if not method(ctypes.byref(incoming), None, None, None, None,
                      _PROTECT_UI_FORBIDDEN, ctypes.byref(outgoing)):
            raise RuntimeError("Credential protection is unavailable.") from None
        try:
            return ctypes.string_at(outgoing.pbData, outgoing.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(outgoing.pbData, ctypes.c_void_p))

    @staticmethod
    def _restrict(path, directory=False):
        # Remove inherited grants and grant only the interactive user. No output,
        # including an OS error, is ever forwarded to a bridge or log.
        user = os.environ["USERNAME"]
        domain = os.environ.get("USERDOMAIN", ".")
        grant = f"{domain}\\{user}:(OI)(CI)F" if directory else f"{domain}\\{user}:F"
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", grant],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    def save(self, name, plaintext):
        path = self._path(name)
        if not isinstance(plaintext, str) or not plaintext:
            raise ValueError("Cannot save an empty credential.")
        created = False
        try:
            encrypted = self._crypt(plaintext.encode("utf-8"), protect=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._restrict(path.parent, directory=True)
            # Exclusive creation prevents a pre-existing link/file being overwritten.
            # An old blob is removed only after protection succeeds.
            path.unlink(missing_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            created = True
            try:
                self._restrict(path)
                with os.fdopen(fd, "wb") as stream:
                    fd = -1
                    stream.write(encrypted)
            finally:
                if fd != -1:
                    os.close(fd)
        except Exception:
            if created:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
            raise RuntimeError("Could not securely remember the credential.") from None

    def load(self, name):
        try:
            data = self._path(name).read_bytes()
            if not data:
                return None
            return self._crypt(data, protect=False).decode("utf-8") or None
        except Exception:
            return None

    def exists(self, name):
        try:
            return self._path(name).is_file()
        except Exception:
            return False

    def forget(self, name):
        try:
            self._path(name).unlink(missing_ok=True)
        except Exception:
            raise RuntimeError("Could not forget the saved credential.") from None
