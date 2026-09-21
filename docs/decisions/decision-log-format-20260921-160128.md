# 决策：决策日志命名与不可变规则

- 决策时间：2026-09-21 16:01:28 +08:00
- 状态：已确认

## 决定

每次独立决策写入 `docs/decisions/<decision-name>-<YYYYMMDD-HHmmss>.md`。

- `decision-name` 使用简短英文 kebab-case，便于跨平台和链接。
- 时间使用 Asia/Hong_Kong 本地时间，精确到秒。
- 已形成历史证据的文件不覆盖；推翻旧决策时新增文件并链接旧文件。
- `docs/decisions/README.md` 只做索引，不替代决策正文。

## 为什么

CHANGELOG 适合版本摘要，但不足以保存一次决策的输入、替代方案、边界和验收条件。不可变时间戳文件能把“当时为什么这样选”保留下来。
