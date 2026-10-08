from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from yida_ai.adapters.captions.base import CaptionSource
from yida_ai.core.models import CaptionEvent


class TranslatedCaptionSource(CaptionSource):
    """Return originals immediately and revise the same event after translation."""

    def __init__(self, source: CaptionSource, translator) -> None:
        self.source = source
        self.translator = translator
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yida-translation")
        # Keep enough completed revisions to absorb a burst without dropping
        # independent sentences.  Once this bound is reached, new captions
        # receive an explicit queue-full status instead of disappearing.
        self._results: queue.Queue[CaptionEvent] = queue.Queue(maxsize=512)
        self._pending = 0
        self._max_pending = 512
        self._closed = False

    def status(self):
        return self.source.status()

    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        result = []
        for event in self.source.poll(limit):
            if self._pending >= self._max_pending:
                result.append(replace(
                    event, metadata={**event.metadata, "translation_error": "queue-full"}
                ))
                continue
            result.append(replace(
                event, metadata={**event.metadata, "translation_pending": True}
            ))
            self._pending += 1
            self._pool.submit(self._translate, event)
        for _ in range(limit):
            try:
                event = self._results.get_nowait()
            except queue.Empty:
                break
            self._pending -= 1
            result.append(event)
        return result

    def _translate(self, event: CaptionEvent) -> None:
        try:
            text = self.translator.translate_text(
                event.source_text, event.source_language, event.translated_language
            )
            update = replace(event, translated_text=text, revision_of=event.event_id)
        except Exception as exc:
            update = replace(
                event, revision_of=event.event_id,
                metadata={**event.metadata, "translation_error": str(exc)},
            )
        if not self._closed:
            # The pending bound and result bound are equal, so a full result
            # queue means the caller has not polled promptly.  Retain the
            # completed event until the next poll instead of replacing an
            # unrelated completed sentence.
            self._results.put(update)

    def close(self) -> None:
        self._closed = True
        self.source.close()
        self._pool.shutdown(wait=False, cancel_futures=True)
