from pathlib import Path

from yida_ai.config.settings import AppSettings

ROOT = Path(__file__).resolve().parents[1]


def test_new_install_is_privacy_preserving_by_default():
    settings = AppSettings()
    assert not settings.privacy.save_history
    assert settings.llm.provider == "mock"


def test_signing_policy_is_truthful_and_excludes_lct():
    policy = (ROOT / "CODE_SIGNING_POLICY.md").read_text(encoding="utf-8")
    assert "# Code signing policy" in policy
    required = "Free code signing provided by SignPath.io, certificate by SignPath Foundation"
    assert required in policy
    assert "o2935285278-stack" in policy
    assert "unsigned" in policy.casefold()
    assert "never covers or re-signs `LiveCaptions Translator.exe`" in policy


def test_signpath_workflow_is_disabled_tag_only_and_has_no_pr_target():
    workflow = (ROOT / ".github" / "workflows" / "signpath-release.yml").read_text(
        encoding="utf-8"
    )
    assert "vars.SIGNPATH_ENABLED == 'true'" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "pull_request_target" not in workflow
    assert "secrets.SIGNPATH_API_TOKEN" in workflow
    pinned_upload = "upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    assert pinned_upload in workflow
    assert "github-artifact-id" in workflow
    assert workflow.index("Upload unsigned application") < workflow.index(
        "Submit YidaAI.exe signing request"
    )
    assert workflow.index("Upload unsigned installer") < workflow.index(
        "Submit installer signing request"
    )


def test_release_inputs_and_dependencies_are_hash_locked():
    lct_fetch = (ROOT / "scripts" / "fetch_lct.ps1").read_text(encoding="utf-8")
    inno_fetch = (ROOT / "scripts" / "install_inno.ps1").read_text(encoding="utf-8")
    lock = (ROOT / "requirements-build-win-py313.txt").read_text(encoding="utf-8")
    lct_hash = "62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31"
    inno_hash = "9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732"
    assert lct_hash in lct_fetch
    assert "v1.7.1300.1822" in lct_fetch
    assert inno_hash in inno_fetch
    assert "innosetup-6.7.3.exe" in inno_fetch
    packages = [line for line in lock.splitlines() if "==" in line and not line.startswith("#")]
    hashes = [line for line in lock.splitlines() if "--hash=sha256:" in line]
    assert len(packages) == len(hashes) == 8


def test_codeowners_protects_signing_and_workflow_files():
    owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert "/.github/workflows/ @o2935285278-stack" in owners
    assert "/.signpath/ @o2935285278-stack" in owners
    assert "/installer/ @o2935285278-stack" in owners


def test_release_sbom_refuses_uncommitted_source_by_default():
    generator = (ROOT / "scripts" / "generate_sbom.py").read_text(encoding="utf-8")
    assert "Refusing release SBOM for a dirty tree" in generator
    assert '"git:dirty"' in generator
