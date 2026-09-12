# Changelog

All notable changes follow Keep a Changelog conventions.

## [Unreleased]

### 0.2.4-beta UI preview

- Simplified the conversation page and moved diagnostics/tools into Settings.
- Adopted native Windows ttk styling and quieter conversation cards.
- Collapsed message details and preserved history scroll position on new messages.
- Added opt-in owned-window auto-hide with readability checks and restoration.
- Hidden-window live recognition and the microphone quick toggle remain release gates;
  see docs/VERIFICATION-0.2.4-preview.md. This is not a completed formal release.

### 0.2.3-beta development preview

- Added in-process WindowsCaptionSource using Windows Live Captions UI Automation;
  retained the LCT adapter as an optional compatibility source.
- Added asynchronous native translation and late LCT translation updates on the
  existing conversation card without a duplicate reply request.
- Added independent reply-language selection and existing-reply translation.
- Added batch drag/drop TXT, MD and text-PDF import with collision-safe filenames.
- Added background Windows caption-language switching and manual fallback hints.
- Clarified saved-key status and fixed stale startup managers after source changes.
- Fixed UTF-8 license-path discovery when building under Chinese directory names.
- This preview is unsigned; Windows-build compatibility and live API latency need
  further real-world testing before public release.

### Added

- Public-project governance, troubleshooting, Windows-language and code-signing policies.
- Full-history sanitized secret scanning and disabled SignPath/supply-chain CI templates.

### Changed

- New installations keep local conversation history off until the user opts in.
- First-run and settings screens now explain external AI data scope and make
  API-key persistence and history storage explicit choices.

## [0.2.2-beta] - 2026-08-10

### Added

- Windows 11 build/architecture, Live Captions model, Windows Update/BITS,
  `0x80070422`, Microsoft catalog, disk, microphone and audio preflight checks.
- Idempotent Start All orchestration with bounded retry, truthful step states,
  single-instance protection and explicit recovery after user-stopped components.
- A privacy-safe Diagnostics & repair page and export bundle.
- Reserved unsigned/signed Windows build modes with SHA-256, RFC 3161 timestamp,
  SignTool verification and formal-Release blocking.

### Changed

- Model setup now prefers the Windows Live Captions download flow and distinguishes
  recognition models from display/input/TTS language features.
- The supported language-direction configuration now explicitly covers all six
  directions among zh-CN, en-US and pt-BR, including a Chinese-to-Brazilian preset.

## [0.2.1-beta] - 2026-08-09

### Added

- A real first-run wizard that keeps interface, speech, translation and reply
  languages independent and checks only the selected Windows speech component.
- Truthful AI verification states and distinct caption database, process and live-input states.
- English, Simplified Chinese and Brazilian Portuguese installer languages.
- Windows executable and installer version metadata for `0.2.1-beta`.

### Changed

- Windows Live Captions is started automatically at most once per application run;
  a user-closed caption window is not reopened without an explicit retry.
- Conversation output is presented as one card per utterance with the suggested
  answer as the primary action and without duplicate translation blocks.
- Main-window sizing adapts to 1366×768 displays and longer Portuguese text.
- Caption database discovery now prefers the database beside the running LCT
  process over stale files in generic install locations.

## [0.2.0-beta] - 2026-08-09

### Added

- Windows DPAPI CurrentUser API-key persistence outside ordinary JSON settings.
- In-app AI connection test and safe error classification for 401, 404, 429,
  timeouts, invalid JSON, network failures and server errors.
- Restored bounded history context, including translation-only turns.
- Explicit speech, translation, reply and interface language settings.
- Complete `zh-CN`, `en-US` and `pt-BR` UI resources, quick listening-language
  switching and Brazilian-customer, English-customer and Chinese-speaker presets.
- Startup checks for all three Windows speech components with Microsoft settings guidance.
- Windows Live Captions language mismatch detection.
- Explicit LCT “return to background” and opt-in Windows caption-window controls.
- Optional desktop shortcut and expanded release/privacy documentation.

### Changed

- Product language now reflects actual Windows, LCT and selected-service limits.
- API failure logs include a safe category and HTTP status without keys or payloads.
- LCT upstream translation failures no longer discard the recognized source sentence.
- Main and settings layouts now remain readable with longer Brazilian Portuguese labels.

## [0.1.0-beta] - 2026-08-09

### Added

- Generic `CaptionSource`, conversation, retrieval, AI provider, storage and UI layers.
- `LiveCaptionsTranslatorSource` and deterministic `MockCaptionSource`.
- Verified `zh-CN`, `en-US` and `pt-BR` configurations and eight scene templates.
- Grounded TXT/Markdown retrieval with citations; experimental extractable-text PDF support.
- Bounded asynchronous reply queue, ordered delivery and stale-session rejection.
- Privacy controls, retention, clear, export, safe configuration and public sample fixtures.
- Automated tests, Windows packaging, CI and release/security documentation.
- Safe lifecycle management for a bundled, unmodified LiveCaptions Translator
  background component, including external-process reuse and explicit settings access.
- Dynamic caption-database discovery, `--no-start-lct`, Windows first-run guidance
  and an Inno Setup per-user installer.

### Changed

- Renamed and propagated the caption boundary to the product-level
  `CaptionSource` terminology; legacy `adapter` configuration migrates on load.
- Documented a research-only future `WindowsCaptionSource` based on Windows Live
  Captions and UI Automation, explicitly without adding an independent speech
  recognition or audio-capture engine to this beta.
- DeepSeek non-thinking mode and empty-JSON retry fallback for faster, more
  reliable real-time suggestions.
- SQLite connections are now explicitly closed to prevent resource leaks.
