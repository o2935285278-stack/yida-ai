# Architecture and data flow

```text
Windows Live Captions
        |
LiveCaptions Translator
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

## Boundaries

- `adapters/captions`: the `CaptionSource` contract plus source-specific schemas
  and discovery. Core code sees only `CaptionEvent`.
- `core`: normalization, conversation and concurrency; no UI or upstream database fields.
- `providers`: replaceable LLM and future translation APIs.
- `retrieval`: replaceable retrieval interface; current implementation is deterministic keyword ranking.
- `storage`: local generic history schema and export.
- `ui`: Tk widgets and main-thread polling. Worker threads never update widgets.
- `config`: languages, scenes and serializable settings.

Each caption and AI request has a unique ID. Results are released in request order. A session generation changes on clear; results carrying an earlier generation/session ID are discarded. The work queue is bounded and drops obsolete queued work rather than growing indefinitely.
