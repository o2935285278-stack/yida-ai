from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from yida_ai import __version__
from yida_ai.adapters.captions.mock import MockCaptionSource
from yida_ai.application import build_runtime
from yida_ai.config.settings import SettingsStore
from yida_ai.system.single_instance import run_single_instance
from yida_ai.ui import run_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yida AI multilingual live reply assistant")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, help="Path to a private local config.json")
    parser.add_argument("--data-dir", type=Path, help="Private data directory")
    parser.add_argument("--mock", type=Path, help="Read captions from a JSONL fixture")
    parser.add_argument(
        "--headless-demo", action="store_true", help="Run a deterministic offline demo"
    )
    parser.add_argument(
        "--no-start-lct",
        action="store_true",
        help="Do not automatically start the bundled LiveCaptions Translator component",
    )
    return parser


def run_headless_demo(store: SettingsStore, mock_path: Path) -> int:
    runtime = build_runtime(store, mock_caption_path=mock_path)
    runtime.settings.caption_source.kind = "mock"
    runtime.settings.llm.provider = "mock"
    deadline = time.monotonic() + 5
    output: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        update = runtime.controller.tick(now=time.monotonic() + 1)
        for result in update.results:
            if result.suggestion:
                output.append(
                    {
                        "event_id": result.suggestion.event_id,
                        "question": result.suggestion.current_question,
                        "suggested_reply": result.suggestion.suggested_reply,
                        "translated_reply": result.suggestion.translated_reply,
                        "sources": [item.document_name for item in result.suggestion.citations],
                    }
                )
        source = runtime.controller.source
        source_empty = isinstance(source, MockCaptionSource) and source.remaining == 0
        if source_empty and runtime.controller.engine.queue_size == 0:
            update = runtime.controller.flush()
            for result in update.results:
                if result.suggestion:
                    output.append(
                        {
                            "event_id": result.suggestion.event_id,
                            "question": result.suggestion.current_question,
                        }
                    )
            if output:
                break
        time.sleep(0.05)
    runtime.close()
    if sys.stdout is not None:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = SettingsStore(args.config, args.data_dir)
    _configure_logging(store.data_dir)
    try:
        if args.headless_demo:
            if args.mock is None:
                raise SystemExit("--headless-demo requires --mock")
            return run_headless_demo(store, args.mock)
        acquired, exit_code = run_single_instance(
            lambda: run_gui(store, args.mock, no_start_lct=args.no_start_lct)
        )
        if not acquired:
            from tkinter import messagebox

            messagebox.showinfo("Yida AI", "译答 AI 已经在运行，不会重复启动。")
        return exit_code
    finally:
        logging.shutdown()


def _configure_logging(data_dir: Path) -> None:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "yida-ai.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for existing in tuple(root.handlers):
        if getattr(existing, "_yida_managed", False):
            root.removeHandler(existing)
            existing.close()
    handler._yida_managed = True  # type: ignore[attr-defined]
    root.addHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())
