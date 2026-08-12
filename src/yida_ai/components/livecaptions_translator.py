from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

LCT_EXECUTABLE_NAME = "LiveCaptions Translator.exe"


class LctComponentState(StrEnum):
    FOUND = "found"
    STARTING = "starting"
    BUNDLED_RUNNING = "bundled-running"
    EXTERNAL_RUNNING = "external-running"
    WAITING_DATABASE = "waiting-database"
    DISABLED = "disabled"
    MISSING = "missing"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class RunningProcess:
    pid: int
    image_name: str = LCT_EXECUTABLE_NAME
    executable_path: Path | None = None


@dataclass(frozen=True, slots=True)
class LctComponentStatus:
    state: LctComponentState
    detail: str
    executable_path: Path | None = None
    pid: int | None = None
    owned: bool = False


class ManagedProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...


class WindowController(Protocol):
    def hide(self, pid: int) -> bool: ...

    def show(self, pid: int) -> bool: ...

    def request_close(self, pid: int) -> bool: ...


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def bundled_component_directory(base_directory: Path | None = None) -> Path:
    base = base_directory or application_directory()
    return base / "components" / "LiveCaptionsTranslator"


def find_running_lct_processes() -> tuple[RunningProcess, ...]:
    if os.name != "nt":
        return ()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        [
            "tasklist.exe",
            "/FI",
            f"IMAGENAME eq {LCT_EXECUTABLE_NAME}",
            "/FO",
            "CSV",
            "/NH",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    if completed.returncode != 0:
        return ()
    processes: list[RunningProcess] = []
    for row in csv.reader(io.StringIO(completed.stdout)):
        if len(row) < 2 or row[0].casefold() != LCT_EXECUTABLE_NAME.casefold():
            continue
        try:
            pid = int(row[1])
            processes.append(
                RunningProcess(
                    pid=pid,
                    image_name=row[0],
                    executable_path=_process_executable_path(pid),
                )
            )
        except ValueError:
            continue
    return tuple(processes)


def _process_executable_path(pid: int) -> Path | None:
    """Return a process image path without reading its command line or environment."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information,
        False,
        pid,
    )
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not ctypes.windll.kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            return None
        return Path(buffer.value)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def launch_lct(executable: Path) -> ManagedProcess:
    startup_info = None
    creation_flags = 0
    if os.name == "nt":
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup_info.wShowWindow = 0
        creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        [str(executable)],
        cwd=str(executable.parent),
        shell=False,
        startupinfo=startup_info,
        creationflags=creation_flags,
    )


class LctComponentManager:
    def __init__(
        self,
        *,
        base_directory: Path | None = None,
        executable_path: Path | None = None,
        no_start: bool = False,
        process_probe: Callable[[], Sequence[RunningProcess]] = find_running_lct_processes,
        launcher: Callable[[Path], ManagedProcess] = launch_lct,
        window_controller: WindowController | None = None,
    ) -> None:
        self.bundled_directory = bundled_component_directory(base_directory)
        self.executable_path = executable_path or (self.bundled_directory / LCT_EXECUTABLE_NAME)
        self.no_start = no_start
        self._process_probe = process_probe
        self._launcher = launcher
        self._windows = window_controller or _Win32WindowController()
        self._owned_process: ManagedProcess | None = None
        self._settings_visible = False
        self._last_status = self._initial_status()
        self._had_running_process = self._last_status.pid is not None
        self._user_stopped = False

    @property
    def owns_process(self) -> bool:
        return self._owned_process is not None and self._owned_process.poll() is None

    def status(self) -> LctComponentStatus:
        return self._last_status

    def ensure_running(self, *, force: bool = False) -> LctComponentStatus:
        running = tuple(self._process_probe())
        owned_pid = self._owned_process.pid if self.owns_process else None
        if owned_pid is not None:
            self._last_status = LctComponentStatus(
                LctComponentState.BUNDLED_RUNNING,
                "内置 LiveCaptions Translator 正在后台运行",
                self.executable_path,
                owned_pid,
                True,
            )
            self._had_running_process = True
            self._user_stopped = False
            self._hide_if_needed(owned_pid)
            return self._last_status
        if running:
            process = running[0]
            self._last_status = LctComponentStatus(
                LctComponentState.EXTERNAL_RUNNING,
                "正在使用用户已运行的 LiveCaptions Translator",
                executable_path=process.executable_path,
                pid=process.pid,
            )
            self._had_running_process = True
            self._user_stopped = False
            return self._last_status
        if self.no_start:
            self._last_status = LctComponentStatus(
                LctComponentState.DISABLED,
                "已通过 --no-start-lct 禁用自动启动",
                self.executable_path if self.executable_path.is_file() else None,
            )
            return self._last_status
        if (self._user_stopped or self._had_running_process) and not force:
            self._user_stopped = True
            self._last_status = LctComponentStatus(
                LctComponentState.STOPPED,
                "LiveCaptions Translator 已被用户关闭；不会自动重新启动",
                self.executable_path if self.executable_path.is_file() else None,
            )
            return self._last_status
        if force:
            self._user_stopped = False
        if self._last_status.state is LctComponentState.FAILED and not force:
            return self._last_status
        if not self.executable_path.is_file():
            self._last_status = LctComponentStatus(
                LctComponentState.MISSING,
                "未找到内置 LiveCaptions Translator；请修复安装或手动运行外部版本",
                self.executable_path,
            )
            return self._last_status
        self._last_status = LctComponentStatus(
            LctComponentState.STARTING,
            "正在启动内置 LiveCaptions Translator",
            self.executable_path,
        )
        try:
            self._owned_process = self._launcher(self.executable_path)
        except OSError as exc:
            self._last_status = LctComponentStatus(
                LctComponentState.FAILED,
                f"LCT 启动失败：{exc}。可点击“打开 LCT 设置”重试",
                self.executable_path,
            )
            return self._last_status
        self._last_status = LctComponentStatus(
            LctComponentState.BUNDLED_RUNNING,
            "内置 LiveCaptions Translator 正在后台运行",
            self.executable_path,
            self._owned_process.pid,
            True,
        )
        self._had_running_process = True
        self._hide_if_needed(self._owned_process.pid)
        return self._last_status

    def refresh(self) -> LctComponentStatus:
        running = tuple(self._process_probe())
        owned_pid = self._owned_process.pid if self.owns_process else None
        if owned_pid is not None:
            self._last_status = LctComponentStatus(
                LctComponentState.BUNDLED_RUNNING,
                "内置 LiveCaptions Translator 正在后台运行",
                self.executable_path,
                owned_pid,
                True,
            )
            self._had_running_process = True
            self._hide_if_needed(owned_pid)
            return self._last_status
        if running:
            process = running[0]
            self._last_status = LctComponentStatus(
                LctComponentState.EXTERNAL_RUNNING,
                "正在使用用户已运行的 LiveCaptions Translator",
                executable_path=process.executable_path,
                pid=process.pid,
            )
            self._had_running_process = True
            return self._last_status
        if self._had_running_process:
            self._user_stopped = True
            self._last_status = LctComponentStatus(
                LctComponentState.STOPPED,
                "LiveCaptions Translator 已被用户关闭；不会自动重新启动",
                self.executable_path if self.executable_path.is_file() else None,
            )
        return self._last_status

    def retry_start(self) -> LctComponentStatus:
        self._user_stopped = False
        return self.ensure_running(force=True)

    def open_settings(self) -> LctComponentStatus:
        status = self.ensure_running(force=True)
        if status.pid is None:
            return status
        self._settings_visible = True
        shown = self._windows.show(status.pid)
        detail = (
            "LiveCaptions Translator 设置已打开"
            if shown
            else "LCT 正在运行，但暂未找到可显示的设置窗口；请稍后重试"
        )
        self._last_status = LctComponentStatus(
            status.state,
            detail,
            status.executable_path,
            status.pid,
            status.owned,
        )
        return self._last_status

    def return_to_background(self) -> LctComponentStatus:
        self._settings_visible = False
        if self._last_status.pid is not None:
            hidden = self._windows.hide(self._last_status.pid)
            detail = (
                "LiveCaptions Translator 已收回后台"
                if hidden
                else "LCT 正在运行，但未找到可隐藏的设置窗口"
            )
            self._last_status = LctComponentStatus(
                self._last_status.state,
                detail,
                self._last_status.executable_path,
                self._last_status.pid,
                self._last_status.owned,
            )
        return self._last_status

    def close(self) -> None:
        if not self.owns_process:
            return
        assert self._owned_process is not None
        pid = self._owned_process.pid
        requested = self._windows.request_close(pid)
        detail = (
            "已请求内置 LCT 正常退出"
            if requested
            else "未能确认内置 LCT 的安全退出方式，已保留后台进程"
        )
        self._last_status = LctComponentStatus(
            LctComponentState.STOPPED,
            detail,
            self.executable_path,
            pid,
            True,
        )

    def _initial_status(self) -> LctComponentStatus:
        if self.no_start:
            return LctComponentStatus(
                LctComponentState.DISABLED,
                "已通过 --no-start-lct 禁用自动启动",
            )
        running = tuple(self._process_probe())
        if running:
            process = running[0]
            return LctComponentStatus(
                LctComponentState.EXTERNAL_RUNNING,
                "正在使用用户已运行的 LiveCaptions Translator",
                process.executable_path,
                process.pid,
            )
        if self.executable_path.is_file():
            return LctComponentStatus(
                LctComponentState.FOUND,
                "已找到内置 LiveCaptions Translator",
                self.executable_path,
            )
        return LctComponentStatus(
            LctComponentState.MISSING,
            "未找到内置 LiveCaptions Translator",
            self.executable_path,
        )

    def _hide_if_needed(self, pid: int) -> None:
        if not self._settings_visible:
            self._windows.hide(pid)


class _Win32WindowController:
    def hide(self, pid: int) -> bool:
        return self._apply(pid, 0)

    def show(self, pid: int) -> bool:
        return self._apply(pid, 9)

    def request_close(self, pid: int) -> bool:
        if os.name != "nt":
            return False
        import ctypes

        wm_close = 0x0010
        found = False

        def callback(hwnd: int, _lparam: int) -> bool:
            nonlocal found
            owner = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid:
                ctypes.windll.user32.PostMessageW(hwnd, wm_close, 0, 0)
                found = True
            return True

        self._enum_windows(callback)
        return found

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

    @staticmethod
    def _enum_windows(callback: Callable[[int, int], bool]) -> None:
        import ctypes

        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        ctypes.windll.user32.EnumWindows(callback_type(callback), 0)
