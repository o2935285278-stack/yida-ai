import json
import zipfile

from yida_ai.adapters.captions import MockCaptionSource
from yida_ai.system.diagnostics import (
    _enum_safe,
    _safe_path,
    _sha256,
    collect_diagnostics,
    diagnostic_text,
    export_diagnostic_bundle,
)


def test_diagnostic_bundle_excludes_private_content(tmp_path):
    snapshot = collect_diagnostics(
        app_version="0.2.2-beta",
        preflight=None,
        windows=None,
        lct=None,
        source=MockCaptionSource(),
        startup=None,
        ai_state="unconfigured",
        knowledge_document_count=2,
    )
    text = diagnostic_text(snapshot)
    assert "api_key" not in text.casefold()
    assert "conversation" not in text.casefold()
    destination = export_diagnostic_bundle(snapshot, tmp_path / "diagnostics.zip")
    with zipfile.ZipFile(destination) as archive:
        assert set(archive.namelist()) == {"README.txt", "diagnostics.json"}
        parsed = json.loads(archive.read("diagnostics.json"))
    assert parsed["knowledge_document_count"] == 2


def test_diagnostic_helpers_hash_and_redact_paths(tmp_path):
    target = tmp_path / "component" / "tool.exe"
    target.parent.mkdir()
    target.write_bytes(b"fixture")
    assert _safe_path(target) == "…/component/tool.exe"
    assert len(_sha256(target)) == 64
    assert _sha256(tmp_path / "missing.exe") == ""
    assert _enum_safe([target, ("value",)]) == ["…/component/tool.exe", ["value"]]
