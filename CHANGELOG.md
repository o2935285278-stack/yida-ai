# Changelog

All notable changes follow Keep a Changelog conventions.

## [0.1.0-beta] - 2026-08-09

### Added

- Generic `CaptionSource`, conversation, retrieval, AI provider, storage and UI layers.
- `LiveCaptionsTranslatorSource` and deterministic `MockCaptionSource`.
- Verified `zh-CN`, `en-US` and `pt-BR` configurations and eight scene templates.
- Grounded TXT/Markdown retrieval with citations; experimental extractable-text PDF support.
- Bounded asynchronous reply queue, ordered delivery and stale-session rejection.
- Privacy controls, retention, clear, export, safe configuration and public sample fixtures.
- Automated tests, Windows packaging, CI and release/security documentation.

### Changed

- Renamed and propagated the caption boundary to the product-level
  `CaptionSource` terminology; legacy `adapter` configuration migrates on load.
- Documented a research-only future `WindowsCaptionSource` based on Windows Live
  Captions and UI Automation, explicitly without adding an independent speech
  recognition or audio-capture engine to this beta.
