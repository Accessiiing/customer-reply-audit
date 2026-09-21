# 技术合同：客服回复幻觉检测 v1

## 边界

输入是 `id / user_question / system_reply / knowledge_base`。检测模块不知道人工标签；评估模块只在预测已保存后按 ID 关联标签。每条回复独立处理，完整知识库直接进入裁判，不跨样本检索。

不做联网搜索、模型训练、向量库、多 Agent、账号系统或发送前拦截。离线检出效果不等于线上幻觉降低比例。

## 三个独立维度

证据关系：`supported`、`contradicted`、`unsupported`、`uncertain`。

问题类型：`factual_contradiction`（事实矛盾）、`unsupported_assertion`（无依据断言）、`fabricated_capability`（能力或操作虚构）、`material_omission`（关键条件遗漏／过度概括）、`safety_denial`（安全限制被否定）。一条断言可多标签。

严重度：`none < low < medium < high < critical`。默认事实矛盾/无依据/关键遗漏为 medium，能力虚构为 high，安全限制否定为 critical；重要权益、地址、承诺和关键参数可升 high。正常项为 none。

## 聚合规则

1. 至少一个 material 的 `contradicted` 或 `unsupported` 断言：整条 `ok / true`，严重度取确认问题最高值。
2. 没有确认问题但存在 `uncertain` 或未决项：`needs_review / null`。
3. 确认问题与未决项并存：保留 `ok / true`，未决项留在断言层。
4. API、schema 或系统故障：`error / null`。不得把失败当正常。
5. 普通省略、礼貌话术和等义改写不构成问题；关键遗漏须说明遗漏条件、与问题的关系和误导后果。

## 证据与机械校验

- `reply_quote` 必须来自本条回复；`evidence_quote` 必须来自本条知识库，按 NFKC + 去空白规范化复核。
- `contradicted` 必须有知识库引文；`unsupported` 不得伪造支持引文，须说明缺少的依据。
- 数值只能在主体、属性、单位和适用条件对齐后比较。
- 字符串存在只证明引用真实，不证明语义支持；语义判断由模型或显式 mock 承担。
- 展示层对所有输入执行 HTML 转义。

## 运行模式

- `real`：OpenAI-compatible Chat Completions API，温度 0。环境变量见 `.env.example`。
- `mock`：公开通用关系规则的受限演示；不读取标签，不按 ID 分支。它验证 schema、证据、评估和报告闭环，不能证明完整语义能力或泛化。

## 评估合同

只对 `ok` 项计算 TP/FP/TN/FN、Precision、Recall、F1、Accuracy、正常回复误报率和 Balanced Accuracy，并显式给出有效判定分母。另报决策覆盖率及 `TP / 全部人工正例`。零分母输出 N/A。类型体系与人工单标签不具同口径，不报类型准确率。

固定展示“全部判为幻觉”基线，防止不平衡数据造成虚高结论。已知标签曾在开发前读取，因此本数据不是盲测。

## 可复现性

每次检测创建唯一 `run_id`，记录输入、提示词和规则哈希、模型、参数、时间、耗时、usage（不可得即 unavailable）及 Git 状态。历史运行不覆盖。真实 API 输出保存后，评估可确定性复算。

