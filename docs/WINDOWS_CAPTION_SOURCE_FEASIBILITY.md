# Future WindowsCaptionSource feasibility

Status: research only; explicitly outside v0.1.0-beta.

## Product boundary

A future `WindowsCaptionSource` could read text produced by Windows Live
Captions without requiring LiveCaptions Translator. It would still rely on
Windows local speech packages and Windows' caption process. It would not capture
audio, run Whisper, bundle a speech model, or claim to be an independent speech
recognition engine.

`LiveCaptionsTranslatorSource` remains the default for v0.1.0-beta and should
remain available as a compatibility option after an independent source becomes
stable.

## Feasible technical direction

The locally audited LiveCaptions Translator source demonstrates the overall
feasibility of observing the Windows Live Captions accessibility tree through
Windows UI Automation. No part of that C# implementation has been copied into
Yida AI.

An independent implementation would need to:

1. Detect a running Windows Live Captions process/window without terminating or
   replacing it.
2. Inspect the window's UI Automation tree and locate the element that exposes
   caption text using stable properties and scoped searches.
3. Read property changes or poll at a bounded interval, then emit only generic
   `CaptionEvent` revisions/finals through the existing `CaptionSource`
   contract.
4. Reacquire elements after window recreation, language changes, accessibility
   tree invalidation or Windows updates.
5. Keep translation separate. Windows' own translation is hardware/version
   dependent; a future source may provide source text only and let a replaceable
   translation provider handle the rest.

Microsoft documents UI Automation as the framework external clients use to
inspect desktop UI elements. `AutomationElement` exposes tree search, properties
and change events. Automation IDs are useful across UI languages, but Microsoft
explicitly warns that they are not guaranteed to remain stable across releases.

References:

- [Microsoft: AutomationElement class](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement?view=windowsdesktop-10.0)
- [Microsoft: AutomationId property and stability warning](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.automationelementinformation.automationid?view=windowsdesktop-10.0)
- [Microsoft: UI Automation properties and change events](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-properties-for-clients)

## Windows compatibility risks

- Windows Live Captions is available on Windows 11 22H2 and later, so an
  independent source cannot support Windows 10 through this route.
- Caption languages depend on downloaded Windows speech-recognition support.
- Windows caption translation is a different capability: Microsoft currently
  documents it for Copilot+ PCs on Windows 11 24H2 and later. Yida AI therefore
  must not assume translated text is always exposed.
- UI Automation class names, hierarchy, Automation IDs and property behavior can
  change in cumulative Windows updates, Insider builds, localization variants
  and display modes.
- Accessibility tree access can fail across privilege/integrity boundaries or
  when an element is recreated. The source must report an actionable error and
  retry acquisition without killing the Windows process.
- Polling too rapidly wastes resources; event delivery can be noisy. Existing
  normalization, revision merging and deduplication must remain downstream.

Microsoft confirms that Live Captions recognition is on-device, works offline,
can include microphone audio, and does not store generated captions. See
[Microsoft's Live Captions support page](https://support.microsoft.com/en-US/accessibility/windows/use-live-captions-to-better-understand-audio).

## Required validation before implementation can ship

Build the future source behind the existing interface and validate it separately
from v0.1.0-beta on at least:

- Windows 11 22H2, 23H2 and supported 24H2+ builds that remain in scope;
- standard and Copilot+ hardware where available;
- `zh-CN`, `en-US` and `pt-BR` speech packages;
- system audio, microphone input, simultaneous speakers and offline operation;
- overlay, top and bottom caption positions, display scaling and multiple
  monitors;
- caption process launch/close/restart, language switching and Windows update
  regressions;
- UI Automation inspection with Accessibility Insights/Inspect plus automated
  property-change and recovery tests;
- bounded CPU/memory use, duplicate/revision behavior and clean shutdown.

Microsoft recommends inspecting accessibility trees and automating Windows UI
through UI Automation-compatible tooling. Useful references are
[Accessibility testing tools](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessibility-testing)
and [Windows app UI testing](https://learn.microsoft.com/en-us/windows/apps/develop/testing/).

Only after that matrix passes should users be told they can omit LiveCaptions
Translator. Until then, the independent source is a roadmap item, not a current
feature or release blocker.
