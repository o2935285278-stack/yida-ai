# Windows language support

## Verified scope

Yida AI v0.2.2-beta has explicit presets and tests for:

- Simplified Chinese (`zh-CN`)
- US English (`en-US`)
- Brazilian Portuguese (`pt-BR`)

The UI keeps four values independent: speech/source language, display/translation
language, AI reply language and interface language. Tests cover all six directed
translation pairs among the three presets. This does not claim simultaneous
mixed-language recognition or support for every BCP-47 language.

## Which Windows component is required

Yida AI depends on the offline recognition model used by **Windows Live Captions**.
The following do not prove that model is present:

- Windows display language
- keyboard/basic typing or handwriting
- text-to-speech voice
- a language shown with `0 MB` in the general Languages page

Open Live Captions with `Win+Ctrl+L`, select the spoken language and complete the
download prompt there. Yida AI does not bundle, mirror or redistribute Microsoft
language models.

## Detection limits

Windows model locations and capability identifiers can change between Windows
releases. Yida AI reports `unknown` instead of treating an inconclusive check as
installed. The actual Windows Live Captions window is the final verification.
When its selected language differs from Yida AI's speech language, the interface
shows a mismatch warning; it does not silently change Windows settings.

Windows 10 is unsupported for this chain. Windows 11 Insider builds may change
caption process, UI Automation or model behavior earlier than stable releases.

## Test matrix

For each preset language:

1. Select the language in Windows Live Captions and Yida AI.
2. Speak or play a long sentence containing conjunctions.
3. Confirm one complete source event, one translation and no duplicate event.
4. Switch to each of the other two display languages.
5. Confirm long Portuguese text wraps without clipping.
6. Remove or simulate a missing model and verify official-install guidance.

