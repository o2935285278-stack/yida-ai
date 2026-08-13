# v0.2.2-beta release checklist

- [x] First-run checks Windows version/architecture and the current recognition model
- [x] Live Captions model is distinguished from display, input and TTS language packages
- [x] Windows Update, BITS and `0x80070422` receive truthful repair guidance
- [x] Store/catalog and general connectivity are not conflated
- [x] Start all is idempotent, bounded and does not silently restart user-stopped components
- [x] Only Yida AI-owned processes are closed; an external LCT process is preserved
- [x] CaptionSource isolates LCT schema from conversation, retrieval, AI, history and UI
- [x] MockCaptionSource supports deterministic end-to-end tests and demonstrations
- [x] zh-CN, en-US and pt-BR settings are independent and six directions are tested
- [x] Three scenario presets and three complete interface catalogs are present
- [x] Diagnostics export excludes captions, replies, imported text, keys and usernames
- [x] Settings layout scrolls and screenshots cover 100%, 125%, 150% and 200% DPI
- [x] API keys use optional DPAPI storage and never enter JSON configuration
- [x] New installations default to no conversation-history persistence
- [x] Onboarding and settings explain the exact AI data boundary before opt-in storage
- [x] 141 tests pass under strict ResourceWarning handling; coverage is 73.01%
- [x] Ruff and `git diff --check` pass
- [x] Current/untracked candidates and all Git commits pass the sanitized sensitive-data scan
- [x] QA install, actual `0.2.1-beta` to `0.2.2-beta` upgrade, packaged smoke and uninstall pass
- [x] A 600-second packaged stability run shows no memory or handle growth trend
- [x] Duplicate packaged launch exits 2 while the first instance stays alive
- [x] Application and installer metadata report `0.2.2-beta`
- [x] LCT `1.7.1300.1822` remains unmodified at the locked SHA-256
- [x] LCT comes from the official immutable release URL and is never sourced from user data
- [x] CPython, PyInstaller and pypdf runtime license texts are packaged
- [x] Unsigned and signed build modes exist; formal unsigned Release is blocked
- [x] Signed mode orders EXE sign, installer build/sign, verification, then final hash
- [x] No signing credential is embedded; LCT is never re-signed with the Yida AI certificate
- [x] SignPath Foundation workflow is disabled by default and limited to tag builds
- [x] Actions are SHA-pinned, permissions are minimal, and `pull_request_target` is absent
- [x] CODEOWNERS, Dependabot, CodeQL and dependency-review configuration are present
- [x] Dependency license audit, CycloneDX SBOM, SHA-256 checksums and Defender scan are automated
- [x] README, privacy, security, conduct, contributing, signing policy and third-party notices are present
- [x] Current candidate is truthfully documented as unsigned
- [ ] Change the private GitHub repository to Public only after explicit user confirmation
- [ ] Publish the unsigned `v0.2.2-beta` only after explicit user confirmation
- [ ] Submit the SignPath Foundation application only after explicit user confirmation

The three unchecked operations are deliberately blocked. No workflow, local
script or verification step may perform them implicitly.

Detailed evidence is recorded in [VERIFICATION.md](VERIFICATION.md).
