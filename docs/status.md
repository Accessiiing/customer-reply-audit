# 当前状态

- 已完成：方案 B v1、20 条显式 mock 检测、独立评估、HTML 报告、16 项测试和招聘方格式 README。
- 已验证：run `20260921T042904Z-2883b270`；TP=18、FP=1（`h16`）、TN=1、FN=0，覆盖率 100%。
- 已验证：仓库内脱敏样例可完成检测、评估和 HTML 报告；完整测试为 16 passed。
- 已验证：从 GitHub `release/v1-final` 干净克隆后，`uv sync --extra dev`、16 项测试与脱敏样例端到端运行全部通过；Jev 与常见密钥模式命中均为 0。
- 最终范围：只发布 V1；招聘原始附件、密钥与本地运行目录不进入 Git。
- 未验证：真实 LLM API 全量效果；README 与报告均明确标注当前指标来自 mock。
- 已发布：通过 [PR #2](https://github.com/Accessiiing/customer-reply-audit/pull/2) 合并到 GitHub `Accessiiing/customer-reply-audit` 的 `main`；远端只保留 `main`。
- 剩余人工交付：补一张真实 Codex/IDE/终端开发过程截图；运行结果截图已存入仓库。
