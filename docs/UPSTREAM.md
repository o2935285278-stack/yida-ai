# Upstream audit and modifications

Audit date: 2026-08-09.

The locally inspected LiveCaptions Translator source version was `1.7.1300.1822`. Its project metadata identifies SakiRinn as author and copyright 2024 SakiRinn and contributors. Its `LICENSE` is Apache License 2.0. The official repository is https://github.com/SakiRinn/LiveCaptions-Translator and also declares Apache-2.0.

No upstream C# source, icons, translations or private configuration is copied
into this repository. No upstream file is modified. A marker scan found
none of the upstream UI Automation implementation identifiers in the public
Python source. Yida AI adds an independently written Python read-only
`LiveCaptionsTranslatorSource` plus conversation, retrieval, provider, history
and UI code.

The release installer redistributes the verified, unmodified x64 upstream
executable as a separate third-party background component. The build script
accepts its path as a parameter and verifies file version `1.7.1300.1822` and
SHA-256 `62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31`.
Only that single binary is copied; adjacent settings, databases and user files
are excluded. The installation includes Apache-2.0 licensing and attribution.
This compatibility and redistribution do not imply upstream endorsement.
