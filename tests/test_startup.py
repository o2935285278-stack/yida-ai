from datetime import UTC, datetime

from yida_ai.adapters.captions import CaptionActivityState, CaptionSourceStatus
from yida_ai.components import LctComponentState, LctComponentStatus
from yida_ai.system.preflight import (
    AudioInfo,
    ConnectivityInfo,
    PreflightIssue,
    PreflightReport,
    RuntimeState,
    ServiceInfo,
    WindowsPlatformInfo,
)
from yida_ai.system.speech_languages import (
    SPEECH_PACKAGES,
    SpeechComponentState,
    SpeechComponentStatus,
)
from yida_ai.system.startup import StartupOrchestrator, StartupStep
from yida_ai.system.windows_captions import WindowsCaptionState, WindowsCaptionStatus


def _report(can_start=True):
    issues = () if can_start else ()
    return PreflightReport(
        "pt-BR",
        WindowsPlatformInfo("10.0.26100", 26100, "x64", True, True, "ok"),
        SpeechComponentStatus(
            "pt-BR", SpeechComponentState.INSTALLED, SPEECH_PACKAGES["pt-BR"], "ok"
        ),
        ServiceInfo("wuauserv", "Running", "Manual", True),
        ServiceInfo("BITS", "Running", "Manual", True),
        ConnectivityInfo(True, True, False, "ok"),
        AudioInfo(True, True, 5_000_000_000, "ok"),
        True,
        issues,
    )


class FakePreflight:
    def __init__(self):
        self.calls = 0

    def run(self, _language):
        self.calls += 1
        return _report()


class FakeWindows:
    def __init__(self, running=True):
        self.running = running
        self.starts = 0

    def ensure_running(self):
        self.starts += 1
        return WindowsCaptionStatus(
            True,
            self.running,
            "running" if self.running else "starting",
            WindowsCaptionState.RUNNING if self.running else WindowsCaptionState.STARTING,
            10 if self.running else None,
        )

    def refresh(self):
        return self.ensure_running()

    def retry_start(self):
        self.running = True
        return self.ensure_running()


class FakeLct:
    def __init__(self, running=True):
        self.running = running
        self.starts = 0

    def ensure_running(self):
        self.starts += 1
        return LctComponentStatus(
            LctComponentState.BUNDLED_RUNNING if self.running else LctComponentState.MISSING,
            "running" if self.running else "missing",
            pid=20 if self.running else None,
        )

    def refresh(self):
        return self.ensure_running()

    def status(self):
        return self.ensure_running()

    def retry_start(self):
        self.running = True
        return self.ensure_running()


class FakeSource:
    def __init__(self, activity=CaptionActivityState.WAITING_AUDIO):
        self.activity = activity
        self.redetects = 0

    def redetect(self):
        self.redetects += 1
        return self.status()

    def status(self):
        now = datetime.now(UTC)
        return CaptionSourceStatus(
            self.activity is not CaptionActivityState.MISSING_DATABASE,
            "fake",
            self.activity.value,
            self.activity,
            self.activity is not CaptionActivityState.MISSING_DATABASE,
            True,
            self.activity is CaptionActivityState.RECEIVING,
            now if self.activity is CaptionActivityState.RECEIVING else None,
            now if self.activity is CaptionActivityState.RECEIVING else None,
        )


def _orchestrator(*, windows=None, lct=None, source=None, ai=True):
    return StartupOrchestrator(
        language="pt-BR",
        preflight=FakePreflight(),
        windows=windows or FakeWindows(),
        lct=lct or FakeLct(),
        source=source or FakeSource(),
        ai_ready=lambda: ai,
    )


def test_start_all_waits_for_audio_then_becomes_ready_without_duplicate_launch():
    windows = FakeWindows()
    lct = FakeLct()
    source = FakeSource()
    orchestrator = _orchestrator(windows=windows, lct=lct, source=source)
    first = orchestrator.start_all()
    assert first.state is RuntimeState.RUNNING_WAITING_AUDIO
    source.activity = CaptionActivityState.RECEIVING
    second = orchestrator.start_all()
    assert second.state is RuntimeState.READY
    assert second.step is StartupStep.READY
    assert windows.starts == 2
    assert lct.starts == 2


