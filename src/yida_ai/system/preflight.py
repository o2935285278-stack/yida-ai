from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from yida_ai.system.speech_languages import (
    SpeechComponentState,
    SpeechComponentStatus,
    check_speech_component,
)

MINIMUM_WINDOWS_BUILD = 22621
ERROR_WINDOWS_UPDATE_DISABLED = "0x80070422"


class RuntimeState(StrEnum):
    UNCHECKED = "unchecked"
    CHECKING = "checking"
    NOT_INSTALLED = "not-installed"
    STOPPED = "stopped"
    STARTING = "starting"
    WAITING_USER = "waiting-user-action"
    RUNNING_WAITING_AUDIO = "running-waiting-audio"
    RECEIVING_CAPTIONS = "receiving-captions"
    TRANSLATING = "translating"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WindowsPlatformInfo:
    version: str
    build: int
    architecture: str
    supported: bool
    architecture_supported: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ServiceInfo:
    name: str
    state: str
    start_mode: str
    available: bool

    @property
    def disabled(self) -> bool:
        return self.start_mode.casefold() == "disabled"


@dataclass(frozen=True, slots=True)
class ConnectivityInfo:
    internet: bool | None
    microsoft_catalog: bool | None
    store_policy_disabled: bool | None
    detail: str


@dataclass(frozen=True, slots=True)
class AudioInfo:
    microphone_permission: bool | None
    audio_endpoint_available: bool | None
    free_disk_bytes: int | None
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    code: str
    detail: str
    blocking: bool
    actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreflightReport:
    language: str
    platform: WindowsPlatformInfo
    speech_model: SpeechComponentStatus
    windows_update: ServiceInfo
    bits: ServiceInfo
    connectivity: ConnectivityInfo
    audio: AudioInfo
    live_captions_present: bool
    issues: tuple[PreflightIssue, ...]

    @property
    def can_start(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    @property
    def error_code(self) -> str:
        for issue in self.issues:
            if issue.code:
                return issue.code
        return ""


def detect_windows_platform(
    *,
    os_name: str | None = None,
    version: tuple[int, int, int] | None = None,
    machine: str | None = None,
) -> WindowsPlatformInfo:
    current_os = os.name if os_name is None else os_name
    architecture = _normalize_architecture(machine or platform.machine())
    architecture_supported = architecture in {"x64", "ARM64"}
    if current_os != "nt":
        return WindowsPlatformInfo(
            platform.platform(), 0, architecture, False, architecture_supported, "仅支持 Windows 11"
        )
    if version is None:
        win = sys.getwindowsversion()
        version = (win.major, win.minor, win.build)
    major, minor, build = version
    supported = major >= 10 and build >= MINIMUM_WINDOWS_BUILD
    product_name = "Windows 11" if build >= 22000 else "Windows 10"
    detail = (
        f"{product_name} build {build} · {architecture}"
        if supported
        else (
            f"当前为 {product_name} build {build} · {architecture}；"
            f"需要 Windows 11 22H2（build {MINIMUM_WINDOWS_BUILD}）或更高版本"
        )
    )
    if not architecture_supported:
        detail += "；当前安装包不支持此处理器架构"
    return WindowsPlatformInfo(
        f"{major}.{minor}.{build}",
        build,
        architecture,
        supported,
        architecture_supported,
        detail,
    )


def check_update_services(
    *, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> tuple[ServiceInfo, ServiceInfo]:
    unknown = (
        ServiceInfo("wuauserv", "unknown", "unknown", False),
        ServiceInfo("BITS", "unknown", "unknown", False),
    )
    if os.name != "nt":
        return unknown
    script = (
        "$ErrorActionPreference='Stop';"
        "$items=Get-CimInstance Win32_Service -Filter "
        "\"Name='wuauserv' OR Name='BITS'\" | "
        "Select-Object Name,State,StartMode;"
        "$items | ConvertTo-Json -Compress"
    )
    completed = runner(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=5,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return unknown
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return unknown
    if isinstance(parsed, dict):
        parsed = [parsed]
    by_name = {str(item.get("Name", "")).casefold(): item for item in parsed}

    def build(name: str) -> ServiceInfo:
        item = by_name.get(name.casefold())
        if not item:
            return ServiceInfo(name, "unknown", "unknown", False)
        return ServiceInfo(
            name,
            str(item.get("State", "unknown")),
            str(item.get("StartMode", "unknown")),
            True,
        )

    return build("wuauserv"), build("BITS")


def check_connectivity(
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    store_policy_probe: Callable[[], bool | None] | None = None,
) -> ConnectivityInfo:
    if os.name != "nt":
        return ConnectivityInfo(None, None, None, "仅在 Windows 上检测网络与商店策略")
    internet = _probe_url("https://www.msftconnecttest.com/connecttest.txt", opener)
    catalog = _probe_url("https://storeedgefd.dsx.mp.microsoft.com/", opener)
    policy = (store_policy_probe or _store_policy_disabled)()
    details: list[str] = []
    details.append("互联网可用" if internet else "互联网不可用或未验证")
    details.append("微软模型目录可达" if catalog else "微软模型目录不可达或未验证")
    if policy is True:
        details.append("Microsoft Store 被组织策略禁用")
    elif policy is None:
        details.append("Microsoft Store 策略未验证")
    return ConnectivityInfo(internet, catalog, policy, "；".join(details))


def check_audio_and_disk(*, data_dir: Path, minimum_free_bytes: int = 1_500_000_000) -> AudioInfo:
    try:
        free = shutil.disk_usage(data_dir.anchor or data_dir).free
    except OSError:
        free = None
    microphone = _microphone_permission()
    endpoint = _audio_endpoint_available()
    details = [
        "麦克风权限已开启"
        if microphone is True
        else "麦克风权限关闭" if microphone is False else "麦克风权限未验证",
        "检测到音频端点"
        if endpoint is True
        else "未检测到音频端点" if endpoint is False else "默认音频端点未验证",
    ]
    if free is not None:
        details.append(f"可用磁盘 {free / (1024**3):.1f} GiB")
        if free < minimum_free_bytes:
            details.append("磁盘空间不足")
    return AudioInfo(microphone, endpoint, free, "；".join(details))


class PreflightChecker:
    def __init__(
        self,
        data_dir: Path,
        *,
        platform_probe: Callable[[], WindowsPlatformInfo] = detect_windows_platform,
        service_probe: Callable[[], tuple[ServiceInfo, ServiceInfo]] = check_update_services,
        connectivity_probe: Callable[[], ConnectivityInfo] = check_connectivity,
        speech_probe: Callable[[str], SpeechComponentStatus] = check_speech_component,
        audio_probe: Callable[..., AudioInfo] = check_audio_and_disk,
        captions_probe: Callable[[], bool] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self._platform_probe = platform_probe
        self._service_probe = service_probe
        self._connectivity_probe = connectivity_probe
        self._speech_probe = speech_probe
        self._audio_probe = audio_probe
        self._captions_probe = captions_probe or live_captions_component_present

    def run(self, language: str, *, requires_microphone: bool = False) -> PreflightReport:
        platform_info = self._platform_probe()
        model = self._speech_probe(language)
        update, bits = self._service_probe()
        connectivity = self._connectivity_probe()
        audio = self._audio_probe(data_dir=self.data_dir)
        captions_present = self._captions_probe()
        issues: list[PreflightIssue] = []
        if not platform_info.supported:
            issues.append(PreflightIssue("WIN_BUILD_UNSUPPORTED", platform_info.detail, True))
        if not platform_info.architecture_supported:
            issues.append(
                PreflightIssue("ARCH_UNSUPPORTED", "当前安装包不支持此处理器架构", True)
            )
        if not captions_present:
            issues.append(
                PreflightIssue(
                    "LIVE_CAPTIONS_MISSING",
                    "未检测到 Windows 实时字幕组件，请先完成 Windows 更新。",
                    True,
                    ("open-windows-update",),
                )
            )
        if model.state is SpeechComponentState.MISSING:
            if update.disabled or bits.disabled:
                issues.append(
                    PreflightIssue(
                        ERROR_WINDOWS_UPDATE_DISABLED,
                        "Windows Update 或 BITS 已被禁用，因此无法下载实时字幕语音识别模型。",
                        True,
                        (
                            "open-services",
                            "open-windows-update",
                            "copy-repair-instructions",
                            "retry",
                        ),
                    )
                )
            elif connectivity.store_policy_disabled is True:
                issues.append(
                    PreflightIssue(
                        "STORE_POLICY_DISABLED",
                        "Microsoft Store 被组织策略禁用，实时字幕模型可能无法下载。",
                        True,
                        ("copy-repair-instructions", "retry"),
                    )
                )
            elif connectivity.internet is False:
                issues.append(
                    PreflightIssue(
                        "NETWORK_UNAVAILABLE",
                        "网络不可用，无法下载实时字幕语音识别模型。",
                        True,
                        ("retry",),
                    )
                )
            else:
                issues.append(
                    PreflightIssue(
                        "CAPTION_MODEL_MISSING",
                        f"缺少 {language} 的 Windows 实时字幕本地语音识别模型。",
                        True,
                        ("open-live-captions-model-flow", "open-language-settings", "retry"),
                    )
                )
        elif model.state is SpeechComponentState.UNKNOWN:
            issues.append(
                PreflightIssue(
                    "CAPTION_MODEL_UNVERIFIED",
                    "无法确认实时字幕模型是否安装；启动字幕后请按界面提示确认。",
                    False,
                    ("open-live-captions-model-flow", "retry"),
                )
            )
        if audio.free_disk_bytes is not None and audio.free_disk_bytes < 1_500_000_000:
            issues.append(PreflightIssue("DISK_LOW", "磁盘可用空间不足 1.5 GB。", True))
        if requires_microphone and audio.microphone_permission is False:
            issues.append(
                PreflightIssue(
                    "MIC_PERMISSION_DENIED",
                    "麦克风权限已关闭；系统音频模式仍可使用。",
                    True,
                    ("open-microphone-settings",),
                )
            )
        return PreflightReport(
            language,
            platform_info,
            model,
            update,
            bits,
            connectivity,
            audio,
            captions_present,
            tuple(issues),
        )


def live_captions_component_present() -> bool:
    if os.name != "nt":
        return False
    system_root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
    return (system_root / "System32" / "LiveCaptions.exe").is_file()


def open_services_console() -> None:
    _open_windows_target(["services.msc"])


def open_windows_update() -> None:
    _open_windows_target(["explorer.exe", "ms-settings:windowsupdate"])


def open_microphone_settings() -> None:
    _open_windows_target(["explorer.exe", "ms-settings:privacy-microphone"])


def repair_instructions(language: str) -> str:
    return (
        f"译答 AI 检测到 {language} 实时字幕模型无法下载。\n"
        f"如果错误代码为 {ERROR_WINDOWS_UPDATE_DISABLED}：\n"
        "1. 按 Win+R，输入 services.msc。\n"
        "2. 检查 Windows Update 与 Background Intelligent Transfer Service (BITS) "
        "没有被设置为‘已禁用’。\n"
        "3. 返回 Windows 更新并完成待处理更新。\n"
        "4. 重新打开 Windows 实时字幕，让 Windows 自行下载本地语音识别模型。\n"
        "译答 AI 不会自动更改服务，也不会内置微软语言包。"
    )


def _normalize_architecture(value: str) -> str:
    folded = value.casefold()
    if folded in {"amd64", "x86_64", "x64"}:
        return "x64"
    if folded in {"arm64", "aarch64"}:
        return "ARM64"
    return value or "unknown"


def _probe_url(url: str, opener: Callable[..., object]) -> bool | None:
    try:
        response = opener(url, timeout=2)
        close = getattr(response, "close", None)
        if close:
            close()
        return True
    except (OSError, urllib.error.URLError, TimeoutError):
        return None
    except Exception:
        return None


def _store_policy_disabled() -> bool | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\WindowsStore",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "RemoveWindowsStore")
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return None


def _microphone_permission() -> bool | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Value")
            return str(value).casefold() == "allow"
    except OSError:
        return None


def _audio_endpoint_available() -> bool | None:
    if os.name != "nt":
        return None
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "@(Get-PnpDevice -Class AudioEndpoint -Status OK -ErrorAction SilentlyContinue).Count",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=4,
    )
    if completed.returncode != 0:
        return None
    try:
        return int(completed.stdout.strip()) > 0
    except ValueError:
        return None


def _open_windows_target(command: list[str]) -> None:
    if os.name != "nt":
        return
    subprocess.Popen(
        command,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
