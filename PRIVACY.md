# Privacy

Yida AI is local-first for caption processing, retrieval and history, but a configured external AI provider is not local.

## Local data

By default `%LOCALAPPDATA%\YidaAI` may contain:

- `config.json`: non-secret settings; API keys are excluded
- `history.db`: captions, translations, replies and citations when history is enabled
- `knowledge/`: documents explicitly imported by the user

Change the location with `--data-dir` or `YIDA_AI_DATA_DIR`. Disable history in Settings, set a retention period, clear all history, export a copy, or delete individual knowledge documents. Deleting a document followed by reindexing removes it from the in-memory keyword index.

## Data sent outside the computer

When `openai-compatible` is selected, Yida AI sends the current caption, translated caption, configured number of recent turns, scene instruction, requested languages, and relevant retrieved excerpts to the configured API endpoint. The provider may retain or process that data under its own policy. The mock provider sends nothing.

LiveCaptions Translator or its configured translation provider may separately process translation data. Review that project's settings and privacy terms.

## Secrets and logs

The API key is read from `YIDA_AI_API_KEY` or held for the current process after entry in the UI. It is not serialized to configuration, examples, logs or history. Yida AI does not log full API payloads by default.

Do not import private documents or enable cloud AI for sensitive conversations unless you are authorized to transmit that data.
