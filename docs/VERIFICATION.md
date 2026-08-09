# v0.1.0-beta verification record

Verification date: 2026-08-09

Host: Windows 11, Python 3.14.6, PyInstaller 6.22.0

## Executed checks

| Check | Command | Result |
| --- | --- | --- |
| Isolated install | `python -m venv .venv` and `.venv\\Scripts\\python.exe -m pip install -e ".[dev]"` | Passed |
| Automated tests | `.venv\\Scripts\\python.exe -m pytest` | 42 passed |
| Lint | `.venv\\Scripts\\python.exe -m ruff check .` | Passed, no warnings |
| Formatting | `.venv\\Scripts\\python.exe -m ruff format .` | Passed |
| Sensitive-data scan | `scripts\\check_sensitive.ps1` | Passed |
| Windows build | `scripts\\build_windows.ps1 -Python .venv\\Scripts\\python.exe` | Passed |
| Packaged offline smoke | Executed by the build script against public JSONL fixture | Passed, exit code 0 |
| Source GUI startup/exit | Automated Tk smoke test | Passed |

Tests cover the `CaptionSource` contract and legacy configuration migration,
normalization, duplicates, sentence merging, progressive revisions, language
combinations, chunking, deterministic ranking and citations, no-source grounding,
history save/restore/disable/clear/retention, mock AI, timeouts,
offline/failure/retry, stale result discard, request ordering, bounded backlog,
missing/corrupt caption database, missing upstream installation, missing key,
corrupt config, source GUI startup/exit and packaged headless startup/exit.

## Build output

The reproducible one-directory Windows application is generated at `dist\\YidaAI\\YidaAI.exe`. The build intentionally excludes local configuration, API keys, history and imported documents. Build and distribution directories are ignored by Git.

## Audit notes

- The public tree contains fictional examples only; the original private project was not copied into the repository.
- No real key, personal candidate profile, conversation database or machine-specific absolute path was found.
- The upstream project/license and independently implemented integration boundary are documented.
- A targeted marker audit found no copied LiveCaptions Translator UI Automation
  implementation in the public Python source. The project reads only its output.
- No WASAPI, Whisper, faster-whisper, whisper.cpp, audio-capture or speech-model
  dependency is present in v0.1.0-beta.
- The base runtime has no third-party dependency; PDF support and development/build dependencies are audited in `DEPENDENCIES.md`.
- PyInstaller warnings were reviewed. Remaining entries are platform-specific or optional modules (for example POSIX modules and optional PDF crypto/image helpers) and do not affect the verified flows.

## Known limitations

- Windows 11 is the only locally verified OS.
- The artifact is an unsigned one-directory build, not an installer.
- Real cloud AI and a real LiveCaptions Translator session were not invoked during automated verification; tests use compatible local fixtures to avoid private data and cost.
- PDF extraction is experimental and does not OCR scanned pages.
- Keyword retrieval is less semantic than a future embedding retriever.
