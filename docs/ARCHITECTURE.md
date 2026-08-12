# Architecture and data flow

```text
Windows Live Captions
        |
LiveCaptions Translator <---- LctComponentManager
        |                     reuse/start/hide/show/safe close request
        |
LiveCaptionsTranslatorSource ---- MockCaptionSource
        |                              |
        +-------- CaptionEvent --------+
                       |
              CaptionAssembler
          normalize / merge / dedupe
                       |
              ConversationManager
                       |
      +----------------+----------------+
      |                                 |
KnowledgeRetriever                 ReplyEngine
relevant chunks/citations     bounded worker queue
      |                        ordered/stale checks
      +----------------+----------------+
                       |
            OpenAI-compatible / Mock
                       |
          ReplySuggestion + citations
                       |
              Tk main-thread render
                       |
          optional HistoryStore/export
```

Before this data flow starts, `SystemPreflight` checks the supported Windows
build and architecture, current Live Captions recognition model, Windows Update
and BITS services, connectivity signals, free disk space, microphone permission
and audio endpoint. `StartupOrchestrator` exposes one bounded, idempotent state
machine to both onboarding and the main window. It never turns a user-stopped
component back on during refresh.

## Boundaries

- `adapters/captions`: the `CaptionSource` contract plus source-specific schemas
  and discovery. Core code sees only `CaptionEvent`.
- `components`: lifecycle boundary for the separately installed, unmodified LCT
  executable. It never reads LCT settings or force-terminates a process.
- `core`: normalization, conversation and concurrency; no UI or upstream database fields.
- `providers`: replaceable LLM and future translation APIs.
- `retrieval`: replaceable retrieval interface; current implementation is deterministic keyword ranking.
- `storage`: local generic history schema and export.
- `ui`: Tk widgets and main-thread polling. Worker threads never update widgets.
- `config`: languages, scenes and serializable settings.
- `system`: preflight, diagnostics, single-instance and startup orchestration.

Diagnostics export is a deliberately reduced system snapshot. It contains
component states, versions, hashes and counts, but not caption text, AI replies,
imported knowledge, usernames or API keys.

Each caption and AI request has a unique ID. Results are released in request order. A session generation changes on clear; results carrying an earlier generation/session ID are discarded. The work queue is bounded and drops obsolete queued work rather than growing indefinitely.

The installer places application files under `%LOCALAPPDATA%\Programs\YidaAI`
and LCT under `components\LiveCaptionsTranslator`. Private Yida AI data remains
under `%LOCALAPPDATA%\YidaAI`; LCT data remains owned by LCT. Neither is compiled
into the installer.

## Signing boundary

The Windows build has explicit unsigned and signed modes. Signed mode builds the
application, signs `YidaAI.exe` with SHA-256 and an RFC 3161 timestamp, builds
and signs the installer, verifies both with SignTool, and only then calculates
the installer SHA-256. A failed verification blocks formal Release output.
Credentials are supplied from the Windows certificate store or CI secrets and
are never accepted as source files. The upstream LCT executable is outside this
signing boundary and remains byte-for-byte unchanged.
