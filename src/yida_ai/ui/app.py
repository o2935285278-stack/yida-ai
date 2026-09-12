from __future__ import annotations

import copy
import os
import queue
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tkinter import (
    BooleanVar,
    Canvas,
    IntVar,
    Listbox,
    Menu,
    StringVar,
    Text,
    Tk,
    filedialog,
    messagebox,
    ttk,
)
from tkinter import font as tkfont

from yida_ai import __version__
from yida_ai.adapters.captions import CaptionActivityState
from yida_ai.application import build_runtime
from yida_ai.components import LctComponentManager, LctComponentState
from yida_ai.config import LANGUAGE_PRESETS, SCENE_TEMPLATES, SettingsStore, language_name
from yida_ai.config.i18n import reply_length_name, reply_mode_name, scene_name, tr
from yida_ai.config.settings import AppSettings
from yida_ai.core.engine import EngineResult
from yida_ai.core.models import CaptionEvent, ReplySuggestion
from yida_ai.providers.llm import OpenAICompatibleConfig, OpenAICompatibleProvider
from yida_ai.providers.llm.base import LLMError
from yida_ai.retrieval import KnowledgeError
from yida_ai.system import (
    SUPPORTED_SPEECH_LANGUAGES,
    PreflightChecker,
    RuntimeState,
    SpeechComponentState,
    StartupOrchestrator,
    WindowsCaptionManager,
    WindowsCaptionState,
    caption_language_warning,
    check_speech_component,
    check_speech_components,
    collect_diagnostics,
    detect_live_captions_language,
    diagnostic_text,
    export_diagnostic_bundle,
    open_services_console,
    open_windows_language_settings,
    open_windows_update,
    repair_instructions,
)
from yida_ai.ui.ai_status import (
    AIConnectionState,
    derive_ai_status,
    state_from_error,
)
from yida_ai.ui.layout import dpi_scaled_preferred_size, responsive_window_metrics

APP_TITLE = "Yida AI"
REPLY_MODES = ("translation", "auto", "every", "confirm")
REPLY_LENGTHS = ("short", "medium", "detailed")


