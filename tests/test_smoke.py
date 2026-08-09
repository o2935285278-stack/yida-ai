from yida_ai.__main__ import main
from yida_ai.config.settings import AdapterSettings, AppSettings, SettingsStore
from yida_ai.ui.app import YidaApp


def test_windows_style_headless_start_and_clean_exit(tmp_path):
    fixture = tmp_path / "captions.jsonl"
    fixture.write_text(
        '{"event_id":"smoke","source_text":"Hello?","translated_text":"你好？"}\n',
        encoding="utf-8",
    )
    assert (
        main(["--headless-demo", "--mock", str(fixture), "--data-dir", str(tmp_path / "data")]) == 0
    )


def test_gui_window_starts_and_closes_cleanly(tmp_path):
    from tkinter import Tk

    store = SettingsStore(tmp_path / "config.json", tmp_path)
    store.save(AppSettings(adapter=AdapterSettings(kind="mock")))
    root = Tk()
    root.withdraw()
    app = YidaApp(root, store)
    root.update_idletasks()
    app.close()
    assert app._closed
