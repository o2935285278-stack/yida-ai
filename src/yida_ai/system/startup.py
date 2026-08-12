from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from yida_ai.adapters.captions import CaptionActivityState, CaptionSource
from yida_ai.components import LctComponentManager, LctComponentState
from yida_ai.system.preflight import PreflightChecker, PreflightReport, RuntimeState
from yida_ai.system.windows_captions import WindowsCaptionManager, WindowsCaptionState


class StartupStep(StrEnum):
    PREFLIGHT = "preflight"
    SPEECH_MODEL = "speech-model"
    WINDOWS_CAPTIONS = "windows-captions"
    LCT = "livecaptions-translator"
    DATABASE = "caption-database"
    SOURCE = "caption-source"
    AI = "ai"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class StartupSnapshot:
    step: StartupStep
    state: RuntimeState
    detail: str
    error_code: str = ""
    attempt: int = 0
    updated_at: float = 0.0


class StartupOrchestrator:
    """Idempotent startup state machine for the external Windows caption chain."""

    def __init__(
        self,
        *,
        language: str,
        preflight: PreflightChecker,
        windows: WindowsCaptionManager,
        lct: LctComponentManager,
        source: CaptionSource,
        ai_ready: Callable[[], bool],
        clock: Callable[[], float] = time.monotonic,
        max_retries: int = 3,
    ) -> None:
        self.language = language
        self.preflight = preflight
        self.windows = windows
        self.lct = lct
        self.source = source
        self.ai_ready = ai_ready
        self.clock = clock
        self.max_retries = max_retries
        self.last_preflight: PreflightReport | None = None
        self._lock = threading.Lock()
        self._attempt = 0
        self._user_stopped = False
        self._snapshot = StartupSnapshot(
            StartupStep.PREFLIGHT,
            RuntimeState.UNCHECKED,
            "尚未执行启动检查",
            updated_at=self.clock(),
        )

    @property
    def snapshot(self) -> StartupSnapshot:
        return self._snapshot

    def start_all(self, *, force_preflight: bool = False) -> StartupSnapshot:
        if not self._lock.acquire(blocking=False):
            return self._snapshot
        try:
            self._user_stopped = False
            if self._attempt >= self.max_retries and self._snapshot.state is RuntimeState.ERROR:
                return self._set(
                    self._snapshot.step,
                    RuntimeState.ERROR,
                    "已达到最大重试次数；请修复失败项后点击‘重试失败步骤’。",
                    self._snapshot.error_code,
                )
            self._attempt += 1
            if self.last_preflight is None or force_preflight:
                self._set(StartupStep.PREFLIGHT, RuntimeState.CHECKING, "正在检查 Windows 环境")
                self.last_preflight = self.preflight.run(self.language)
            report = self.last_preflight
            if not report.can_start:
                issue = next(issue for issue in report.issues if issue.blocking)
                state = (
                    RuntimeState.WAITING_USER
                    if issue.actions
                    else RuntimeState.ERROR
                )
                step = (
                    StartupStep.SPEECH_MODEL
                    if "MODEL" in issue.code or issue.code == "0x80070422"
                    else StartupStep.PREFLIGHT
                )
                return self._set(step, state, issue.detail, issue.code)

            windows = self.windows.ensure_running()
            if not windows.running:
                state = {
                    WindowsCaptionState.STARTING: RuntimeState.STARTING,
                    WindowsCaptionState.WAITING_COMPONENT: RuntimeState.WAITING_USER,
                    WindowsCaptionState.USER_STOPPED: RuntimeState.STOPPED,
                }.get(windows.state, RuntimeState.ERROR)
                return self._set(
                    StartupStep.WINDOWS_CAPTIONS,
                    state,
                    windows.detail,
                    "WINDOWS_CAPTIONS_NOT_READY",
                )

            lct = self.lct.ensure_running()
            if lct.state not in {
                LctComponentState.BUNDLED_RUNNING,
                LctComponentState.EXTERNAL_RUNNING,
            }:
                state = (
                    RuntimeState.STARTING
                    if lct.state is LctComponentState.STARTING
                    else RuntimeState.ERROR
                )
                return self._set(StartupStep.LCT, state, lct.detail, "LCT_NOT_READY")

            source = self.source.redetect()
            if source.activity is CaptionActivityState.MISSING_DATABASE:
                return self._set(
                    StartupStep.DATABASE,
                    RuntimeState.STARTING,
                    source.detail,
                    "LCT_DATABASE_WAITING",
                )
            if source.activity is CaptionActivityState.ERROR:
                return self._set(
                    StartupStep.SOURCE,
                    RuntimeState.ERROR,
                    source.detail,
                    "CAPTION_SOURCE_ERROR",
                )
            if not self.ai_ready():
                return self._set(
                    StartupStep.AI,
                    RuntimeState.DEGRADED,
                    "字幕链已连接，但 AI 尚未配置或尚未通过连接验证。",
                    "AI_NOT_VERIFIED",
                )
            if source.activity in {
                CaptionActivityState.RECEIVING,
                CaptionActivityState.STALE,
            }:
                return self._set(
                    StartupStep.READY,
                    RuntimeState.READY,
                    "字幕、翻译和 AI 回复链已就绪。",
                )
            return self._set(
                StartupStep.SOURCE,
                RuntimeState.RUNNING_WAITING_AUDIO,
                "组件已启动，正在等待音频和新字幕。",
            )
        finally:
            self._lock.release()

    def refresh(self) -> StartupSnapshot:
        if self._user_stopped:
            return self._snapshot
        windows = self.windows.refresh()
        if windows.state is WindowsCaptionState.USER_STOPPED:
            self._user_stopped = True
            return self._set(
                StartupStep.WINDOWS_CAPTIONS,
                RuntimeState.STOPPED,
                windows.detail,
                "WINDOWS_CAPTIONS_USER_STOPPED",
            )
        lct = self.lct.refresh()
        if lct.state is LctComponentState.STOPPED:
            self._user_stopped = True
            return self._set(
                StartupStep.LCT,
                RuntimeState.STOPPED,
                lct.detail,
                "LCT_USER_STOPPED",
            )
        return self.start_all()

    def retry_failed_step(self) -> StartupSnapshot:
        self._attempt = 0
        self._user_stopped = False
        if self._snapshot.step is StartupStep.WINDOWS_CAPTIONS:
            self.windows.retry_start()
        elif self._snapshot.step is StartupStep.LCT:
            self.lct.retry_start()
        return self.start_all(force_preflight=self._snapshot.step in {
            StartupStep.PREFLIGHT,
            StartupStep.SPEECH_MODEL,
        })

    def mark_user_stopped(self, step: StartupStep) -> StartupSnapshot:
        self._user_stopped = True
        return self._set(step, RuntimeState.STOPPED, "已按用户操作停止；不会自动重新启动。")

    def _set(
        self,
        step: StartupStep,
        state: RuntimeState,
        detail: str,
        error_code: str = "",
    ) -> StartupSnapshot:
        self._snapshot = StartupSnapshot(
            step,
            state,
            detail,
            error_code,
            self._attempt,
            self.clock(),
        )
        return self._snapshot
