# Yida AI (译答 AI)

> Hear the conversation, consult your material, and get a reply you can actually say.

Yida AI is a Windows-oriented, real-time multilingual knowledge-assisted reply system. It connects to Windows Live Captions through [LiveCaptions Translator](https://github.com/SakiRinn/LiveCaptions-Translator), keeps short conversational context, retrieves relevant passages from local documents, and asks a configured AI provider for a grounded reply.

This is a **v0.1.0-beta** project. It is not a speech-recognition engine and does not promise perfect translation or zero latency.

[简体中文说明](README.zh-CN.md)

## Responsibilities

- **Windows Live Captions** performs on-device speech recognition for system audio or microphone input.
- **LiveCaptions Translator** is the default caption/translation source and stores the records read by `LiveCaptionsTranslatorSource`.
- **Yida AI** adds caption normalization, deduplication, conversation context, document retrieval, AI reply suggestions, citations, privacy controls, history and export.

No upstream source file is bundled or modified. The companion integration is an
independently written, read-only `LiveCaptionsTranslatorSource`. See
[upstream attribution](docs/UPSTREAM.md) and
[integration notes](docs/LIVECAPTIONS_TRANSLATOR.md).

## Features

- Uniform `CaptionSource` interface with `LiveCaptionsTranslatorSource` and
  `MockCaptionSource`, both emitting stable `CaptionEvent` values
- Original text, translation, current question, suggested reply, reply-language output and citations
- General, business, sales, customer service, technical support, interview, language learning and custom scenes
- Translation-only, automatic suggestion, every-caption suggestion and confirm-before-generate modes
- Configurable context window (15 turns by default)
- OpenAI-compatible APIs, including DeepSeek, plus an offline deterministic mock provider
- TXT and Markdown knowledge; extractable-text PDF is experimental
- Bounded asynchronous request queue, ordered results and stale-session rejection
- Optional local history, retention policy, clear, export and document deletion

Verified language configurations are Simplified Chinese (`zh-CN`), English (`en-US`) and Brazilian Portuguese (`pt-BR`). Other languages depend on upstream providers and are experimental until tested.

## Requirements

- Windows 11 (the integration and packaged build target)
- Python 3.11–3.14 for source use
- Windows Live Captions and LiveCaptions Translator for real captions

The mock demo works without LiveCaptions Translator, a microphone, network access or an API key.

## Install from source

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m yida_ai --mock examples\captions\demo.jsonl
```

For an offline end-to-end console smoke test:

```powershell
.\.venv\Scripts\python.exe -m yida_ai --headless-demo --mock examples\captions\demo.jsonl --data-dir .local-smoke
```

## Configure real captions and AI

1. Enable Windows Live Captions and select computer audio or microphone input.
2. Install and run LiveCaptions Translator.
3. Start Yida AI. If auto-detection does not find `translation_history.db`, select it in Settings.
4. Keep `mock` for a no-cost offline demonstration, or select `openai-compatible`.
5. Enter the API URL and model. Supply the API key only for the current process:

```powershell
$env:YIDA_AI_API_KEY = "your-private-key"
python -m yida_ai
```

DeepSeek example values are `https://api.deepseek.com/chat/completions` and a currently supported chat model name. Check the provider's official documentation before use because endpoints, model availability and pricing can change.

The key is never serialized into `config.json`. Do not commit `.env`, local data, imported knowledge or build-time secrets.

## Data and privacy

Private data is stored under `%LOCALAPPDATA%\YidaAI` by default, not in the repository. You can override it with `--data-dir` or `YIDA_AI_DATA_DIR`. Depending on configuration, the current caption, recent context and retrieved excerpts are sent to the selected AI provider. See [PRIVACY.md](PRIVACY.md).

## Development and release commands

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m yida_ai --mock examples\captions\demo.jsonl
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_sensitive.ps1
```

Architecture, data flow and extension points are documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Release status is tracked in [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).

## Known limitations

- Windows 11 is the verified operating system; there is no direct microphone/STT engine in Yida AI.
- LiveCaptions Translator database compatibility is isolated; an upstream schema
  change requires updating only `LiveCaptionsTranslatorSource`.
- Keyword retrieval is deterministic but less semantic than an embedding-based retriever.
- PDF extraction works only for PDFs with extractable text and is marked experimental.
- AI suggestions can be wrong. Verify facts and do not use them as professional, legal, medical or financial advice.

## License

Apache License 2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
