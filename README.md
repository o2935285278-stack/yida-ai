# Yida AI (译答 AI)

> Hear the conversation, consult your material, and get a reply you can actually say.

Yida AI is a multilingual real-time translation and document-assisted reply tool
based on Windows Live Captions and translation services. It reads Windows captions
directly, with [LiveCaptions Translator](https://github.com/SakiRinn/LiveCaptions-Translator)
available as a compatibility option, and
keeps bounded conversational context, retrieves relevant passages from local
documents, and asks a user-configured AI provider for a grounded reply.

This is a **v0.2.4-beta development preview** project. It is not a speech-recognition engine and does
not promise perfect translation or zero latency. The current release candidate
is **unsigned** and must not be represented as signed.

The 0.2.4 UI preview simplifies the conversation page and nests diagnostics inside
Settings. Automatic caption-window hiding is experimental and opt-in; live
hidden-window recognition and the microphone quick toggle remain incomplete.
See [verification limitations](docs/VERIFICATION-0.2.4-preview.md).

Official repository: <https://github.com/o2935285278-stack/yida-ai>. Use only
its [Releases](https://github.com/o2935285278-stack/yida-ai/releases)
and verify the published SHA-256. Reposted binaries are not official builds.

[简体中文说明](README.zh-CN.md)

## Responsibilities

- **Windows Live Captions** performs on-device speech recognition for system audio or microphone input.
- **WindowsCaptionSource** reads the Windows caption window via UI Automation in the Yida process. Translation uses your configured AI endpoint and key.
- **LiveCaptions Translator** is an optional compatibility source; existing configurations are preserved on upgrade. Select `windows-captions` in settings to use the new source.
- **Yida AI** adds caption normalization, deduplication, conversation context, document retrieval, AI reply suggestions, citations, privacy controls, history and export.

The Windows installer redistributes an unmodified upstream LCT executable as a
clearly identified Apache-2.0 third-party background component. No upstream
source file is copied or modified. Process management and the read-only
`LiveCaptionsTranslatorSource` are independently written by Yida AI. See
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
- Opt-in local history (off on new installs), retention policy, clear, export and document deletion
- Restored recent history across restarts, with 15 turns by default
- Complete Simplified Chinese, US English and Brazilian Portuguese interfaces,
  with independent interface, speech, translation and reply languages
- Windows DPAPI CurrentUser protection for an optionally saved API key
- In-app AI connection test with safe error categories

Verified presets are Simplified Chinese (`zh-CN`), English (`en-US`) and
Brazilian Portuguese (`pt-BR`). Custom BCP-47 codes can be entered, but this is
not a claim that every language works: recognition depends on Windows Live
Captions, translation depends on LCT and its service, and the AI reply language
can be selected separately.

## Requirements

- Windows 11 (the integration and packaged build target)
- Python 3.11–3.14 for source use
- Windows Live Captions; the release installer includes the verified LCT component

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

## Install and first run

1. Require Windows 11 22H2 (build 22621) or newer; Windows 10 is unsupported for this caption chain.
2. Run `YidaAI-0.2.2-beta-win-x64-setup.exe`. The unsigned beta may trigger an
   unknown-publisher warning.
3. Keep the per-user installation directory. One **译答 AI** Start menu entry is
   created; the desktop shortcut is optional.
4. Start Yida AI and choose the interface language on the isolated first screen;
   no caption, LCT or AI process starts before that choice.
5. Choose the speech, reading and reply languages. Only the current speech
   language's Windows component is checked.
6. Continue through the Windows caption, LCT and AI tests; document import is optional.
7. If automatic Windows caption startup fails, use the explicit `Win+Ctrl+L`
   fallback. Yida AI does not keep toggling the shortcut in the background.

Speech components are downloaded only through the
[official Windows Live Captions flow](https://support.microsoft.com/windows/use-live-captions-to-better-understand-audio);
they are not bundled with Yida AI. Installed components are skipped automatically.

## Configure real captions and AI

1. Install Yida AI and start the single **译答 AI** shortcut.
2. If captions did not start automatically, press Win+Ctrl+L, download the
   required local speech pack, and select the source language.
3. Yida AI starts its bundled LCT component in the background. For first-time translation configuration, click **Open LCT settings** in Yida AI.
4. If a compatible external LCT is already running, Yida AI reuses it instead of launching another copy.
5. If auto-detection does not yet find `translation_history.db`, leave Yida AI open; it continues detecting dynamically.
6. Keep `mock` for a no-cost offline demonstration, or select `openai-compatible`.
7. Enter the API URL, model and key. Select **Protect Key with Windows DPAPI**
   to reuse it after restart, then click **Test AI connection**. The key is
   encrypted for the current Windows user in `%LOCALAPPDATA%\YidaAI\api-key.dpapi`
   and never written to `config.json`. Environment-only use remains supported:

```powershell
$env:YIDA_AI_API_KEY = "your-private-key"
python -m yida_ai
```

DeepSeek example values are `https://api.deepseek.com/chat/completions` and a currently supported chat model name. Check the provider's official documentation before use because endpoints, model availability and pricing can change.

The result displays the provider and model, never the key. Do not commit `.env`,
local data, imported knowledge or build-time secrets.

## Import documents

Open **Settings & documents**, import a `.txt`, `.md`, or extractable-text
`.pdf`, and rebuild the index if needed. Recognized text, translation, AI reply
and document citations are displayed separately. If evidence is insufficient,
the assistant must say that the documents do not contain enough evidence.

## Data and privacy

Private data is stored under `%LOCALAPPDATA%\YidaAI` by default, not in the repository. You can override it with `--data-dir` or `YIDA_AI_DATA_DIR`. Depending on configuration, the current caption, recent context and retrieved excerpts are sent to the selected AI provider. See [PRIVACY.md](PRIVACY.md).

## Development and release commands

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m yida_ai --mock examples\captions\demo.jsonl
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 `
  -LctExecutable "C:\path\to\LiveCaptions Translator.exe"
powershell -ExecutionPolicy Bypass -File scripts\check_sensitive.ps1
python scripts\check_dependency_licenses.py
```

The release workflow uses `requirements-build-win-py313.txt` with
`pip --require-hashes`, verifies official LCT and Inno Setup downloads,
generates a CycloneDX SBOM and SHA-256 list, and performs a Defender scan. See
[repository security](docs/REPOSITORY_SECURITY.md).

Unsigned builds are the default and print `当前安装包未进行可信代码签名。`. Signed builds select a certificate from the Windows certificate store without placing private credentials in source:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 `
  -LctExecutable "C:\path\to\LiveCaptions Translator.exe" `
  -SigningMode Signed -CertificateThumbprint "CERTIFICATE_THUMBPRINT" -FormalRelease
```

The signed pipeline uses SHA-256, an RFC 3161 timestamp, SignTool verification, and computes the final installer SHA-256 only after signing. Verification failure blocks a formal Release. PFX/private keys, passwords, hardware-token details, and cloud credentials must stay out of source, logs, and installers; CI may use only repository Secrets or a trusted cloud-signing service. The upstream LCT executable is never re-signed with a Yida AI certificate.

Architecture, data flow and extension points are documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Release status is tracked in [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).

Public-project policies and operational help:

- [Privacy](PRIVACY.md) and [security reporting](SECURITY.md)
- [Code signing policy](CODE_SIGNING_POLICY.md)
- [SignPath Foundation application record](docs/SIGNPATH_FOUNDATION_APPLICATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Windows language support](docs/WINDOWS_LANGUAGE_SUPPORT.md)
- [Contributing](CONTRIBUTING.md) and [code of conduct](CODE_OF_CONDUCT.md)

The public `v0.2.2-beta` release is unsigned. SignPath workflow files are disabled
placeholders until Foundation approval; they are not evidence of a valid
certificate or signed release.

## Known limitations

- Windows 11 is the verified operating system; there is no direct microphone/STT engine in Yida AI.
- The beta installer is unsigned, so Windows may display a reputation warning.
- LCT remains an independent third-party process underneath the unified Yida AI interface.
- LiveCaptions Translator database compatibility is isolated; an upstream schema
  change requires updating only `LiveCaptionsTranslatorSource`.
- Keyword retrieval is deterministic but less semantic than an embedding-based retriever.
- PDF extraction works only for PDFs with extractable text and is marked experimental.
- AI suggestions can be wrong. Verify facts and do not use them as professional, legal, medical or financial advice.

System-caption hiding is opt-in and defaults to visible. Yida AI restores a
pre-existing visible window on exit and closes only processes it started. If
safe hiding cannot be confirmed, it restores the window.

Simultaneous mixed Chinese/English/Portuguese recognition is not claimed or
enabled; select one actual Windows caption language at a time.

## Troubleshooting

- `0x80070422`: Windows Update or BITS is disabled, so Windows cannot download the Live Captions recognition model. Use Diagnostics & repair to open Services and Windows Update; Yida AI never changes service settings silently.
- A language pack or TTS voice shown as installed is not proof that the Live Captions local recognition model is installed. Open Live Captions and complete its own model-download prompt.

- **No captions:** confirm Windows 11 22H2+, press Win+Ctrl+L, install the speech
  pack, and use **Redetect caption source**.
- **No translation:** open translator settings and verify LCT's target language
  and translation provider. Yida AI never reads LCT's API key.
- **No Key / 401 / 404 / 429:** resave the key, verify model/endpoint, check
  quota, then run **Test AI connection**.
- **Timeout or service error:** captions continue; check the network/provider.
- **History not restored:** history is off on new installs; enable **Save history** and check retention days.

## Uninstall

Use Windows **Settings → Apps → Installed apps → Yida AI → Uninstall**. Program
files and shortcuts are removed. User configuration, encrypted key, history and
documents under `%LOCALAPPDATA%\YidaAI` are preserved by default; delete that
folder manually only when you intentionally want to erase the data.

## License

Apache License 2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
