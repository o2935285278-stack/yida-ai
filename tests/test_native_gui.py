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
    from yida_ai.core.models import CaptionEvent
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
    finally:
        app.close()
