# 决策索引

> 本目录只记录已经发生、会影响实现或交付的项目决策。文件名固定为 `<decision-name>-<YYYYMMDD-HHmmss>.md`；新决策新增文件，不覆盖历史。

| 时间（Asia/Hong_Kong） | 决策 | 文件 |
|---|---|---|
| 2026-09-21 16:01:26 | 使用三版本并行实验，而不是覆盖现有基线 | [three-version-experiment-20260921-160126.md](three-version-experiment-20260921-160126.md) |
| 2026-09-21 16:01:28 | 决策文档使用不可变时间戳文件 | [decision-log-format-20260921-160128.md](decision-log-format-20260921-160128.md) |
| 2026-09-21 16:01:29 | Jev 只负责类型化语义判断 | [jev-typed-judgment-boundary-20260921-160129.md](jev-typed-judgment-boundary-20260921-160129.md) |
| 2026-09-21 16:01:30 | 原始附件污染时生成可追溯派生输入 | [source-input-contamination-20260921-160130.md](source-input-contamination-20260921-160130.md) |
| 2026-09-21 16:01:31 | 最终版本只能由冻结排序规则产生 | [final-selection-policy-20260921-160131.md](final-selection-policy-20260921-160131.md) |
| 2026-09-21 16:13:55 | 官方 Jev 实测完成前保持 Draft PR | [draft-until-live-benchmark-20260921-161355.md](draft-until-live-benchmark-20260921-161355.md) |
| 2026-09-21 16:40:10 | Jev 零额度时阻断三版本实验 | [jev-zero-credit-gate-20260921-164010.md](jev-zero-credit-gate-20260921-164010.md) |

最终赢家产生后，必须再新增一份 `final-version-selection-<time>.md`，记录三版真实指标和选择理由。
