# LiveCaptions Translator integration

Yida AI v0.2.2-beta deliberately reuses the existing Windows caption and translation path.

1. Windows Live Captions recognizes system audio or microphone input using Windows capabilities.
2. LiveCaptions Translator captures/translates captions and writes its caption history.
3. `LiveCaptionsTranslatorSource` opens `translation_history.db` in read-only
   mode and maps recognized schema aliases to `CaptionEvent`.

Database detection order is: a manually configured path, the
`LIVECAPTIONS_TRANSLATOR_DB` environment variable, the database beside the
currently running LCT executable, the bundled component directory, then common
external LCT locations. This prevents a stale database in a generic location
from hiding the active instance's output. Detection is repeated while the
application runs, so a first-run database can appear without restarting Yida AI.
Connections are read-only and explicitly closed.

`LctComponentManager` first reuses a compatible running external LCT. Otherwise
it starts the verified executable from
`components/LiveCaptionsTranslator/LiveCaptions Translator.exe` without
`shell=True` and hides only the window of the process it started. The UI can
show LCT settings on request. At shutdown, Yida AI never closes an external LCT;
for an owned process it sends a normal window-close request and never force-kills
an uncertain target. `--no-start-lct`, mock and headless modes do not start LCT.

If LCT or its database is missing, the GUI remains open with recovery guidance.
Yida AI never reads or modifies the upstream API key/configuration.

The redistributed x64-with-runtime asset comes from the official
`v1.7.1300.1822` release. Its official GitHub asset digest, local build input and
post-install copy must all equal
`62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31`.
Yida AI never applies its current or future signing certificate to that file.

Supported column aliases are deliberately contained in
`src/yida_ai/adapters/captions/livecaptions_translator.py`. If an upstream release
changes the schema, update and test only `LiveCaptionsTranslatorSource`.
