from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path
from typing import Protocol


class SecretStoreError(RuntimeError):
    """Raised when a secret cannot be protected or recovered safely."""


class SecretProtector(Protocol):
    def protect(self, value: bytes) -> bytes: ...

    def unprotect(self, value: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    return (
        _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))),
        buffer,
    )


class DPAPIProtector:
    """Protect values with Windows DPAPI for the current Windows user."""

    _CRYPTPROTECT_UI_FORBIDDEN = 0x01
    _DESCRIPTION = "Yida AI API key"

    def protect(self, value: bytes) -> bytes:
        if os.name != "nt":
            raise SecretStoreError("安全保存 API Key 仅在 Windows 上可用")
        input_blob, input_buffer = _blob(value)
        output_blob = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        result = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            self._DESCRIPTION,
            None,
            None,
            None,
            self._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        del input_buffer
        if not result:
            raise SecretStoreError(f"Windows 无法加密 API Key（错误 {ctypes.get_last_error()}）")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output_blob.pbData)

    def unprotect(self, value: bytes) -> bytes:
        if os.name != "nt":
            raise SecretStoreError("安全读取 API Key 仅在 Windows 上可用")
        input_blob, input_buffer = _blob(value)
        output_blob = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        result = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            self._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        del input_buffer
        if not result:
            raise SecretStoreError(
                f"Windows 无法解密已保存的 API Key（错误 {ctypes.get_last_error()}）"
            )
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output_blob.pbData)


class SecretStore:
    """Store one API key as DPAPI ciphertext outside normal JSON settings."""

    def __init__(self, path: Path, protector: SecretProtector | None = None) -> None:
        self.path = path
        self.protector = protector or DPAPIProtector()

    @property
    def exists(self) -> bool:
        return self.path.is_file() and self.path.stat().st_size > 0

    def save(self, secret: str) -> None:
        value = secret.strip()
        if not value:
            raise SecretStoreError("不能保存空的 API Key")
        protected = self.protector.protect(value.encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.write_bytes(protected)
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def load(self) -> str:
        if not self.exists:
            return ""
        try:
            protected = self.path.read_bytes()
            return self.protector.unprotect(protected).decode("utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise SecretStoreError("已保存的 API Key 无法读取，请删除后重新保存") from exc

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise SecretStoreError("无法删除已保存的 API Key") from exc
