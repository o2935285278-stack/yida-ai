# 译答 AI（Yida AI）

> 听懂现场，读懂资料，给出能说出口的回答。

译答 AI 是“基于 Windows 实时字幕和翻译服务的多语言实时翻译与文档辅助回答工具”。它通过 [LiveCaptions Translator](https://github.com/SakiRinn/LiveCaptions-Translator) 接收 Windows 实时字幕及翻译，保留有限的最近对话，检索本地资料，并调用用户配置的 AI 生成有来源的建议回复。

当前版本为 **v0.2.2-beta**。译答 AI 本身没有语音识别引擎，也不承诺完全准确或零延迟。当前待发布构建为**未签名测试版**，不得显示为“已签名”。

官方仓库：<https://github.com/o2935285278-stack/yida-ai>。仓库公开后，只从其
[Releases](https://github.com/o2935285278-stack/yida-ai/releases) 下载并核对 SHA-256；其他账号转载的二进制不是官方构建。

## 三部分各自负责什么

- **Windows 实时字幕**：使用本地语音包识别电脑声音或麦克风。
- **LiveCaptions Translator**：第一版默认的字幕与翻译来源。
- **译答 AI**：提供去重与断句、对话上下文、资料检索、AI 回复建议、引用、历史和隐私控制。

Windows 安装包会把未经修改的上游 LCT 可执行文件作为明确标注的
Apache-2.0 第三方后台组件一同安装；公开仓库不复制或修改上游源代码。
进程管理器和只读 `LiveCaptionsTranslatorSource` 均由译答 AI 独立实现。详见
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
- 本地历史为显式选择（新安装默认关闭），可设置保留天数、清空、导出、删除资料
- 重启后恢复最近历史并重新用于 AI 上下文，默认最多 15 轮
- 简体中文、英语和巴西葡语三套完整界面资源与独立的四类语言设置
- 可选使用 Windows DPAPI CurrentUser 加密保存 AI API Key
- 设置页可测试 AI 连接，并区分缺 Key、无效 Key、模型、超时、限流和服务错误
- 一键启动协调器和“诊断与修复”页：分步显示 Windows、识别模型、LCT、数据库、字幕、翻译和 AI 的真实状态
- 诊断包不包含 API Key、资料正文、字幕/翻译/回复正文、对话或用户名

正式验证预设为简体中文 `zh-CN`、英语 `en-US`、巴西葡萄牙语 `pt-BR`。
用户可以填写其他 BCP-47 代码，但这不代表“支持所有语言”：语音识别语言取决于
Windows 实时字幕，翻译语言取决于 LCT 及其所选翻译服务，AI 回答语言可以单独选择。

## 安装与首次运行

1. 确认系统为 Windows 11 22H2（build 22621）或更高版本；Windows 10 不支持本版本的实时字幕链。
2. 运行 `YidaAI-0.2.2-beta-win-x64-setup.exe`。当前安装包未进行可信代码签名，Windows 可能提示未知发布者。
3. 使用默认的当前用户安装目录。开始菜单只会出现“译答 AI”；桌面快捷方式为可选项。
4. 启动译答 AI，选择界面、听取、翻译显示和回答语言。程序只检查当前听取语言的实时字幕模型。
5. 缺少模型时，优先点击“打开实时字幕下载识别模型”；完成后向导会自动复检。只有系统流程要求时才打开“语言设置（备用）”。
6. 完成向导后点击“一键启动全部”。只有字幕、翻译源和已验证 AI 都可用时才显示“就绪”。

三种语音组件只通过[微软 Windows 实时字幕官方流程](https://support.microsoft.com/windows/use-live-captions-to-better-understand-audio)
下载，本安装包不会内置微软语言包；已经安装的组件会自动跳过。

“显示语言”“基本输入/手写”“文本转语音声音”和“Windows 实时字幕本地语音识别模型”是不同组件。设置中显示某语言包或朗读声音已安装，不代表实时字幕识别模型已经安装。

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

1. 安装后只启动一个“译答 AI”快捷方式。
2. 如果系统字幕没有自动启动，按 Win+Ctrl+L 开启，并按提示下载源语言本地语音包。
3. 译答 AI 会自动在后台启动内置 LCT；首次配置翻译服务时点击“打开 LCT 设置”。
4. 如果用户已经运行兼容的外部 LCT，译答 AI 会直接连接，不重复启动。
5. 数据库尚未生成时保持程序打开，译答 AI 会持续动态检测，无需重启。
6. 离线演示保持 `mock`；真实 AI 选择 `openai-compatible`，填写 API 地址与模型。
7. 填写 API 地址、模型和 API Key。勾选“用 Windows DPAPI 安全保存 Key”后，
   重启仍可使用；点击“测试 AI 连接”会显示实际服务商和模型，但不显示密钥。
   也可以只通过当前进程环境变量提供：

```powershell
$env:YIDA_AI_API_KEY = "你的私有密钥"
python -m yida_ai
```

加密文件位于 `%LOCALAPPDATA%\YidaAI\api-key.dpapi`，只可由当前 Windows 用户解密，
普通 `config.json` 中没有 Key。DeepSeek 可使用其 OpenAI-compatible 接口。
接口地址、可用模型和费用会变化，请使用前查看官方文档。

## 导入资料

在“设置与资料”中导入 `.txt`、`.md` 或可提取文字的 `.pdf`。原始识别、翻译、
AI 建议和文档引用会分开显示；资料证据不足时必须提示“资料中没有足够依据”。

## 数据与隐私

默认私人数据目录是 `%LOCALAPPDATA%\YidaAI`，不在代码仓库内。也可使用 `--data-dir` 或 `YIDA_AI_DATA_DIR` 修改。启用外部 AI 后，当前字幕、最近上下文和检索到的资料片段会发送给所选提供商。新安装默认不保存对话历史；用户主动开启后才创建历史数据库。完整说明见 [PRIVACY.md](PRIVACY.md)。

## 验证和构建

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 `
  -LctExecutable "C:\path\to\LiveCaptions Translator.exe"
powershell -ExecutionPolicy Bypass -File scripts\check_sensitive.ps1
python scripts\check_dependency_licenses.py
```

发布工作流通过 `requirements-build-win-py313.txt` 与 `pip --require-hashes`
锁定构建依赖，校验官方 LCT 和 Inno Setup 下载，生成 CycloneDX SBOM 与
SHA-256 清单，并执行 Defender 扫描。参见[仓库安全建议](docs/REPOSITORY_SECURITY.md)。

以上为默认无证书构建，并会明确输出“当前安装包未进行可信代码签名。”。已有可信证书时，从 Windows 证书存储按指纹签名：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 `
  -LctExecutable "C:\path\to\LiveCaptions Translator.exe" `
  -SigningMode Signed `
  -CertificateThumbprint "证书指纹" `
  -FormalRelease
```

流水线按顺序签署并验证 `YidaAI.exe`、构建安装包、签署并验证安装包，使用 SHA-256 与 RFC 3161 时间戳，最后才计算安装包 SHA-256。正式 Release 验证失败会停止。PFX、私钥、密码、令牌或云签名凭据不得写入源码、日志或安装包；CI 只能使用 Secrets 或可信云签名服务。上游 LCT 始终保持原文件和原签名，不使用译答 AI 证书重新签署。

架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，发布结果见 [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)。

公开项目与使用文档：

- [隐私政策](PRIVACY.md)与[安全报告](SECURITY.md)
- [代码签名政策](CODE_SIGNING_POLICY.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [Windows 语言支持](docs/WINDOWS_LANGUAGE_SUPPORT.md)
- [贡献说明](CONTRIBUTING.md)与[行为准则](CODE_OF_CONDUCT.md)

当前候选包仍未签名。仓库中的 SignPath 工作流是未获批准前保持禁用的占位配置，
不代表项目已经获得证书，也不代表已有签名发行版。

## 已知限制

- 当前只正式验证 Windows 11；译答 AI 不直接读取麦克风，也不内置 STT。
- beta 安装包尚未进行代码签名，Windows 可能显示信誉提示。
- 统一界面下的 LCT 仍是独立第三方后台进程，不是译答 AI 自研语音识别能力。
- 上游数据库结构若改变，只需要更新 `LiveCaptionsTranslatorSource`。
- 当前关键词检索稳定、可测试，但不等于语义检索。
- PDF 只支持有可复制文字的文件，属于实验功能。
- AI 建议可能出错；涉及事实、承诺或专业决策时必须人工核对。

系统字幕窗口默认保持可见；隐藏为可选功能。程序退出时会恢复原本可见的外部字幕窗口，
且只关闭自己启动的字幕/LCT 进程。如果无法安全隐藏，会自动恢复窗口并提示限制。

当前不声称能够同时识别混合的中英葡语；每次应在 Windows 实时字幕中选择一种实际听取语言。

## 常见错误排查

- `0x80070422`：Windows Update 或 BITS 被禁用，实时字幕识别模型无法下载。进入“诊断与修复”，打开“服务”与“Windows 更新”，按复制的说明人工检查；译答 AI 不会静默启用或修改服务。
- 语言设置显示已下载但仍提示模型缺失：已安装的可能只是显示语言、输入功能或 TTS 声音。打开 Windows 实时字幕，让它通过自己的提示下载当前听取语言的本地识别模型。
- Microsoft Store/模型目录不可用：诊断页会区分普通网络、微软模型目录和组织策略；无法确认时显示“未验证”，不会误报正常。
- 没有字幕：确认 Windows 11 build 22621+、当前听取语言模型和 Win+Ctrl+L，然后点“一键启动全部”或“重试失败步骤”。
- 没有翻译：打开翻译器设置，检查 LCT 目标语言和翻译服务；译答 AI 不读取 LCT Key。
- AI 提示缺 Key、401、404、429：分别检查保存状态、密钥权限、模型/端点和额度。
- 网络超时或服务端错误：字幕仍会继续；检查网络/服务状态后重试。
- 历史未恢复：新安装默认关闭历史；确认此前已主动开启“保存历史”，并检查保留期限。

## 卸载

在 Windows“设置 → 应用 → 已安装的应用”中卸载 Yida AI。程序和快捷方式会移除，
`%LOCALAPPDATA%\YidaAI` 下的配置、加密 Key、历史与导入资料默认保留，避免升级或卸载
误删用户数据；只有确定要彻底清除时才手动删除该目录。

## 许可证

Apache License 2.0。参见 [LICENSE](LICENSE)、[NOTICE](NOTICE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
