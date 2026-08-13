# Privacy policy

Yida AI is local-first for caption-text processing, retrieval and optional
history. Windows speech recognition is local; external translation and AI
providers are not. This policy describes v0.2.2-beta behavior as implemented.

## Data flow

| Part | Receives | Where processing occurs |
| --- | --- | --- |
| Windows Live Captions | System audio or microphone selected in Windows | Windows local recognition model |
| LiveCaptions Translator (LCT) | Recognized caption text | Separate LCT process and any translation provider the user selects |
| Yida AI local pipeline | Source/translated text, recent context and imported documents | This Windows account |
| OpenAI-compatible AI | Only when configured: current caption, recent context, scene/language instructions and retrieved excerpts | The endpoint selected by the user |

Yida AI does not capture audio or open the microphone itself. Windows Live
Captions handles audio and produces text. Yida AI reads text output through the
LCT database adapter. Pausing Yida AI stops it processing new caption events;
Windows and LCT may continue until the user stops them separately.

## Local data

New installations keep history **off by default**. `%LOCALAPPDATA%\YidaAI` may
contain:

- `config.json`: non-secret settings; API keys are excluded
- `api-key.dpapi`: optional DPAPI CurrentUser ciphertext if the user enables key storage
- `history.db`: captions, translations, replies and citations only when history is enabled
- `knowledge/`: copies of documents the user explicitly imports
- rotating operational logs that exclude full AI payloads and caption/document bodies

Change the location with `--data-dir` or `YIDA_AI_DATA_DIR`. Existing user
settings are respected during upgrades; changing the new-install default does
not silently delete or disable an existing history choice.

## Data sent outside the computer

When `openai-compatible` is selected, Yida AI sends:

- the latest source and translated caption text;
- up to the configured number of recent caption/translation turns;
- source, display and reply languages, reply length and scene instruction; and
- up to three relevant excerpts from imported documents, with local document names.

This request is sent to the configured endpoint. Official DeepSeek and OpenAI
endpoints process data under their own terms; a custom OpenAI-compatible endpoint
is controlled by its operator. Yida AI does not proxy those requests. The
provider's answer returns to Yida AI and may be saved locally only if history is
enabled. **Translation-only** mode and the deterministic `mock` provider make no
AI request.

LCT is a separate third-party process. Depending on its settings, it may send
raw caption text to a translation provider such as Google or another service.
Yida AI does not read, copy or change LCT's provider selection, API key or
`setting.json`. Review LCT and the selected translation provider's privacy terms.

During preflight diagnostics Yida AI may make simple connectivity requests to
Microsoft's connectivity-test and Store catalog endpoints. These requests carry
normal network metadata such as the public IP address but no captions, document
contents, AI key or conversation history.

## API keys and logs

An AI key can be supplied in `YIDA_AI_API_KEY` for the current process or saved
only after the user selects DPAPI storage. DPAPI CurrentUser ciphertext is
decryptable only under the same Windows account. Keys are never serialized to
ordinary JSON, examples, history, diagnostics or application logs. Provider
errors redact the configured key, Bearer tokens and credential-shaped values.

Do not import private documents or enable cloud AI/translation for sensitive
conversations unless you are authorized to transmit that data.

## Telemetry and updates

Yida AI has no analytics, advertising identifier, usage telemetry, automatic
crash upload or application auto-update service in v0.2.2-beta. Network access
is limited to the user-selected AI service, LCT's independent translation path,
and the Microsoft diagnostic probes described above.

## Delete or stop processing

- Select Mock or translation-only mode to stop Yida AI AI-provider requests.
- Pause Yida AI to stop processing new text; stop Windows Live Captions/LCT to
  stop their audio, caption and translation paths.
- Use **Clear Key** to delete `api-key.dpapi`.
- Use **Clear history** to delete saved history rows; disable history to prevent new rows.
- Delete imported documents individually from the knowledge library.
- Uninstalling removes program files but preserves user-created data by default.
  Delete `%LOCALAPPDATA%\YidaAI` manually for a complete Yida AI data reset.

LCT may create its own settings and caption database beside its executable or in
an external installation. Remove those through LCT or its documented data path;
Yida AI deliberately does not delete third-party data.

## Release-package boundary

Release packages exclude `setting.json`, `translation_history.db`, Yida AI
`config.json`, history databases, knowledge documents, exports, logs, API keys
and user profiles. The installer includes only a hash-verified, unmodified LCT
executable plus license/attribution material; it never includes an LCT user key.
