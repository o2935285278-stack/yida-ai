# 0.2.3-beta local preview verification

Date: 2026-09-12. This is a local, unsigned development preview, not a public release.

## Passed

- 152 tests with `YIDA_GUI_TEST=1`, including real Tk window creation, drag-target
  registration, batch import callback, same-card translation updates and existing
  scaling smoke tests. No automated physical mouse drag was performed.
- Ruff checks on src and tests.
- Dependency license allowlist (including comtypes and tkinterdnd2).
- Synthetic configured-provider request: English-to-Chinese translation 0.89 s;
  English reply generation 0.83 s. One sample each; not a latency guarantee.
  No personal documents/conversation were sent and no credential was printed.
- Windows UI Automation caption text acquisition previously observed with
  synthetic SAPI speech on this development machine.
- Windows caption language selection controls exercised for zh-CN, en-US, pt-BR.
  This is not a claim of multilingual recognition accuracy or mixed-language support.
- Installer and frozen executable mock smoke build succeeded. A final rebuild
  is required after any further source changes; build output includes installer hash.

## Build limitations / release gates

- Local Python 3.11.15 build, not the pinned Python 3.13 release environment.
- No trusted signature or signer, no timestamp, no SignTool signature verification
  in unsigned mode. Do not label this a signed/formal release.
- Windows UI Automation IDs depend on Windows version. Cross-version testing,
  extended real-audio tests, and end-to-end packaged native/network tests remain.
- Existing configs retain their source. Select windows-captions to opt in;
  the adapter must not reuse any LCT key.
- Windows LiveCaptions.exe remains required. LCT compatibility binary remains in
  the installer but is not started by the default native source.
- Continuous speech segmentation and late corrections need longer recordings;
  the bounded translation queue is not a guarantee against overload.
- No GitHub push or upload performed.
