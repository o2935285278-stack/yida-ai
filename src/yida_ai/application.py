from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yida_ai.adapters.captions import (
    LiveCaptionsTranslatorSource,
    MockCaptionSource,
)
from yida_ai.config.settings import AppSettings, SettingsStore
from yida_ai.core.captions import CaptionAssembler
from yida_ai.core.controller import ApplicationController
from yida_ai.core.conversation import ConversationManager
from yida_ai.core.engine import ReplyEngine
from yida_ai.providers.llm import (
    MockLLMProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from yida_ai.retrieval import KeywordRetriever, KnowledgeLibrary
from yida_ai.storage import HistoryStore


@dataclass(slots=True)
class Runtime:
    settings: AppSettings
    settings_store: SettingsStore
    controller: ApplicationController
    knowledge_library: KnowledgeLibrary
    retriever: KeywordRetriever
    history: HistoryStore


def build_runtime(
    settings_store: SettingsStore,
    *,
    mock_caption_path: Path | None = None,
) -> Runtime:
    settings = settings_store.load()
    data_dir = settings_store.data_dir
    knowledge_library = KnowledgeLibrary(data_dir / "knowledge")
    retriever = KeywordRetriever()
    retriever.index_directory(knowledge_library.directory)

    if settings.caption_source.kind == "mock" or mock_caption_path is not None:
        caption_source = (
            MockCaptionSource.from_jsonl(mock_caption_path)
            if mock_caption_path is not None
            else MockCaptionSource()
        )
    else:
        caption_source = LiveCaptionsTranslatorSource(
            settings.caption_source.database_path or None,
            source_language=settings.source_language,
            translated_language=settings.user_language,
        )

    if settings.llm.provider == "openai-compatible":
        provider = OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                api_url=settings.llm.api_url,
                api_key=settings.llm.api_key,
                model=settings.llm.model,
                timeout_seconds=settings.llm.timeout_seconds,
                max_tokens=settings.llm.max_tokens,
                temperature=settings.llm.temperature,
                retry_limit=settings.llm.retry_limit,
            )
        )
    else:
        provider = MockLLMProvider()

    conversation = ConversationManager(settings.context_turns)
    history = HistoryStore(
        data_dir / "history.db",
        enabled=settings.privacy.save_history,
        retention_days=settings.privacy.retention_days,
    )
    history.prune()
    engine = ReplyEngine(
        provider,
        retriever,
        conversation,
        history,
        scene=settings.scene,
        custom_scene_instruction=settings.custom_scene_instruction,
        user_language=settings.user_language,
        reply_language=settings.reply_language,
        reply_length=settings.reply_length,
    )
    controller = ApplicationController(
        caption_source,
        CaptionAssembler(),
        engine,
        reply_mode=settings.reply_mode,
    )
    return Runtime(
        settings=settings,
        settings_store=settings_store,
        controller=controller,
        knowledge_library=knowledge_library,
        retriever=retriever,
        history=history,
    )
