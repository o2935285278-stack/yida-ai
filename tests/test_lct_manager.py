from pathlib import Path

from yida_ai.components import (
    LctComponentManager,
    LctComponentState,
    RunningProcess,
)


class FakeProcess:
    def __init__(self, pid=4321):
        self.pid = pid
        self.return_code = None

    def poll(self):
        return self.return_code


class FakeWindows:
    def __init__(self):
        self.hidden = []
        self.shown = []
        self.closed = []

    def hide(self, pid):
        self.hidden.append(pid)
        return True

    def show(self, pid):
        self.shown.append(pid)
        return True

    def request_close(self, pid):
        self.closed.append(pid)
        return True


def _bundled_executable(tmp_path: Path) -> Path:
    path = tmp_path / "components" / "LiveCaptionsTranslator" / "LiveCaptions Translator.exe"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"fixture")
    return path


def test_finds_bundled_lct_without_starting(tmp_path):
    executable = _bundled_executable(tmp_path)
    manager = LctComponentManager(base_directory=tmp_path, process_probe=lambda: ())
    assert manager.status().state is LctComponentState.FOUND
    assert manager.status().executable_path == executable


def test_external_lct_is_reused_and_never_closed(tmp_path):
    _bundled_executable(tmp_path)
    external = tmp_path / "external" / "LiveCaptions Translator.exe"
    windows = FakeWindows()
    launches = []
    manager = LctComponentManager(
        base_directory=tmp_path,
        process_probe=lambda: (RunningProcess(100, executable_path=external),),
        launcher=lambda path: launches.append(path),
        window_controller=windows,
    )
    status = manager.ensure_running()
    manager.close()
    assert status.state is LctComponentState.EXTERNAL_RUNNING
    assert status.executable_path == external
    assert launches == []
    assert windows.closed == []


def test_starts_bundled_lct_once_and_hides_it(tmp_path):
    executable = _bundled_executable(tmp_path)
    process = FakeProcess()
    launches = []
    windows = FakeWindows()

    def launch(path):
        launches.append(path)
        return process

    manager = LctComponentManager(
        base_directory=tmp_path,
        process_probe=lambda: (),
        launcher=launch,
        window_controller=windows,
    )
    first = manager.ensure_running()
    second = manager.refresh()
    assert first.state is LctComponentState.BUNDLED_RUNNING
    assert second.owned
    assert launches == [executable]
    assert windows.hidden == [process.pid, process.pid]


def test_start_failure_is_nonfatal(tmp_path):
    _bundled_executable(tmp_path)

    def fail(_path):
        raise OSError("blocked")

    attempts = []

    def tracked_fail(path):
        attempts.append(path)
        fail(path)

    manager = LctComponentManager(
        base_directory=tmp_path,
        process_probe=lambda: (),
        launcher=tracked_fail,
        window_controller=FakeWindows(),
    )
    status = manager.ensure_running()
    manager.refresh()
    assert status.state is LctComponentState.FAILED
    assert "blocked" in status.detail
    assert len(attempts) == 1

    manager.retry_start()
    assert len(attempts) == 2


def test_no_start_lct_never_launches(tmp_path):
    _bundled_executable(tmp_path)
    launches = []
    manager = LctComponentManager(
        base_directory=tmp_path,
        no_start=True,
        process_probe=lambda: (),
        launcher=lambda path: launches.append(path),
    )
    assert manager.ensure_running().state is LctComponentState.DISABLED
    assert launches == []


def test_open_settings_and_safe_owned_close(tmp_path):
    _bundled_executable(tmp_path)
    process = FakeProcess()
    windows = FakeWindows()
    manager = LctComponentManager(
        base_directory=tmp_path,
        process_probe=lambda: (),
        launcher=lambda _path: process,
        window_controller=windows,
    )
    manager.ensure_running()
    status = manager.open_settings()
    manager.close()
    assert status.pid == process.pid
    assert windows.shown == [process.pid]
    assert windows.closed == [process.pid]


def test_external_settings_can_return_to_background_without_closing(tmp_path):
    _bundled_executable(tmp_path)
    windows = FakeWindows()
    manager = LctComponentManager(
        base_directory=tmp_path,
        process_probe=lambda: (RunningProcess(100),),
        window_controller=windows,
    )
    manager.open_settings()
    status = manager.return_to_background()
    manager.return_to_background()
    manager.close()
    assert status.pid == 100
    assert windows.shown == [100]
    assert windows.hidden == [100, 100]
    assert windows.closed == []
