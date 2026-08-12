import gc
import time

from yida_ai.__main__ import build_parser, main
from yida_ai.components import LctComponentState, LctComponentStatus
from yida_ai.config.settings import AppSettings, CaptionSourceSettings, SettingsStore
from yida_ai.ui.app import YidaApp
from yida_ai.ui.onboarding import OnboardingStep, OnboardingWizard


def _create_tk_with_retry():
    """Retry only Tcl runtime initialization; application assertions remain strict."""
    from tkinter import TclError, Tk

    last_error = None
    for _ in range(3):
        try:
            return Tk()
        except TclError as exc:
            last_error = exc
            gc.collect()
            time.sleep(0.05)
    raise last_error


class StubLctManager:
    def __init__(self):
        self.opened = False
        self.redetected = False
        self.closed = False
        self.backgrounded = False

    def open_settings(self):
        self.opened = True
        return LctComponentStatus(
            LctComponentState.EXTERNAL_RUNNING,
            "LiveCaptions Translator 设置已打开",
            pid=99,
        )

    def refresh(self):
        return LctComponentStatus(
            LctComponentState.EXTERNAL_RUNNING,
            "正在使用用户已运行的 LiveCaptions Translator",
            pid=99,
        )

    def retry_start(self):
        self.redetected = True
        return self.refresh()

    def return_to_background(self):
        self.backgrounded = True
        return LctComponentStatus(
            LctComponentState.EXTERNAL_RUNNING,
            "LiveCaptions Translator 已收回后台",
            pid=99,
        )

    def close(self):
        self.closed = True


def test_windows_style_headless_start_and_clean_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "yida_ai.application.LctComponentManager",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("headless started LCT")),
    )
    fixture = tmp_path / "captions.jsonl"
    fixture.write_text(
        '{"event_id":"smoke","source_text":"Hello?","translated_text":"你好？"}\n',
        encoding="utf-8",
    )
    assert (
        main(["--headless-demo", "--mock", str(fixture), "--data-dir", str(tmp_path / "data")]) == 0
    )


def test_no_start_lct_argument_is_available():
    assert build_parser().parse_args(["--no-start-lct"]).no_start_lct


def test_gui_window_starts_and_closes_cleanly(tmp_path, monkeypatch):
    from tkinter import messagebox

    store = SettingsStore(tmp_path / "config.json", tmp_path)
    store.save(
        AppSettings(
            interface_language="en-US",
            caption_source=CaptionSourceSettings(kind="mock"),
        )
    )
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr("yida_ai.ui.app.check_speech_components", lambda: ())
    monkeypatch.setattr("yida_ai.ui.app.detect_live_captions_language", lambda: "pt-BR")
    monkeypatch.setattr(
        "yida_ai.application.LctComponentManager",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("mock GUI started LCT")),
    )
    root = _create_tk_with_retry()
    root.withdraw()
    wizard_store = SettingsStore(tmp_path / "wizard-config.json", tmp_path / "wizard-data")
    wizard = OnboardingWizard(root, wizard_store, lambda *_managers: None, no_start_lct=True)
    assert wizard.flow.step is OnboardingStep.INTERFACE
    assert wizard.windows_manager is None
    assert wizard.lct_manager is None
    wizard._select_interface("pt-BR")
    assert wizard.flow.step is OnboardingStep.SPEECH
    assert wizard.locale == "pt-BR"
    assert wizard.windows_manager is None
    assert wizard.lct_manager is None
    wizard.shell.destroy()
    app = YidaApp(root, store)
    root.update_idletasks()
    assert app.notebook.tab(app.main_tab, "text") == "Live conversation"
    assert app.scene.get() == "General conversation"
    assert app.reply_mode.get() == "Reply to every utterance"
    assert app.reply_length.get() == "Short"
    app.scene.set("brazilian_customer")
    app._apply_scene_language_preset()
    assert (
        app.speech_language.get(),
        app.translation_language.get(),
        app.reply_language.get(),
    ) == (
        "pt-BR",
        "zh-CN",
        "pt-BR",
    )
    switched = []
    monkeypatch.setattr(app, "apply_settings", lambda: switched.append(True))
    app.quick_speech_language.set("en-US")
    app.quick_switch_speech_language()
    assert app.speech_language.get() == "en-US"
    assert switched == [True]
    app.test_ai_connection()
    deadline = time.monotonic() + 2
    while "success" not in app.bottom_status.get().casefold() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    assert "success" in app.bottom_status.get().casefold()
    manager = StubLctManager()
    app.runtime.lct_manager = manager
    app.open_lct_settings()
    app.return_lct_to_background()
    app.redetect_caption_source()
    assert manager.opened
    assert manager.backgrounded
    assert manager.redetected
    app.close()
    assert app._closed
    assert manager.closed


def test_main_controls_fit_at_125_and_150_percent_tk_scaling(tmp_path, monkeypatch):
    from tkinter import messagebox

    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr("yida_ai.ui.app.check_speech_components", lambda: ())
    for suffix, scale, locale in (
        ("125", 1.6666667, "en-US"),
        ("150", 2.0, "pt-BR"),
    ):
        store = SettingsStore(data_dir=tmp_path / suffix)
        settings = AppSettings(
            onboarding_completed=True,
            interface_language=locale,
            caption_source=CaptionSourceSettings(kind="mock"),
        )
        settings.llm.provider = "mock"
        store.save(settings)
        root = _create_tk_with_retry()
        root.withdraw()
        root.tk.call("tk", "scaling", scale)
        app = YidaApp(root, store)
        root.geometry("1240x900")
        root.update_idletasks()
        assert max(child.winfo_reqwidth() for child in app.main_tab.winfo_children()) <= 1240
        app.close()


def test_portuguese_ui_resource_and_long_text_timeline():
    from yida_ai.config.i18n import reply_length_name, reply_mode_name, scene_name, tr

    class FakeTimeline:
        def __init__(self):
            self.content = ""

        def configure(self, **kwargs):
            pass

        def insert(self, _position, text, _tag):
            self.content += text

        def see(self, _position):
            pass

    app = object.__new__(YidaApp)
    app.timeline = FakeTimeline()
    text = (
        "Gostaria de entender detalhadamente como o produto protege os meus dados "
        "e se vocês podem explicar as condições sem omitir informações importantes."
    ) * 4
    app._write_timeline(text)
    assert tr("pt-BR", "main_tab") == "Conversa em tempo real"
    assert scene_name("pt-BR", "brazilian_customer") == "Cliente brasileiro"
    assert reply_mode_name("pt-BR", "every") == "Responder a cada fala"
    assert reply_length_name("pt-BR", "short") == "Curta"
    assert text in app.timeline.content
