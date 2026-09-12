from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

from yida_ai.adapters.captions.base import (
    CaptionActivityState,
    CaptionSource,
    CaptionSourceStatus,
    CaptionSourceUnavailable,
)
from yida_ai.core.models import CaptionEvent


class WindowsTextReader:
    """UI Automation stays on its owning worker thread; no helper process."""

    def __init__(self) -> None:
        import comtypes
        import comtypes.client

        comtypes.CoInitialize()
        self._com = comtypes
        module = comtypes.client.GetModule("UIAutomationCore.dll")
        self.automation = comtypes.client.CreateObject(
            module.CUIAutomation, interface=module.IUIAutomation
        )

    @staticmethod
    def window_handle():
        import ctypes
        from ctypes import wintypes

        find = ctypes.windll.user32.FindWindowW
        find.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        find.restype = wintypes.HWND
        return find("LiveCaptionsDesktopWindow", None)

    def read(self) -> str:
        # Match the system caption window, never enumerate other apps' text.
        hwnd = self.window_handle()
        if not hwnd:
            raise CaptionSourceUnavailable("Windows Live Captions is not running")
        root = self.automation.ElementFromHandle(hwnd)
        # Windows 11 exposes the live text under this stable automation id.
        condition = self.automation.CreatePropertyCondition(30011, "CaptionsTextBlock")
        element = root.FindFirst(4, condition)
        if not element:
            ready = root.FindFirst(
                4, self.automation.CreatePropertyCondition(30011, "ReadyToCaptionTextBlock")
            )
            if ready:
                return ""
            raise CaptionSourceUnavailable("Windows caption text control is unavailable")
        return element.CurrentName or ""

    def close(self) -> None:
        self.automation = None
        self._com.CoUninitialize()


class SnapshotSegments:
    """Emit stable text once, retaining the rolling window overlap."""

    def __init__(self, settle: float = 0.45, max_wait: float = 2.0) -> None:
        self.settle = settle
        self.max_wait = max_wait
        self.previous = ""
        self.committed = ""
        self.changed_at = 0.0
        self.started_at = 0.0

    def accept(self, text: str, now: float) -> str:
        text = " ".join(text.split())
        if text != self.previous:
            if not self.previous:
                self.started_at = now
            self.previous = text
            self.changed_at = now
        if not text or (now - self.changed_at < self.settle
                        and now - self.started_at < self.max_wait):
            return ""
        if text == self.committed:
            return ""
        overlap = 0
        for size in range(min(len(self.committed), len(text)), 0, -1):
            if self.committed[-size:] == text[:size]:
                overlap = size
                break
        remaining = text[overlap:].strip()
        self.committed = text
        self.started_at = now
        return remaining


class WindowsCaptionSource(CaptionSource):
    def __init__(
        self, source_language: str, translated_language: str,
        reader_factory: Callable = WindowsTextReader,
    ) -> None:
        self.source_language = source_language
        self.translated_language = translated_language
        self._events: queue.Queue[CaptionEvent] = queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._error = ""
        self._ready = False
        self._last = None
        self._factory = reader_factory
        self._thread = threading.Thread(target=self._run, name="yida-captions", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        reader = None
        segments = SnapshotSegments()
        try:
            reader = self._factory()
            while not self._stop.is_set():
                try:
                    text = segments.accept(reader.read(), time.monotonic())
                    self._ready = True
                    self._error = ""
                    if text:
                        event = CaptionEvent(
                            source_text=text, source_language=self.source_language,
                            translated_language=self.translated_language,
                            source="windows-captions",
                        )
                        self._events.put(event, timeout=0.2)
                        self._last = event.occurred_at
                except Exception as exc:
                    self._error = type(exc).__name__
                self._stop.wait(0.15)
        except Exception as exc:
            self._error = type(exc).__name__
        finally:
            if reader is not None:
                reader.close()

    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        result = []
        for _ in range(limit):
            try:
                result.append(self._events.get_nowait())
            except queue.Empty:
                break
        return result

    def status(self) -> CaptionSourceStatus:
        return CaptionSourceStatus(
            self._ready and not self._error, "Windows Live Captions", self._error,
            CaptionActivityState.ERROR if self._error else (
                CaptionActivityState.RECEIVING if self._last else CaptionActivityState.WAITING_AUDIO
            ), process_running=self._ready, live=bool(self._last), last_caption_at=self._last,
        )

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=0.5)
