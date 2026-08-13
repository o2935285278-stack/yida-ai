# Security policy

## Supported version

Security fixes target the latest published `0.2.x` beta. Older beta builds may
receive a fix only when the issue also affects the current version.

## Reporting

Do not open a public issue containing API keys, private captions, documents,
personal data or unpatched exploit details. Use GitHub's **Report a
vulnerability** private security advisory for this repository. If that channel
is unavailable, contact `@o2935285278-stack` privately through GitHub. Include
reproduction steps using sanitized fixtures and state the affected version.

The maintainer will acknowledge a complete report when practical, assess scope,
prepare a fix without exposing reporters or users, and publish an advisory when
users have a safe update path. No bounty or response-time guarantee is offered.

## Operational guidance

- Install only from a trusted release or build from source.
- Keep API keys in the process environment or use the in-app Windows DPAPI
  CurrentUser option. Rotate any accidentally exposed key.
- Treat imported documents and conversation exports as sensitive user files.
- Configure only HTTPS API endpoints from providers you trust.
- Review packaged dependency notices before redistributing a binary.
- Verify release checksums and signing status. `v0.2.2-beta` is unsigned; a
  future SignPath-signed release will be built and verified by the documented CI path.
