from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yida_ai.adapters.captions import (
    LiveCaptionsTranslatorSource,
    MockCaptionSource,
)
from yida_ai.adapters.captions.translated import TranslatedCaptionSource
from yida_ai.adapters.captions.windows_native import WindowsCaptionSource
from yida_ai.components import LctComponentManager
from yida_ai.config.settings import AppSettings, SettingsStore
from yida_ai.core.captions import CaptionAssembler
from yida_ai.core.controller import ApplicationController
from yida_ai.core.conversation import ConversationManager
from yida_ai.core.engine import ReplyEngine
from yida_ai.core.models import CaptionEvent, ReplySuggestion
from yida_ai.providers.llm import (
    MockLLMProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from yida_ai.retrieval import KeywordRetriever, KnowledgeLibrary
from yida_ai.storage import HistoryStore
from yida_ai.system import WindowsCaptionManager


@dataclass(slots=True)
class Runtime:
    settings: AppSettings
    settings_store: SettingsStore
    controller: ApplicationController
    knowledge_library: KnowledgeLibrary
    retriever: KeywordRetriever
    history: HistoryStore
    restored_history: tuple[tuple[str, CaptionEvent, ReplySuggestion | None], ...] = ()
    lct_manager: LctComponentManager | None = None
    windows_caption_manager: WindowsCaptionManager | None = None

    def close(self) -> None:
        self.controller.close()
        if self.lct_manager is not None:
            self.lct_manager.close()
        if self.windows_caption_manager is not None:
            self.windows_caption_manager.close()


def build_runtime(
    settings_store: SettingsStore,
    *,
    mock_caption_path: Path | None = None,
    no_start_lct: bool = False,
    lct_manager: LctComponentManager | None = None,
    windows_caption_manager: WindowsCaptionManager | None = None,
    start_components: bool = True,
) -> Runtime:
    settings = settings_store.load()
    data_dir = settings_store.data_dir
    knowledge_library = KnowledgeLibrary(data_dir / "knowledge")
    retriever = KeywordRetriever()
    retriever.index_directory(knowledge_library.directory)

    using_mock = settings.caption_source.kind == "mock" or mock_caption_path is not None
    active_lct_manager: LctComponentManager | None = None
    active_windows_manager: WindowsCaptionManager | None = None
    if using_mock:
        caption_source = (
            MockCaptionSource.from_jsonl(mock_caption_path)
            if mock_caption_path is not None
            else MockCaptionSource()
        )
    elif settings.caption_source.kind == "windows-captions":
        active_windows_manager = windows_caption_manager or WindowsCaptionManager(
            auto_start=settings.caption_source.auto_start_windows_captions,
            show_window=settings.caption_source.show_system_caption_window,
        )
        if start_components:
            active_windows_manager.ensure_running()
        caption_source = WindowsCaptionSource(
            settings.speech_language, settings.translation_language
        )
    else:
        active_windows_manager = windows_caption_manager or WindowsCaptionManager(
            auto_start=settings.caption_source.auto_start_windows_captions,
            show_window=settings.caption_source.show_system_caption_window,
        )
        if start_components:
            active_windows_manager.ensure_running()
        active_lct_manager = lct_manager or LctComponentManager(no_start=no_start_lct)
        lct_status = (
            active_lct_manager.ensure_running()
            if start_components
            else active_lct_manager.status()
        )
        running_lct_directory = (
            lct_status.executable_path.parent if lct_status.executable_path is not None else None
        )
        caption_source = LiveCaptionsTranslatorSource(
            settings.caption_source.database_path or None,
            source_language=settings.speech_language,
            translated_language=settings.translation_language,
            bundled_lct_directory=active_lct_manager.bundled_directory,
            running_lct_directory=running_lct_directory,
        )

    if settings.llm.provider == "openai-compatible":
        provider = OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                api_url=settings.llm.api_url,
                api_key=settings_store.load_api_key(),
                model=settings.llm.model,
                timeout_seconds=settings.llm.timeout_seconds,
                max_tokens=settings.llm.max_tokens,
                temperature=settings.llm.temperature,
                retry_limit=settings.llm.retry_limit,
            )
        )
    else:
        provider = MockLLMProvider()

    if settings.caption_source.kind == "windows-captions" and not using_mock:
        caption_source = TranslatedCaptionSource(caption_source, provider)

    conversation = ConversationManager(settings.context_turns)
    history = HistoryStore(
        data_dir / "history.db",
        enabled=settings.privacy.save_history,
        retention_days=settings.privacy.retention_days,
    )
    history.prune()
    restored_history = tuple(history.load_recent(settings.context_turns))
    conversation.restore([(event, suggestion) for _, event, suggestion in restored_history])
    engine = ReplyEngine(
        provider,
        retriever,
        conversation,
        history,
        scene=settings.scene,
        custom_scene_instruction=settings.custom_scene_instruction,
        user_language=settings.translation_language,
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
        restored_history=restored_history,
        lct_manager=active_lct_manager,
        windows_caption_manager=active_windows_manager,
    )
