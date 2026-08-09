# 译答 AI（Yida AI）

> 听懂现场，读懂资料，给出能说出口的回答。

译答 AI 是面向 Windows 的实时多语言知识辅助对话系统。它通过 [LiveCaptions Translator](https://github.com/SakiRinn/LiveCaptions-Translator) 接收 Windows 实时字幕及翻译，保留最近对话，检索本地资料，并调用用户配置的 AI 生成有来源的建议回复。

当前版本为 **v0.1.0-beta**。译答 AI 本身没有语音识别引擎，也不承诺完全准确或零延迟。

## 三部分各自负责什么

- **Windows 实时字幕**：使用本地语音包识别电脑声音或麦克风。
- **LiveCaptions Translator**：第一版默认的字幕与翻译来源。
- **译答 AI**：提供去重与断句、对话上下文、资料检索、AI 回复建议、引用、历史和隐私控制。

公开仓库没有复制或修改上游源代码，只独立实现了只读的
`LiveCaptionsTranslatorSource`，属于伴侣项目。详见
[上游说明](docs/UPSTREAM.md)和[集成说明](docs/LIVECAPTIONS_TRANSLATOR.md)。

## 已实现功能

- 统一 `CaptionSource` 接口，以及 `LiveCaptionsTranslatorSource` 和
  `MockCaptionSource` 两种实现
- 同时显示原文、翻译、当前问题、建议回复、目标语言回复和资料来源
- 通用、商务、销售、客户服务、技术支持、面试、语言学习、自定义场景
- 仅翻译、自动建议、每句建议、确认后生成四种模式
- 最近对话轮数可配置，默认 15 轮
- OpenAI-compatible AI 接口（可配置 DeepSeek）和不收费的离线 Mock
- TXT、Markdown 知识库；可复制文本的 PDF 为实验功能
- 异步限长队列、结果顺序保护、清空会话后的旧结果丢弃
- 可关闭历史保存、设置保留天数、清空、导出、删除资料

正式验证语言为简体中文 `zh-CN`、英语 `en-US`、巴西葡萄牙语 `pt-BR`。其他语言取决于 Windows 和翻译提供商能力，当前只能视为实验性支持。

## 从源码运行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m yida_ai --mock examples\captions\demo.jsonl
```

不依赖麦克风、网络、真实 API 和 LiveCaptions Translator 的端到端测试：

```powershell
.\.venv\Scripts\python.exe -m yida_ai --headless-demo --mock examples\captions\demo.jsonl --data-dir .local-smoke
```

## 使用真实字幕与 AI

1. 开启 Windows 实时字幕，选择电脑音频或麦克风输入。
2. 安装并运行 LiveCaptions Translator。
3. 启动译答 AI；自动检测失败时，在设置中手动选择 `translation_history.db`。
4. 离线演示保持 `mock`；真实 AI 选择 `openai-compatible`，填写 API 地址与模型。
5. API Key 只通过当前进程提供，不写入配置：

```powershell
$env:YIDA_AI_API_KEY = "你的私有密钥"
python -m yida_ai
```

DeepSeek 可使用其 OpenAI-compatible 接口。接口地址、可用模型和费用会变化，请使用前查看官方文档。本项目的测试不会调用真实 API 或产生费用。

## 数据与隐私

默认私人数据目录是 `%LOCALAPPDATA%\YidaAI`，不在代码仓库内。也可使用 `--data-dir` 或 `YIDA_AI_DATA_DIR` 修改。启用外部 AI 后，当前字幕、最近上下文和检索到的资料片段会发送给所选提供商。完整说明见 [PRIVACY.md](PRIVACY.md)。

## 验证和构建

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_sensitive.ps1
```

架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，发布结果见 [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)。

## 已知限制

- 当前只正式验证 Windows 11；译答 AI 不直接读取麦克风，也不内置 STT。
- 上游数据库结构若改变，只需要更新 `LiveCaptionsTranslatorSource`。
- 当前关键词检索稳定、可测试，但不等于语义检索。
- PDF 只支持有可复制文字的文件，属于实验功能。
- AI 建议可能出错；涉及事实、承诺或专业决策时必须人工核对。

## 许可证

Apache License 2.0。参见 [LICENSE](LICENSE)、[NOTICE](NOTICE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
