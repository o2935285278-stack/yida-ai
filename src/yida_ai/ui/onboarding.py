from __future__ import annotations

import os
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk

from yida_ai.adapters.captions import LiveCaptionsTranslatorSource
from yida_ai.components import LctComponentManager
from yida_ai.config.i18n import tr
from yida_ai.config.languages import LANGUAGE_PRESETS, language_name
from yida_ai.config.settings import AppSettings, SettingsStore
from yida_ai.providers.llm import OpenAICompatibleConfig, OpenAICompatibleProvider
from yida_ai.retrieval import KnowledgeLibrary
from yida_ai.system import (
    PreflightChecker,
    SpeechComponentState,
    WindowsCaptionManager,
    check_speech_component,
    open_live_captions_model_flow,
    open_services_console,
    open_windows_language_settings,
    open_windows_update,
)
from yida_ai.ui.layout import dpi_scaled_preferred_size, responsive_window_metrics


class OnboardingStep(StrEnum):
    INTERFACE = "interface"
    SPEECH = "speech"
    OUTPUT = "output"
    COMPONENT = "component"
    WINDOWS = "windows"
    LCT = "lct"
    AI = "ai"
    KNOWLEDGE = "knowledge"
    COMPLETE = "complete"


ONBOARDING_STEPS = tuple(OnboardingStep)
INTERFACE_LABELS = {
    "zh-CN": "简体中文",
    "en-US": "English (United States)",
    "pt-BR": "Português (Brasil)",
}


@dataclass(slots=True)
class OnboardingFlow:
    settings: AppSettings
    index: int = 0

    @property
    def step(self) -> OnboardingStep:
        return ONBOARDING_STEPS[self.index]

    def select_interface(self, language: str) -> None:
        if language not in INTERFACE_LABELS:
            raise ValueError(language)
        self.settings.interface_language = language

    def select_speech(self, language: str) -> None:
        if language not in INTERFACE_LABELS:
            raise ValueError(language)
        self.settings.speech_language = language

    def set_output_languages(self, translation: str, reply: str) -> None:
        if translation not in INTERFACE_LABELS or reply not in INTERFACE_LABELS:
            raise ValueError("unsupported output language")
        self.settings.translation_language = translation
        self.settings.reply_language = reply

    def next(self) -> OnboardingStep:
        self.index = min(self.index + 1, len(ONBOARDING_STEPS) - 1)
        return self.step

    def back(self) -> OnboardingStep:
        self.index = max(0, self.index - 1)
        return self.step


