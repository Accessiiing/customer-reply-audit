# 客服回复幻觉检测 · 完整技术规范

**版本**：v2.0-draft · **更新**：2026-09-21

> 本文档是项目的权威技术规范。项目门面见 [README.md](README.md)，版本演进见 [CHANGELOG.md](CHANGELOG.md)，独立决策见 [docs/decisions/](docs/decisions/README.md)。

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

- `real`：OpenAI-compatible Chat Completions API，温度 0。环境变量见 `.env.example`。schema 失败时只允许一次格式修复；第二次失败即 `error`，不无限重试。
- `mock`：公开通用关系规则的受限演示；不读取标签，不按 ID 分支。它验证 schema、证据、评估和报告闭环，不能证明完整语义能力或泛化。
- `jev`：TypeSafe System One API。确定性代码生成回复断言与知识事实候选；Jev 只返回 Choice/Noul 类型化判断，不生成引文或解释文本。
- `hybrid`：保留 `mock-rules-v2` 中明确事实冲突、能力虚构和安全限制规则；语义关系、无依据断言与遗漏判断交给 Jev。

## Jev 判断合同

### 候选

- 回复按句号、问号、感叹号、分号和逗号切分为 `R01...Rn`；候选文本必须是原回复子串。
- 知识库按句号、问号、感叹号和分号切分为 `K01...Km`；候选文本必须是原知识库子串。
- 原始问题、完整回复、完整知识库和候选数组共同进入单条样本的 state；不得跨样本共享。

### 问题

每个回复候选并行产生：

1. `relation_Rxx` Choice：`supported_by_Kxx / contradicted_by_Kxx / unsupported / uncertain`。
2. `material_Rxx` Noul：错误版本是否会实质影响权益、安全、购买决策或信任。
3. `issue_Rxx` Choice：五类问题或 `none`。

每个知识候选产生 `coverage_Kxx` Choice：`covered / materially_omitted / not_relevant / uncertain`。

关系与证据编号必须在同一个 Choice 内选择；同一请求中的问题相互独立，禁止设计“后一个问题依赖前一个答案”的隐式链路。

### 门禁与聚合

- 门禁值来自 [configs/jev-v1.json](configs/jev-v1.json)，属于待真实数据校准的 v1 配置。
- Choice 最高选项概率或 confidence 低于门禁时降为 `uncertain`。
- 引文由候选编号复制，任何未知编号触发 provider error。
- Jev 问题类型无效或低于门禁时，只允许按证据关系使用确定性 fallback，并记录 unresolved。
- 严重度由 taxonomy 与业务标签决定，不使用模型自由分数。

## 三版本最终选择

只有 `mock / jev / hybrid` 都完成后才允许比较。排序规则在看到结果前冻结：

1. 排除存在系统 error 的版本。
2. 决策覆盖率降序。
3. Balanced Accuracy 降序。
4. F1 降序。
5. 正常回复误报率升序。
6. 总耗时升序。
7. 指标完全相同时，外部依赖更少者优先。

完整 why 见 [final-selection-policy-20260921-160131.md](docs/decisions/final-selection-policy-20260921-160131.md)。

## 评估合同

只对 `ok` 项计算 TP/FP/TN/FN、Precision、Recall、F1、Accuracy、正常回复误报率和 Balanced Accuracy，并显式给出有效判定分母。另报决策覆盖率及 `TP / 全部人工正例`。零分母输出 N/A。类型体系与人工单标签不具同口径，不报类型准确率。

固定展示“全部判为幻觉”基线，防止不平衡数据造成虚高结论。已知标签曾在开发前读取，因此本数据不是盲测。

## 可复现性

每次检测创建唯一 `run_id`，记录输入、提示词和规则哈希、模型、参数、时间、耗时、usage（不可得即 unavailable）及 Git 状态。历史运行不覆盖。真实 API 输出保存后，评估可确定性复算。

## 输入完整性

默认加载器必须拒绝合法 JSON 后的额外文本。若原始附件被污染，只允许通过 `prepare-input` 生成 ignored staging 副本，并记录源/派生 SHA-256、记录数和尾部哈希；原附件不可修改或提交。

## 复刻验收

- `python -m pytest -q`：期望 23 项通过。
- 无 Jev key 执行 `benchmark`：期望退出码 2，且不写入部分比较结果。
- 有 Jev key 执行 `benchmark`：期望产生三个独立 run 和一个 comparison；comparison 必须给出自动 winner。
- 任一 `needs_review/error`：`is_hallucination` 必须为 `null`。
