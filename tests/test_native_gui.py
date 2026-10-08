"""Opt-in Windows desktop smoke test; only synthetic documents and captions."""
import os
import time
from dataclasses import replace

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("YIDA_GUI_TEST") != "1", reason="requires interactive Windows desktop"
)


def test_native_drag_target_and_translation_card(tmp_path, monkeypatch):
    from tkinterdnd2 import TkinterDnD

    from yida_ai.config import SettingsStore
    from yida_ai.core.models import CaptionEvent, EvidenceStatus, ReplySuggestion
    from yida_ai.ui import app as ui

    monkeypatch.setattr(ui, "check_speech_components", lambda: [])
    errors = []
    monkeypatch.setattr(ui.messagebox, "showerror", lambda *args: errors.append(args))
    store = SettingsStore(tmp_path / "data")
    settings = store.load()
    settings.caption_source.kind = "mock"
    settings.llm.provider = "mock"
    store.save(settings)
    root = TkinterDnD.Tk()
    app = ui.YidaApp(root, store)
    try:
        root.update()
        assert len(app.notebook.tabs()) == 2
        assert app.diagnostics_tab.master is not app.notebook
        assert not app.confirm_button.winfo_manager()
        assert not app.start_all_button.winfo_ismapped()
        assert app.knowledge_list.dnd_bind("<<Drop>>")
        source = tmp_path / "sample document.txt"
        source.write_text("Our opening time is nine o'clock.", encoding="utf-8")
        # Exercise the drop callback's batch-import path, not a simulated OS drag.
        app.import_paths(root.tk.splitlist(root.tk.call("list", str(source))))
        deadline = time.monotonic() + 5
        while app._importing and time.monotonic() < deadline:
            root.update()
            time.sleep(.02)
        assert not app._importing
        assert not errors
        assert len(app.runtime.knowledge_library.list_documents()) == 1
        event = CaptionEvent(source_text="When do you open?", source_language="en-US",
                             translated_language="zh-CN")
        app._show_caption(event)
        count = len(app.pending_cards)
        app._show_caption(replace(event, translated_text="九点开门。", revision_of=event.event_id))
        assert len(app.pending_cards) == count
        assert app.pending_cards[event.event_id]["translation"].get() == "九点开门。"
        app._show_suggestion(
            event,
            ReplySuggestion(
                request_id="request-1",
                event_id=event.event_id,
                current_question="隐藏字段仍然保留",
                suggested_reply="我们九点开门。",
                translated_reply="We open at nine.",
                evidence_status=EvidenceStatus.NOT_FOUND,
            ),
        )
        assert "当前问题" not in app.pending_cards[event.event_id]["explanation"].get()
        assert "建议回答" in app.pending_cards[event.event_id]["explanation"].get()
        ordered_events = [
            CaptionEvent(event_id=f"order-{index}", source_text=f"Sentence {index}")
            for index in range(3)
        ]
        for ordered_event in ordered_events:
            app._show_caption(ordered_event)
        assert app._card_order[-3:] == [item.event_id for item in ordered_events]
        assert app.pending_cards[app._card_order[-1]]["original"].get() == "Sentence 2"
        for index in range(205):
            app._show_caption(CaptionEvent(event_id=f"limit-{index}", source_text=f"Limit {index}"))
        assert "order-0" not in app.pending_cards
        assert "limit-204" in app.pending_cards
        root.update_idletasks()
        app.timeline.yview_moveto(0.5)
        app._update_follow_state()
        assert not app.follow_latest.get()
        before = app._new_content_count
        app._show_caption(CaptionEvent(source_text="A late translation"))
        assert app._new_content_count > before
        app._return_to_latest()
        assert app.follow_latest.get()
        assert app._new_content_count == 0
        assert app.timeline.yview()[0] <= .02
    finally:
        app.close()
