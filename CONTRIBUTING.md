# Contributing

Contributions are welcome for isolated adapters, providers, retrieval implementations, tests, accessibility and documentation.

1. Do not commit real captions, resumes, customer data, API keys, databases or absolute user paths.
2. Create a virtual environment and install `.[dev]`.
3. Keep core models language- and scene-neutral.
4. Add deterministic tests that do not call paid or real APIs.
5. Run `python -m pytest`, `python -m ruff check .` and `scripts/check_sensitive.ps1`.
6. Explain upstream-derived code and its license in the pull request.

Use UTF-8 for all text. New adapters must fail with a user-understandable message and must not terminate unrelated processes.

## Pull requests

- Work from a branch and keep each pull request focused.
- Add a changelog entry for user-visible behavior.
- Do not commit generated executables, installers, databases, logs, screenshots
  containing private content or locally downloaded LCT files.
- SignPath, workflow and installer changes are CODEOWNERS-protected. A pull
  request from a fork never receives signing credentials.
- Maintainers may ask for a clean test fixture, dependency-license evidence or
  an upstream source/hash before accepting a binary-boundary change.

By contributing, you agree that your contribution is licensed under Apache-2.0
and that you have the right to submit it. Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
and report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.
