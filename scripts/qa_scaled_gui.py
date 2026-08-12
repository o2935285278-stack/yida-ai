from __future__ import annotations

import argparse
from pathlib import Path
from tkinter import Tk

from yida_ai.config.settings import AppSettings, SettingsStore
from yida_ai.ui.app import YidaApp


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the real Tk UI at a QA-only scale")
    parser.add_argument("--scale", type=float, required=True)
    parser.add_argument("--locale", choices=("zh-CN", "en-US", "pt-BR"), required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--mock", type=Path, required=True)
    args = parser.parse_args()

    settings = AppSettings(
        onboarding_completed=True,
        interface_language=args.locale,
        speech_language="pt-BR",
        translation_language="zh-CN",
        reply_language="pt-BR",
    )
    settings.caption_source.kind = "mock"
    settings.llm.provider = "mock"
    settings.privacy.save_history = False
    store = SettingsStore(data_dir=args.data_dir)
    store.save(settings)

    root = Tk()
    root.tk.call("tk", "scaling", args.scale)
    YidaApp(root, store, args.mock)
    root.mainloop()


if __name__ == "__main__":
    main()
