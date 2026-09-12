# v0.2.3-beta

Local preview, unsigned. Do not represent this build as a signed public release.

- Direct Windows Live Captions input through in-process UI Automation; no LCT
  process is needed in the windows-captions mode. Windows Live Captions remains
  the speech recognition engine.
- Translation uses the configured AI endpoint and key. This sends recognized
  text to that provider and consumes its API quota, including translation-only mode.
- Originals appear before translation. Translation updates the same card
  without generating a second reply.
- Background language switching for zh-CN/en-US/pt-BR. A failed switch keeps
  the previous app language and displays manual instructions.
- Independent reply-language selector and conversion of an existing reply.
- Multi-file drag/drop of TXT, Markdown and text PDF. Identical files are reused;
  different same-name files get numbered names. Empty/scanned PDFs are rejected.
- Saved-key hint explicitly explains that a blank field retains the stored key.
- LCT remains an optional compatibility adapter; delayed translation rows are
  rechecked for 60 seconds, bounded to 128 pending records.

## Limits and rollout

UI Automation control IDs depend on Windows versions. This beta requires
Windows 11 and local speech packages; do not claim all Windows builds have been
verified. Speech recognition of mixed languages is not supported.
Existing configurations retain their source choice. Select windows-captions
in Settings to enable the new mode. New installations default to this mode.
Mock translations are explicitly labeled and are not real translations.
Live recognition is segmented after 450 ms without change or 2 seconds of
continuous text. Recognition corrections across finalized segments need
continued real-world testing.
