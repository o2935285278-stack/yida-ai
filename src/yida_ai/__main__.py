from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from yida_ai import __version__
from yida_ai.adapters.captions.mock import MockCaptionSource
from yida_ai.application import build_runtime
from yida_ai.config.settings import SettingsStore
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
    runtime.controller.close()
    if sys.stdout is not None:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = SettingsStore(args.config, args.data_dir)
    _configure_logging(store.data_dir)
    if args.headless_demo:
        if args.mock is None:
            raise SystemExit("--headless-demo requires --mock")
        return run_headless_demo(store, args.mock)
    run_gui(store, args.mock)
    return 0


def _configure_logging(data_dir: Path) -> None:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "yida-ai.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
