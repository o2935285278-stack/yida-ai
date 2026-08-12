from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from yida_ai.adapters.captions import CaptionSource
from yida_ai.components import LctComponentManager
from yida_ai.system.preflight import PreflightReport
from yida_ai.system.startup import StartupSnapshot
from yida_ai.system.windows_captions import WindowsCaptionManager


@dataclass(frozen=True, slots=True)
class DiagnosticSnapshot:
    generated_at: str
    app_version: str
    windows: dict[str, object]
    services: dict[str, object]
    connectivity: dict[str, object]
    speech_model: dict[str, object]
    audio: dict[str, object]
    live_captions: dict[str, object]
    lct: dict[str, object]
    caption_source: dict[str, object]
    startup: dict[str, object]
    ai_state: str
    knowledge_document_count: int


def collect_diagnostics(
    *,
    app_version: str,
    preflight: PreflightReport | None,
    windows: WindowsCaptionManager | None,
    lct: LctComponentManager | None,
    source: CaptionSource,
    startup: StartupSnapshot | None,
    ai_state: str,
    knowledge_document_count: int,
) -> DiagnosticSnapshot:
    windows_status = windows.refresh() if windows else None
    lct_status = lct.status() if lct else None
    source_status = source.status()
    lct_path = lct_status.executable_path if lct_status else None
    return DiagnosticSnapshot(
        datetime.now(UTC).isoformat(),
        app_version,
        asdict(preflight.platform) if preflight else {"state": "unchecked"},
        {
            "windows_update": asdict(preflight.windows_update) if preflight else "unchecked",
            "bits": asdict(preflight.bits) if preflight else "unchecked",
        },
        asdict(preflight.connectivity) if preflight else {"state": "unchecked"},
        asdict(preflight.speech_model) if preflight else {"state": "unchecked"},
        asdict(preflight.audio) if preflight else {"state": "unchecked"},
        _enum_safe(asdict(windows_status)) if windows_status else {"state": "mock"},
        {
            **(_enum_safe(asdict(lct_status)) if lct_status else {"state": "mock"}),
            "executable_path": _safe_path(lct_path),
            "sha256": _sha256(lct_path),
        },
        {
            "available": source_status.available,
            "activity": source_status.activity.value,
            "database_readable": source_status.database_readable,
            "process_running": source_status.process_running,
            "live": source_status.live,
            "last_caption_at": _iso(source_status.last_caption_at),
            "last_translation_at": _iso(source_status.last_translation_at),
            "detail": source_status.detail,
        },
        _enum_safe(asdict(startup)) if startup else {"state": "unchecked"},
        ai_state,
        knowledge_document_count,
    )


def diagnostic_text(snapshot: DiagnosticSnapshot) -> str:
    return json.dumps(_enum_safe(asdict(snapshot)), ensure_ascii=False, indent=2)


def export_diagnostic_bundle(snapshot: DiagnosticSnapshot, destination: Path) -> Path:
    """Export state only; never includes keys, knowledge text, history, or conversation text."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="yida-diagnostic-") as temp:
        root = Path(temp)
        (root / "diagnostics.json").write_text(
            diagnostic_text(snapshot) + "\n", encoding="utf-8"
        )
        (root / "README.txt").write_text(
            "This bundle contains component state only. It excludes API keys, documents, "
            "conversation text, captions, translations, replies, and user names.\n",
            encoding="utf-8",
        )
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(root.iterdir()):
                archive.write(item, item.name)
    return destination


def _safe_path(path: Path | None) -> str:
    if path is None:
        return ""
    return f"…/{path.parent.name}/{path.name}"


def _sha256(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _enum_safe(value: object) -> object:
    if isinstance(value, dict):
        return {key: _enum_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_safe(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Path):
        return _safe_path(value)
    return value
