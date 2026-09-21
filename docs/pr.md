# Draft PR 状态

- PR：[feat: add three-version Jev evaluation pipeline](https://github.com/Accessiiing/customer-reply-audit/pull/1)
- 分支：`feat/jev-system-one` → `main`
- 状态：Draft

## 已进入 PR

- V1 `mock`、V2 `jev`、V3 `hybrid` 三种模式。
- 显式污染输入派生与哈希清单。
- 自动三版比较和冻结 winner 规则。
- 时间戳决策档案。
- 23 项测试。

## 已验证

- `python -m pytest -q`：23 passed。
- 当前派生输入：20 条；原附件未修改。
- V1 新 run：TP=18、FP=1、TN=1、FN=0。
- 无官方 Jev key 时，benchmark 在写部分结果前以退出码 2 失败。

## Draft 退出条件

官方 Jev 三版真实比较、最终选择决策和公开结果尚未完成。完成前不得把 PR 标记 Ready，也不得把契约测试写成 Jev 效果。
