# 决策：官方 Jev 实测完成前保持 Draft PR

- 决策时间：2026-09-21 16:13:55 +08:00
- 状态：已确认

## 决定

GitHub PR #1 保持 Draft，直到以下条件全部满足：

1. 使用官方 TypeSafe 凭证完成 `mock / jev / hybrid` 三个 run。
2. 冻结比较规则产生唯一 winner。
3. 新增最终版本选择决策文档并发布可审查结果。
4. README、status 和截图与最终事实同步。

## 为什么不现在标记 Ready

23 项测试只证明接口、门禁和比较代码可运行；MockTransport 不能证明 Jev 在 20 条中文数据上的真实效果。把当前 PR 标记 Ready 会把“实现完成”误写成“效果已验证”。
