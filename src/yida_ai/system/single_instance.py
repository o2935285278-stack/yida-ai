from __future__ import annotations

import os
from collections.abc import Callable


class SingleInstanceLock:
    """Per-user named mutex; it never terminates an existing Yida AI process."""

    def __init__(
        self,
        name: str = r"Local\YidaAI-3C4D56F8-CB55-4C1B-A487-44D11BD60D2D",
        *,
        windows_api: object | None = None,
    ) -> None:
        self.name = name
        self._api = windows_api
        self._handle: int | None = None

    def acquire(self) -> bool:
        if os.name != "nt" and self._api is None:
            return True
        api = self._api
        if api is None:
            import ctypes

            api = ctypes.windll.kernel32
            api.CreateMutexW.restype = ctypes.c_void_p
            api.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = api.CreateMutexW(None, False, self.name)
        if not handle:
            return False
        self._handle = int(handle)
        return int(api.GetLastError()) != 183

    def close(self) -> None:
        if self._handle is None:
            return
        api = self._api
        if api is None:
            import ctypes

            api = ctypes.windll.kernel32
            api.CloseHandle.argtypes = (ctypes.c_void_p,)
        api.CloseHandle(self._handle)
        self._handle = None

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def run_single_instance(
    callback: Callable[[], int | None],
    *,
    lock: SingleInstanceLock | None = None,
) -> tuple[bool, int]:
    active_lock = lock or SingleInstanceLock()
    if not active_lock.acquire():
        active_lock.close()
        return False, 2
    try:
        result = callback()
        return True, int(result or 0)
    finally:
        active_lock.close()