class YidaApp:
    def __init__(
        self,
        root: Tk,
        settings_store: SettingsStore,
        mock_path: Path | None = None,
        *,
        no_start_lct: bool = False,
        lct_manager: LctComponentManager | None = None,
        windows_caption_manager: WindowsCaptionManager | None = None,
        reopen_onboarding: Callable[[], None] | None = None,
        reload_application: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.settings_store = settings_store
        self.mock_path = mock_path
        self.no_start_lct = no_start_lct
        self.runtime = build_runtime(
            settings_store,
            mock_caption_path=mock_path,
            no_start_lct=no_start_lct,
            lct_manager=lct_manager,
            windows_caption_manager=windows_caption_manager,
            start_components=False,
        )
        self.reopen_onboarding = reopen_onboarding
        self.reload_application = reload_application
        self.locale = self.runtime.settings.interface_language
        self.speech_components = check_speech_components()
        self.pending_cards: dict[str, dict[str, object]] = {}
        self._ai_test_results: queue.Queue[tuple[bool, str, AIConnectionState, str, str]] = (
            queue.Queue()
        )
        self._caption_language_results: queue.Queue[str | None] = queue.Queue()
        self._startup_results: queue.Queue[object] = queue.Queue()
        self._startup_worker_running = False
        self._closed = False
        self._next_system_refresh = 0.0
        self.ai_connection_state = derive_ai_status(
            self.runtime.settings.llm,
            has_key=bool(self.settings_store.load_api_key()),
        ).state
        self.startup_orchestrator: StartupOrchestrator | None = None
        if self.runtime.windows_caption_manager and self.runtime.lct_manager:
            self.startup_orchestrator = StartupOrchestrator(
                language=self.runtime.settings.speech_language,
                preflight=PreflightChecker(self.settings_store.data_dir),
                windows=self.runtime.windows_caption_manager,
                lct=self.runtime.lct_manager,
                source=self.runtime.controller.source,
                ai_ready=lambda: self.ai_connection_state is AIConnectionState.VERIFIED,
            )
        self._build_ui()
        self._load_settings_into_form()
        self._render_restored_history()
        self._refresh_knowledge_list()
        self._refresh_status()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(self.runtime.settings.caption_source.poll_interval_ms, self._tick)
        if self.runtime.windows_caption_manager is not None:
            self.root.after(150, self.start_all)
        if self.runtime.settings.caption_source.kind == "livecaptions-translator":
            self.root.after(400, self._start_caption_language_probe)
        current_component = next(
            (
                item
                for item in self.speech_components
                if item.language == self.runtime.settings.speech_language
            ),
            None,
        )
        if current_component and current_component.state is SpeechComponentState.MISSING:
            self.root.after(500, self._show_missing_speech_components)
        if not self.settings_store.path.exists():
            self.root.after(250, self._show_first_run)

    def _build_ui(self) -> None:
        self.root.title(self._t("app_title"))
        preferred_width, preferred_height = dpi_scaled_preferred_size(
            float(self.root.tk.call("tk", "scaling")), 1240, 900
        )
        metrics = responsive_window_metrics(
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
            preferred_width=preferred_width,
            preferred_height=preferred_height,
            normal_min_width=900,
            normal_min_height=620,
        )
        self.root.geometry(f"{metrics.width}x{metrics.height}")
        self.root.minsize(metrics.min_width, metrics.min_height)
        tkfont.nametofont("TkDefaultFont").configure(family="Microsoft YaHei UI", size=10)
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TFrame", background="#f3f3f3")
        style.configure("TLabel", background="#f3f3f3")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Card.TLabel", background="#ffffff")
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        self.notebook = notebook
        self.main_tab = ttk.Frame(notebook, padding=12)
        self.settings_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.main_tab, text=self._t("main_tab"))
        notebook.add(self.settings_tab, text=self._t("settings_tab"))
        settings_sections = ttk.Notebook(self.settings_tab)
        settings_sections.pack(fill="both", expand=True)
        self.settings_content_tab = ttk.Frame(settings_sections, padding=8)
        self.diagnostics_tab = ttk.Frame(settings_sections, padding=8)
        settings_sections.add(self.settings_content_tab, text=self._t("settings_tab"))
        settings_sections.add(self.diagnostics_tab, text=self._t("diagnostics_tab"))
        self._build_main_tab()
        self._build_settings_tab()
        self._build_diagnostics_tab()

    def _build_main_tab(self) -> None:
        header = ttk.Frame(self.main_tab)
        header.pack(fill="x")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="Yida AI", font=("Microsoft YaHei UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        preferences_header = ttk.Frame(self.diagnostics_tab)
        preferences_header.pack(fill="x", pady=8)
        self.quick_interface_language = StringVar(
            value=language_name(self.runtime.settings.interface_language, self.locale)
        )
        interface_picker = ttk.Combobox(
            preferences_header,
            textvariable=self.quick_interface_language,
            values=tuple(language_name(code, self.locale) for code in SUPPORTED_SPEECH_LANGUAGES),
            state="readonly",
            width=20,
        )
        interface_picker.grid(row=0, column=3, sticky="e")
        interface_picker.bind("<<ComboboxSelected>>", self.quick_switch_interface_language)
        ttk.Label(preferences_header, text=self._t("interface_language"), wraplength=150).grid(
            row=0, column=2, sticky="e", padx=6
        )

        status = ttk.Frame(self.diagnostics_tab)
        status.pack(fill="x", pady=(10, 2))
        status_more = ttk.Frame(self.diagnostics_tab)
        status_more.pack(fill="x", pady=(0, 8))
        self.source_status = StringVar(value=self._t("input_checking"))
        self.lct_status = StringVar(value=self._t("lct_checking"))
        self.windows_status = StringVar(value=self._t("windows_checking"))
        self.language_status = StringVar(value=self._t("language_empty"))
        self.ai_status = StringVar(value=self._t("ai_waiting"))
        self.knowledge_status = StringVar(value=self._t("knowledge_checking"))
        self.scene_status = StringVar(value=self._t("scene_empty"))
        status.columnconfigure(0, weight=1)
        status.columnconfigure(1, weight=1)
        for index, variable in enumerate(
            (self.source_status, self.lct_status, self.windows_status, self.language_status)
        ):
            ttk.Label(
                status,
                textvariable=variable,
                foreground="#344054",
                padding=(7, 3),
                wraplength=560,
                justify="left",
            ).grid(
                row=index // 2,
                column=index % 2,
                sticky="w",
                padx=(0, 6),
            )
        for column in range(3):
            status_more.columnconfigure(column, weight=1)
        for column, variable in enumerate(
            (self.scene_status, self.ai_status, self.knowledge_status)
        ):
            ttk.Label(
                status_more,
                textvariable=variable,
                foreground="#344054",
                padding=(7, 3),
                wraplength=360,
                justify="left",
            ).grid(row=0, column=column, sticky="w", padx=(0, 6))

        language_controls = ttk.Frame(self.main_tab)
        language_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(language_controls, text=self._t("listening_language")).pack(side="left")
        self.quick_speech_language = StringVar()
        ttk.Combobox(
            language_controls,
            textvariable=self.quick_speech_language,
            values=tuple(language_name(code, self.locale) for code in SUPPORTED_SPEECH_LANGUAGES),
            state="readonly",
            width=26,
        ).pack(side="left", padx=6)
        ttk.Button(
            language_controls,
            text=self._t("switch_language"),
            command=self.quick_switch_speech_language,
        ).pack(side="left")
        self.caption_language_notice = StringVar(value="")
        self.quick_reply_language = StringVar()
        ttk.Label(language_controls, text=self._t("reply_language")).pack(side="left", padx=8)
        reply_picker = ttk.Combobox(
            language_controls, textvariable=self.quick_reply_language,
            values=SUPPORTED_SPEECH_LANGUAGES, state="readonly", width=8,
        )
        reply_picker.pack(side="left")
        reply_picker.bind("<<ComboboxSelected>>", self.quick_switch_reply_language)
        ttk.Label(
            language_controls,
            textvariable=self.caption_language_notice,
            foreground="#b54708",
            wraplength=620,
            justify="left",
        ).pack(side="left", padx=12)

        controls = ttk.Frame(self.main_tab)
        controls.pack(fill="x", pady=(0, 8))
        self.pause_button = ttk.Button(controls, text=self._t("pause"), command=self.toggle_pause)
        self.pause_button.pack(side="left")
        self.confirm_button = ttk.Button(
            controls, text=self._t("confirm_reply"), command=self.confirm_latest
        )
        self.confirm_button.pack(side="left", padx=6)
        if self.runtime.settings.reply_mode != "confirm":
            self.confirm_button.pack_forget()
        more = ttk.Menubutton(preferences_header, text=self._t("more_actions"))
        more_menu = Menu(more, tearoff=False)
        more_menu.add_command(label=self._t("clear_session"), command=self.clear_session)
        more_menu.add_command(label=self._t("export_history"), command=self.export_history)
        more_menu.add_separator()
        more_menu.add_command(label=self._t("clear_history"), command=self.clear_history)
        more.configure(menu=more_menu)
        more.grid(row=0, column=0, padx=6)
        ttk.Button(
            controls,
            text=self._t("open_settings"),
            command=lambda: self.notebook.select(self.settings_tab),
        ).pack(side="right")

        integration_controls = ttk.Frame(self.diagnostics_tab)
        integration_controls.pack(fill="x", pady=(0, 8))
        self.start_all_button = ttk.Button(
            integration_controls,
            text=self._t("start_all"),
            command=self.start_all,
        )
        self.start_all_button.grid(row=0, column=0, sticky="w")
        ttk.Button(
            integration_controls, text=self._t("open_lct"), command=self.open_lct_settings
        ).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(
            integration_controls,
            text=self._t("hide_lct"),
            command=self.return_lct_to_background,
        ).grid(row=0, column=2, sticky="w", padx=6)
        ttk.Button(
            integration_controls,
            text=self._t("redetect"),
            command=self.redetect_caption_source,
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Button(
            integration_controls,
            text=self._t("wizard_restart_captions"),
            command=self.restart_windows_captions,
        ).grid(row=1, column=1, sticky="w", padx=6, pady=(5, 0))

        self.timeline = Text(
            self.main_tab,
            wrap="word",
            state="disabled",
            background="#f3f3f3",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=12,
            pady=10,
        )
        self.timeline.pack(fill="both", expand=True)
        self.timeline.tag_configure(
            "heading", font=("Microsoft YaHei UI", 10, "bold"), foreground="#175cd3"
        )
        self.timeline.tag_configure("reply", foreground="#067647")
        self.timeline.tag_configure("source", foreground="#6941c6")
        self.timeline.tag_configure("error", foreground="#b42318")
        self.timeline.tag_configure("muted", foreground="#667085")
        self.bottom_status = StringVar(value=self._t("waiting"))
        ttk.Label(self.main_tab, textvariable=self.bottom_status, foreground="#344054").pack(
            fill="x", pady=(7, 0)
        )

    def _build_diagnostics_tab(self) -> None:
        header = ttk.Frame(self.diagnostics_tab)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(
            header,
            text=self._t("diagnostics_title"),
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text=self._t("refresh_diagnostics"), command=self.refresh_diagnostics
        ).pack(side="right")
        actions = ttk.Frame(self.diagnostics_tab)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text=self._t("retry_failed_step"), command=self.retry_startup).pack(
            side="left"
        )
        ttk.Button(actions, text=self._t("open_services"), command=open_services_console).pack(
            side="left", padx=5
        )
        ttk.Button(actions, text=self._t("open_windows_update"), command=open_windows_update).pack(
            side="left", padx=5
        )
        ttk.Button(
            actions,
            text=self._t("copy_repair_instructions"),
            command=self.copy_repair_instructions,
        ).pack(side="left", padx=5)
        ttk.Button(
            actions, text=self._t("export_diagnostics"), command=self.export_diagnostics
        ).pack(side="right")
        self.startup_status = StringVar(value=self._t("startup_unchecked"))
        ttk.Label(
            self.diagnostics_tab,
            textvariable=self.startup_status,
            foreground="#175cd3",
            wraplength=1100,
            justify="left",
        ).pack(fill="x", pady=(0, 8))
        self.diagnostics_text = Text(
            self.diagnostics_tab,
            wrap="word",
            state="disabled",
            background="#f7f9fc",
            padx=12,
            pady=10,
        )
        self.diagnostics_text.pack(fill="both", expand=True)

    def _build_settings_tab(self) -> None:
        settings_canvas = Canvas(self.settings_content_tab, highlightthickness=0)
        settings_scrollbar = ttk.Scrollbar(
            self.settings_content_tab, orient="vertical", command=settings_canvas.yview
        )
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        settings_scrollbar.pack(side="right", fill="y")
        settings_canvas.pack(side="left", fill="both", expand=True)
        settings_content = ttk.Frame(settings_canvas)
        settings_window = settings_canvas.create_window(
            (0, 0), window=settings_content, anchor="nw"
        )
        settings_content.bind(
            "<Configure>",
            lambda _event: settings_canvas.configure(
                scrollregion=settings_canvas.bbox("all")
            ),
        )
        settings_canvas.bind(
            "<Configure>",
            lambda event: settings_canvas.itemconfigure(settings_window, width=event.width),
        )
        self.settings_canvas = settings_canvas
        form = ttk.LabelFrame(settings_content, text=self._t("runtime_settings"), padding=10)
        form.pack(fill="x")
        self.speech_language = StringVar()
        self.translation_language = StringVar()
        self.reply_language = StringVar()
        self.interface_language = StringVar()
        self.scene = StringVar()
        self.custom_scene_instruction = StringVar()
        self.reply_mode = StringVar()
        self.reply_length = StringVar()
        self.context_turns = IntVar(value=15)
        self.caption_source_kind = StringVar()
        self.database_path = StringVar()
        self.ai_provider = StringVar()
        self.api_url = StringVar()
        self.model = StringVar()
        self.api_key = StringVar()
        self.persist_api_key = BooleanVar(value=False)
        self.key_status = StringVar(value=self._t("no_saved_key"))
        self.save_history = BooleanVar(value=True)
        self.retention_days = IntVar(value=30)
        self.auto_start_windows_captions = BooleanVar(value=True)
        self.show_system_caption_window = BooleanVar(value=True)
        rows = [
            ("caption_source", self.caption_source_kind,
             ("windows-captions", "livecaptions-translator", "mock"), True),
            (
                "interface_language",
                self.interface_language,
                ("zh-CN", "en-US", "pt-BR"),
                True,
            ),
            ("speech_language", self.speech_language, LANGUAGE_PRESETS, False),
            (
                "translation_language",
                self.translation_language,
                LANGUAGE_PRESETS,
                False,
            ),
            ("reply_language", self.reply_language, LANGUAGE_PRESETS, False),
            (
                "scene",
                self.scene,
                tuple(scene_name(self.locale, code) for code in SCENE_TEMPLATES),
                True,
            ),
            (
                "reply_mode",
                self.reply_mode,
                tuple(reply_mode_name(self.locale, code) for code in REPLY_MODES),
                True,
            ),
            (
                "reply_length",
                self.reply_length,
                tuple(reply_length_name(self.locale, code) for code in REPLY_LENGTHS),
                True,
            ),
            ("ai_provider", self.ai_provider, ("mock", "openai-compatible"), True),
        ]
        for index, (label_key, variable, values, readonly) in enumerate(rows):
            row, column = divmod(index, 2)
            base_column = column * 3
            ttk.Label(form, text=self._t(label_key)).grid(
                row=row, column=base_column, sticky="e", padx=5, pady=4
            )
            combobox = ttk.Combobox(
                form,
                textvariable=variable,
                values=values,
                state="readonly" if readonly else "normal",
                width=24,
            )
            combobox.grid(row=row, column=base_column + 1, sticky="ew", padx=5, pady=4)
            if label_key == "scene":
                combobox.bind("<<ComboboxSelected>>", self._apply_scene_language_preset)

        row = 5
        ttk.Label(form, text=self._t("language_limit"), foreground="#667085").grid(
            row=row, column=0, columnspan=6, sticky="w", padx=5, pady=3
        )
        row += 1
        ttk.Label(form, text=self._t("custom_scene")).grid(
            row=row, column=0, sticky="e", padx=5, pady=4
        )
        ttk.Entry(form, textvariable=self.custom_scene_instruction).grid(
            row=row, column=1, columnspan=5, sticky="ew", padx=5
        )
        row += 1
        ttk.Label(form, text=self._t("caption_database")).grid(
            row=row, column=0, sticky="e", padx=5, pady=4
        )
        ttk.Entry(form, textvariable=self.database_path, width=55).grid(
            row=row, column=1, columnspan=4, sticky="ew", padx=5
        )
        ttk.Button(form, text=self._t("choose"), command=self.choose_database).grid(
            row=row, column=5, padx=5
        )
        row += 1
        ttk.Label(form, text=self._t("api_url")).grid(row=row, column=0, sticky="e", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.api_url).grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=5
        )
        ttk.Label(form, text=self._t("model")).grid(row=row, column=3, sticky="e", padx=5)
        ttk.Entry(form, textvariable=self.model).grid(
            row=row, column=4, columnspan=2, sticky="ew", padx=5
        )
        row += 1
        ttk.Label(form, text=self._t("api_key")).grid(row=row, column=0, sticky="e", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.api_key, show="•").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=5
        )
        ttk.Label(form, text=self._t("context_turns")).grid(row=row, column=3, sticky="e", padx=5)
        ttk.Spinbox(form, from_=1, to=50, textvariable=self.context_turns, width=8).grid(
            row=row, column=4, sticky="w", padx=5
        )
        ttk.Label(form, textvariable=self.key_status, foreground="#667085").grid(
            row=row, column=5, sticky="e", padx=5
        )
        row += 1
        ttk.Checkbutton(form, text=self._t("save_key"), variable=self.persist_api_key).grid(
            row=row, column=1, columnspan=2, sticky="w", padx=5
        )
        ttk.Button(form, text=self._t("test_ai"), command=self.test_ai_connection).grid(
            row=row, column=4, sticky="e", padx=5
        )
        ttk.Button(form, text=self._t("clear_key"), command=self.clear_saved_api_key).grid(
            row=row, column=5, sticky="e", padx=5
        )
        row += 1
        ttk.Checkbutton(form, text=self._t("save_history"), variable=self.save_history).grid(
            row=row, column=1, sticky="w", padx=5
        )
        ttk.Label(form, text=self._t("retention")).grid(row=row, column=3, sticky="e", padx=5)
        ttk.Spinbox(form, from_=0, to=3650, textvariable=self.retention_days, width=8).grid(
            row=row, column=4, sticky="w", padx=5
        )
        row += 1
        ttk.Label(
            form,
            text=self._t("settings_privacy_notice"),
            foreground="#667085",
            wraplength=760,
            justify="left",
        ).grid(row=row, column=0, columnspan=6, sticky="w", padx=5, pady=(2, 6))
        row += 1
        ttk.Checkbutton(
            form,
            text=self._t("auto_start_captions"),
            variable=self.auto_start_windows_captions,
        ).grid(row=row, column=1, columnspan=2, sticky="w", padx=5)
        ttk.Checkbutton(
            form,
            text=self._t("show_captions"),
            variable=self.show_system_caption_window,
        ).grid(row=row, column=3, columnspan=2, sticky="w", padx=5)
        ttk.Button(
            form, text=self._t("toggle_captions"), command=self.toggle_system_caption_window
        ).grid(row=row, column=5, sticky="e", padx=5)
        row += 1
        component_labels = {
            SpeechComponentState.INSTALLED: self._t("component_installed"),
            SpeechComponentState.MISSING: self._t("component_missing"),
            SpeechComponentState.UNKNOWN: self._t("component_unknown"),
        }
        ttk.Label(form, text=self._t("quiet_start_note"), wraplength=850).grid(
            row=row, column=0, columnspan=6, sticky="w", padx=5, pady=5,
        )
        row += 1
        component_text = " / ".join(
            f"{item.language}: {component_labels[item.state]}" for item in self.speech_components
        )
        ttk.Label(form, text=f"{self._t('speech_components')}：{component_text}").grid(
            row=row, column=0, columnspan=4, sticky="w", padx=5
        )
        ttk.Button(
            form, text=self._t("manage_speech"), command=open_windows_language_settings
        ).grid(row=row, column=5, sticky="e", padx=5)
        row += 1
        ttk.Button(form, text=self._t("open_lct"), command=self.open_lct_settings).grid(
            row=row, column=3, sticky="e", padx=5
        )
        ttk.Button(form, text=self._t("hide_lct"), command=self.return_lct_to_background).grid(
            row=row, column=4, sticky="e", padx=5
        )
        ttk.Button(form, text=self._t("save_reload"), command=self.apply_settings).grid(
            row=row, column=5, sticky="e", padx=5, pady=6
        )
        for column in (1, 2, 4, 5):
            form.columnconfigure(column, weight=1)

        knowledge = ttk.LabelFrame(settings_content, text=self._t("knowledge"), padding=10)
        knowledge.pack(fill="both", expand=True, pady=(12, 0))
        self.knowledge_list = Listbox(knowledge, height=9)
        self.knowledge_list.pack(fill="both", expand=True, side="left")
        ttk.Label(knowledge, text=self._t("drop_hint")).pack(fill="x")
        if (hasattr(self.knowledge_list, "drop_target_register")
                and self.root.tk.call("info", "commands", "tkdnd::drop_target")):
            self.knowledge_list.drop_target_register("DND_Files")
            self.knowledge_list.dnd_bind(
                "<<Drop>>", lambda event: self.import_paths(self.root.tk.splitlist(event.data))
            )
        knowledge_buttons = ttk.Frame(knowledge)
        knowledge_buttons.pack(side="right", fill="y", padx=(10, 0))
        ttk.Button(
            knowledge_buttons, text=self._t("import_document"), command=self.import_document
        ).pack(fill="x")
        ttk.Button(
            knowledge_buttons, text=self._t("delete_document"), command=self.delete_document
        ).pack(fill="x", pady=6)
        ttk.Button(knowledge_buttons, text=self._t("reindex"), command=self.reindex).pack(fill="x")
        ttk.Button(
            knowledge_buttons,
            text=self._t("reopen_wizard"),
            command=self._open_onboarding_again,
        ).pack(fill="x", pady=(6, 0))
        ttk.Label(
            knowledge_buttons,
            text=self._t("data_note"),
            foreground="#667085",
            justify="left",
        ).pack(anchor="w", pady=10)

    def _load_settings_into_form(self) -> None:
        settings = self.runtime.settings
        self.speech_language.set(settings.speech_language)
        self.quick_speech_language.set(language_name(settings.speech_language, self.locale))
        self.translation_language.set(settings.translation_language)
        self.reply_language.set(settings.reply_language)
        self.quick_reply_language.set(settings.reply_language)
        self.interface_language.set(settings.interface_language)
        self.scene.set(scene_name(self.locale, settings.scene))
        self.custom_scene_instruction.set(settings.custom_scene_instruction)
        self.reply_mode.set(reply_mode_name(self.locale, settings.reply_mode))
        self.reply_length.set(reply_length_name(self.locale, settings.reply_length))
        self.context_turns.set(settings.context_turns)
        self.caption_source_kind.set(settings.caption_source.kind)
        self.database_path.set(settings.caption_source.database_path)
        self.ai_provider.set(settings.llm.provider)
        self.api_url.set(settings.llm.api_url)
        self.model.set(settings.llm.model)
        self.persist_api_key.set(self.settings_store.has_saved_api_key())
        self.key_status.set(
            self._t("saved_unreadable")
            if self.settings_store.last_secret_error
            else (
                self._t("saved_key")
                if self.settings_store.has_saved_api_key()
                else self._t("no_saved_key")
            )
        )
        self.save_history.set(settings.privacy.save_history)
        self.retention_days.set(settings.privacy.retention_days)
        self.auto_start_windows_captions.set(settings.caption_source.auto_start_windows_captions)
        self.show_system_caption_window.set(settings.caption_source.show_system_caption_window)

    def _settings_from_form(self) -> AppSettings:
        settings = copy.deepcopy(self.runtime.settings)
        settings.speech_language = self.speech_language.get().strip()
        settings.translation_language = self.translation_language.get().strip()
        settings.reply_language = self.reply_language.get().strip()
        settings.interface_language = self.interface_language.get()
        settings.scene = self._choice_code(self.scene.get(), SCENE_TEMPLATES, scene_name)
        settings.custom_scene_instruction = self.custom_scene_instruction.get().strip()
        settings.reply_mode = self._choice_code(self.reply_mode.get(), REPLY_MODES, reply_mode_name)
        settings.reply_length = self._choice_code(
            self.reply_length.get(), REPLY_LENGTHS, reply_length_name
        )
        settings.context_turns = self.context_turns.get()
        settings.caption_source.kind = self.caption_source_kind.get()
        settings.caption_source.database_path = self.database_path.get().strip()
        settings.caption_source.auto_start_windows_captions = self.auto_start_windows_captions.get()
        settings.caption_source.show_system_caption_window = self.show_system_caption_window.get()
        settings.llm.provider = self.ai_provider.get()
        settings.llm.api_url = self.api_url.get().strip()
        settings.llm.model = self.model.get().strip()
        settings.privacy.save_history = self.save_history.get()
        settings.privacy.retention_days = self.retention_days.get()
        return settings

    def apply_settings(self) -> None:
        try:
            settings = self._settings_from_form()
            entered_key = self.api_key.get().strip()
            if entered_key:
                os.environ["YIDA_AI_API_KEY"] = entered_key
                if self.persist_api_key.get():
                    self.settings_store.save_api_key(entered_key)
            self.settings_store.save(settings)
            previous_manager = self.runtime.lct_manager
            previous_windows = self.runtime.windows_caption_manager
            if previous_windows is not None:
                previous_windows.show_window = settings.caption_source.show_system_caption_window
            self.runtime.controller.close()
            use_previous_manager = settings.caption_source.kind == "livecaptions-translator"
            use_previous_windows = settings.caption_source.kind != "mock"
            if previous_manager is not None and not use_previous_manager:
                previous_manager.close()
            if previous_windows is not None and not use_previous_windows:
                previous_windows.close()
            self.runtime = build_runtime(
                self.settings_store,
                mock_caption_path=self.mock_path,
                no_start_lct=self.no_start_lct,
                lct_manager=previous_manager if use_previous_manager else None,
                windows_caption_manager=previous_windows if use_previous_windows else None,
            )
            # Never keep an orchestrator bound to the previous caption source.
            self.startup_orchestrator = None
            if self.runtime.windows_caption_manager and self.runtime.lct_manager:
                self.startup_orchestrator = StartupOrchestrator(
                    language=settings.speech_language,
                    preflight=PreflightChecker(self.settings_store.data_dir),
                    windows=self.runtime.windows_caption_manager,
                    lct=self.runtime.lct_manager,
                    source=self.runtime.controller.source,
                    ai_ready=lambda: self.ai_connection_state is AIConnectionState.VERIFIED,
                )
            self._refresh_status()
            self.key_status.set(
                self._t("saved_key")
                if self.settings_store.has_saved_api_key()
                else self._t("no_saved_key")
            )
            self.api_key.set("")
            suffix = self._t("ui_restart") if settings.interface_language != self.locale else ""
            self.bottom_status.set(f"{self._t('settings_saved')}{suffix}")
            self.quick_speech_language.set(language_name(settings.speech_language, self.locale))
            if settings.reply_mode == "confirm":
                self.confirm_button.pack(side="left", padx=6)
            else:
                self.confirm_button.pack_forget()
            if settings.caption_source.kind == "livecaptions-translator":
                self._start_caption_language_probe()
            else:
                self.caption_language_notice.set("")
        except Exception as exc:
            messagebox.showerror(self._t("app_title"), str(exc))

    def clear_saved_api_key(self) -> None:
        try:
            self.settings_store.clear_api_key()
            os.environ.pop("YIDA_AI_API_KEY", None)
            self.api_key.set("")
            self.key_status.set(self._t("no_saved_key"))
            self.bottom_status.set(self._t("key_deleted"))
        except Exception as exc:
            messagebox.showerror(self._t("app_title"), str(exc))

    def _apply_scene_language_preset(self, _event: object | None = None) -> None:
        scene_code = self._choice_code(self.scene.get(), SCENE_TEMPLATES, scene_name)
        template = SCENE_TEMPLATES.get(scene_code)
        if template is None or not template.speech_language:
            return
        self.speech_language.set(template.speech_language)
        self.translation_language.set(template.translation_language)
        self.reply_language.set(template.reply_language)

    def quick_switch_speech_language(self) -> None:
        selected_label = self.quick_speech_language.get()
        selected = next(
            (
                code
                for code in SUPPORTED_SPEECH_LANGUAGES
                if selected_label in {code, language_name(code, self.locale)}
            ),
            "",
        )
        if selected not in SUPPORTED_SPEECH_LANGUAGES:
            return
        if self.runtime.settings.caption_source.kind == "mock":
            self.speech_language.set(selected)
            self.apply_settings()
            return
        if getattr(self, "_switching_language", False):
            return
        self._switching_language = True
        self.bottom_status.set(self._t("switching"))
        controller = self.runtime.controller
        was_paused = controller.paused
        controller.paused = True
        def work():
            from yida_ai.system.native_language import switch_caption_language
            try:
                component = check_speech_component(selected)
                if component.state is SpeechComponentState.MISSING:
                    return False
                return switch_caption_language(selected)
            except Exception:
                return False
        def done(ok):
            self._switching_language = False
            if ok:
                self.speech_language.set(selected)
                controller.clear_session()
                self.apply_settings()
                self.runtime.controller.paused = was_paused
                self.bottom_status.set(self._t("switch_done", language=selected))
            else:
                controller.paused = was_paused
                self.bottom_status.set(self._t("switch_manual", language=selected))
        self._background(work, done)

    def quick_switch_reply_language(self, _event=None) -> None:
        selected = self.quick_reply_language.get()
        if selected not in SUPPORTED_SPEECH_LANGUAGES:
            return
        settings = self.runtime.settings
        settings.reply_language = selected
        self.settings_store.save(settings)
        self.reply_language.set(selected)
        engine = self.runtime.controller.engine
        engine.reply_language = selected
        engine.conversation.generation += 1
        self.bottom_status.set(self._t("reply_language") + ": " + selected)

    def quick_switch_interface_language(self, _event: object | None = None) -> None:
        selected_label = self.quick_interface_language.get()
        selected = next(
            (
                code
                for code in SUPPORTED_SPEECH_LANGUAGES
                if selected_label in {code, language_name(code, self.locale)}
            ),
            "",
        )
        if not selected or selected == self.runtime.settings.interface_language:
            return
        settings = copy.deepcopy(self.runtime.settings)
        settings.interface_language = selected
        self.settings_store.save(settings)
        self._closed = True
        self.runtime.close()
        if self.reload_application is not None:
            self.reload_application()

    def _choice_code(self, value: str, codes: object, labeler: object) -> str:
        for code in codes:
            if value == code or value == labeler(self.locale, code):
                return code
        return value

    def _show_missing_speech_components(self) -> None:
        current = self.runtime.settings.speech_language
        status = next(
            (item for item in self.speech_components if item.language == current),
            None,
        )
        if status is None or status.state is not SpeechComponentState.MISSING or self._closed:
            return
        message = self._t("speech_missing", languages=language_name(current, self.locale))
        if messagebox.askyesno(self._t("app_title"), message):
            open_windows_language_settings()

    def _start_caption_language_probe(self) -> None:
        if self._closed:
            return

        def worker() -> None:
            self._caption_language_results.put(detect_live_captions_language())

        threading.Thread(target=worker, name="yida-caption-language", daemon=True).start()
        self.root.after(50, self._poll_caption_language_probe)

    def _poll_caption_language_probe(self) -> None:
        if self._closed:
            return
        try:
            detected = self._caption_language_results.get_nowait()
        except queue.Empty:
            self.root.after(50, self._poll_caption_language_probe)
            return
        warning = caption_language_warning(
            self.runtime.settings.speech_language,
            detected,
        )
        self.caption_language_notice.set(warning or self._t("caption_language_ok"))

    def test_ai_connection(self) -> None:
        try:
            settings = self._settings_from_form()
            settings.validate()
            api_key = self.api_key.get().strip() or self.settings_store.load_api_key()
        except Exception as exc:
            messagebox.showerror(self._t("app_title"), str(exc))
            return
        self.bottom_status.set(self._t("connection_testing"))
        self._set_ai_state(AIConnectionState.TESTING)

        def worker() -> None:
            if settings.llm.provider == "mock":
                result = (
                    True,
                    "Mock / built-in",
                    AIConnectionState.MOCK,
                    "Mock",
                    "Mock",
                )
            else:
                provider = OpenAICompatibleProvider(
                    OpenAICompatibleConfig(
                        api_url=settings.llm.api_url,
                        api_key=api_key,
                        model=settings.llm.model,
                        timeout_seconds=settings.llm.timeout_seconds,
                        max_tokens=settings.llm.max_tokens,
                        temperature=settings.llm.temperature,
                        retry_limit=settings.llm.retry_limit,
                    )
                )
                try:
                    provider_name, model = provider.test_connection()
                    result = (
                        True,
                        f"{provider_name} / {model}",
                        AIConnectionState.VERIFIED,
                        settings.llm.provider,
                        model,
                    )
                except LLMError as exc:
                    result = (
                        False,
                        str(exc),
                        state_from_error(exc.kind),
                        settings.llm.provider,
                        settings.llm.model,
                    )
                except Exception as exc:
                    result = (
                        False,
                        str(exc),
                        AIConnectionState.NETWORK_ERROR,
                        settings.llm.provider,
                        settings.llm.model,
                    )
            self._ai_test_results.put(result)

        threading.Thread(target=worker, name="yida-ai-connection-test", daemon=True).start()
        self.root.after(25, self._poll_ai_connection_test)

    def _poll_ai_connection_test(self) -> None:
        if self._closed:
            return
        try:
            result = self._ai_test_results.get_nowait()
        except queue.Empty:
            self.root.after(25, self._poll_ai_connection_test)
            return
        self._finish_ai_connection_test(result)

    def _finish_ai_connection_test(
        self, result: tuple[bool, str, AIConnectionState, str, str]
    ) -> None:
        success, detail, state, provider, model = result
        self._set_ai_state(state)
        if success:
            if state is AIConnectionState.VERIFIED:
                self._record_ai_verification(provider, model, from_form=True)
            self.bottom_status.set(f"{self._t('connection_success')}：{detail}")
            messagebox.showinfo(self._t("app_title"), f"{self._t('connection_success')}\n{detail}")
        else:
            self.bottom_status.set(f"{self._t('connection_failure')}：{detail}")
            messagebox.showerror(self._t("app_title"), detail)

    def choose_database(self) -> None:
        path = filedialog.askopenfilename(
            title="translation_history.db",
            filetypes=[("SQLite", "*.db"), (self._t("all_files"), "*.*")],
        )
        if path:
            self.database_path.set(path)

    def import_document(self) -> None:
        paths = filedialog.askopenfilenames(
            filetypes=[(self._t("knowledge_files"), "*.txt *.md *.pdf")]
        )
        if not paths:
            return
        self.import_paths(paths)

    def import_paths(self, paths) -> None:
        if getattr(self, "_importing", False):
            return
        self._importing = True
        library = self.runtime.knowledge_library
        self.bottom_status.set(self._t("import_progress"))
        def work():
            count, errors = 0, []
            for path in paths:
                try:
                    library.import_document(Path(path))
                    count += 1
                except Exception as exc:
                    errors.append(f"{Path(path).name}: {exc}")
            return count, errors
        def done(result):
            self._importing = False
            self.reindex()
            count, errors = result
            self.bottom_status.set(self._t("import_done", count=count, errors=len(errors)))
            if errors:
                messagebox.showerror(APP_TITLE, "\n".join(errors))
        self._background(work, done)

    def delete_document(self) -> None:
        selection = self.knowledge_list.curselection()
        if not selection:
            return
        name = self.knowledge_list.get(selection[0])
        try:
            self.runtime.knowledge_library.delete_document(name)
            self.reindex()
        except (OSError, KnowledgeError) as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def reindex(self) -> None:
        count = self.runtime.retriever.index_directory(self.runtime.knowledge_library.directory)
        self._refresh_knowledge_list()
        document_count = len(self.runtime.knowledge_library.list_documents())
        error_count = len(self.runtime.retriever.index_errors)
        self.knowledge_status.set(
            self._t(
                "knowledge_summary",
                documents=document_count,
                chunks=count,
                errors=error_count,
            )
        )
        if error_count:
            self.bottom_status.set(
                self._t("knowledge_error", detail=self.runtime.retriever.index_errors[-1])
            )

    def _refresh_knowledge_list(self) -> None:
        self.knowledge_list.delete(0, "end")
        for path in self.runtime.knowledge_library.list_documents():
            self.knowledge_list.insert("end", path.name)

    def toggle_pause(self) -> None:
        paused = self.runtime.controller.toggle_pause()
        self.pause_button.configure(text=self._t("resume") if paused else self._t("pause"))
        self.bottom_status.set(self._t("paused") if paused else self._t("resumed"))

    def open_lct_settings(self) -> None:
        manager = self.runtime.lct_manager
        if manager is None:
            self.bottom_status.set(self._t("mock_no_lct"))
            return
        status = manager.open_settings()
        self.lct_status.set(f"LCT：{status.detail}")
        self.bottom_status.set(status.detail)

    def return_lct_to_background(self) -> None:
        manager = self.runtime.lct_manager
        if manager is None:
            self.bottom_status.set(self._t("mock_no_lct"))
            return
        status = manager.return_to_background()
        self.lct_status.set(f"LCT：{status.detail}")
        self.bottom_status.set(status.detail)

    def toggle_system_caption_window(self) -> None:
        manager = self.runtime.windows_caption_manager
        if manager is None:
            self.bottom_status.set(self._t("mock_no_windows"))
            return
        status = manager.refresh()
        if status.visible:
            status = manager.hide_window()
            self.show_system_caption_window.set(False)
        else:
            status = manager.show_caption_window()
            self.show_system_caption_window.set(True)
        self.windows_status.set(self._t("windows_status", detail=status.detail))
        self.bottom_status.set(status.detail)

    def restart_windows_captions(self) -> None:
        manager = self.runtime.windows_caption_manager
        if manager is None:
            self.bottom_status.set(self._t("mock_no_windows"))
            return
        status = manager.retry_start()
        self.bottom_status.set(status.detail)
        self._refresh_live_status()

    def start_all(self) -> None:
        orchestrator = self.startup_orchestrator
        if orchestrator is None:
            if self.runtime.windows_caption_manager:
                manager = self.runtime.windows_caption_manager
                self._background(
                    manager.retry_start,
                    lambda status: self.bottom_status.set(status.detail),
                )
                return
            self.bottom_status.set(self._t("mock_no_windows"))
            return
        if self._startup_worker_running:
            return
        self._startup_worker_running = True
        self.start_all_button.configure(state="disabled")
        self.startup_status.set(self._t("startup_checking"))

        def worker() -> None:
            snapshot = orchestrator.snapshot
            if snapshot.state in {
                RuntimeState.ERROR,
                RuntimeState.STOPPED,
                RuntimeState.WAITING_USER,
            }:
                result = orchestrator.retry_failed_step()
            else:
                result = orchestrator.start_all()
            self._startup_results.put(result)

        threading.Thread(target=worker, name="yida-startup", daemon=True).start()
        self.root.after(50, self._poll_startup_result)

    def retry_startup(self) -> None:
        orchestrator = self.startup_orchestrator
        if orchestrator is None or self._startup_worker_running:
            return
        self._startup_worker_running = True
        self.start_all_button.configure(state="disabled")
        self.startup_status.set(self._t("startup_checking"))

        def worker() -> None:
            self._startup_results.put(orchestrator.retry_failed_step())

        threading.Thread(target=worker, name="yida-startup-retry", daemon=True).start()
        self.root.after(50, self._poll_startup_result)

    def _poll_startup_result(self) -> None:
        try:
            snapshot = self._startup_results.get_nowait()
        except queue.Empty:
            if not self._closed:
                self.root.after(50, self._poll_startup_result)
            return
        self._startup_worker_running = False
        self.start_all_button.configure(state="normal")
        assert hasattr(snapshot, "detail")
        code = f" [{snapshot.error_code}]" if snapshot.error_code else ""
        self.startup_status.set(
            f"{self._t('startup_step')} {snapshot.step.value} · "
            f"{snapshot.state.value}{code}\n{snapshot.detail}"
        )
        self.bottom_status.set(snapshot.detail)
        self._refresh_live_status()
        self.refresh_diagnostics()
        if snapshot.state is RuntimeState.STARTING and not self._closed:
            self.root.after(700, self.start_all)

    def _diagnostic_snapshot(self):
        orchestrator = self.startup_orchestrator
        return collect_diagnostics(
            app_version=__version__,
            preflight=orchestrator.last_preflight if orchestrator else None,
            windows=self.runtime.windows_caption_manager,
            lct=self.runtime.lct_manager,
            source=self.runtime.controller.source,
            startup=orchestrator.snapshot if orchestrator else None,
            ai_state=self.ai_connection_state.value,
            knowledge_document_count=len(self.runtime.knowledge_library.list_documents()),
        )

    def refresh_diagnostics(self) -> None:
        try:
            content = diagnostic_text(self._diagnostic_snapshot())
        except Exception as exc:
            content = self._t("diagnostics_failed", detail=exc)
        self.diagnostics_text.configure(state="normal")
        self.diagnostics_text.delete("1.0", "end")
        self.diagnostics_text.insert("1.0", content)
        self.diagnostics_text.configure(state="disabled")

    def copy_repair_instructions(self) -> None:
        content = repair_instructions(self.runtime.settings.speech_language)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.bottom_status.set(self._t("repair_copied"))

    def export_diagnostics(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile="YidaAI-diagnostics.zip",
        )
        if not path:
            return
        try:
            export_diagnostic_bundle(self._diagnostic_snapshot(), Path(path))
            self.bottom_status.set(self._t("diagnostics_exported", path=path))
        except OSError as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def redetect_caption_source(self) -> None:
        manager = self.runtime.lct_manager
        if manager is not None:
            manager.retry_start()
        status = self.runtime.controller.source.redetect()
        self._refresh_status()
        self.bottom_status.set(status.detail)

    def confirm_latest(self) -> None:
        pending = self.runtime.controller.pending_confirmation
        if not pending:
            self.bottom_status.set(self._t("no_pending"))
            return
        event_id = next(reversed(pending))
        if self.runtime.controller.confirm(event_id):
            self.bottom_status.set(self._t("submitted"))

    def clear_session(self) -> None:
        self.runtime.controller.clear_session()
        self._write_timeline(f"\n{self._t('new_session')}\n", "muted")

    def clear_history(self) -> None:
        if messagebox.askyesno(self._t("app_title"), self._t("clear_history_confirm")):
            try:
                self.runtime.history.clear()
                self.bottom_status.set(self._t("history_cleared"))
            except Exception as exc:
                messagebox.showerror(APP_TITLE, str(exc))

    def export_history(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json"), ("CSV", "*.csv")]
        )
        if not path:
            return
        try:
            count = (
                self.runtime.history.export_csv(Path(path))
                if path.lower().endswith(".csv")
                else self.runtime.history.export_json(Path(path))
            )
            self.bottom_status.set(self._t("exported", count=count, path=path))
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _tick(self) -> None:
        if self._closed:
            return
        update = self.runtime.controller.tick()
        for event in update.captions:
            self._show_caption(event)
        for result in update.results:
            self._show_result(result)
        if update.errors:
            self.source_status.set(self._t("source_error", detail=update.errors[-1]))
        now = time.monotonic()
        if now >= self._next_system_refresh:
            self._refresh_live_status()
            self._next_system_refresh = now + 3.0
        self.root.after(self.runtime.settings.caption_source.poll_interval_ms, self._tick)

    def _show_caption(self, event: CaptionEvent) -> None:
        if event.event_id in self.pending_cards:
            card = self.pending_cards[event.event_id]
            card["translation"].set(self._translation_text(event))
            button = card["translation_button"]
            button.configure(command=lambda: self._copy_to_clipboard(event.translated_text))
            if event.translated_text:
                button.state(["!disabled"])
            return
        follow_latest = self.timeline.yview()[1] >= .98
        card = ttk.Frame(self.timeline, padding=16, style="Card.TFrame")
        card.columnconfigure(0, weight=1)
        ttk.Label(
            card,
            text=f"{self._t('original_caption')} · {event.source_language}",
            foreground="#475467",
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            card,
            text=event.source_text,
            wraplength=920,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 10))
        ttk.Label(
            card,
            text=f"{self._t('translation')} · {event.translated_language or '—'}",
            foreground="#475467",
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="w")
        translation_var = StringVar(value=self._translation_text(event))
        ttk.Label(
            card,
            textvariable=translation_var,
            wraplength=920,
            justify="left",
        ).grid(row=3, column=0, sticky="ew", pady=(3, 12))
        ttk.Separator(card).grid(row=4, column=0, sticky="ew", pady=4)
        ttk.Label(
            card,
            text=f"{self._t('reply_target')} · {self.runtime.settings.reply_language}",
            foreground="#067647",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).grid(row=5, column=0, sticky="w", pady=(8, 2))
        reply_var = StringVar(value=self._t("ai_waiting"))
        ttk.Label(
            card,
            textvariable=reply_var,
            foreground="#067647",
            font=("Microsoft YaHei UI", 13, "bold"),
            wraplength=920,
            justify="left",
        ).grid(row=6, column=0, sticky="ew", pady=(0, 12))
        explanation_var = StringVar(value="")
        ttk.Label(
            card,
            textvariable=explanation_var,
            foreground="#344054",
            wraplength=920,
            justify="left",
        ).grid(row=7, column=0, sticky="ew", pady=(0, 8))
        evidence_var = StringVar(value="")
        evidence_label = ttk.Label(
            card,
            textvariable=evidence_var,
            foreground="#667085",
            wraplength=920,
            justify="left",
        )
        def toggle_details():
            if evidence_label.winfo_manager():
                evidence_label.grid_remove()
                buttons.grid_remove()
            else:
                evidence_label.grid(row=8, column=0, sticky="ew", pady=(0, 8))
                buttons.grid(row=10, column=0, sticky="w", pady=5)
        primary_actions = ttk.Frame(card, style="Card.TFrame")
        primary_actions.grid(row=9, column=0, sticky="w")
        buttons = ttk.Frame(card)
        ttk.Button(
            buttons,
            text=self._t("copy_source"),
            command=lambda: self._copy_to_clipboard(event.source_text),
        ).pack(side="left")
        translation_button = ttk.Button(
            buttons,
            text=self._t("copy_translation"),
            command=lambda: self._copy_to_clipboard(event.translated_text),
        )
        if not event.translated_text:
            translation_button.state(["disabled"])
        translation_button.pack(side="left", padx=6)
        reply_button = ttk.Button(primary_actions, text=self._t("copy_reply"))
        reply_button.state(["disabled"])
        reply_button.pack(side="left")
        convert_button = ttk.Button(
            primary_actions, text=self._t("convert_reply"), state="disabled",
            command=lambda: self.convert_reply(event.event_id),
        )
        convert_button.pack(side="left", padx=6)
        ttk.Button(
            primary_actions, text=self._t("message_details"), command=toggle_details,
        ).pack(side="left")
        for child in card.winfo_children():
            if isinstance(child, ttk.Label):
                child.configure(style="Card.TLabel")
        self.timeline.configure(state="normal")
        self.timeline.window_create("end", window=card, padx=8, pady=8)
        self.timeline.insert("end", "\n")
        self.timeline.configure(state="disabled")
        if follow_latest:
            self.timeline.see("end")
        self.pending_cards[event.event_id] = {
            "translation": translation_var,
            "translation_button": translation_button,
            "frame": card,
            "reply": reply_var,
            "explanation": explanation_var,
            "evidence": evidence_var,
            "reply_button": reply_button,
            "convert_button": convert_button,
        }
        if self.runtime.settings.reply_mode == "confirm":
            self.bottom_status.set(self._t("confirm_hint"))

    def _show_result(self, result: EngineResult) -> None:
        if result.error:
            card = self.pending_cards.get(result.request.event.event_id)
            if card:
                reply_var = card["reply"]
                assert isinstance(reply_var, StringVar)
                reply_var.set(self._t("ai_error", detail=result.error))
            self._set_ai_state(AIConnectionState.NETWORK_ERROR)
            return
        suggestion = result.suggestion
        if suggestion is None:
            return
        self._show_suggestion(result.request.event, suggestion)
        if self.runtime.settings.llm.provider == "mock":
            self._set_ai_state(AIConnectionState.MOCK)
        else:
            self._record_ai_verification(
                self.runtime.settings.llm.provider,
                self.runtime.settings.llm.model,
            )
        if result.warning:
            self._write_timeline(f"{self._t('storage_warning', detail=result.warning)}\n", "error")
            self.bottom_status.set(result.warning)

    def _translation_text(self, event: CaptionEvent) -> str:
        if event.translated_text:
            return event.translated_text
        if event.metadata.get("translation_error"):
            return self._t("translation_failed", detail=event.metadata["translation_error"])
        return self._t("translation_pending")

    def _background(self, work, done) -> None:
        results = queue.Queue()
        def worker():
            try:
                results.put((True, work()))
            except Exception as exc:
                results.put((False, str(exc)))
        def poll():
            if self._closed:
                return
            try:
                ok, value = results.get_nowait()
            except queue.Empty:
                self.root.after(50, poll)
                return
            if ok:
                done(value)
            else:
                self.bottom_status.set(str(value))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(50, poll)

    def convert_reply(self, event_id: str) -> None:
        card = self.pending_cards.get(event_id)
        if not card:
            return
        text = card["reply"].get()
        provider = self.runtime.controller.engine.provider
        if not hasattr(provider, "translate_text"):
            return
        target = self.runtime.settings.reply_language
        generation = self.runtime.controller.engine.conversation.generation
        self.bottom_status.set(self._t("translation_pending"))
        def done(value):
            if (generation != self.runtime.controller.engine.conversation.generation
                    or self.pending_cards.get(event_id) is not card):
                return
            card["reply"].set(value)
            card["reply_button"].configure(command=lambda: self._copy_to_clipboard(value))
            self.bottom_status.set(self._t("settings_saved"))
        self._background(lambda: provider.translate_text(text, "auto", target), done)

    def _show_suggestion(self, event: CaptionEvent, suggestion: ReplySuggestion) -> None:
        card = self.pending_cards.get(event.event_id)
        if card is None:
            self._show_caption(event)
            card = self.pending_cards[event.event_id]
        reply_var = card["reply"]
        explanation_var = card["explanation"]
        evidence_var = card["evidence"]
        reply_button = card["reply_button"]
        assert isinstance(reply_var, StringVar)
        assert isinstance(explanation_var, StringVar)
        assert isinstance(evidence_var, StringVar)
        assert isinstance(reply_button, ttk.Button)
        reply_var.set(suggestion.translated_reply)
        explanation_var.set(
            f"{self._t('suggested_reply')}：{suggestion.suggested_reply}\n"
            f"{self._t('current_question')}：{suggestion.current_question}"
        )
        if suggestion.citations:
            citation_text = "\n".join(
                f"• {citation.document_name}：{citation.excerpt.replace(chr(10), ' ')[:240]}"
                for citation in suggestion.citations
            )
        else:
            citation_text = self._t("no_citation")
        evidence_var.set(
            f"{self._t('citations')}：{citation_text}\n"
            f"{self._t('evidence_status', status=suggestion.evidence_status.value)}"
        )
        reply_button.configure(command=lambda: self._copy_to_clipboard(suggestion.translated_reply))
        reply_button.state(["!disabled"])
        card["convert_button"].state(["!disabled"])

    def _copy_to_clipboard(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.bottom_status.set(self._t("copied"))

    def _render_restored_history(self) -> None:
        if not self.runtime.restored_history:
            return
        self._write_timeline(
            f"{self._t('restored', count=len(self.runtime.restored_history))}\n", "muted"
        )
        for _, event, suggestion in self.runtime.restored_history:
            self._show_caption(event)
            if suggestion is not None:
                self._show_suggestion(event, suggestion)
        self.bottom_status.set(self._t("waiting"))

    def _write_timeline(self, text: str, tag: str | None = None) -> None:
        follow_latest = not hasattr(self.timeline, "yview") or self.timeline.yview()[1] >= .98
        self.timeline.configure(state="normal")
        self.timeline.insert("end", text, tag or ())
        self.timeline.configure(state="disabled")
        if follow_latest:
            self.timeline.see("end")

    def _refresh_status(self) -> None:
        self._refresh_live_status()
        settings = self.runtime.settings
        self.language_status.set(
            f"speech {settings.speech_language} → display {settings.translation_language} "
            f"/ reply {settings.reply_language}"
        )
        derived = derive_ai_status(
            settings.llm,
            has_key=bool(self.settings_store.load_api_key()),
        )
        self._set_ai_state(derived.state)
        self.scene_status.set(f"{self._t('scene')}：{scene_name(self.locale, settings.scene)}")
        self.reindex()

    def _refresh_live_status(self) -> None:
        self._refresh_component_status()
        status = self.runtime.controller.source.status()
        windows_manager = self.runtime.windows_caption_manager
        windows_running = windows_manager is None or windows_manager.refresh().running
        if not windows_running and self.runtime.settings.caption_source.kind != "mock":
            label = self._t("input_windows_stopped")
        else:
            labels = {
                CaptionActivityState.RECEIVING: "input_receiving",
                CaptionActivityState.WAITING_AUDIO: "input_waiting",
                CaptionActivityState.PROCESS_RUNNING: "input_waiting",
                CaptionActivityState.DATABASE_READY: "input_database_only",
                CaptionActivityState.STALE: "input_stale",
                CaptionActivityState.MISSING_DATABASE: "input_missing",
                CaptionActivityState.ERROR: "source_unavailable_generic",
            }
            label = self._t(labels[status.activity])
        if status.last_caption_at is not None:
            caption_time = status.last_caption_at.astimezone().strftime("%H:%M:%S")
            translation_time = (
                status.last_translation_at.astimezone().strftime("%H:%M:%S")
                if status.last_translation_at is not None
                else "—"
            )
            label = (
                f"{label} · "
                f"{self._t('input_last_times', caption=caption_time, translation=translation_time)}"
            )
        self.source_status.set(label)

    def _refresh_component_status(self) -> None:
        windows_manager = self.runtime.windows_caption_manager
        if windows_manager is None:
            self.windows_status.set(self._t("windows_mock"))
        else:
            windows = windows_manager.refresh()
            labels = {
                WindowsCaptionState.UNSUPPORTED: self._t("windows_unsupported"),
                WindowsCaptionState.STOPPED: self._t("windows_stopped"),
                WindowsCaptionState.STARTING: self._t("windows_starting"),
                WindowsCaptionState.WAITING_COMPONENT: self._t("windows_waiting_component"),
                WindowsCaptionState.RUNNING: self._t("windows_running"),
                WindowsCaptionState.HIDDEN: self._t("windows_hidden"),
                WindowsCaptionState.FAILED: self._t("windows_failed"),
                WindowsCaptionState.USER_STOPPED: self._t("windows_user_stopped"),
            }
            self.windows_status.set(labels[windows.state])
        manager = self.runtime.lct_manager
        if manager is None:
            self.lct_status.set(self._t(
                "native_source" if self.runtime.settings.caption_source.kind == "windows-captions"
                else "lct_mock"
            ))
            return
        status = manager.refresh()
        labels = {
            LctComponentState.FOUND: self._t("lct_found"),
            LctComponentState.STARTING: self._t("lct_starting"),
            LctComponentState.BUNDLED_RUNNING: self._t("lct_bundled"),
            LctComponentState.EXTERNAL_RUNNING: self._t("lct_external"),
            LctComponentState.WAITING_DATABASE: self._t("lct_waiting"),
            LctComponentState.DISABLED: self._t("lct_disabled"),
            LctComponentState.MISSING: self._t("lct_missing"),
            LctComponentState.FAILED: self._t("lct_failed"),
            LctComponentState.STOPPED: self._t("lct_stopped"),
        }
        self.lct_status.set(f"LCT: {labels[status.state]}")

    def _set_ai_state(self, state: AIConnectionState) -> None:
        self.ai_connection_state = state
        self.ai_status.set(self._t(f"ai_state_{state.value}"))

    def _record_ai_verification(
        self, provider: str, model: str, *, from_form: bool = False
    ) -> None:
        settings = self._settings_from_form() if from_form else self.runtime.settings
        verified_at = datetime.now(UTC).isoformat()
        settings.llm.last_verified_at = verified_at
        settings.llm.last_verified_provider = provider
        settings.llm.last_verified_model = model
        if from_form:
            entered_key = self.api_key.get().strip()
            if entered_key and self.persist_api_key.get():
                self.settings_store.save_api_key(entered_key)
            self.runtime.settings.llm = settings.llm
        try:
            self.settings_store.save(settings)
        except OSError as exc:
            self.bottom_status.set(self._t("storage_warning", detail=exc))
        self._set_ai_state(AIConnectionState.VERIFIED)

    def _show_first_run(self) -> None:
        self.notebook.select(self.settings_tab)
        messagebox.showinfo(
            APP_TITLE,
            self._t("first_run"),
        )

    def close(self) -> None:
        self._closed = True
        self.runtime.close()
        self.root.destroy()

    def _open_onboarding_again(self) -> None:
        if self.reopen_onboarding is None:
            return
        self._closed = True
        self.runtime.close()
        self.reopen_onboarding()

    def _t(self, key: str, **values: object) -> str:
        return tr(self.locale, key, **values)


def run_gui(
    settings_store: SettingsStore,
    mock_path: Path | None = None,
    *,
    no_start_lct: bool = False,
) -> None:
    from tkinterdnd2 import TkinterDnD
    root = TkinterDnD.Tk()
    current_app: list[YidaApp | None] = [None]

    def clear_root() -> None:
        for child in root.winfo_children():
            child.destroy()

    def show_main(
        lct_manager: LctComponentManager | None = None,
        windows_manager: WindowsCaptionManager | None = None,
    ) -> None:
        clear_root()
        current_app[0] = YidaApp(
            root,
            settings_store,
            mock_path,
            no_start_lct=no_start_lct,
            lct_manager=lct_manager,
            windows_caption_manager=windows_manager,
            reopen_onboarding=reopen_onboarding,
            reload_application=reload_application,
        )

    def show_onboarding() -> None:
        from yida_ai.ui.onboarding import OnboardingWizard

        clear_root()
        current_app[0] = None
        OnboardingWizard(
            root,
            settings_store,
            show_main,
            no_start_lct=no_start_lct,
        )

    def reopen_onboarding() -> None:
        settings = settings_store.load()
        settings.onboarding_completed = False
        settings_store.save(settings)
        show_onboarding()

    def reload_application() -> None:
        show_main()

    try:
        if settings_store.load().onboarding_completed:
            show_main()
        else:
            show_onboarding()
    except Exception as exc:
        messagebox.showerror(APP_TITLE, tr("zh-CN", "app_start_failed", detail=exc))
        root.destroy()
        return
    root.mainloop()