class OnboardingWizard:
    """First-run UI that does not build the main runtime before language choice."""

    def __init__(
        self,
        root: Tk,
        settings_store: SettingsStore,
        on_complete: Callable[[LctComponentManager | None, WindowsCaptionManager | None], None],
        *,
        no_start_lct: bool = False,
    ) -> None:
        self.root = root
        self.settings_store = settings_store
        self.on_complete = on_complete
        self.no_start_lct = no_start_lct
        self.flow = OnboardingFlow(settings_store.load())
        self.locale = self.flow.settings.interface_language
        self.windows_manager: WindowsCaptionManager | None = None
        self.lct_manager: LctComponentManager | None = None
        self.translation_language = StringVar(value=self.flow.settings.translation_language)
        self.reply_language = StringVar(value=self.flow.settings.reply_language)
        self.ai_provider = StringVar(value=self.flow.settings.llm.provider)
        self.api_url = StringVar(value=self.flow.settings.llm.api_url)
        self.model = StringVar(value=self.flow.settings.llm.model)
        self.api_key = StringVar()
        self.persist_api_key = BooleanVar(value=settings_store.has_saved_api_key())
        self.save_history = BooleanVar(value=self.flow.settings.privacy.save_history)
        self.status_text = StringVar()
        self._ai_results: queue.Queue[tuple[bool, str]] = queue.Queue()
        self._preflight_results: queue.Queue[object] = queue.Queue()
        self.preflight_checker = PreflightChecker(settings_store.data_dir)
        self._waiting_for_model = False
        self._closed = False
        self._build_shell()
        self.render()

    def _build_shell(self) -> None:
        self.root.title("Yida AI")
        preferred_width, preferred_height = dpi_scaled_preferred_size(
            float(self.root.tk.call("tk", "scaling")), 780, 590
        )
        metrics = responsive_window_metrics(
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
            preferred_width=preferred_width,
            preferred_height=preferred_height,
            normal_min_width=680,
            normal_min_height=520,
        )
        self.root.geometry(f"{metrics.width}x{metrics.height}")
        self.root.minsize(metrics.min_width, metrics.min_height)
        self.shell = ttk.Frame(self.root, padding=28)
        self.shell.pack(fill="both", expand=True)
        self.progress = StringVar()
        ttk.Label(self.shell, textvariable=self.progress, foreground="#667085").pack(anchor="w")
        self.title = StringVar()
        ttk.Label(
            self.shell, textvariable=self.title, font=("Microsoft YaHei UI", 20, "bold")
        ).pack(anchor="w", pady=(12, 6))
        self.description = StringVar()
        ttk.Label(
            self.shell,
            textvariable=self.description,
            foreground="#475467",
            wraplength=700,
            justify="left",
        ).pack(anchor="w")
        self.content = ttk.Frame(self.shell)
        self.content.pack(fill="both", expand=True, pady=24)
        ttk.Separator(self.shell).pack(fill="x")
        navigation = ttk.Frame(self.shell)
        navigation.pack(fill="x", pady=(14, 0))
        self.back_button = ttk.Button(navigation, command=self._back)
        self.back_button.pack(side="left")
        self.skip_button = ttk.Button(navigation, command=self._advance)
        self.skip_button.pack(side="right", padx=(8, 0))
        self.next_button = ttk.Button(navigation, command=self._advance)
        self.next_button.pack(side="right")

    def render(self) -> None:
        self.locale = self.flow.settings.interface_language
        for child in self.content.winfo_children():
            child.destroy()
        current = self.flow.index + 1
        total = len(ONBOARDING_STEPS)
        self.progress.set(self._t("wizard_progress", current=current, total=total))
        self.back_button.configure(text=self._t("wizard_back"))
        self.next_button.configure(text=self._t("wizard_next"), state="normal")
        self.skip_button.configure(text=self._t("wizard_later"))
        self.back_button.configure(state="disabled" if self.flow.index == 0 else "normal")
        self.skip_button.pack_forget()
        step = self.flow.step
        self.title.set(self._t(f"wizard_{step.value}_title"))
        self.description.set(self._t(f"wizard_{step.value}_desc"))
        renderer = getattr(self, f"_render_{step.value}")
        renderer()

    def _render_interface(self) -> None:
        self.next_button.configure(state="disabled")
        for language, label in INTERFACE_LABELS.items():
            ttk.Button(
                self.content,
                text=label,
                command=lambda code=language: self._select_interface(code),
                width=34,
            ).pack(fill="x", pady=7, ipady=9)

    def _render_speech(self) -> None:
        self.next_button.configure(state="disabled")
        for language in LANGUAGE_PRESETS:
            ttk.Button(
                self.content,
                text=language_name(language, self.locale),
                command=lambda code=language: self._select_speech(code),
                width=34,
            ).pack(fill="x", pady=7, ipady=9)

    def _render_output(self) -> None:
        if self.translation_language.get() in LANGUAGE_PRESETS:
            self.translation_language.set(
                language_name(self.translation_language.get(), self.locale)
            )
        if self.reply_language.get() in LANGUAGE_PRESETS:
            self.reply_language.set(language_name(self.reply_language.get(), self.locale))
        self._language_combobox("wizard_translation_label", self.translation_language, 0)
        self._language_combobox("wizard_reply_label", self.reply_language, 1)

    def _language_combobox(self, label_key: str, variable: StringVar, row: int) -> None:
        ttk.Label(self.content, text=self._t(label_key)).grid(
            row=row, column=0, sticky="e", padx=8, pady=10
        )
        ttk.Combobox(
            self.content,
            textvariable=variable,
            values=tuple(language_name(code, self.locale) for code in LANGUAGE_PRESETS),
            state="readonly",
            width=30,
        ).grid(row=row, column=1, sticky="w", padx=8, pady=10)

    def _render_component(self) -> None:
        self._show_component_status()
        actions = ttk.Frame(self.content)
        actions.pack(anchor="w", pady=14)
        ttk.Button(
            actions, text=self._t("wizard_recheck"), command=self._show_component_status
        ).pack(side="left")
        ttk.Button(
            actions,
            text=self._t("wizard_live_captions_model"),
            command=self._open_model_flow,
        ).pack(side="left", padx=8)
        ttk.Button(
            actions,
            text=self._t("wizard_language_settings_fallback"),
            command=open_windows_language_settings,
        ).pack(side="left", padx=8)
        ttk.Button(actions, text=self._t("open_services"), command=open_services_console).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text=self._t("open_windows_update"), command=open_windows_update).pack(
            side="left", padx=8
        )

    def _show_component_status(self) -> None:
        self.status_text.set(self._t("startup_checking"))
        self.next_button.configure(state="disabled")
        self._status_label()

        def worker() -> None:
            self._preflight_results.put(
                self.preflight_checker.run(self.flow.settings.speech_language)
            )

        threading.Thread(target=worker, name="yida-onboarding-preflight", daemon=True).start()
        self.root.after(50, self._poll_preflight_result)

    def _poll_preflight_result(self) -> None:
        if self._closed or self.flow.step is not OnboardingStep.COMPONENT:
            return
        try:
            report = self._preflight_results.get_nowait()
        except queue.Empty:
            self.root.after(50, self._poll_preflight_result)
            return
        status = report.speech_model
        names = {
            SpeechComponentState.INSTALLED: self._t("component_installed"),
            SpeechComponentState.MISSING: self._t("component_missing"),
            SpeechComponentState.UNKNOWN: self._t("component_unknown"),
        }
        parts = [
            report.platform.detail,
            f"{language_name(status.language, self.locale)} · {names[status.state]}",
            f"Windows Update: {report.windows_update.state}/{report.windows_update.start_mode}",
            f"BITS: {report.bits.state}/{report.bits.start_mode}",
        ]
        parts.extend(
            f"{issue.code}: {issue.detail}" if issue.code else issue.detail
            for issue in report.issues
        )
        self.status_text.set("\n".join(parts))
        self._status_label()
        self.next_button.configure(
            state="normal" if report.can_start else "disabled"
        )
        self._waiting_for_model = status.state is SpeechComponentState.MISSING
        if self._waiting_for_model:
            self.root.after(1500, self._poll_model_installation)

    def _open_model_flow(self) -> None:
        self._waiting_for_model = True
        open_live_captions_model_flow()
        self.status_text.set(self._t("wizard_waiting_model_install"))
        self.root.after(1200, self._poll_model_installation)

    def _poll_model_installation(self) -> None:
        if (
            self._closed
            or self.flow.step is not OnboardingStep.COMPONENT
            or not self._waiting_for_model
        ):
            return
        status = check_speech_component(self.flow.settings.speech_language)
        if status.state is SpeechComponentState.INSTALLED:
            self._waiting_for_model = False
            self.flow.next()
            self.render()
            return
        self.root.after(1500, self._poll_model_installation)

    def _render_windows(self) -> None:
        if self.windows_manager is None:
            self.windows_manager = WindowsCaptionManager(
                auto_start=self.flow.settings.caption_source.auto_start_windows_captions,
                show_window=True,
            )
            status = self.windows_manager.ensure_running()
        else:
            status = self.windows_manager.refresh()
        self.status_text.set(status.detail)
        self._status_label()
        ttk.Button(
            self.content,
            text=self._t("wizard_restart_captions"),
            command=self._retry_windows,
        ).pack(anchor="w", pady=12)
        self.skip_button.pack(side="right", padx=(8, 0))
        self.root.after(500, self._poll_windows_status)

    def _poll_windows_status(self) -> None:
        if self._closed or self.flow.step is not OnboardingStep.WINDOWS:
            return
        assert self.windows_manager is not None
        self.status_text.set(self.windows_manager.refresh().detail)
        self.root.after(500, self._poll_windows_status)

    def _retry_windows(self) -> None:
        assert self.windows_manager is not None
        self.status_text.set(self.windows_manager.retry_start().detail)

    def _render_lct(self) -> None:
        if self.flow.settings.caption_source.kind == "windows-captions":
            self.title.set(self._t("native_source"))
            self.description.set(self._t("native_source"))
            self.status_text.set(self._t("native_source"))
            self._status_label()
            return
        if self.lct_manager is None:
            self.lct_manager = LctComponentManager(no_start=self.no_start_lct)
            self.lct_manager.ensure_running()
        self._refresh_lct_status()
        actions = ttk.Frame(self.content)
        actions.pack(anchor="w", pady=12)
        ttk.Button(actions, text=self._t("open_lct"), command=self._open_lct).pack(side="left")
        ttk.Button(actions, text=self._t("hide_lct"), command=self._hide_lct).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text=self._t("wizard_recheck"), command=self._refresh_lct_status).pack(
            side="left"
        )
        self.skip_button.pack(side="right", padx=(8, 0))
        self.root.after(1000, self._poll_lct_status)

    def _poll_lct_status(self) -> None:
        if self._closed or self.flow.step is not OnboardingStep.LCT:
            return
        self._refresh_lct_status()
        self.root.after(1000, self._poll_lct_status)

    def _open_lct(self) -> None:
        assert self.lct_manager is not None
        self.status_text.set(self.lct_manager.open_settings().detail)

    def _hide_lct(self) -> None:
        assert self.lct_manager is not None
        self.status_text.set(self.lct_manager.return_to_background().detail)

    def _refresh_lct_status(self) -> None:
        assert self.lct_manager is not None
        component_status = self.lct_manager.refresh()
        running_lct_directory = (
            component_status.executable_path.parent
            if component_status.executable_path is not None
            else None
        )
        source = LiveCaptionsTranslatorSource(
            source_language=self.flow.settings.speech_language,
            translated_language=self.flow.settings.translation_language,
            bundled_lct_directory=self.lct_manager.bundled_directory,
            running_lct_directory=running_lct_directory,
        )
        try:
            status = source.status()
            parts = [
                status.detail,
                self._t(
                    "wizard_chain_direction",
                    source=self.flow.settings.speech_language,
                    target=self.flow.settings.translation_language,
                ),
            ]
            if status.last_caption_at:
                parts.append(
                    self._t(
                        "wizard_chain_caption_time",
                        time=status.last_caption_at.astimezone().strftime("%H:%M:%S"),
                    )
                )
            if status.last_translation_at:
                parts.append(
                    self._t(
                        "wizard_chain_translation_time",
                        time=status.last_translation_at.astimezone().strftime("%H:%M:%S"),
                    )
                )
                observed = status.last_translation_at
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=UTC)
                age = max(0.0, (datetime.now(UTC) - observed).total_seconds())
                parts.append(self._t("wizard_chain_age", seconds=f"{age:.1f}"))
            self.status_text.set("\n".join(parts))
        finally:
            source.close()
        self._status_label()

    def _render_ai(self) -> None:
        fields = (
            ("ai_provider", self.ai_provider),
            ("api_url", self.api_url),
            ("model", self.model),
            ("api_key", self.api_key),
        )
        for row, (label_key, variable) in enumerate(fields):
            ttk.Label(self.content, text=self._t(label_key)).grid(
                row=row, column=0, sticky="e", padx=8, pady=5
            )
            show = "•" if label_key == "api_key" else ""
            ttk.Entry(self.content, textvariable=variable, show=show, width=52).grid(
                row=row, column=1, sticky="ew", padx=8, pady=5
            )
        ttk.Button(self.content, text=self._t("test_ai"), command=self._test_ai_connection).grid(
            row=len(fields), column=1, sticky="w", padx=8, pady=10
        )
        ttk.Checkbutton(
            self.content,
            text=self._t("save_key"),
            variable=self.persist_api_key,
        ).grid(row=len(fields) + 1, column=1, sticky="w", padx=8, pady=3)
        ttk.Checkbutton(
            self.content,
            text=self._t("save_history"),
            variable=self.save_history,
        ).grid(row=len(fields) + 2, column=1, sticky="w", padx=8, pady=3)
        ttk.Label(
            self.content,
            text=self._t("wizard_ai_privacy_notice"),
            foreground="#667085",
            wraplength=620,
            justify="left",
        ).grid(row=len(fields) + 3, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        ttk.Label(self.content, textvariable=self.status_text, foreground="#475467").grid(
            row=len(fields) + 4, column=0, columnspan=2, sticky="w", padx=8
        )
        self.skip_button.pack(side="right", padx=(8, 0))

    def _test_ai_connection(self) -> None:
        self._save_ai_fields()
        self.status_text.set(self._t("connection_testing"))

        def worker() -> None:
            if self.flow.settings.llm.provider == "mock":
                self._ai_results.put((True, "Mock"))
                return
            key = self.api_key.get().strip() or self.settings_store.load_api_key()
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    self.flow.settings.llm.api_url,
                    key,
                    self.flow.settings.llm.model,
                    timeout_seconds=self.flow.settings.llm.timeout_seconds,
                )
            )
            try:
                name, model = provider.test_connection()
                self._ai_results.put((True, f"{name} / {model}"))
            except Exception as exc:
                self._ai_results.put((False, str(exc)))

        threading.Thread(target=worker, name="yida-onboarding-ai", daemon=True).start()
        self.root.after(50, self._poll_ai_result)

    def _poll_ai_result(self) -> None:
        try:
            success, detail = self._ai_results.get_nowait()
        except queue.Empty:
            self.root.after(50, self._poll_ai_result)
            return
        self.status_text.set(
            f"{self._t('connection_success' if success else 'connection_failure')} · {detail}"
        )

    def _render_knowledge(self) -> None:
        ttk.Button(
            self.content, text=self._t("import_document"), command=self._import_document
        ).pack(anchor="w")
        self._status_label()
        self.skip_button.pack(side="right", padx=(8, 0))

    def _import_document(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Documents", "*.txt *.md *.pdf")])
        if not path:
            return
        try:
            library = KnowledgeLibrary(self.settings_store.data_dir / "knowledge")
            imported = library.import_document(Path(path))
            self.status_text.set(str(imported))
        except Exception as exc:
            messagebox.showerror("Yida AI", str(exc))

    def _render_complete(self) -> None:
        self.next_button.configure(text=self._t("wizard_finish"))
        self.status_text.set(self._t("wizard_status_ready"))
        self._status_label()

    def _status_label(self) -> None:
        existing = [
            child
            for child in self.content.winfo_children()
            if getattr(child, "_yida_status", False)
        ]
        for child in existing:
            child.destroy()
        label = ttk.Label(
            self.content,
            textvariable=self.status_text,
            foreground="#175cd3",
            wraplength=680,
            justify="left",
        )
        label._yida_status = True  # type: ignore[attr-defined]
        label.pack(anchor="w", pady=8)

    def _select_interface(self, language: str) -> None:
        self.flow.select_interface(language)
        self.locale = language
        self.flow.next()
        self.render()

    def _select_speech(self, language: str) -> None:
        self.flow.select_speech(language)
        self.flow.next()
        self.render()

    def _save_ai_fields(self) -> None:
        settings = self.flow.settings
        settings.llm.provider = self.ai_provider.get().strip() or "mock"
        settings.llm.api_url = self.api_url.get().strip()
        settings.llm.model = self.model.get().strip()
        settings.privacy.save_history = self.save_history.get()
        key = self.api_key.get().strip()
        if key:
            os.environ["YIDA_AI_API_KEY"] = key
        if self.persist_api_key.get() and key:
            self.settings_store.save_api_key(key)
        elif not self.persist_api_key.get() and self.settings_store.has_saved_api_key():
            self.settings_store.clear_api_key()

    def _advance(self) -> None:
        step = self.flow.step
        if step is OnboardingStep.OUTPUT:
            self.flow.set_output_languages(
                self._language_code(self.translation_language.get()),
                self._language_code(self.reply_language.get()),
            )
        elif step is OnboardingStep.AI:
            self._save_ai_fields()
        elif step is OnboardingStep.COMPLETE:
            self._finish()
            return
        self.flow.next()
        self.render()

    def _back(self) -> None:
        self.flow.back()
        self.render()

    def _finish(self) -> None:
        settings = self.flow.settings
        settings.onboarding_completed = True
        self.settings_store.save(settings)
        self._closed = True
        self.shell.destroy()
        self.on_complete(self.lct_manager, self.windows_manager)

    def _t(self, key: str, **values: object) -> str:
        return tr(self.locale, key, **values)

    def _language_code(self, value: str) -> str:
        for code in LANGUAGE_PRESETS:
            if value in {code, language_name(code, self.locale)}:
                return code
        raise ValueError(value)
