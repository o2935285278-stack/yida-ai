from pathlib import Path

from yida_ai import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_is_per_user_and_has_only_yida_product_shortcuts():
    content = (ROOT / "installer" / "YidaAI.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in content
    assert "DefaultDirName={localappdata}\\Programs\\YidaAI" in content
    icon_lines = [
        line for line in content.splitlines() if line.startswith("Name:") and "Filename:" in line
    ]
    production_icons = [line for line in icon_lines if "译答 AI QA" not in line]
    qa_icons = [line for line in icon_lines if "译答 AI QA" in line]
    assert len(production_icons) == 2
    assert len(qa_icons) == 2
    assert all("YidaAI.exe" in line for line in icon_lines)
    assert all("LiveCaptions Translator.exe" not in line for line in icon_lines)
    assert any("Tasks: desktopicon" in line for line in icon_lines)


def test_installer_has_three_languages_and_version_metadata():
    content = (ROOT / "installer" / "YidaAI.iss").read_text(encoding="utf-8")
    assert f'#define AppVersion "{__version__}"' in content
    assert "VersionInfoVersion={#AppNumericVersion}" in content
    assert 'Name: "english"; MessagesFile: "compiler:Default.isl"' in content
    assert 'Name: "chinesesimplified"' in content
    assert 'Name: "brazilianportuguese"' in content
    assert "{cm:CreateDesktopIcon}" in content
    assert "chinesesimplified.LaunchYidaAI=启动译答 AI" in content
    assert "brazilianportuguese.LaunchYidaAI=Iniciar o Yida AI" in content
    assert (ROOT / "installer" / "languages" / "ChineseSimplified.isl").is_file()
    assert (ROOT / "installer" / "languages" / "INNO_SETUP_LICENSE.txt").is_file()


def test_packaged_executable_uses_version_resource():
    content = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    version_resource = (ROOT / "installer" / "version_info.txt").read_text(encoding="utf-8")
    assert "--version-file installer/version_info.txt" in content
    numeric = tuple(int(part) for part in __version__.split("-")[0].split(".")) + (0,)
    assert f"filevers={numeric}" in version_resource
    assert f"ProductVersion', '{__version__}'" in version_resource


def test_windows_bundle_packages_runtime_license_texts():
    content = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "CPython-LICENSE.txt" in content
    assert "PyInstaller-COPYING.txt" in content
    assert "pypdf-LICENSE.txt" in content


def test_build_pipeline_reserves_secure_unsigned_and_signed_modes():
    windows_build = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    installer_build = (ROOT / "scripts" / "build_installer.ps1").read_text(
        encoding="utf-8"
    )
    signing = (ROOT / "scripts" / "signing.ps1").read_text(encoding="utf-8")
    combined = windows_build + installer_build + signing
    assert 'ValidateSet("Unsigned", "Signed")' in windows_build
    unsigned_message = "5b2T5YmN5a6J6KOF5YyF5pyq6L+b6KGM5Y+v5L+h5Luj56CB562+5ZCN44CC"
    assert unsigned_message in windows_build
    assert unsigned_message in installer_build
    assert "/fd SHA256" in signing
    assert "/tr $TimestampUrl /td SHA256" in signing
    assert "& $SignTool verify /pa /all /v $Path" in signing
    assert "FormalRelease" in installer_build
    assert "ThirdPartyLctResigned = $false" in signing
    for secret in ("pfx_password", "certificate_password", "token_password"):
        assert secret not in combined.casefold()


def test_installer_sources_only_the_parameterized_lct_executable():
    content = (ROOT / "installer" / "YidaAI.iss").read_text(encoding="utf-8")
    assert 'Source: "{#LctExecutable}"' in content
    for private_name in ("setting.json", "translation_history.db", "config.json", "history.db"):
        assert private_name not in content


def test_build_outputs_are_gitignored():
    content = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "build/" in content
    assert "dist/" in content
    assert "setting.json" in content
