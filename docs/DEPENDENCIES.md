# Dependency audit

Audit date: 2026-08-09. The base runtime uses only the Python standard library.

| Package | Audited version | Purpose | Declared license |
| --- | ---: | --- | --- |
| pypdf | 6.15.0 | Optional extractable-text PDF support | BSD-3-Clause |
| PyInstaller | 6.22.0 | Windows build only | GPL-2.0-or-later with the PyInstaller bootloader exception |
| Ruff | 0.16.2 | Development lint/format only | MIT |
| pytest | 9.1.1 | Tests only | MIT |
| pytest-cov | 7.1.0 | Test coverage tooling only | MIT |
| coverage | 7.15.4 | Test coverage engine only | Apache-2.0 |
| setuptools | 84.0.0 | Build backend | MIT |
| Inno Setup | 6.7.3 | Windows installer build only | Inno Setup License |

The release installer additionally redistributes the unmodified
LiveCaptions Translator `1.7.1300.1822` executable under Apache-2.0. See
`THIRD_PARTY_NOTICES.md`; LCT is not linked into the Python application.

Versions above record the environment used for the local beta verification; `pyproject.toml` uses compatible lower bounds. Before publishing a binary, rebuild in CI, review PyInstaller's warning file and generated bundle, and repeat the license/security audit for resolved versions.
