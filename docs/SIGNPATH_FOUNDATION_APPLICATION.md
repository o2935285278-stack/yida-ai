# SignPath Foundation application record

Status: **submitted by the maintainer on 2026-08-13; awaiting review**. This is
not evidence of approval, an issued certificate, or a signed release. The
maintainer personally provided private contact details, confirmed the current
terms, and submitted the application; those private values are not recorded in
this repository.

## Project identity

- Project name: Yida AI (译答 AI)
- Suggested project handle: `yida-ai`
- Repository: <https://github.com/o2935285278-stack/yida-ai>
- Release: <https://github.com/o2935285278-stack/yida-ai/releases/tag/v0.2.2-beta>
- License: Apache License 2.0
- Maintainer: [`@o2935285278-stack`](https://github.com/o2935285278-stack)
- Private applicant name and email: **maintainer must enter privately in the
  application form; do not commit them here**

## Short description

Yida AI is an early-beta Windows desktop application that turns captions from
Windows Live Captions and LiveCaptions Translator into a bounded multilingual
conversation timeline. It adds duplicate filtering, recent context, local
document retrieval, translation display, and suggested replies from an AI
provider configured by the user. The verified language scope is Simplified
Chinese, US English, and Brazilian Portuguese.

The application does not implement its own speech-recognition engine, does not
capture raw microphone audio, and is not a security, exploitation, monitoring,
or circumvention tool.

## Why signing is requested

The public `v0.2.2-beta` installer is intentionally unsigned and Windows may
show an unknown-publisher or SmartScreen warning. Signing is requested to make
future Windows releases traceable to the public repository and its automated
GitHub Actions build. Signing is not presented as proof of translation or AI
accuracy and is not expected to remove SmartScreen reputation warnings
immediately.

## Current maturity and reputation

This is a newly public, early-beta project maintained by one person. The project
does not claim an established user count, download count, star count, company
history, or independent review. If the project does not yet meet SignPath
Foundation's reputation threshold, the maintainer will continue accumulating
public commits, releases, issues and genuine user feedback before applying
again. No repeated or misleading applications will be submitted.

## Source, release, and verification evidence

- Current unsigned release: `v0.2.2-beta`
- Release source commit: `80e850bd826884b29144ed718eb9b67a80451cfd`
- Installer SHA-256:
  `4f5593860d49797204176196302b9eb16c610c2de7058e71cfc4f1e54b07e900`
- Release assets include `SHA256SUMS.txt` and a CycloneDX 1.5 SBOM.
- The public release page states that the installer is unsigned.
- Local interactive-desktop verification completed 141 tests. GitHub-hosted
  Windows tests exercise Python 3.11 and 3.13; two Tk layout tests are skipped
  on the non-interactive runner and are covered by local verification.
- The release-candidate workflow checks locked dependency hashes, dependency
  licenses, the official upstream LCT and Inno Setup hashes, packaged smoke
  behavior, SBOM generation, final checksums, and Microsoft Defender scanning.
- CodeQL, dependency review, Dependabot, secret scanning and push protection are
  configured.

See [VERIFICATION.md](VERIFICATION.md),
[REPOSITORY_SECURITY.md](REPOSITORY_SECURITY.md), and the public GitHub Actions
runs for evidence.

## Privacy and system behavior

Windows Live Captions performs speech recognition. Yida AI reads caption text,
not raw audio. When the user enables and configures an external AI provider, the
current caption, bounded recent context, scene rules, and relevant local
document excerpts may be sent to that provider. The privacy notice is displayed
during onboarding and in settings. AI can remain disabled, the mock provider
works offline, local conversation-history storage is off by default, and saved
API keys are opt-in and protected with Windows DPAPI CurrentUser.

Yida AI has no telemetry service. Connectivity probes and user-selected AI or
translation services are documented in [PRIVACY.md](../PRIVACY.md). The per-user
installer creates application files and optional shortcuts; it provides a
normal uninstaller. User data behavior and manual deletion are documented.

## Third-party and proprietary-code statement

The Yida AI source and build scripts are published under Apache-2.0. The
installer includes an unmodified LiveCaptions Translator `1.7.1300.1822`
executable from its official Apache-2.0 release, locked to SHA-256
`62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31`.
Runtime components and their licenses are recorded in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and
[DEPENDENCIES.md](DEPENDENCIES.md).

No proprietary Yida AI component is distributed. User-selected external AI and
translation services are network services, not bundled source or binaries, and
remain governed by their providers' terms and privacy policies.

## Signing scope

The proposed SignPath configuration may sign only binaries maintained and
built from this repository:

1. `dist/YidaAI/YidaAI.exe`
2. the final Yida AI installer after the application EXE is signed

The configuration must **not** sign, modify, or present as original:

- LiveCaptions Translator or any of its EXE/DLL files;
- CPython, Tcl/Tk, PyInstaller bootloader, pypdf, or other upstream runtime
  files;
- Microsoft system components or user-provided files.

The final signed installer may contain the clearly attributed, unmodified and
unsigned upstream LCT binary as permitted by the applicable policy. The nested
signing rules must select Yida AI's own EXE explicitly and exclude upstream
files.

## Team and approval roles

The project currently has one maintainer. The same real GitHub account is listed
for all responsibilities; this is not an assertion of independent review.

- Committer/author: `@o2935285278-stack`
- Reviewer for external contributions: `@o2935285278-stack`
- Signing-request approver: `@o2935285278-stack`

Every signing request must require manual approval. If additional trusted
maintainers join, roles and review rules will be separated and documented.

## Trusted build and proposed release process

1. A protected version tag triggers a GitHub-hosted Windows runner.
2. Actions check out the exact public commit and install hash-locked build
   dependencies.
3. The workflow verifies third-party hashes and builds `YidaAI.exe` from source.
4. The unsigned application artifact is uploaded to GitHub Actions before a
   SignPath signing request is submitted with origin verification.
5. After manual approval, the signed Yida AI application is verified.
6. The installer is built without rebuilding the signed application.
7. The unsigned installer is uploaded before the separate installer-signing
   request.
8. After manual approval, SHA-256 Authenticode signatures, RFC 3161 timestamps,
   SignTool verification, Defender results, SBOM and final checksums are checked.
9. A new `v0.2.3-beta` Release is published. `v0.2.2-beta` remains unchanged as
   the historical unsigned release.

The SignPath workflow remains disabled until SignPath Foundation supplies real
organization, project, policy, and artifact-configuration identifiers. API
tokens may only be stored in GitHub Secrets. See
[CODE_SIGNING_POLICY.md](../CODE_SIGNING_POLICY.md) and
[the disabled workflow](../.github/workflows/signpath-release.yml).

## Submission record and next steps

- [x] The maintainer personally reviewed and accepted the current SignPath
      Foundation terms.
- [x] GitHub MFA was confirmed enabled; recovery information remains private.
- [x] Private applicant contact details were entered directly into the
      application form and were not committed.
- [x] Repository, release, privacy, license, and signing-scope links were
      rechecked before submission.
- [x] The early project history and limited reputation were stated
      honestly.
- [x] The application excludes LCT and other upstream binaries from the Yida AI
      signature scope.
- [x] The maintainer personally submitted the application on 2026-08-13.
- [ ] Wait for a real SignPath Foundation decision without repeatedly
      resubmitting.
- [ ] If approved, enter only the actual SignPath identifiers as GitHub
      Variables/Secrets, enable the signing workflow, and publish the first
      signed build under a new `v0.2.3-beta` tag.
- [ ] Add a passkey or another GitHub recovery method where practical.
