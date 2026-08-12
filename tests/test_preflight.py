from pathlib import Path

from yida_ai.system.preflight import (
    ERROR_WINDOWS_UPDATE_DISABLED,
    AudioInfo,
    ConnectivityInfo,
    PreflightChecker,
    ServiceInfo,
    check_audio_and_disk,
    check_connectivity,
    check_update_services,
    detect_windows_platform,
    live_captions_component_present,
    open_microphone_settings,
    open_services_console,
    open_windows_update,
    repair_instructions,
)
from yida_ai.system.speech_languages import (
    SPEECH_PACKAGES,
    SpeechComponentState,
    SpeechComponentStatus,
)


def _speech(language: str, state: SpeechComponentState) -> SpeechComponentStatus:
    return SpeechComponentStatus(language, state, SPEECH_PACKAGES[language], state.value)


def _audio(**_kwargs) -> AudioInfo:
    return AudioInfo(True, True, 5_000_000_000, "ok")


def test_windows_10_and_low_windows_11_are_blocked():
    win10 = detect_windows_platform(os_name="nt", version=(10, 0, 19045), machine="AMD64")
    low_win11 = detect_windows_platform(os_name="nt", version=(10, 0, 22000), machine="AMD64")
    current = detect_windows_platform(os_name="nt", version=(10, 0, 22621), machine="AMD64")
    assert not win10.supported
    assert not low_win11.supported
    assert current.supported
    assert current.architecture == "x64"


def test_arm64_is_recognized_as_supported_architecture():
    result = detect_windows_platform(os_name="nt", version=(10, 0, 26100), machine="ARM64")
    assert result.supported
    assert result.architecture_supported
    assert result.architecture == "ARM64"


def test_disabled_update_service_maps_to_0x80070422(tmp_path: Path):
    checker = PreflightChecker(
        tmp_path,
        platform_probe=lambda: detect_windows_platform(
            os_name="nt", version=(10, 0, 26100), machine="AMD64"
        ),
        service_probe=lambda: (
            ServiceInfo("wuauserv", "Stopped", "Disabled", True),
            ServiceInfo("BITS", "Stopped", "Manual", True),
        ),
        connectivity_probe=lambda: ConnectivityInfo(True, True, False, "ok"),
        speech_probe=lambda language: _speech(language, SpeechComponentState.MISSING),
        audio_probe=_audio,
        captions_probe=lambda: True,
    )
    report = checker.run("en-US")
    assert not report.can_start
    assert report.error_code == ERROR_WINDOWS_UPDATE_DISABLED
    issue = report.issues[0]
    assert "open-services" in issue.actions
    assert "copy-repair-instructions" in issue.actions


def test_store_policy_and_network_are_distinct_failures(tmp_path: Path):
    base = dict(
        platform_probe=lambda: detect_windows_platform(
            os_name="nt", version=(10, 0, 26100), machine="AMD64"
        ),
        service_probe=lambda: (
            ServiceInfo("wuauserv", "Running", "Manual", True),
            ServiceInfo("BITS", "Running", "Manual", True),
        ),
        speech_probe=lambda language: _speech(language, SpeechComponentState.MISSING),
        audio_probe=_audio,
        captions_probe=lambda: True,
    )
    store = PreflightChecker(
        tmp_path,
        connectivity_probe=lambda: ConnectivityInfo(True, False, True, "policy"),
        **base,
    ).run("pt-BR")
    network = PreflightChecker(
        tmp_path,
        connectivity_probe=lambda: ConnectivityInfo(False, False, False, "offline"),
        **base,
    ).run("pt-BR")
    assert store.error_code == "STORE_POLICY_DISABLED"
    assert network.error_code == "NETWORK_UNAVAILABLE"


def test_microphone_denial_only_blocks_microphone_mode(tmp_path: Path):
    checker = PreflightChecker(
        tmp_path,
        platform_probe=lambda: detect_windows_platform(
            os_name="nt", version=(10, 0, 26100), machine="AMD64"
        ),
        service_probe=lambda: (
            ServiceInfo("wuauserv", "Running", "Manual", True),
            ServiceInfo("BITS", "Running", "Manual", True),
        ),
        connectivity_probe=lambda: ConnectivityInfo(True, True, False, "ok"),
        speech_probe=lambda language: _speech(language, SpeechComponentState.INSTALLED),
        audio_probe=lambda **_kwargs: AudioInfo(False, True, 5_000_000_000, "mic denied"),
        captions_probe=lambda: True,
    )
    assert checker.run("zh-CN", requires_microphone=False).can_start
    mic_report = checker.run("zh-CN", requires_microphone=True)
    assert not mic_report.can_start
    assert mic_report.error_code == "MIC_PERMISSION_DENIED"


def test_service_probe_parses_json_and_handles_failures(monkeypatch):
    import subprocess

    monkeypatch.setattr("yida_ai.system.preflight.os.name", "nt")

    def success(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            [],
            0,
            '[{"Name":"wuauserv","State":"Stopped","StartMode":"Disabled"},'
            '{"Name":"BITS","State":"Running","StartMode":"Manual"}]',
            "",
        )

    update, bits = check_update_services(runner=success)
    assert update.disabled
    assert bits.state == "Running"

    def failure(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 1, "", "blocked")

    unknown = check_update_services(runner=failure)
    assert all(not item.available for item in unknown)


