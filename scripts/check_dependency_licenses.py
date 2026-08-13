from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements-build-win-py313.txt"
EXPECTED = {
    "altgraph": "MIT",
    "packaging": "Apache-2.0 OR BSD-2-Clause",
    "pefile": "MIT",
    "pyinstaller": "GPL-2.0-or-later WITH Bootloader-exception",
    "pyinstaller-hooks-contrib": "Apache-2.0 AND GPL-2.0-or-later (file-specific)",
    "pypdf": "BSD-3-Clause",
    "pywin32-ctypes": "BSD-3-Clause",
    "setuptools": "MIT",
}


def locked_packages() -> dict[str, str]:
    packages: dict[str, str] = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ ]+)", line)
        if match:
            packages[match.group(1).casefold()] = match.group(2)
    return packages


def main() -> int:
    packages = locked_packages()
    missing = sorted(set(EXPECTED) - set(packages))
    unexpected = sorted(set(packages) - set(EXPECTED))
    if missing or unexpected:
        raise SystemExit(
            f"Dependency license review required: missing={missing}, unexpected={unexpected}"
        )
    for name, version in sorted(packages.items()):
        print(f"{name}=={version}: {EXPECTED[name]}")
    print("Dependency license allowlist passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
