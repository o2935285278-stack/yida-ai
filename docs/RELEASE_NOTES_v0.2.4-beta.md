# 译答 AI v0.2.4-beta｜简洁对话界面预览

这是面向 Windows 的开发预览版（Pre-release），不是稳定正式版。安装包未进行可信代码签名。

## 本次更新

- **对话页面更简洁**：组件状态、启动与修复工具、历史操作移入设置，诊断页面也收进设置。
- **更贴近 Windows 风格**：原生控件主题、浅色背景、弱化边框的对话卡片。
- **阅读更连贯**：来源和次要复制操作收进“详情”；向上查看记录时，新消息不再强制滚动到底部。
- **直接读取 Windows 字幕**：原文先显示，翻译完成后补到同一条对话；原生模式无需额外启动 LCT。
- **回答语言独立切换**：支持切换建议回答语言及转译已有回答。
- **资料批量导入**：支持拖入 TXT、Markdown、文字型 PDF；扫描 PDF 暂不支持 OCR。
- **试验性字幕自动隐藏**：取消设置中的“显示系统字幕窗口”后，只对译答启动的字幕窗口尝试隐藏；读取检查失败会恢复窗口。

## 使用与升级

1. 下载 `YidaAI-0.2.4-beta-win-x64-setup.exe`，用随附 SHA-256 文件核对完整性。
2. 建议先备份已有资料和配置，退出旧版后再安装；不要公开分享自己的配置、Key 或聊天记录。
3. 旧配置保留原字幕来源。若要使用直接读取模式，在设置中选择 `windows-captions` 并保存。
4. Windows 自带实时字幕和对应语言组件仍然必须安装并运行。当前主要支持简体中文、美国英语、巴西葡语，不承诺混合语言同时识别。
5. 配置自己的 AI 服务和 API Key。原生字幕翻译会向该服务发送识别出的文本并消耗 API 配额，包括“仅翻译”模式。

## 已知限制，请先阅读

- **未签名**：没有可信代码签名证书或可信时间戳；校验和不等于代码签名。请遵循设备安全策略，不建议关闭系统安全防护。
- 自动隐藏**默认关闭**，仍可能短暂出现系统窗口。隐藏后的真实持续识别与不同 Windows 版本兼容性尚未完成实测。
- 主界面麦克风快捷开关尚未完成，请使用 Windows 实时字幕中的现有麦克风控制。
- 自动语言切换依赖 Windows 字幕界面；失败时需在系统字幕设置中手动选择语言。
- 连续长音频、识别纠错和高负载场景仍需更多测试。网络故障及 AI 服务速度会影响翻译与回复。
- 安装包仍保留未经修改的 LCT 作为兼容选项；并非只有译答一个系统进程。

## 验证情况

- 155 项本地自动测试通过，包含 Tk 界面启动、缩放、资料导入和隐藏保护测试。
- Ruff 检查及待发布源码敏感信息检查通过。
- 安装包构建及打包后离线模拟测试通过。
- 本地构建环境为 Python 3.11.15，不是锁定的 Python 3.13 正式发布环境。
- 实际界面截图及隐藏后持续识别验收尚未完成；测试通过不代表所有真实使用场景已经验证。

欢迎通过 Issues 反馈：请提供 Windows 版本、字幕来源、语言方向和复现步骤。提交前遮挡 API Key、私人资料与真实对话。

---

**English:** This unsigned development pre-release simplifies the conversation UI,
adds in-process Windows caption input, independent reply languages and document
drag/drop. Windows Live Captions is still required. Automatic window hiding is
experimental and opt-in; continuous hidden recognition and the microphone quick
toggle are not complete. Native translation sends caption text to your configured
AI provider and may incur API charges. Back up your settings before upgrading.
