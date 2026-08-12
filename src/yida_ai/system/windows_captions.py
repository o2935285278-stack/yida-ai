from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

WINDOWS_CAPTION_IMAGE = "LiveCaptions.exe"


class WindowsCaptionState(StrEnum):
    UNSUPPORTED = "unsupported"
    STOPPED = "stopped"
    STARTING = "starting"
    WAITING_COMPONENT = "waiting-component"
    RUNNING = "running"
    HIDDEN = "hidden"
    FAILED = "failed"
    USER_STOPPED = "user-stopped"


@dataclass(frozen=True, slots=True)
class WindowsCaptionProcess:
    pid: int


@dataclass(frozen=True, slots=True)
class WindowsCaptionStatus:
    supported: bool
    running: bool
    detail: str
    state: WindowsCaptionState = WindowsCaptionState.STOPPED
    pid: int | None = None
    owned: bool = False
    visible: bool | None = None


class CaptionWindowController(Protocol):
    def hide(self, pid: int) -> bool: ...

    def show(self, pid: int) -> bool: ...

    def is_visible(self, pid: int) -> bool: ...

    def request_close(self, pid: int) -> bool: ...


def find_windows_caption_processes() -> tuple[WindowsCaptionProcess, ...]:
    if os.name != "nt":
        return ()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        ["tasklist.exe", "/FI", f"IMAGENAME eq {WINDOWS_CAPTION_IMAGE}", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    if completed.returncode != 0:
        return ()
    result: list[WindowsCaptionProcess] = []
    for row in csv.reader(io.StringIO(completed.stdout)):
        if len(row) < 2 or row[0].casefold() != WINDOWS_CAPTION_IMAGE.casefold():
            continue
        try:
            result.append(WindowsCaptionProcess(int(row[1])))
        except ValueError:
            continue
    return tuple(result)


def _toggle_windows_captions_hotkey() -> None:
    if os.name != "nt":
        return
    import ctypes

    key_up = 0x0002
    vk_lwin = 0x5B
    vk_control = 0x11
    vk_l = 0x4C
    user32 = ctypes.windll.user32
    for key in (vk_lwin, vk_control, vk_l):
        user32.keybd_event(key, 0, 0, 0)
    for key in (vk_l, vk_control, vk_lwin):
        user32.keybd_event(key, 0, key_up, 0)


def _start_windows_captions() -> None:
    """Prefer the system executable; fall back to the documented keyboard shortcut."""
    if os.name != "nt":
        return
    import ctypes

    executable = os.path.join(
        os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", WINDOWS_CAPTION_IMAGE
    )
    if os.path.isfile(executable):
        result = ctypes.windll.shell32.ShellExecuteW(None, "open", executable, None, None, 1)
        if result > 32:
            return
    _toggle_windows_captions_hotkey()


class WindowsCaptionManager:
    """Manage only visibility and processes started during this Yida AI run."""

    def __init__(
        self,
        *,
        auto_start: bool = True,
        show_window: bool = True,
        process_probe: Callable[[], Sequence[WindowsCaptionProcess]] = (
            find_windows_caption_processes
        ),
        starter: Callable[[], None] = _start_windows_captions,
        window_controller: CaptionWindowController | None = None,
        clock: Callable[[], float] = time.monotonic,
        start_timeout_seconds: float = 12.0,
    ) -> None:
        self.auto_start = auto_start
        self.show_window = show_window
        self._process_probe = process_probe
        self._starter = starter
        self._windows = window_controller or _Win32CaptionWindowController()
        self._clock = clock
        self.start_timeout_seconds = start_timeout_seconds
        self._initial_pids = {process.pid for process in process_probe()}
        self._owned_pids: set[int] = set()
        self._restore_visible_pids: set[int] = set()
        self._launch_attempted = False
        self._launch_started_at: float | None = None
        self._had_running_process = bool(self._initial_pids)
        self._user_stopped = False
        self._status = self._initial_status()

    @property
    def owned_pids(self) -> frozenset[int]:
        return frozenset(self._owned_pids)

    def ensure_running(self) -> WindowsCaptionStatus:
        if not _is_supported_windows():
            self._status = WindowsCaptionStatus(
                False,
                False,
                "需要 Windows 11 22H2 或更高版本的实时字幕",
                WindowsCaptionState.UNSUPPORTED,
            )
            return self._status
        running = tuple(self._process_probe())
        if running:
            return self._running_status(running, apply_visibility=True)
        if self._user_stopped:
            return self._set_stopped_by_user()
        if self.auto_start and not self._launch_attempted:
            self._launch_attempted = True
            self._launch_started_at = self._clock()
            self._status = WindowsCaptionStatus(
                True, False, "正在启动 Windows 实时字幕", WindowsCaptionState.STARTING
            )
            self._starter()
            running = tuple(self._process_probe())
            if running:
                return self._running_status(running, apply_visibility=True)
            return self._status
        if self._launch_started_at is not None:
            if self._clock() - self._launch_started_at < self.start_timeout_seconds:
                return self._status
            self._status = WindowsCaptionStatus(
                True,
                False,
                "自动启动失败；请点击重新启动，或按 Win+Ctrl+L",
                WindowsCaptionState.FAILED,
            )
            return self._status
        self._status = WindowsCaptionStatus(
            True,
            False,
            "尚未开启（按 Win+Ctrl+L，或点击重新启动字幕）",
            WindowsCaptionState.STOPPED,
        )
        return self._status

    def refresh(self) -> WindowsCaptionStatus:
        """Read current state only; never sends the system shortcut."""
        running = tuple(self._process_probe())
        if running:
            return self._running_status(running)
        if self._had_running_process:
            self._user_stopped = True
            return self._set_stopped_by_user()
        if self._launch_started_at is not None:
            if self._clock() - self._launch_started_at < self.start_timeout_seconds:
                return self._status
            self._status = WindowsCaptionStatus(
                True,
                False,
                "启动超时；请检查语音组件，或按 Win+Ctrl+L",
                WindowsCaptionState.FAILED,
            )
            return self._status
        return self._status

    def retry_start(self) -> WindowsCaptionStatus:
        """Explicit user retry; grants exactly one new launch attempt."""
        self._user_stopped = False
        self._launch_attempted = False
        self._launch_started_at = None
        return self.ensure_running()

    def wait_for_component(self) -> WindowsCaptionStatus:
        self._status = WindowsCaptionStatus(
            True,
            False,
            "正在等待 Windows 安装当前语言的语音组件",
            WindowsCaptionState.WAITING_COMPONENT,
        )
        return self._status

    def hide_window(self) -> WindowsCaptionStatus:
        running = tuple(self._process_probe())
        if not running:
            return self.refresh()
        pid = running[0].pid
        was_visible = self._windows.is_visible(pid)
        hidden = self._windows.hide(pid)
        if was_visible and hidden:
            self._restore_visible_pids.add(pid)
        still_running = any(item.pid == pid for item in self._process_probe())
        if not hidden or not still_running:
            self._windows.show(pid)
            self._status = WindowsCaptionStatus(
                True,
                still_running,
                "无法安全隐藏系统字幕窗口，已恢复可见状态",
                WindowsCaptionState.FAILED,
                pid,
                pid in self._owned_pids,
                True,
            )
            return self._status
        self.show_window = False
        self._status = WindowsCaptionStatus(
            True,
            True,
            "系统字幕窗口已隐藏；识别进程仍在运行",
            WindowsCaptionState.HIDDEN,
            pid,
            pid in self._owned_pids,
            False,
        )
        return self._status

    def show_caption_window(self) -> WindowsCaptionStatus:
        running = tuple(self._process_probe())
        if not running:
            return self.refresh()
        pid = running[0].pid
        shown = self._windows.show(pid)
        self._restore_visible_pids.discard(pid)
        self.show_window = True
        self._status = WindowsCaptionStatus(
            True,
            True,
            "系统字幕窗口已显示" if shown else "未找到可显示的系统字幕窗口",
            WindowsCaptionState.RUNNING if shown else WindowsCaptionState.FAILED,
            pid,
            pid in self._owned_pids,
            shown,
        )
        return self._status

    def close(self) -> None:
        current_pids = {process.pid for process in self._process_probe()}
        for pid in self._restore_visible_pids & current_pids:
            if pid not in self._owned_pids:
                self._windows.show(pid)
        for pid in self._owned_pids & current_pids:
            self._windows.request_close(pid)
        self._restore_visible_pids.clear()

    def _initial_status(self) -> WindowsCaptionStatus:
        if not _is_supported_windows():
            return WindowsCaptionStatus(
                False,
                False,
                "仅支持 Windows 11 22H2 或更高版本的实时字幕",
                WindowsCaptionState.UNSUPPORTED,
            )
        running = tuple(self._process_probe())
        if not running:
            return WindowsCaptionStatus(
                True, False, "Windows 实时字幕尚未开启", WindowsCaptionState.STOPPED
            )
        pid = running[0].pid
        visible = self._windows.is_visible(pid)
        return WindowsCaptionStatus(
            True,
            True,
            "Windows 实时字幕已开启",
            WindowsCaptionState.RUNNING if visible else WindowsCaptionState.HIDDEN,
            pid,
            False,
            visible,
        )

    def _running_status(
        self,
        running: Sequence[WindowsCaptionProcess],
        *,
        apply_visibility: bool = False,
    ) -> WindowsCaptionStatus:
        new_pids = {process.pid for process in running if process.pid not in self._initial_pids}
        if self._launch_attempted:
            self._owned_pids.update(new_pids)
        self._had_running_process = True
        self._user_stopped = False
        pid = running[0].pid
        if apply_visibility and self.show_window:
            self._windows.show(pid)
        visible = self._windows.is_visible(pid)
        state = WindowsCaptionState.RUNNING if visible else WindowsCaptionState.HIDDEN
        detail = "Windows 实时字幕窗口可见" if visible else "Windows 实时字幕在后台运行"
        self._status = WindowsCaptionStatus(
            True, True, detail, state, pid, pid in self._owned_pids, visible
        )
        return self._status

    def _set_stopped_by_user(self) -> WindowsCaptionStatus:
        self._status = WindowsCaptionStatus(
            True,
            False,
            "Windows 实时字幕已被用户停止；不会自动重新打开",
            WindowsCaptionState.USER_STOPPED,
        )
        return self._status


def check_windows_live_captions() -> WindowsCaptionStatus:
    return WindowsCaptionManager(auto_start=False).refresh()


def open_live_captions_model_flow() -> None:
    """Open Live Captions so Windows can display its own model consent/download UI."""
    _start_windows_captions()


def _is_supported_windows() -> bool:
    return os.name == "nt" and sys.getwindowsversion().build >= 22621


class _Win32CaptionWindowController:
    def hide(self, pid: int) -> bool:
        return self._apply(pid, 0)

    def show(self, pid: int) -> bool:
        return self._apply(pid, 9)

    def is_visible(self, pid: int) -> bool:
        if os.name != "nt":
            return False
        import ctypes

        visible = False

        def callback(hwnd: int, _lparam: int) -> bool:
            nonlocal visible
            owner = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
                visible = True
            return True

        self._enum_windows(callback)
        return visible

    def request_close(self, pid: int) -> bool:
        return self._post(pid, 0x0010)

    def _apply(self, pid: int, command: int) -> bool:
        if os.name != "nt":
            return False
        import ctypes

        found = False

        def callback(hwnd: int, _lparam: int) -> bool:
            nonlocal found
            owner = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid:
                ctypes.windll.user32.ShowWindow(hwnd, command)
                found = True
            return True

        self._enum_windows(callback)
        return found

    def _post(self, pid: int, message: int) -> bool:
        if os.name != "nt":
            return False
        import ctypes

        found = False

        def callback(hwnd: int, _lparam: int) -> bool:
            nonlocal found
            owner = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid:
                ctypes.windll.user32.PostMessageW(hwnd, message, 0, 0)
                found = True
            return True

        self._enum_windows(callback)
        return found

    @staticmethod
    def _enum_windows(callback: Callable[[int, int], bool]) -> None:
        import ctypes

        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        ctypes.windll.user32.EnumWindows(callback_type(callback), 0)
