# GitHub 提交说明

## 标题

`feat: 发布客服回复幻觉检测 V1`

## 交付内容

- 五类幻觉定义、证据关系和严重度。
- 20 条显式 mock 检测与结构化证据。
- 隔离 ground truth 的独立评估。
- TP=18、FP=1、TN=1、FN=0；误报 `h16`，无漏报。
- 16 项自动化测试、脱敏样例和真实 HTML 报告截图。

## 审查边界

- 指标来自 `mock-rules-v2`，不是 LLM 实测。
- 数据不是盲测，且只有 2 条负例，不证明泛化。
- 招聘原始附件、密钥和本地运行目录未提交。

最终提交入口：<https://github.com/Accessiiing/customer-reply-audit>
