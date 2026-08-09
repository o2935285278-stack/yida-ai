# Roadmap

## After v0.1.0-beta

- Research and, only after separate validation, implement `WindowsCaptionSource`
  using Windows Live Captions and Windows UI Automation. It would continue to
  use Windows on-device speech packages rather than adding a speech engine.
- Keep `LiveCaptionsTranslatorSource` as a supported compatibility source after
  an independent Windows source becomes stable.
- OCR and meeting-application caption sources
- Optional embedding-based semantic retrieval
- Secret-store integration using Windows Credential Manager
- Better per-card confirmation and answer editing
- Accessibility review and UI localization
- Signed installer, automatic updates and broader Windows version validation
- Additional language validation suites

These are intentionally outside the first beta and should not be advertised as completed.

The independent Windows path, compatibility risks and required test matrix are
recorded in [docs/WINDOWS_CAPTION_SOURCE_FEASIBILITY.md](docs/WINDOWS_CAPTION_SOURCE_FEASIBILITY.md).
