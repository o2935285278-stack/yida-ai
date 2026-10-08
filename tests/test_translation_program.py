import base64
import copy
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import replace

import pytest

from yida_ai.adapters.captions.mock import MockCaptionSource
from yida_ai.adapters.captions.translation_program import FeedDecoder
from yida_ai.core.captions import CaptionAssembler
from yida_ai.core.controller import ApplicationController
from yida_ai.core.conversation import ConversationManager
from yida_ai.core.engine import ReplyEngine
from yida_ai.providers.llm.mock import MockLLMProvider
from yida_ai.retrieval.keyword import KeywordRetriever


def packet(sequence=1, revision=1, text="Question?", kind="update", generation=0):
    caption = dict(sequence=sequence, revision=revision, utterance_id="one",
                   generation=generation, source_text=text, source_text_language="en-US",
                   translation_language="zh-CN")
    return {"type": kind, "gap": 0, "data": {
        "schema_version": 1, "session_id": "session", "generation": generation,
        "event_sequence": sequence, "status": "pending", "current": caption,
        "translation": None,
    }}


def test_replay_heartbeat_and_revision_identity():
    decoder = FeedDecoder()
    first = decoder.accept(packet(kind="snapshot"))[0]
    assert first.metadata["replay"]
    assert not decoder.accept(packet(kind="heartbeat"))
    next_event = decoder.accept(packet(2, 2, "New question?"))[0]
    assert not next_event.metadata["replay"]
    assert first.event_id == next_event.event_id == next_event.revision_of
    assert not decoder.accept(packet())


def test_old_translation_never_pairs_with_new_original():
    decoder = FeedDecoder()
    old = packet()
    decoder.accept(old)
    new = packet(2, 2, "Different question?")
    new["data"]["translation"] = {
        "caption": old["data"]["current"], "status": "completed", "translated_text": "旧译文"
    }
    events = decoder.accept(new)
    assert len(events) == 1
    assert events[0].translated_text == ""
    new["data"]["event_sequence"] = 3
    new["data"]["translation"]["caption"] = copy.deepcopy(new["data"]["current"])
    translated = decoder.accept(new)[0]
    assert translated.event_id == events[0].event_id
    assert translated.translated_text == "旧译文"


def test_generation_reset_discards_cached_translation():
    decoder = FeedDecoder()
    old_id = decoder.accept(packet())[0].event_id
    reset = packet(2, generation=1)
    reset["data"]["current"] = None
    assert decoder.accept(reset) == []
    assert not decoder.events
    new_id = decoder.accept(packet(3, generation=1))[0].event_id
    assert new_id != old_id


def test_unsupported_schema_is_explicit():
    bad = packet()
    bad["data"]["schema_version"] = 100
    with pytest.raises(ValueError):
        FeedDecoder().accept(bad)


def test_external_runtime_never_starts_windows_or_lct(tmp_path, monkeypatch):
    import yida_ai.application as application
    from yida_ai.config import SettingsStore
    store = SettingsStore(data_dir=tmp_path)
    settings = store.load()
    settings.caption_source.kind = "translation-program"
    store.save(settings)
    def forbidden(**kwargs):
        raise AssertionError("External input must not own system components")
    monkeypatch.setattr(application, "LctComponentManager", forbidden)
    monkeypatch.setattr(application, "WindowsCaptionManager", forbidden)
    monkeypatch.setattr(application, "TranslationProgramSource", MockCaptionSource)
    runtime = application.build_runtime(store)
    try:
        assert runtime.lct_manager is None
        assert runtime.windows_caption_manager is None
    finally:
        runtime.close()


def test_quota_errors_are_not_network_failures():
    from yida_ai.providers.llm.base import LLMErrorKind
    from yida_ai.providers.llm.openai_compatible import _http_error
    from yida_ai.ui.ai_status import AIConnectionState, state_from_error
    for code, detail in [(402, ""), (429, "insufficient_quota")]:
        error = _http_error(code, detail, "")
        assert error.kind == LLMErrorKind.QUOTA
        assert state_from_error(error.kind) == AIConnectionState.QUOTA


class Stream(MockCaptionSource):
    def __init__(self):
        super().__init__()
        self.items = []
        self.epoch = ("session", 0)

    def poll(self, limit=50):
        items, self.items = self.items, []
        return items


def setup_controller():
    source = Stream()
    engine = ReplyEngine(MockLLMProvider(), KeywordRetriever(), ConversationManager())
    return source, engine, ApplicationController(source, CaptionAssembler(), engine)


def test_snapshot_does_not_answer_but_live_change_waits_for_stability():
    source, engine, controller = setup_controller()
    calls = []
    original_submit = engine.submit
    engine.submit = lambda event, **kw: calls.append(event)  # deterministic scheduling check
    try:
        decoder = FeedDecoder()
        source.items = decoder.accept(packet(kind="snapshot"))
        controller.tick(now=0)
        controller.tick(now=3)
        assert calls == []
        source.items = decoder.accept(packet(2, 2, "Updated question?"))
        controller.tick(now=4)
        controller.tick(now=4.5)
        assert calls == []
        controller.tick(now=4.8)
        assert len(calls) == 1
        assert len(engine.conversation.turns) == 1
        controller.tick(now=8)
        assert len(calls) == 1
    finally:
        engine.submit = original_submit
        controller.close()


