# LiveCaptions Translator integration

Yida AI v0.1.0-beta deliberately reuses the existing Windows caption and translation path.

1. Windows Live Captions recognizes system audio or microphone input using Windows capabilities.
2. LiveCaptions Translator captures/translates captions and writes its caption history.
3. Yida AI opens `translation_history.db` in read-only mode and maps recognized schema aliases to `CaptionEvent`.

The adapter searches user-independent common locations and the `LIVECAPTIONS_TRANSLATOR_DB` environment variable. A user can always select the database manually. It does not read the upstream API key/configuration and does not start, kill or control the upstream process.

If no database exists, the GUI remains open with a configuration message. Use mock mode to test without the upstream application.

Supported column aliases are deliberately contained in `src/yida_ai/adapters/captions/livecaptions_translator.py`. If an upstream release changes the schema, update and test only that adapter.
