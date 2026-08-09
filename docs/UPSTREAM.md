# Upstream audit and modifications

Audit date: 2026-08-09.

The locally inspected LiveCaptions Translator source version was `1.7.1300.1822`. Its project metadata identifies SakiRinn as author and copyright 2024 SakiRinn and contributors. Its `LICENSE` is Apache License 2.0. The official repository is https://github.com/SakiRinn/LiveCaptions-Translator and also declares Apache-2.0.

No upstream C# source, icons, translations, binary or private configuration is
copied into this repository. No upstream file is modified. A marker scan found
none of the upstream UI Automation implementation identifiers in the public
Python source. Yida AI adds an independently written Python read-only
`LiveCaptionsTranslatorSource` plus conversation, retrieval, provider, history
and UI code. It is an independent companion project; references to the upstream
name describe compatibility and do not imply endorsement.
