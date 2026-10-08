"""Read-only client for TranslationProgram IPC v1. No keys or process ownership."""
from __future__ import annotations

import csv
import ctypes
import io
import json
import os
import subprocess
import threading
import time
from collections import OrderedDict
from dataclasses import replace

from yida_ai.adapters.captions.base import CaptionActivityState, CaptionSource, CaptionSourceStatus
from yida_ai.core.models import CaptionEvent


class FeedDecoder:
    def __init__(self):
        self.epoch = None
        self.sequence = -1
        self.events: OrderedDict[str, CaptionEvent] = OrderedDict()
        self.state = "connecting"

    def accept(self, packet: dict) -> list[CaptionEvent]:
        data = packet["data"]
        if data["schema_version"] != 1 or packet["type"] not in {
            "snapshot", "update", "heartbeat"
        }:
            raise ValueError("Unsupported caption protocol")
        epoch = (str(data["session_id"]), int(data["generation"]))
        sequence = int(data["event_sequence"])
        if self.epoch != epoch:
            self.epoch, self.sequence = epoch, -1
            self.events.clear()
        if sequence <= self.sequence:
            return []
        self.sequence = sequence
        self.state = str(data["status"])
        output = []
        current = data.get("current")
        replay = packet["type"] == "snapshot"
        if current and int(current["generation"]) == epoch[1]:
            event_id = f"tp:{epoch[0]}:{epoch[1]}:{current['utterance_id']}"
            previous = self.events.get(event_id)
            revision = int(current["revision"])
            if previous is None or revision > previous.metadata["revision"]:
                event = CaptionEvent(
                    source_text=str(current["source_text"]),
                    source_language=str(current.get("source_text_language", "und")),
                    translated_language=str(current.get("translation_language", "")),
                    event_id=event_id, source="translation-program", is_final=False,
                    revision_of=event_id if previous else None,
                    metadata={"revision": revision, "replay": replay,
                              "translation_pending": True, "epoch": epoch,
                              "feed_state": self.state},
                )
                self.events[event_id] = event
                output.append(event)
            previous = self.events.get(event_id)
            if previous and self.state == "failed" and not previous.translated_text:
                failed = replace(previous, revision_of=event_id,
                                 metadata={**previous.metadata,
                                           "translation_error": "Upstream translation failed"})
                self.events[event_id] = failed
                if previous.metadata != failed.metadata:
                    output.append(failed)
        translated = data.get("translation")
        if translated and translated.get("status") == "completed":
            caption = translated["caption"]
            event_id = f"tp:{epoch[0]}:{epoch[1]}:{caption['utterance_id']}"
            previous = self.events.get(event_id)
            # Never attach a translation to a different revision of its original.
            if (previous and int(caption["generation"]) == epoch[1]
                    and int(caption["revision"]) == previous.metadata["revision"]
                    and caption["source_text"] == previous.source_text
                    and translated.get("translated_text") != previous.translated_text):
                event = replace(previous, translated_text=translated["translated_text"] or "",
                                revision_of=event_id,
                                metadata={**previous.metadata, "translation_pending": False})
                self.events[event_id] = event
                output.append(event)
        while len(self.events) > 64:
            self.events.popitem(last=False)
        return output


def current_user_pipe() -> str:
    result = subprocess.run(
        ["whoami.exe", "/user", "/fo", "csv", "/nh"], capture_output=True,
        text=True, timeout=5, check=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    row = next(csv.reader(io.StringIO(result.stdout)))
    sid = row[-1].strip()
    if not sid.startswith("S-1-") or any(c not in "S-0123456789" for c in sid):
        raise ValueError("Cannot identify current Windows account")
    return "\\\\.\\pipe\\TranslationProgram.v1." + sid


class TranslationProgramSource(CaptionSource):
    def __init__(self, *, pipe_path: str | None = None):
        self._path = pipe_path
        self.decoder = FeedDecoder()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pending: OrderedDict[str, CaptionEvent] = OrderedDict()
        self._connected = False
        self._detail = "connecting"
        self._connection_epoch = 0
        self._thread = threading.Thread(target=self._run, name="yida-caption-ipc", daemon=True)
        self._thread.start()

    @property
    def epoch(self):
        return self.decoder.epoch

    def _run(self):
        if os.name != "nt":
            self._detail = "unsupported"
            return
        import msvcrt
        from ctypes import wintypes

        peek = ctypes.windll.kernel32.PeekNamedPipe
        peek.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        peek.restype = wintypes.BOOL
        while not self._stop.is_set():
            descriptor = None
            try:
                if self._path is None:
                    self._path = current_user_pipe()
                path = self._path
                descriptor = os.open(path, os.O_RDWR | os.O_BINARY)
                handle = msvcrt.get_osfhandle(descriptor)
                os.write(descriptor, b'{"schema_version":1,"type":"subscribe"}\n')
                buffer = b""
                last_packet = time.monotonic()
                while not self._stop.wait(.05):
                    available = wintypes.DWORD()
                    if not peek(handle, None, 0, None, ctypes.byref(available), None):
                        raise OSError("Disconnected")
                    if available.value:
                        buffer += os.read(descriptor, min(available.value, 65536))
                    if len(buffer) > 1024 * 1024:
                        raise ValueError("Caption frame exceeds size limit")
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        packet = json.loads(line)
                        with self._lock:
                            old_epoch = self.decoder.epoch
                            events = self.decoder.accept(packet)
                            if old_epoch != self.decoder.epoch:
                                self._pending.clear()
                            for event in events:
                                self._pending[event.event_id] = event
                            while len(self._pending) > 64:
                                self._pending.popitem(last=False)
                        self._connected = True
                        self._detail = self.decoder.state
                        last_packet = time.monotonic()
                    if time.monotonic() - last_packet > 5:
                        raise TimeoutError("Caption heartbeat timed out")
            except (OSError, ValueError, KeyError, TypeError, AttributeError,
                    subprocess.SubprocessError):
                self._connected = False
                self._detail = "reconnecting"
                self._connection_epoch += 1
            finally:
                if descriptor is not None:
                    os.close(descriptor)
            self._stop.wait(1)

    def poll(self, limit=50):
        with self._lock:
            return [self._pending.popitem(last=False)[1]
                    for _ in range(min(limit, len(self._pending)))]

    def status(self):
        return CaptionSourceStatus(
            self._connected, "TranslationProgram", self._detail,
            CaptionActivityState.RECEIVING if self._connected else CaptionActivityState.ERROR,
            process_running=self._connected, live=self._connected,
        )

    @property
    def connection_epoch(self) -> int:
        return self._connection_epoch

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
