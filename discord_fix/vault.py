"""Windows DPAPI secrets, encrypted for the current OS user. No plaintext fallback."""

import ctypes
import os
import re
from ctypes import wintypes
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data: bytes, decrypt=False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Geheimen opslaan vereist Windows DPAPI; geen onveilige fallback.")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise RuntimeError("Windows kon dit geheim niet beveiligen of ontsleutelen.")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class Vault:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        if not re.fullmatch("[A-Za-z0-9_-]{1,100}", name):
            raise ValueError("Ongeldige sleutelnaam.")
        return self.directory / (name + ".dpapi")

    def save(self, name, value):
        destination = self._path(name)
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(protect(value.encode()))
        temporary.replace(destination)

    def read(self, name):
        path = self._path(name)
        return protect(path.read_bytes(), decrypt=True).decode() if path.exists() else ""

    def forget(self, name):
        self._path(name).unlink(missing_ok=True)
