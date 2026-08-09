# v0.1.0-beta release checklist

- [x] Independent sanitized `yida-ai` directory; original private project unchanged
- [x] Apache-2.0 upstream license verified; attribution and modifications documented
- [x] `CaptionSource` contract with isolated `LiveCaptionsTranslatorSource`
- [x] `MockCaptionSource` and public fictional fixtures
- [x] Generic languages, scenes, four reply modes and configurable context
- [x] OpenAI-compatible and mock providers; no serialized key or real API tests
- [x] TXT/Markdown retrieval and experimental PDF extraction with citations
- [x] Bounded async queue, ordered results and stale-session discard
- [x] Optional history, retention, clear, export and knowledge deletion
- [x] GUI fields, source/status panels, controls and first-run guidance
- [x] Automated coverage of the 25 requested validation areas
- [x] English and Chinese install/privacy/limitation documentation
- [x] Windows build script, smoke script and GitHub Actions workflow
- [x] Clean virtual-environment install, 42 tests, lint, build and packaged smoke passed
- [x] Sensitive-data, license, dependency and maintainability audit completed
- [x] Local Git repository contains only public files and has a release-preparation commit

Local verification details are recorded in [VERIFICATION.md](VERIFICATION.md). The final item is
checked after the local commit is created; no remote repository or release is created by this work.
