# Dependency audit

Audit date: 2026-08-13. The base runtime uses only the Python standard library.

The Windows CPython 3.13 release build is locked with hashes in
`requirements-build-win-py313.txt`. `scripts/check_dependency_licenses.py`
requires every locked package to appear in the reviewed allowlist; any package
change fails until it receives a new review.

| Package | Audited version | Purpose | Declared license |
| --- | ---: | --- | --- |
| pypdf | 6.18.1 | Extractable-text PDF support | BSD-3-Clause |
| PyInstaller | 6.22.0 | Windows build only | GPL-2.0-or-later with bootloader exception |
| altgraph | 0.17.5 | PyInstaller build dependency | MIT |
| packaging | 26.3 | Build dependency | Apache-2.0 OR BSD-2-Clause |
| pefile | 2024.8.26 | Windows PE build dependency | MIT |
| pyinstaller-hooks-contrib | 2026.6 | Build hooks | Apache-2.0 and GPL-2.0-or-later, file-specific |
| pywin32-ctypes | 0.2.3 | Windows build dependency | BSD-3-Clause |
| setuptools | 84.0.0 | Build backend | MIT |
| Ruff | 0.16.2 | Development lint/format only | MIT |
| pytest | 9.1.1 | Tests only | MIT |
| pytest-cov | 7.1.0 | Test coverage only | MIT |
| coverage | 7.15.4 | Coverage engine only | Apache-2.0 |

The release installer redistributes the unmodified LiveCaptions Translator
`1.7.1300.1822` executable under Apache-2.0. LCT is not linked into Yida AI and
is excluded from project signing. See `THIRD_PARTY_NOTICES.md`.

Inno Setup 6.7.3 is a build-only compiler under the Inno Setup License. CI
downloads its immutable official JRSoftware release and verifies SHA-256
`9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732`.
The installer also retains the license for the unmodified Simplified Chinese
language file.

Before every binary publication, review PyInstaller's warning file and bundle,
run the license allowlist, generate the CycloneDX SBOM, scan the binaries and
verify that the locked versions/hashes still match their official sources.
