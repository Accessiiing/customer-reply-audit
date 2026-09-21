# Agent 工作约束

读取顺序：`docs/status.md` → `README.md` → `SPEC.md` → 当前 run 的 `evaluation.md`。

- 检测入口只能读取回复数据；只有独立 `evaluate` 入口可读取人工标签。
- 不得按样本 ID、整段固定回复或人工解释写判定分支。
- 原始招聘附件只读，不复制进仓库，不覆盖历史运行。
- `needs_review` / `error` 的 `is_hallucination` 必须为 `null`。
- 引用存在校验不代表语义支持；真实模型、mock、机械测试必须分开陈述。
- 提示词、规则或聚合行为改变时升级版本并记录 `CHANGELOG.md`。
- 密钥只来自环境变量或被忽略的 `.env`，不得写入代码、日志和截图。