def test_missing_lct_and_database_are_precise_steps():
    lct = FakeLct(running=False)
    failed = _orchestrator(lct=lct).start_all()
    assert failed.step is StartupStep.LCT
    assert failed.error_code == "LCT_NOT_READY"

    waiting = _orchestrator(
        source=FakeSource(CaptionActivityState.MISSING_DATABASE)
    ).start_all()
    assert waiting.step is StartupStep.DATABASE
    assert waiting.state is RuntimeState.STARTING


def test_ai_unconfigured_is_degraded_not_false_ready():
    result = _orchestrator(ai=False).start_all()
    assert result.step is StartupStep.AI
    assert result.state is RuntimeState.DEGRADED
    assert result.error_code == "AI_NOT_VERIFIED"


def test_blocking_preflight_waits_for_user_action():
    report = _report()
    report = PreflightReport(
        report.language,
        report.platform,
        report.speech_model,
        report.windows_update,
        report.bits,
        report.connectivity,
        report.audio,
        report.live_captions_present,
        (
            PreflightIssue(
                "0x80070422", "update disabled", True, ("open-services", "retry")
            ),
        ),
    )

    class Blocked:
        def run(self, _language):
            return report

    orchestrator = StartupOrchestrator(
        language="pt-BR",
        preflight=Blocked(),
        windows=FakeWindows(),
        lct=FakeLct(),
        source=FakeSource(),
        ai_ready=lambda: True,
    )
    result = orchestrator.start_all()
    assert result.step is StartupStep.SPEECH_MODEL
    assert result.state is RuntimeState.WAITING_USER


def test_windows_starting_and_source_error_are_not_reported_ready():
    starting = _orchestrator(windows=FakeWindows(running=False)).start_all()
    assert starting.step is StartupStep.WINDOWS_CAPTIONS
    assert starting.state is RuntimeState.STARTING

    source_error = _orchestrator(source=FakeSource(CaptionActivityState.ERROR)).start_all()
    assert source_error.step is StartupStep.SOURCE
    assert source_error.state is RuntimeState.ERROR


def test_refresh_detects_user_closed_components_without_restarting():
    class StoppedWindows(FakeWindows):
        def refresh(self):
            return WindowsCaptionStatus(
                True,
                False,
                "user stopped",
                WindowsCaptionState.USER_STOPPED,
            )

    windows_orchestrator = _orchestrator(windows=StoppedWindows())
    windows_orchestrator.start_all()
    stopped = windows_orchestrator.refresh()
    assert stopped.state is RuntimeState.STOPPED
    assert stopped.error_code == "WINDOWS_CAPTIONS_USER_STOPPED"

    class StoppedLct(FakeLct):
        def refresh(self):
            return LctComponentStatus(LctComponentState.STOPPED, "user stopped")

    lct_orchestrator = _orchestrator(lct=StoppedLct())
    lct_orchestrator.start_all()
    stopped = lct_orchestrator.refresh()
    assert stopped.step is StartupStep.LCT
    assert stopped.error_code == "LCT_USER_STOPPED"


def test_retry_failed_step_and_max_retry_guard():
    lct = FakeLct(running=False)
    orchestrator = _orchestrator(lct=lct)
    assert orchestrator.start_all().state is RuntimeState.ERROR
    result = orchestrator.retry_failed_step()
    assert result.state is RuntimeState.RUNNING_WAITING_AUDIO

    failing = _orchestrator(lct=FakeLct(running=False))
    for _ in range(3):
        failing.start_all()
    guarded = failing.start_all()
    assert guarded.state is RuntimeState.ERROR
    assert "最大重试" in guarded.detail


def test_concurrent_start_call_returns_current_snapshot():
    orchestrator = _orchestrator()
    orchestrator._lock.acquire()
    try:
        assert orchestrator.start_all().state is RuntimeState.UNCHECKED
    finally:
        orchestrator._lock.release()
    marked = orchestrator.mark_user_stopped(StartupStep.LCT)
    assert marked.state is RuntimeState.STOPPED
