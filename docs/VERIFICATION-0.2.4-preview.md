# 0.2.4-beta development checkpoint

2026-09-13. Local preview, not a formal release.

## Implemented

- Native Windows ttk theme, lighter conversation background, borderless cards.
- Main page no longer lists system/component statuses, repair/start tools,
  interface-language selector or history actions. Diagnostics is inside Settings.
- Listening/reply language, pause, settings and conditional reply confirmation
  remain accessible on the main page.
- Citation details and secondary copy actions collapse; primary reply actions stay visible.
- Appending messages preserves scroll position while reviewing older conversation.
- Opt-in quiet start through the existing show-caption-window checkbox. Only
  Yida-owned Windows caption windows qualify, and only after text becomes readable.
  A failed post-hide read restores visibility without repeatedly hiding the window.
  External processes are not automatically hidden or closed.

## Verification and limits

- 155 automated tests passed with YIDA_GUI_TEST=1, including Tk startup and scaling.
- Ruff passed. New tests cover external-window preservation, readiness and rollback.
- Computer Use initialization failed twice: kernel asset path not found. Therefore
  no visual screenshot review or live hidden-window continuous-caption verification
  was performed in this turn. The computer-use skill requires stopping failed UI
  automation after recovery; no alternate UI automation was used to bypass it.
- Automatic hiding remains opt-in, not enabled by default. Startup flash is possible.
- Main-page microphone toggle and fuller hide/language-switch integration are not
  complete. Do not advertise the entire 0.2.4 plan as finished.
- Unsigned local build; no signer, timestamp or successful SignTool verification.
- Existing installation and private user settings have not been overwritten.
- No GitHub publication or push.
