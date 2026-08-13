# v0.2.2-beta verification record

Verification date: 2026-08-13

Host: Windows 11 build 26200, x64, Python 3.14.6, PyInstaller 6.22.0 and
Inno Setup 6.7.3.

## Release gates

| Check | Result |
| --- | --- |
| Automated tests | 141 passed with `-W error::ResourceWarning` |
| Coverage | 73.01%; required floor 73% passed |
| Static checks | Ruff and `git diff --check` passed |
| Language scope | zh-CN, en-US and pt-BR; all six translation directions tested |
| Startup | Unified preflight and idempotent start-all state machine tested |
| Windows checks | Build/architecture, model, Update/BITS, 0x80070422, disk, audio and microphone covered |
| Caption boundary | LiveCaptionsTranslatorSource and MockCaptionSource emit only CaptionEvent |
| Diagnostics | Privacy-safe report and ZIP export tested; no captions, replies, knowledge text or key included |
| GUI evidence | Main/settings/diagnostics checked at 100%, 125%, 150% and 200% across all three locales |
| QA installer | First install, actual `0.2.1-beta` to `0.2.2-beta` upgrade, packaged smoke and uninstall all exited 0 |
| Upgrade safety | Program removed on uninstall; isolated user data remained present |
| Stability | Packaged GUI stayed alive for 600 seconds with 20 samples |
| Stability resources | Working set -507,904 B; private memory -110,592 B; handles 211 to 210 |
| Single instance | Second packaged instance exited 2 while the first remained alive |
| LCT integrity | Bundled upstream executable hash matched before build and after QA install |
| Bundle privacy | No config, database, log, DPAPI key, knowledge or LCT user settings packaged |
| Repository privacy | Current files, untracked candidates and all 3 Git commits passed the sanitized sensitive-data scan |
| Dependency licenses | Hash-locked Windows build dependencies passed the allowlisted license audit |
| Workflow validation | All GitHub Actions workflows passed actionlint 1.7.12 |
| Malware scan | Microsoft Defender found no threats in the final application executable or installer |
| GitHub candidate | Ignored/private path and candidate-content checks passed; no remote upload performed by verification |

The 600-second runner originally returned exit 1 because its assertion expected
the already-blocked second instance to remain open. The authoritative process
evidence is `duplicate_exit=2`, first instance alive, and 20 completed samples;
the application behavior passed and the test-harness expectation was incorrect.

## Current host preflight

- Windows 11 build 26200, x64: supported.
- Live Captions recognition component: present.
- Windows Update (`wuauserv`) and BITS: running.
- Microphone permission and audio endpoint: available.
- zh-CN, en-US and pt-BR language checks: available on this host.
- General/catalog connectivity probes: unverified when the probe endpoint did
  not return a definitive result; this is not reported as a false failure.

## Screenshot evidence

- `dist/verification/v0.2.2-main-zh-CN-100.png`
- `dist/verification/v0.2.2-diagnostics-zh-CN-100.png`
- `dist/verification/v0.2.2-main-en-US-125.png`
- `dist/verification/v0.2.2-diagnostics-en-US-125.png`
- `dist/verification/v0.2.2-main-pt-BR-150.png`
- `dist/verification/v0.2.2-settings-pt-BR-150.png`
- `dist/verification/v0.2.2-diagnostics-pt-BR-150.png`
- `dist/verification/v0.2.2-main-zh-CN-200.png`
- `dist/verification/v0.2.2-settings-zh-CN-200.png`
- `dist/verification/v0.2.2-diagnostics-zh-CN-200.png`

These ignored verification artifacts are not source inputs and are not included
in the installer.

## Redistributed component

- Component: LiveCaptions Translator
- Version: `1.7.1300.1822`
- SHA-256: `62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31`
- Upstream: <https://github.com/SakiRinn/LiveCaptions-Translator>
- License: Apache License 2.0
- Packaging: unmodified executable under `components/LiveCaptionsTranslator`
- Yida AI certificate applied to LCT: no

No adjacent `setting.json`, translation database, API key, chat history or other
upstream user file was copied into the installer.

## Code-signing status

| File | Signed | Signer | Digest | Timestamp | SignTool verification |
| --- | --- | --- | --- | --- | --- |
| `YidaAI.exe` | No | empty | none | not applicable | false |
| installer | No | empty | none | not applicable | false |

This beta was built in unsigned mode and is not a formal signed Release. The
pipeline supports a local certificate-store mode and a disabled-by-default
SignPath Foundation mode. Both order application signing before installer build,
installer signing before final hashing, and require SHA-256, an RFC 3161
timestamp and signature verification. No PFX, private key, password, token or
cloud-signing credential is present in source or output.

The SignPath workflow is intentionally inert unless the repository variable
`SIGNPATH_ENABLED` is explicitly set to `true`. It accepts tags only, uses
GitHub-hosted Windows runners, uploads each unsigned artifact before requesting
signing, and never applies the Yida AI certificate to the redistributed LCT
binary. The sole current maintainer, `o2935285278-stack`, is truthfully listed
for the committer, reviewer and approver responsibilities; the project does not
claim independent review.

## Supply-chain evidence

- Windows build dependencies are exact-version and SHA-256 locked in
  `requirements-build-win-py313.txt`.
- GitHub Actions are pinned to immutable commit SHAs and have minimal declared
  permissions. No workflow uses `pull_request_target`.
- Dependabot, CodeQL and dependency-review workflows are configured.
- Release builds generate a CycloneDX 1.5 SBOM, final SHA-256 checksums and a
  Microsoft Defender scan result.
- A test-only local SBOM may be generated from a dirty worktree for validation,
  but it is not a publishable release SBOM. The release workflow refuses that
  state and generates the public SBOM from a committed checkout.
- The clean dependency environment used for the local build contained the
  locked packages. The local interpreter was Python 3.14.6; CI is pinned to
  Python 3.13.15 and uses the same hash lock.

## Final installer candidate

- Path: `dist/installer/YidaAI-0.2.2-beta-win-x64-setup.exe`
- Size: `81,535,089` bytes
- SHA-256: `4F5593860D49797204176196302B9EB16C610C2DE7058E71CFC4F1E54B07E900`
- Application ProductVersion: `0.2.2-beta`
- Authenticode: `NotSigned`

The artifact has not been published as a Release by this verification step.
The repository remains private, the pre-existing draft Release was not changed,
and no SignPath application or signing request was submitted.
