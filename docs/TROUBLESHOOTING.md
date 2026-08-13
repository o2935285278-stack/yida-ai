# Troubleshooting

Start with **Diagnostics & repair** in Yida AI. Its exported report deliberately
excludes caption text, replies, document contents, API keys and usernames.

## Windows Live Captions has no text

1. Confirm Windows 11 22H2 (build 22621) or newer.
2. Press `Win+Ctrl+L` and keep the Windows caption window visible while testing.
3. Select the same spoken language in Windows and Yida AI.
4. Complete the model download inside Windows Live Captions. A display language,
   keyboard or text-to-speech voice is not the same component.
5. Play system audio or allow microphone access in Windows privacy settings.

Error `0x80070422` normally means Windows Update or BITS is disabled. Yida AI
does not change these services. Use its diagnostic links to open Services and
Windows Update, then retry the official model download.

## Captions exist but Yida AI receives nothing

- Confirm LCT is running and has produced `translation_history.db`.
- Use **Redetect caption source**. Detection continues while Yida AI is open.
- If LCT is installed elsewhere, select the database manually.
- Do not copy another user's database or `setting.json` into the install folder.

## Translation is blank or stale

Open LCT settings and check its source/target languages, provider and network
state. Yida AI reads LCT output in read-only mode and cannot inspect or repair
the LCT API key. Raw recognized text remains available when translation fails.

## AI does not reply

- `mock` is offline and deterministic; use it to test the Yida AI pipeline.
- For `openai-compatible`, verify the HTTPS endpoint, model and key, then use
  **Test AI connection**.
- HTTP 401/403 means key or permission failure; 404 means endpoint/model mismatch;
  429 means quota/rate limiting. Timeouts do not stop caption collection.
- Translation-only mode intentionally makes no AI reply request.

## Windows warns about the publisher

The `v0.2.2-beta` candidate is unsigned. Windows may show Unknown Publisher or
SmartScreen. Verify the SHA-256 published beside the official GitHub release.
Do not download a build reposted by an unrelated account. Future SignPath-signed
builds will be labelled separately; an unsigned beta never becomes signed later.

## Reset or remove local data

Use Settings to clear the DPAPI key and history and to delete imported documents.
Uninstall removes program files but preserves `%LOCALAPPDATA%\YidaAI`. Delete
that directory manually only when a complete local-data reset is intended. LCT
may keep its own settings/database separately.