def test_translation_completion_does_not_trigger_duplicate_reply():
    source, engine, controller = setup_controller()
    calls = []
    engine.submit = lambda event, **kw: calls.append(event)
    try:
        event = FeedDecoder().accept(packet())[0]
        source.items = [event]
        controller.tick(now=0)
        source.items = [replace(event, translated_text="问题？", revision_of=event.event_id)]
        controller.tick(now=.2)
        controller.tick(now=.8)
        assert len(calls) == 1
        assert calls[0].translated_text == "问题？"
    finally:
        controller.close()


def test_old_epoch_event_is_discarded_after_reconnect():
    source, engine, controller = setup_controller()
    try:
        decoder = FeedDecoder()
        source.items = decoder.accept(packet())
        controller.tick(now=0)
        assert len(engine.conversation.turns) == 1
        source.epoch = ("session", 1)
        stale = decoder.accept(packet(2, 2, "Stale after reconnect?"))[0]
        source.items = [stale]
        controller.tick(now=1)
        assert len(engine.conversation.turns) == 0
    finally:
        controller.close()


def test_manual_reply_cancels_scheduled_automatic_reply():
    source, engine, controller = setup_controller()
    calls = []
    engine.submit = lambda event, **kw: calls.append(event)
    try:
        event = FeedDecoder().accept(packet())[0]
        source.items = [event]
        controller.tick(now=0)
        controller.confirm(event.event_id)
        controller.tick(now=2)
        assert len(calls) == 1
    finally:
        controller.close()


def test_late_reply_is_discarded_after_source_revision():
    source, engine, controller = setup_controller()
    try:
        event = FeedDecoder().accept(packet())[0]
        engine.submit(event)
        engine.invalidate_event(event.event_id)
        time.sleep(.1)
        assert engine.drain_results() == []
    finally:
        controller.close()


def test_obsolete_slow_request_does_not_hold_new_reply():
    gate, started = threading.Event(), threading.Event()
    class Provider(MockLLMProvider):
        def generate(self, request):
            if request.event.source_text == "Question?":
                started.set()
                gate.wait(3)
            return super().generate(request)
    engine = ReplyEngine(Provider(), KeywordRetriever(), ConversationManager())
    try:
        event = FeedDecoder().accept(packet())[0]
        engine.submit(event)
        assert started.wait(1)
        engine.invalidate_event(event.event_id)
        engine.submit(replace(event, source_text="New question?"), record_event=False)
        deadline = time.monotonic() + 1
        results = []
        while time.monotonic() < deadline and not results:
            results.extend(engine.drain_results())
            time.sleep(.01)
        assert len(results) == 1
        assert results[0].request.event.source_text == "New question?"
    finally:
        gate.set()
        engine.shutdown()


def test_document_index_reuses_only_unchanged_files(tmp_path, monkeypatch):
    import yida_ai.retrieval.keyword as module
    real = module.load_chunks
    parsed = []
    monkeypatch.setattr(module, "load_chunks", lambda p: (parsed.append(p.name), real(p))[1])
    document = tmp_path / "sample.txt"
    document.write_text("Sample public text", encoding="utf-8")
    retriever = KeywordRetriever()
    retriever.index_directory(tmp_path)
    retriever.index_directory(tmp_path)
    assert parsed == ["sample.txt"]
    document.write_text("Updated sample public text", encoding="utf-8")
    retriever.index_directory(tmp_path)
    assert parsed == ["sample.txt", "sample.txt"]
    document.unlink()
    retriever.index_directory(tmp_path)
    assert not retriever.chunks


@pytest.mark.skipif(os.name != "nt" or not shutil.which("pwsh"), reason="Windows pipe test")
def test_windows_pipe_handshake_and_reconnect():
    from yida_ai.adapters.captions.translation_program import TranslationProgramSource
    name = "YidaSyntheticTest." + uuid.uuid4().hex
    first = base64.b64encode(json.dumps(packet(kind="snapshot")).encode()).decode()
    second = base64.b64encode(json.dumps(packet(2, 2, "After reconnect?",
                                                kind="snapshot")).encode()).decode()
    script = f"""
    $ErrorActionPreference='Stop'
    foreach($payload in @('{first}','{second}')) {{
      $pipe=[IO.Pipes.NamedPipeServerStream]::new('{name}',[IO.Pipes.PipeDirection]::InOut,1,
        [IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::CurrentUserOnly)
      try {{
        $pipe.WaitForConnection()
        $reader=[IO.StreamReader]::new($pipe)
        $writer=[IO.StreamWriter]::new($pipe,[Text.UTF8Encoding]::new($false),1024,$true)
        $writer.AutoFlush=$true
        $hello=$reader.ReadLine()|ConvertFrom-Json
        if($hello.type -ne 'subscribe') {{throw 'Invalid handshake'}}
        $writer.WriteLine([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload)))
        Start-Sleep -Milliseconds 400
      }} finally {{$pipe.Dispose()}}
    }}
    """
    process = subprocess.Popen([shutil.which("pwsh"), "-NoProfile", "-Command", script],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    source = TranslationProgramSource(pipe_path="\\\\.\\pipe\\" + name)
    try:
        events = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and len(events) < 2:
            events.extend(source.poll())
            time.sleep(.05)
        assert [e.source_text for e in events] == ["Question?", "After reconnect?"]
        assert all(e.metadata["replay"] for e in events)
        assert events[0].event_id == events[1].event_id
    finally:
        source.close()
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=3)
