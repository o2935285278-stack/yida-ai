from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from check_dependency_licenses import EXPECTED, locked_packages

ROOT = Path(__file__).resolve().parents[1]
LCT_HASH = "62a5c9ac04fa48ec89a28168bb5835745dd332497ca1ef6184498e6565b4cb31"


def _git_state() -> tuple[str, bool]:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip(), bool(status.stdout.strip())


def _component(name: str, version: str, license_id: str, *, role: str) -> dict[str, object]:
    normalized = re.sub(r"[-_.]+", "-", name).casefold()
    return {
        "type": "library",
        "name": name,
        "version": version,
        "purl": f"pkg:pypi/{normalized}@{version}",
        "licenses": [{"license": {"name": license_id}}],
        "properties": [{"name": "yida-ai:role", "value": role}],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="0.2.2-beta")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Generate test-only SBOM metadata for an explicitly dirty local tree.",
    )
    args = parser.parse_args()
    commit, dirty = _git_state()
    if dirty and not args.allow_dirty:
        raise SystemExit(
            "Refusing release SBOM for a dirty tree; "
            "commit or pass --allow-dirty for testing."
        )
    created = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    components = [
        _component(name, version, EXPECTED[name], role="runtime" if name == "pypdf" else "build")
        for name, version in sorted(locked_packages().items())
    ]
    components.extend(
        [
            {
                "type": "framework",
                "name": "CPython",
                "version": platform.python_version(),
                "licenses": [{"license": {"id": "PSF-2.0"}}],
                "properties": [{"name": "yida-ai:role", "value": "runtime"}],
            },
            {
                "type": "application",
                "name": "LiveCaptions Translator",
                "version": "1.7.1300.1822",
                "hashes": [{"alg": "SHA-256", "content": LCT_HASH}],
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "externalReferences": [
                    {
                        "type": "distribution",
                        "url": "https://github.com/SakiRinn/LiveCaptions-Translator/releases/tag/v1.7.1300.1822",
                    }
                ],
                "properties": [
                    {"name": "yida-ai:ownership", "value": "unmodified third-party component"},
                    {"name": "yida-ai:code-signing-scope", "value": "excluded"},
                ],
            },
        ]
    )
    serial_seed = hashlib.sha256(f"yida-ai:{args.version}:{commit}".encode()).digest()[:16]
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.UUID(bytes=serial_seed)}",
        "version": 1,
        "metadata": {
            "timestamp": created,
            "component": {
                "type": "application",
                "name": "Yida AI",
                "version": args.version,
                "bom-ref": f"pkg:github/o2935285278-stack/yida-ai@{commit}",
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "properties": [{"name": "git:commit", "value": commit}],
            },
        },
        "components": components,
    }
    document["metadata"]["component"]["properties"].append(
        {"name": "git:dirty", "value": str(dirty).lower()}
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"SBOM={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
