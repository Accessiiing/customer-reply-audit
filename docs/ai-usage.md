# AI 工具使用记录

- 开发工具：OpenAI Codex 桌面 Agent，用于读取需求、收集高质量项目参考、设计合同、编写代码/测试/文档和执行本地验证；产物由真实命令与测试复核。
- 技术调研：查阅 TypeSafe 官方 API、模型与 Agent Skill 文档，确认 `jev-latest` 当前指向 `jev-1.13.0`，并按 System One 的 typed decision 合同设计运行时；公开试玩代理只用于早期可行性确认，不进入正式三版本比较。
- 运行时检测：实现 OpenAI-compatible、Jev 和规则＋Jev 三种可选路径；当前没有 TypeSafe 官方凭证，因此只真实运行了显式规则基线，Jev HTTP 契约使用本地 MockTransport 测试。
- 人工检查：核对了 20 条 ID 集合、选定 run 的混淆矩阵、h16 误报证据和 h07 首轮漏检调整轨迹。人工标签只进入独立评估入口，不进入检测提示词或规则。
- 未发生：未调用其他项目密钥、未用 stub 结果选择最终赢家、未声称盲测或真实 Jev 效果。
