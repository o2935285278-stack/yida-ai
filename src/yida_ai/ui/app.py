from __future__ import annotations

import copy
import os
from pathlib import Path
from tkinter import BooleanVar, IntVar, Listbox, StringVar, Text, Tk, filedialog, messagebox, ttk
from tkinter import font as tkfont

from yida_ai.application import build_runtime
from yida_ai.config import LANGUAGES, SCENE_TEMPLATES, SettingsStore, language_name
from yida_ai.config.settings import AppSettings
from yida_ai.core.engine import EngineResult
from yida_ai.core.models import CaptionEvent
from yida_ai.retrieval import KnowledgeError

APP_TITLE = "译答 AI · Yida AI"
REPLY_MODES = {
    "仅翻译": "translation",
    "自动建议": "auto",
    "每句建议": "every",
    "确认后生成": "confirm",
}
REPLY_LENGTHS = {"简短": "short", "适中": "medium", "详细": "detailed"}


class YidaApp:
    def __init__(
        self, root: Tk, settings_store: SettingsStore, mock_path: Path | None = None
    ) -> None:
        self.root = root
        self.settings_store = settings_store
        self.mock_path = mock_path
        self.runtime = build_runtime(settings_store, mock_caption_path=mock_path)
        self.pending_cards: dict[str, dict[str, str]] = {}
        self._closed = False
        self._build_ui()
        self._load_settings_into_form()
        self._refresh_knowledge_list()
        self._refresh_status()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(self.runtime.settings.adapter.poll_interval_ms, self._tick)
        if not self.settings_store.path.exists():
            self.root.after(250, self._show_first_run)

    def _build_ui(self) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("1040x780")
        self.root.minsize(850, 620)
        tkfont.nametofont("TkDefaultFont").configure(family="Microsoft YaHei UI", size=10)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        self.notebook = notebook
        self.main_tab = ttk.Frame(notebook, padding=12)
        self.settings_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.main_tab, text="实时对话")
        notebook.add(self.settings_tab, text="设置与资料")
        self._build_main_tab()
        self._build_settings_tab()

    def _build_main_tab(self) -> None:
        header = ttk.Frame(self.main_tab)
        header.pack(fill="x")
        ttk.Label(header, text="译答 AI", font=("Microsoft YaHei UI", 18, "bold")).pack(side="left")
        ttk.Label(
            header, text="听懂现场，读懂资料，给出能说出口的回答。", foreground="#52606d"
        ).pack(side="left", padx=14)

        status = ttk.Frame(self.main_tab)
        status.pack(fill="x", pady=(10, 8))
        self.source_status = StringVar(value="字幕来源：检查中")
        self.language_status = StringVar(value="语言：—")
        self.ai_status = StringVar(value="AI：等待")
        self.knowledge_status = StringVar(value="知识库：检查中")
        self.scene_status = StringVar(value="场景：—")
        for variable in (
            self.source_status,
            self.language_status,
            self.scene_status,
            self.ai_status,
            self.knowledge_status,
        ):
            ttk.Label(status, textvariable=variable, relief="groove", padding=(7, 4)).pack(
                side="left", padx=(0, 6)
            )

        controls = ttk.Frame(self.main_tab)
        controls.pack(fill="x", pady=(0, 8))
        self.pause_button = ttk.Button(controls, text="暂停", command=self.toggle_pause)
        self.pause_button.pack(side="left")
        self.confirm_button = ttk.Button(
            controls, text="生成待确认回复", command=self.confirm_latest
        )
        self.confirm_button.pack(side="left", padx=6)
        ttk.Button(controls, text="清空当前会话", command=self.clear_session).pack(
            side="left", padx=6
        )
        ttk.Button(controls, text="清空全部历史", command=self.clear_history).pack(side="left")
        ttk.Button(controls, text="导出会话", command=self.export_history).pack(side="left", padx=6)
        ttk.Button(
            controls, text="打开设置", command=lambda: self.notebook.select(self.settings_tab)
        ).pack(side="right")

        self.timeline = Text(
            self.main_tab,
            wrap="word",
            state="disabled",
            background="#f7f9fc",
            relief="solid",
            borderwidth=1,
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
        self.bottom_status = StringVar(value="等待字幕…")
        ttk.Label(self.main_tab, textvariable=self.bottom_status, foreground="#344054").pack(
            fill="x", pady=(7, 0)
        )

    def _build_settings_tab(self) -> None:
        form = ttk.LabelFrame(self.settings_tab, text="运行设置", padding=10)
        form.pack(fill="x")
        self.source_language = StringVar()
        self.user_language = StringVar()
        self.reply_language = StringVar()
        self.scene = StringVar()
        self.custom_scene_instruction = StringVar()
        self.reply_mode = StringVar()
        self.reply_length = StringVar()
        self.context_turns = IntVar(value=15)
        self.adapter_kind = StringVar()
        self.database_path = StringVar()
        self.ai_provider = StringVar()
        self.api_url = StringVar()
        self.model = StringVar()
        self.api_key = StringVar()
        self.save_history = BooleanVar(value=True)
        self.retention_days = IntVar(value=30)
        rows = [
            ("字幕来源", self.adapter_kind, ("livecaptions-translator", "mock")),
            ("源语言", self.source_language, tuple(LANGUAGES)),
            ("用户阅读语言", self.user_language, tuple(LANGUAGES)),
            ("回答语言", self.reply_language, tuple(LANGUAGES)),
            ("场景模板", self.scene, tuple(SCENE_TEMPLATES)),
            ("建议模式", self.reply_mode, tuple(REPLY_MODES.values())),
            ("回复长度", self.reply_length, tuple(REPLY_LENGTHS.values())),
            ("AI 提供商", self.ai_provider, ("mock", "openai-compatible")),
        ]
        for index, (label, variable, values) in enumerate(rows):
            row, column = divmod(index, 2)
            base_column = column * 3
            ttk.Label(form, text=label).grid(
                row=row, column=base_column, sticky="e", padx=5, pady=4
            )
            ttk.Combobox(
                form, textvariable=variable, values=values, state="readonly", width=24
            ).grid(row=row, column=base_column + 1, sticky="ew", padx=5, pady=4)

        row = 4
        ttk.Label(form, text="自定义场景规则").grid(row=row, column=0, sticky="e", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.custom_scene_instruction).grid(
            row=row, column=1, columnspan=5, sticky="ew", padx=5
        )
        row += 1
        ttk.Label(form, text="字幕数据库").grid(row=row, column=0, sticky="e", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.database_path, width=55).grid(
            row=row, column=1, columnspan=4, sticky="ew", padx=5
        )
        ttk.Button(form, text="选择", command=self.choose_database).grid(row=row, column=5, padx=5)
        row += 1
        ttk.Label(form, text="API 地址").grid(row=row, column=0, sticky="e", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.api_url).grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=5
        )
        ttk.Label(form, text="模型").grid(row=row, column=3, sticky="e", padx=5)
        ttk.Entry(form, textvariable=self.model).grid(
            row=row, column=4, columnspan=2, sticky="ew", padx=5
        )
        row += 1
        ttk.Label(form, text="API Key（仅本次运行）").grid(
            row=row, column=0, sticky="e", padx=5, pady=4
        )
        ttk.Entry(form, textvariable=self.api_key, show="•").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=5
        )
        ttk.Label(form, text="最近轮数").grid(row=row, column=3, sticky="e", padx=5)
        ttk.Spinbox(form, from_=1, to=50, textvariable=self.context_turns, width=8).grid(
            row=row, column=4, sticky="w", padx=5
        )
        row += 1
        ttk.Checkbutton(form, text="保存历史", variable=self.save_history).grid(
            row=row, column=1, sticky="w", padx=5
        )
        ttk.Label(form, text="保留天数（0=不自动清理）").grid(row=row, column=3, sticky="e", padx=5)
        ttk.Spinbox(form, from_=0, to=3650, textvariable=self.retention_days, width=8).grid(
            row=row, column=4, sticky="w", padx=5
        )
        ttk.Button(form, text="保存并重新载入", command=self.apply_settings).grid(
            row=row, column=5, sticky="e", padx=5, pady=6
        )
        for column in (1, 2, 4, 5):
            form.columnconfigure(column, weight=1)

        knowledge = ttk.LabelFrame(self.settings_tab, text="知识库", padding=10)
        knowledge.pack(fill="both", expand=True, pady=(12, 0))
        self.knowledge_list = Listbox(knowledge, height=9)
        self.knowledge_list.pack(fill="both", expand=True, side="left")
        knowledge_buttons = ttk.Frame(knowledge)
        knowledge_buttons.pack(side="right", fill="y", padx=(10, 0))
        ttk.Button(knowledge_buttons, text="导入 TXT/MD/PDF", command=self.import_document).pack(
            fill="x"
        )
        ttk.Button(knowledge_buttons, text="删除选中资料", command=self.delete_document).pack(
            fill="x", pady=6
        )
        ttk.Button(knowledge_buttons, text="重新建立索引", command=self.reindex).pack(fill="x")
        ttk.Label(
            knowledge_buttons,
            text="资料保存在用户数据目录，\n不会写入程序仓库。",
            foreground="#667085",
            justify="left",
        ).pack(anchor="w", pady=10)

    def _load_settings_into_form(self) -> None:
        settings = self.runtime.settings
        self.source_language.set(settings.source_language)
        self.user_language.set(settings.user_language)
        self.reply_language.set(settings.reply_language)
        self.scene.set(settings.scene)
        self.custom_scene_instruction.set(settings.custom_scene_instruction)
        self.reply_mode.set(settings.reply_mode)
        self.reply_length.set(settings.reply_length)
        self.context_turns.set(settings.context_turns)
        self.adapter_kind.set(settings.adapter.kind)
        self.database_path.set(settings.adapter.database_path)
        self.ai_provider.set(settings.llm.provider)
        self.api_url.set(settings.llm.api_url)
        self.model.set(settings.llm.model)
        self.save_history.set(settings.privacy.save_history)
        self.retention_days.set(settings.privacy.retention_days)

    def _settings_from_form(self) -> AppSettings:
        settings = copy.deepcopy(self.runtime.settings)
        settings.source_language = self.source_language.get()
        settings.user_language = self.user_language.get()
        settings.reply_language = self.reply_language.get()
        settings.scene = self.scene.get()
        settings.custom_scene_instruction = self.custom_scene_instruction.get().strip()
        settings.reply_mode = self.reply_mode.get()
        settings.reply_length = self.reply_length.get()
        settings.context_turns = self.context_turns.get()
        settings.adapter.kind = self.adapter_kind.get()
        settings.adapter.database_path = self.database_path.get().strip()
        settings.llm.provider = self.ai_provider.get()
        settings.llm.api_url = self.api_url.get().strip()
        settings.llm.model = self.model.get().strip()
        settings.privacy.save_history = self.save_history.get()
        settings.privacy.retention_days = self.retention_days.get()
        return settings

    def apply_settings(self) -> None:
        try:
            settings = self._settings_from_form()
            if self.api_key.get().strip():
                os.environ["YIDA_AI_API_KEY"] = self.api_key.get().strip()
            self.settings_store.save(settings)
            self.runtime.controller.close()
            self.runtime = build_runtime(self.settings_store, mock_caption_path=self.mock_path)
            self._refresh_status()
            self.bottom_status.set("设置已保存并重新载入；API Key 只保存在当前进程环境中。")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def choose_database(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 translation_history.db", filetypes=[("SQLite", "*.db"), ("所有文件", "*.*")]
        )
        if path:
            self.database_path.set(path)

    def import_document(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("知识资料", "*.txt *.md *.pdf")])
        if not path:
            return
        try:
            self.runtime.knowledge_library.import_document(Path(path))
            self.reindex()
        except (OSError, KnowledgeError) as exc:
            messagebox.showerror(APP_TITLE, str(exc))

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
        suffix = f" / {error_count} 个错误" if error_count else ""
        self.knowledge_status.set(f"知识库：{document_count} 个文档 / {count} 个片段{suffix}")
        if error_count:
            self.bottom_status.set(f"资料索引失败：{self.runtime.retriever.index_errors[-1]}")

    def _refresh_knowledge_list(self) -> None:
        self.knowledge_list.delete(0, "end")
        for path in self.runtime.knowledge_library.list_documents():
            self.knowledge_list.insert("end", path.name)

    def toggle_pause(self) -> None:
        paused = self.runtime.controller.toggle_pause()
        self.pause_button.configure(text="继续" if paused else "暂停")
        self.bottom_status.set("已暂停监听" if paused else "已继续监听")

    def confirm_latest(self) -> None:
        pending = self.runtime.controller.pending_confirmation
        if not pending:
            self.bottom_status.set("当前没有等待确认的字幕")
            return
        event_id = next(reversed(pending))
        if self.runtime.controller.confirm(event_id):
            self.bottom_status.set("已提交生成，字幕监听不会暂停")

    def clear_session(self) -> None:
        self.runtime.controller.clear_session()
        self._write_timeline("\n—— 已开始新会话；旧请求结果将被丢弃 ——\n", "muted")

    def clear_history(self) -> None:
        if messagebox.askyesno(APP_TITLE, "确定清空所有已保存的历史记录吗？此操作不可撤销。"):
            try:
                self.runtime.history.clear()
                self.bottom_status.set("历史记录已清空")
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
            self.bottom_status.set(f"已导出 {count} 条记录：{path}")
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
            self.source_status.set(f"字幕来源：异常 · {update.errors[-1]}")
        self.root.after(self.runtime.settings.adapter.poll_interval_ms, self._tick)

    def _show_caption(self, event: CaptionEvent) -> None:
        self._write_timeline(f"\n原始字幕 [{event.source_language}]\n", "heading")
        self._write_timeline(f"{event.source_text}\n")
        self._write_timeline(f"翻译结果 [{event.translated_language or '—'}]\n", "heading")
        self._write_timeline(f"{event.translated_text or '（字幕源未提供翻译）'}\n")
        self.pending_cards[event.event_id] = {"source": event.source_text}
        if self.runtime.settings.reply_mode == "confirm":
            self.bottom_status.set("已记录字幕；点击“生成待确认回复”后提交最新一条")

    def _show_result(self, result: EngineResult) -> None:
        if result.error:
            self._write_timeline(f"AI 错误：{result.error}\n", "error")
            self.ai_status.set("AI：异常（字幕仍在运行）")
            return
        suggestion = result.suggestion
        if suggestion is None:
            return
        self._write_timeline("当前问题\n", "heading")
        self._write_timeline(f"{suggestion.current_question}\n")
        self._write_timeline("建议回复\n", "heading")
        self._write_timeline(f"{suggestion.suggested_reply}\n", "reply")
        self._write_timeline(f"目标语言回复 [{self.runtime.settings.reply_language}]\n", "heading")
        self._write_timeline(f"{suggestion.translated_reply}\n", "reply")
        self._write_timeline(f"证据状态：{suggestion.evidence_status.value}\n", "muted")
        if suggestion.citations:
            self._write_timeline("引用资料来源\n", "heading")
            for citation in suggestion.citations:
                excerpt = citation.excerpt.replace("\n", " ")[:240]
                self._write_timeline(f"• {citation.document_name}：{excerpt}\n", "source")
        else:
            self._write_timeline("引用资料来源：无匹配资料\n", "muted")
        self.ai_status.set("AI：正常")
        if result.warning:
            self._write_timeline(f"存储警告：{result.warning}\n", "error")
            self.bottom_status.set(result.warning)

    def _write_timeline(self, text: str, tag: str | None = None) -> None:
        self.timeline.configure(state="normal")
        self.timeline.insert("end", text, tag or ())
        self.timeline.configure(state="disabled")
        self.timeline.see("end")

    def _refresh_status(self) -> None:
        status = self.runtime.controller.adapter.status()
        self.source_status.set(f"字幕来源：{status.source_name} · {status.detail}")
        settings = self.runtime.settings
        source_name = language_name(settings.source_language)
        user_name = language_name(settings.user_language)
        reply_name = language_name(settings.reply_language)
        self.language_status.set(f"语言：{source_name} → {user_name} / 回答 {reply_name}")
        self.ai_status.set(f"AI：{settings.llm.provider}")
        scene = SCENE_TEMPLATES.get(settings.scene)
        self.scene_status.set(f"场景：{scene.name if scene else settings.scene}")
        self.reindex()

    def _show_first_run(self) -> None:
        self.notebook.select(self.settings_tab)
        messagebox.showinfo(
            APP_TITLE,
            "首次运行：请确认字幕来源与语言。若未安装 LiveCaptions Translator，"
            "可选择 mock 使用模拟字幕；真实 API Key 只通过本次运行或环境变量提供。",
        )

    def close(self) -> None:
        self._closed = True
        self.runtime.controller.close()
        self.root.destroy()


def run_gui(settings_store: SettingsStore, mock_path: Path | None = None) -> None:
    root = Tk()
    try:
        YidaApp(root, settings_store, mock_path)
    except Exception as exc:
        messagebox.showerror(APP_TITLE, f"应用无法启动：{exc}")
        root.destroy()
        return
    root.mainloop()
