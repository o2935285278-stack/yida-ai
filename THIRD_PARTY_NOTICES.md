# Third-party notices

## LiveCaptions Translator

- Project: LiveCaptions Translator
- Author/copyright: Copyright 2024 SakiRinn and contributors
- Repository: https://github.com/SakiRinn/LiveCaptions-Translator
- Distributed version: `1.7.1300.1822`
- Verified SHA-256: `62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31`
- License verified from that tag and the official repository: Apache License 2.0
- Role: optional compatibility caption/translation source. The default source in
  0.2.3-beta reads Windows Live Captions directly using independently written UI Automation code.

The Windows installer redistributes the unmodified upstream executable under
`components/LiveCaptionsTranslator`. Yida AI starts that separate process in the
background when required, reuses an existing external process, and exposes an
explicit button to show its settings. Yida AI contains independently written
process-management and read-only database-adapter code. It does not modify or
claim ownership of LCT, copy its source, read its API key/configuration, or imply
that the upstream authors endorse Yida AI. There are no modified upstream files.

The installer includes this notice, the Apache-2.0 license text, and a component
manifest containing the redistributed binary version and hash.

## Inno Setup Simplified Chinese language file

- Source: https://github.com/jrsoftware/issrc/blob/main/Files/Languages/ChineseSimplified.isl
- Maintainer identified in the upstream file: Zhenghan Yang (Kira)
- Verified SHA-256: `BF0751FA176569C6FAA2F6E17ED2734617BEF325D5CC06EAE030FDD0258EE778`
- Role: build-time Simplified Chinese messages for the Windows installer.
- License: Inno Setup License; retained at `installer/languages/INNO_SETUP_LICENSE.txt`.

The language file is kept unmodified and is consumed only while compiling the
installer. It is not application runtime code and does not change the selected
Yida AI interface language.

Runtime/development Python packages and their own license texts remain governed by their respective distributions. Release builders should review the generated bundle before distribution.

## comtypes and tkinterdnd2

- comtypes 1.4.16: MIT, https://github.com/enthought/comtypes . Provides Windows
  COM/UI Automation bindings; license bundled as `licenses/comtypes-LICENSE.txt`.
- tkinterdnd2 0.6.3: MIT, https://github.com/Eliav2/tkinterdnd2 . Provides Tk drag
  and drop support; license bundled as `licenses/tkinterdnd2-LICENSE.txt`.

These packages are unmodified dependencies, not copied LCT source code.

## Packaged Python runtime and libraries

The Windows application bundle includes the CPython runtime, PyInstaller
bootloader and pypdf. Their license texts are installed under `licenses/` as
`CPython-LICENSE.txt`, `PyInstaller-COPYING.txt` and `pypdf-LICENSE.txt`.
Build-only packages and their reviewed license expressions are listed in
`docs/DEPENDENCIES.md` and the release CycloneDX SBOM.
