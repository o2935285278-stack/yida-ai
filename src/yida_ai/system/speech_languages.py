from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from yida_ai.system.windows_captions import find_windows_caption_processes

SUPPORTED_SPEECH_LANGUAGES = ("zh-CN", "en-US", "pt-BR")

SPEECH_PACKAGES = {
    "zh-CN": "MicrosoftWindows.Speech.zh-CN.1",
    "en-US": "MicrosoftWindows.Speech.en-US.1",
    "pt-BR": "MicrosoftWindows.Speech.pt-BR.1",
}

_LANGUAGE_MARKERS = {
    "zh-CN": (
        "chinese (simplified, china)",
        "chinese (simplified)",
        "中文(简体，中国)",
        "简体中文",
    ),
    "en-US": ("english (united states)", "english (us)", "英语(美国)"),
    "pt-BR": (
        "portuguese (brazil)",
        "português (brasil)",
        "葡萄牙语(巴西)",
    ),
}


class SpeechComponentState(StrEnum):
    INSTALLED = "installed"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SpeechComponentStatus:
    language: str
    state: SpeechComponentState
    package_name: str
    detail: str


def check_speech_components(
    package_output: str | None = None,
    *,
    languages: tuple[str, ...] = SUPPORTED_SPEECH_LANGUAGES,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[SpeechComponentStatus, ...]:
    """Check current-user Live Captions speech packages without elevation."""
    if package_output is None:
        if os.name != "nt":
            return tuple(
                SpeechComponentStatus(
                    code,
                    SpeechComponentState.UNKNOWN,
                    package,
                    "仅可在 Windows 上检测",
                )
                for code, package in SPEECH_PACKAGES.items()
                if code in languages
            )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = runner(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-AppxPackage -Name 'MicrosoftWindows.Speech.*' | "
                "Select-Object -ExpandProperty Name",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        if completed.returncode != 0:
            package_output = ""
            unknown = True
        else:
            package_output = completed.stdout
            unknown = False
    else:
        unknown = False

    installed_names = {
        line.strip().casefold() for line in package_output.splitlines() if line.strip()
    }
    statuses: list[SpeechComponentStatus] = []
    for code, package in SPEECH_PACKAGES.items():
        if code not in languages:
            continue
        if unknown:
            state = SpeechComponentState.UNKNOWN
            detail = "无法读取 Windows 语音组件状态"
        elif package.casefold() in installed_names:
            state = SpeechComponentState.INSTALLED
            detail = "已安装"
        else:
            state = SpeechComponentState.MISSING
            detail = "缺少 Windows 语音识别组件"
        statuses.append(SpeechComponentStatus(code, state, package, detail))
    return tuple(statuses)


def check_speech_component(
    language: str,
    package_output: str | None = None,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> SpeechComponentStatus:
    if language not in SPEECH_PACKAGES:
        raise ValueError(f"Unsupported speech language: {language}")
    return check_speech_components(
        package_output,
        languages=(language,),
        runner=runner,
    )[0]


def missing_speech_languages(statuses: tuple[SpeechComponentStatus, ...]) -> tuple[str, ...]:
    return tuple(item.language for item in statuses if item.state is SpeechComponentState.MISSING)


def open_windows_language_settings() -> None:
    """Open Microsoft's Settings flow; never download or bundle language packs."""
    if os.name != "nt":
        return
    subprocess.Popen(
        ["explorer.exe", "ms-settings:regionlanguage"],
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def detect_live_captions_language(
    automation_text: str | None = None,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str | None:
    """Best-effort UI Automation probe of the visible Live Captions window."""
    configured = os.getenv("YIDA_WINDOWS_CAPTION_LANGUAGE", "").strip()
    if configured in SUPPORTED_SPEECH_LANGUAGES:
        return configured
    if automation_text is None:
        processes = find_windows_caption_processes()
        if os.name != "nt" or not processes:
            return None
        pid = processes[0].pid
        script = (
            "$OutputEncoding=[Console]::OutputEncoding="
            "[System.Text.UTF8Encoding]::new($false);"
            "Add-Type -AssemblyName UIAutomationClient;"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$root=[Windows.Automation.AutomationElement]::RootElement;"
            "$cond=New-Object Windows.Automation.PropertyCondition("
            "[Windows.Automation.AutomationElement]::ProcessIdProperty,"
            f"{pid});"
            "function GetEls{$root.FindAll([Windows.Automation.TreeScope]::Descendants,$cond)};"
            "function InvokeNamed($names,$type){foreach($e in (GetEls)){"
            "if($e.Current.Name -in $names -and $e.Current.ControlType -eq $type){"
            "$pattern=$null;if($e.TryGetCurrentPattern("
            "[Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){"
            "$pattern.Invoke();Start-Sleep -Milliseconds 250;return}}}};"
            "InvokeNamed @('设置','Settings','Configurações') "
            "([Windows.Automation.ControlType]::Button);"
            "InvokeNamed @('更改语言','Change language','Alterar idioma') "
            "([Windows.Automation.ControlType]::MenuItem);"
            "foreach($e in (GetEls)){if($e.Current.Name){$e.Current.Name}};"
            "[System.Windows.Forms.SendKeys]::SendWait('{ESC}');"
            "[System.Windows.Forms.SendKeys]::SendWait('{ESC}')"
        )
        completed = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
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
        automation_text = completed.stdout
    folded = automation_text.casefold()
    for code, markers in _LANGUAGE_MARKERS.items():
        if any(marker.casefold() in folded for marker in markers):
            return code
    return None


def caption_language_warning(expected: str, detected: str | None) -> str:
    if detected is None:
        return "无法自动读取 Windows 实时字幕语言，请确认它与当前听取语言一致"
    if detected != expected:
        return f"Windows 实时字幕当前为 {detected}，与听取语言 {expected} 不一致"
    return ""
