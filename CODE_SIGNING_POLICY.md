# Code signing policy

Free code signing provided by SignPath.io, certificate by SignPath Foundation

Repository: <https://github.com/o2935285278-stack/yida-ai>

Privacy policy: [PRIVACY.md](PRIVACY.md)

## Current status

The `v0.2.2-beta` release candidate is unsigned. It must be labelled
**Unsigned Beta** and must not be represented as a SignPath-signed release.
SignPath configuration in this repository remains disabled and contains only
placeholders until the project and signing policies are approved.

## Maintainers and signing roles

The project currently has one maintainer, `@o2935285278-stack`. This account is
the only current SignPath team member and, if the Foundation application is
approved, will be listed truthfully as Committer, Reviewer and Approver. There
is no claim of independent two-person review. The roles will be separated and
this document updated if additional trusted maintainers join.

Changes to GitHub Actions workflows, installer scripts and `.signpath/` require
review by `@o2935285278-stack` through CODEOWNERS. The account must use GitHub
multi-factor authentication. Recovery codes and signing credentials are never
stored in this repository.

## Signing and release process

1. A version tag identifies one immutable source commit.
2. GitHub-hosted Windows runners build the application from that commit using
   the checked-in dependency lock and verify the locked LCT binary hash.
3. The unsigned `YidaAI.exe` artifact is uploaded before a SignPath request.
4. After policy approval, the returned signed application is verified, then the
   installer is built from it. The locked upstream LCT binary remains untouched.
5. The installer artifact is uploaded and submitted under the installer policy.
6. SignTool verification, malware scanning, SBOM generation and SHA-256 checksum
   generation must succeed before a signed GitHub Release is published.
7. No file is modified after its final signature is applied.

Signing requests are limited to version tags matching the release workflow.
Pull requests and untrusted forks cannot access the SignPath token or request a
signature. A failed or rejected verification blocks the signed release.

## Signing scope

The Yida AI certificate may cover:

- `YidaAI.exe`, built from this repository; and
- the final Yida AI installer, built by the trusted release workflow.

It never covers or re-signs `LiveCaptions Translator.exe`, Microsoft language
components, or any other upstream binary. LCT keeps its upstream filename,
version, SHA-256, license and original signature state inside the installer.

## Security contact

Do not publish credentials, private captions or exploitable details in an
issue. Use GitHub's **Report a vulnerability** private security advisory for
this repository. If that channel is unavailable, contact
`@o2935285278-stack` privately through GitHub without attaching sensitive data.

