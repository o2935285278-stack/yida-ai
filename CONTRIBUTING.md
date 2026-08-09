# Contributing

Contributions are welcome for isolated adapters, providers, retrieval implementations, tests, accessibility and documentation.

1. Do not commit real captions, resumes, customer data, API keys, databases or absolute user paths.
2. Create a virtual environment and install `.[dev]`.
3. Keep core models language- and scene-neutral.
4. Add deterministic tests that do not call paid or real APIs.
5. Run `python -m pytest`, `python -m ruff check .` and `scripts/check_sensitive.ps1`.
6. Explain upstream-derived code and its license in the pull request.

Use UTF-8 for all text. New adapters must fail with a user-understandable message and must not terminate unrelated processes.
