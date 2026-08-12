from yida_ai.system.speech_languages import (
    SpeechComponentState,
    caption_language_warning,
    check_speech_components,
    detect_live_captions_language,
)
from yida_ai.system.windows_captions import (
    WindowsCaptionManager,
    WindowsCaptionProcess,
    WindowsCaptionState,
    find_windows_caption_processes,
    open_live_captions_model_flow,
)


class FakeWindows:
    def __init__(self, visible=True):
        self.visible = visible
        self.hidden = []
        self.shown = []
        self.closed = []

    def hide(self, pid):
        self.hidden.append(pid)
        self.visible = False
        return True

    def show(self, pid):
        self.shown.append(pid)
        self.visible = True
        return True

    def is_visible(self, pid):
        return self.visible

    def request_close(self, pid):
        self.closed.append(pid)
        return True


def test_existing_windows_captions_is_hidden_then_restored(monkeypatch):
    monkeypatch.setattr("yida_ai.system.windows_captions._is_supported_windows", lambda: True)
    windows = FakeWindows()
    manager = WindowsCaptionManager(
        auto_start=False,
        process_probe=lambda: (WindowsCaptionProcess(100),),
        window_controller=windows,
    )
    status = manager.hide_window()
    assert status.state is WindowsCaptionState.HIDDEN
    assert status.running
    manager.close()
    assert windows.shown[-1] == 100
    assert windows.closed == []


def test_started_windows_captions_is_owned_and_only_owned_process_closes(monkeypatch):
    monkeypatch.setattr("yida_ai.system.windows_captions._is_supported_windows", lambda: True)
    processes = []
    windows = FakeWindows()

    def start():
        processes.append(WindowsCaptionProcess(200))

    manager = WindowsCaptionManager(
        process_probe=lambda: tuple(processes),
        starter=start,
        window_controller=windows,
    )
    status = manager.ensure_running()
    assert status.owned
    assert manager.owned_pids == {200}
    manager.close()
    assert windows.closed == [200]


def test_auto_start_attempts_only_once_until_explicit_retry(monkeypatch):
    monkeypatch.setattr("yida_ai.system.windows_captions._is_supported_windows", lambda: True)
    starts = []
    now = [10.0]
    manager = WindowsCaptionManager(
        process_probe=lambda: (),
        starter=lambda: starts.append(now[0]),
        window_controller=FakeWindows(),
        clock=lambda: now[0],
        start_timeout_seconds=12,
    )
    assert manager.ensure_running().state is WindowsCaptionState.STARTING
    for _ in range(5):
        manager.refresh()
    assert starts == [10.0]
    now[0] = 23.0
    assert manager.refresh().state is WindowsCaptionState.FAILED
    manager.refresh()
    assert starts == [10.0]
    assert manager.retry_start().state is WindowsCaptionState.STARTING
    assert starts == [10.0, 23.0]


def test_manual_close_is_not_automatically_reopened(monkeypatch):
    monkeypatch.setattr("yida_ai.system.windows_captions._is_supported_windows", lambda: True)
    processes = [WindowsCaptionProcess(100)]
    starts = []
    manager = WindowsCaptionManager(
        process_probe=lambda: tuple(processes),
        starter=lambda: starts.append(True),
        window_controller=FakeWindows(),
    )
    assert manager.ensure_running().running
    processes.clear()
    assert manager.refresh().state is WindowsCaptionState.USER_STOPPED
    assert manager.refresh().state is WindowsCaptionState.USER_STOPPED
    assert starts == []


def test_three_speech_components_detect_installed_and_missing():
    statuses = check_speech_components(
        "\n".join(
            [
                "MicrosoftWindows.Speech.zh-CN.1",
                "MicrosoftWindows.Speech.en-US.1",
            ]
        )
    )
    states = {item.language: item.state for item in statuses}
    assert states == {
        "zh-CN": SpeechComponentState.INSTALLED,
        "en-US": SpeechComponentState.INSTALLED,
        "pt-BR": SpeechComponentState.MISSING,
    }


def test_live_caption_language_detection_and_mismatch_warning():
    detected = detect_live_captions_language("Pronto para legendar em Português (Brasil)")
    assert detected == "pt-BR"
    assert caption_language_warning("pt-BR", detected) == ""
    assert "不一致" in caption_language_warning("en-US", detected)
    assert "确认" in caption_language_warning("zh-CN", None)


def test_process_probe_parses_tasklist_csv_and_ignores_bad_rows(monkeypatch):
    import subprocess

    monkeypatch.setattr("yida_ai.system.windows_captions.os.name", "nt")
    monkeypatch.setattr(
        "yida_ai.system.windows_captions.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            0,
            '"LiveCaptions.exe","123","Console","1","10,000 K"\n'
            '"LiveCaptions.exe","bad","Console","1","10,000 K"\n'
            '"Other.exe","999","Console","1","10,000 K"',
            "",
        ),
    )
    assert find_windows_caption_processes()[0].pid == 123


def test_process_probe_failure_and_unsupported_platform(monkeypatch):
    import subprocess

    monkeypatch.setattr("yida_ai.system.windows_captions.os.name", "nt")
    monkeypatch.setattr(
        "yida_ai.system.windows_captions.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "blocked"),
    )
    assert find_windows_caption_processes() == ()
    monkeypatch.setattr("yida_ai.system.windows_captions._is_supported_windows", lambda: False)
    manager = WindowsCaptionManager(process_probe=lambda: (), window_controller=FakeWindows())
    assert manager.ensure_running().state is WindowsCaptionState.UNSUPPORTED


def test_no_auto_start_and_failed_hide_are_truthful(monkeypatch):
    monkeypatch.setattr("yida_ai.system.windows_captions._is_supported_windows", lambda: True)
    stopped = WindowsCaptionManager(
        auto_start=False,
        process_probe=lambda: (),
        window_controller=FakeWindows(),
    )
    assert stopped.ensure_running().state is WindowsCaptionState.STOPPED

    class FailingWindows(FakeWindows):
        def hide(self, pid):
            self.hidden.append(pid)
            return False

    controller = FailingWindows()
    failed = WindowsCaptionManager(
        process_probe=lambda: (WindowsCaptionProcess(50),),
        window_controller=controller,
    ).hide_window()
    assert failed.state is WindowsCaptionState.FAILED
    assert controller.shown == [50]


def test_model_flow_delegates_to_caption_starter(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "yida_ai.system.windows_captions._start_windows_captions", lambda: calls.append(True)
    )
    open_live_captions_model_flow()
    assert calls == [True]
