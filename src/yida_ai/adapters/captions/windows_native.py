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
        self._epoch = 0
        self._connected = False
        self._detail = "connecting"
        self._last = None
        self._factory = reader_factory
        self._thread = threading.Thread(target=self._run, name="yida-captions", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        segments = SnapshotSegments()
        outage = False
        while not self._stop.is_set():
            reader = None
            try:
                reader = self._factory()
                self._connected = True
                self._detail = "waiting-audio"
                if outage:
                    self._epoch += 1
                    outage = False
                    segments = SnapshotSegments(segments.settle, segments.max_wait)
                while not self._stop.is_set():
                    try:
                        text = segments.accept(reader.read(), time.monotonic())
                        self._ready = True
                        self._connected = True
                        self._detail = "receiving" if text else "waiting-audio"
                        self._error = ""
                        if text:
                            event = CaptionEvent(
                                source_text=text, source_language=self.source_language,
                                translated_language=self.translated_language,
                                source="windows-captions",
                                metadata={"epoch": self._epoch},
                            )
                            self._enqueue(event)
                            self._last = event.occurred_at
                    except Exception as exc:
                        self._error = type(exc).__name__
                        self._connected = False
                        self._detail = "reconnecting"
                        if not outage:
                            self._epoch += 1
                            outage = True
                        break
                    self._stop.wait(0.15)
            except Exception as exc:
                self._error = type(exc).__name__
                self._connected = False
                self._detail = "reconnecting"
                if not outage:
                    self._epoch += 1
                    outage = True
            finally:
                if reader is not None:
                    try:
                        reader.close()
                    except Exception:
                        pass
            if not self._stop.is_set():
                self._stop.wait(0.5)

    def _enqueue(self, event: CaptionEvent) -> None:
        try:
            self._events.put_nowait(event)
        except queue.Full:
            try:
                self._events.get_nowait()
            except queue.Empty:
                pass
            self._events.put_nowait(event)

    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        result = []
        for _ in range(limit):
            try:
                result.append(self._events.get_nowait())
            except queue.Empty:
                break
        return result

    @property
    def epoch(self) -> int:
        return self._epoch

    def status(self) -> CaptionSourceStatus:
        return CaptionSourceStatus(
            self._connected,
            "Windows Live Captions",
            self._detail,
            CaptionActivityState.ERROR if self._error and not self._connected else (
                CaptionActivityState.RECEIVING if self._last else CaptionActivityState.WAITING_AUDIO
            ), process_running=self._connected, live=bool(self._last), last_caption_at=self._last,
        )

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=0.5)
