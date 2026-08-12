# Privacy

Yida AI is local-first for caption processing, retrieval and history, but a configured external AI provider is not local.

## Local data

By default `%LOCALAPPDATA%\YidaAI` may contain:

- `config.json`: non-secret settings; API keys are excluded
- `api-key.dpapi`: optional DPAPI CurrentUser ciphertext for the AI API key
- `history.db`: captions, translations, replies and citations when history is enabled
- `knowledge/`: documents explicitly imported by the user

Change the location with `--data-dir` or `YIDA_AI_DATA_DIR`. Disable history in Settings, set a retention period, clear all history, export a copy, or delete individual knowledge documents. Deleting a document followed by reindexing removes it from the in-memory keyword index.

## Data sent outside the computer

When `openai-compatible` is selected, Yida AI sends the current caption, translated caption, configured number of recent turns, scene instruction, requested languages, and relevant retrieved excerpts to the configured API endpoint. The provider may retain or process that data under its own policy. The mock provider sends nothing.

LiveCaptions Translator or its configured translation provider may separately process translation data. Review that project's settings and privacy terms.

The Windows installer includes an unmodified LiveCaptions Translator executable.
It remains a separate third-party process. Yida AI may start it, hide its normal
window, show its settings on request and read `translation_history.db` in
read-only mode. Yida AI does not read or change LCT's API key or `setting.json`.
LCT may create its own private settings and caption database next to the bundled
component or in an external installation. Uninstalling Yida AI preserves
user-created data by default.

## Secrets and logs

The API key is read from `YIDA_AI_API_KEY`, held only for the current process,
or optionally protected with Windows DPAPI CurrentUser. It is never serialized
to ordinary JSON, examples, logs or history. The encrypted file is usable only
by the Windows user that saved it. Yida AI does not log full API payloads and
redacts credential-shaped text from provider error details.

Do not import private documents or enable cloud AI for sensitive conversations unless you are authorized to transmit that data.

Release packages exclude `setting.json`, `translation_history.db`, Yida AI
`config.json`, history databases, knowledge documents, logs and API keys.
