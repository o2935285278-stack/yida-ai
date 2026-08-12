# Security policy

## Supported version

Security fixes target the latest `0.1.x` beta release.

## Reporting

Do not open a public issue containing API keys, private captions, documents or personal data. Contact the repository maintainer privately through the security reporting channel configured on GitHub. Include reproduction steps with sanitized fixtures.

## Operational guidance

- Install only from a trusted release or build from source.
- Keep API keys in the process environment or use the in-app Windows DPAPI
  CurrentUser option. Rotate any accidentally exposed key.
- Treat imported documents and conversation exports as sensitive user files.
- Configure only HTTPS API endpoints from providers you trust.
- Review packaged dependency notices before redistributing a binary.