def test_connectivity_reports_catalog_separately(monkeypatch):
    monkeypatch.setattr("yida_ai.system.preflight.os.name", "nt")

    class Response:
        def close(self):
            return None

    def opener(url, **_kwargs):
        if "storeedgefd" in url:
            raise OSError("catalog blocked")
        return Response()

    result = check_connectivity(opener=opener, store_policy_probe=lambda: None)
    assert result.internet is True
    assert result.microsoft_catalog is None
    assert result.store_policy_disabled is None


def test_missing_live_captions_and_low_disk_are_blocking(tmp_path: Path):
    checker = PreflightChecker(
        tmp_path,
        platform_probe=lambda: detect_windows_platform(
            os_name="nt", version=(10, 0, 26100), machine="AMD64"
        ),
        service_probe=lambda: (
            ServiceInfo("wuauserv", "Running", "Manual", True),
            ServiceInfo("BITS", "Running", "Manual", True),
        ),
        connectivity_probe=lambda: ConnectivityInfo(True, True, False, "ok"),
        speech_probe=lambda language: _speech(language, SpeechComponentState.INSTALLED),
        audio_probe=lambda **_kwargs: AudioInfo(True, True, 1, "low"),
        captions_probe=lambda: False,
    )
    report = checker.run("en-US")
    assert {item.code for item in report.issues} == {"LIVE_CAPTIONS_MISSING", "DISK_LOW"}


def test_unknown_model_is_nonblocking_and_repair_text_is_explicit(tmp_path: Path):
    checker = PreflightChecker(
        tmp_path,
        platform_probe=lambda: detect_windows_platform(
            os_name="nt", version=(10, 0, 26100), machine="AMD64"
        ),
        service_probe=lambda: (
            ServiceInfo("wuauserv", "Running", "Manual", True),
            ServiceInfo("BITS", "Running", "Manual", True),
        ),
        connectivity_probe=lambda: ConnectivityInfo(None, None, None, "unknown"),
        speech_probe=lambda language: _speech(language, SpeechComponentState.UNKNOWN),
        audio_probe=_audio,
        captions_probe=lambda: True,
    )
    report = checker.run("zh-CN")
    assert report.can_start
    assert report.issues[0].code == "CAPTION_MODEL_UNVERIFIED"
    instructions = repair_instructions("zh-CN")
    assert ERROR_WINDOWS_UPDATE_DISABLED in instructions
    assert "不会自动更改服务" in instructions


def test_live_captions_component_probe_uses_system_root(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("yida_ai.system.preflight.os.name", "nt")
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    executable = tmp_path / "System32" / "LiveCaptions.exe"
    executable.parent.mkdir()
    assert not live_captions_component_present()
    executable.write_bytes(b"fixture")
    assert live_captions_component_present()


def test_non_windows_and_unknown_architecture_are_reported_truthfully():
    non_windows = detect_windows_platform(os_name="posix", machine="x86_64")
    unsupported_arch = detect_windows_platform(
        os_name="nt", version=(10, 0, 26100), machine="x86"
    )
    assert not non_windows.supported
    assert not unsupported_arch.architecture_supported
    assert "不支持" in unsupported_arch.detail


def test_audio_and_disk_probe_combines_independent_states(tmp_path: Path, monkeypatch):
    class Usage:
        free = 900_000_000

    monkeypatch.setattr("yida_ai.system.preflight.shutil.disk_usage", lambda _path: Usage())
    monkeypatch.setattr("yida_ai.system.preflight._microphone_permission", lambda: False)
    monkeypatch.setattr("yida_ai.system.preflight._audio_endpoint_available", lambda: True)
    result = check_audio_and_disk(data_dir=tmp_path)
    assert result.free_disk_bytes == 900_000_000
    assert result.microphone_permission is False
    assert "磁盘空间不足" in result.detail


def test_invalid_service_json_and_single_service_are_safe(monkeypatch):
    import subprocess

    monkeypatch.setattr("yida_ai.system.preflight.os.name", "nt")
    invalid = check_update_services(
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "not json", "")
    )
    assert all(item.state == "unknown" for item in invalid)
    single = check_update_services(
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, '{"Name":"BITS","State":"Running","StartMode":"Auto"}', ""
        )
    )
    assert single[0].state == "unknown"
    assert single[1].start_mode == "Auto"


def test_windows_repair_shortcuts_only_open_explicit_targets(monkeypatch):
    calls = []
    monkeypatch.setattr("yida_ai.system.preflight.os.name", "nt")
    monkeypatch.setattr(
        "yida_ai.system.preflight.subprocess.Popen",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )
    open_services_console()
    open_windows_update()
    open_microphone_settings()
    assert [item[0] for item in calls] == [
        ["services.msc"],
        ["explorer.exe", "ms-settings:windowsupdate"],
        ["explorer.exe", "ms-settings:privacy-microphone"],
    ]
    assert all(item[1]["shell"] is False for item in calls)
