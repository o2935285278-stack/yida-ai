# SignPath placeholders

These files document the intended policy but are not proof that SignPath has
approved the project. The signing workflow stays disabled unless repository
variable `SIGNPATH_ENABLED` is exactly `true`.

After Foundation approval, create two SignPath artifact configurations whose
input root is the ZIP produced by GitHub `upload-artifact`:

1. one configuration that permits only `YidaAI.exe`; and
2. one configuration that permits only
   `YidaAI-0.2.2-beta-win-x64-setup.exe`.

Set organization/project/policy/artifact-configuration identifiers through
GitHub repository variables and put only the API token in the
`SIGNPATH_API_TOKEN` secret. Never commit exported SignPath credentials. Review
the exact configuration in SignPath before enabling the workflow.

