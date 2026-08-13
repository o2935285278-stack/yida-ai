# Repository security recommendations

Apply these settings only after the repository is public and CI has completed at
least once, so the real check names are available:

- Require pull requests for `main`; require the Windows test, CodeQL and
  dependency-review checks; dismiss stale approvals after changes.
- Require conversation resolution, block force pushes and branch deletion, and
  require linear history if it matches the maintainer workflow.
- Enforce CODEOWNERS review for workflow, installer and `.signpath` changes.
- Enable private vulnerability reporting, secret scanning, push protection,
  Dependabot alerts/security updates and dependency graph.
- Enable release immutability when available. Never replace an existing tag or
  asset; issue a new version for every rebuilt binary.
- Limit Actions to trusted actions, retain SHA pinning and use read-only default
  `GITHUB_TOKEN` permissions. Signing is tag-only and has no
  `pull_request_target` path.
- Require MFA for the maintainer. Recovery codes must be handled personally and
  never shared with Codex, committed, logged or uploaded.

Every release must trace to one tag/commit and contain installer, CycloneDX SBOM,
`SHA256SUMS.txt`, truthful signature status and known limitations. Local/manual
binaries must not be substituted for the CI-produced signed artifact.

