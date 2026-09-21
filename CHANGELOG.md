# CHANGELOG

> 记录版本演进时优先写修订动因（why），不只写改动内容（what）。

## Unreleased

### Added

- 新增 `jev`：使用 TypeSafe `/v1/systemone` 的 Choice/Noul 完成证据关系、实质性、类型和遗漏判断。
- 新增 `hybrid`：确定性硬规则与 Jev 语义判断合并，API 失败不静默降级。
- 新增 `benchmark`：同一输入连续运行 `mock / jev / hybrid` 并按冻结规则选择 winner。
- 新增 `prepare-input`：原始 JSON 尾部污染时生成带双哈希与尾部哈希的 ignored 派生输入。
- 新增时间戳决策档案；一次决策一个文件，不覆盖旧判断。
- 测试从 16 项增加到 26 项，覆盖 Jev HTTP 契约、鉴权预检、非瞬态错误不重试、候选绑定、混合聚合、比较排序和污染输入。

### Decisions

- **不推翻规则版**：三版并存 —— 没有 V1 基线就无法证明 Jev 带来的真实收益。
- **不复用 Chat Completions provider**：Jev 使用独立客户端 —— `/v1/systemone` 的 state/questions/answers 与生成式 JSON 合同不同。
- **关系与证据合并选择**：一个 Choice 同时选择 `relation + Kxx` —— Jev 同请求问题相互独立，分两问会产生隐式依赖。
- **最终赢家自动产生**：先覆盖率与 Balanced Accuracy，再看 F1/误报/耗时 —— 18:2 的不平衡数据不能只看 Accuracy。

### Build Issues Encountered

- 已配置 key 但 TypeSafe 账号零额度时官方返回 401；旧版把“有字符串”误当成“可运行”，并在 V2/V3 全失败时错误输出 V1 winner → 新增一次最小真实预检，401 立即停止且不写部分结果；任一版本失格时 `winner=null`。
- 原始 `task4_replies.json` 在合法数组后多出 27 个尾部字符 → 严格加载继续失败；新增显式 `prepare-input`，不修改现场、不静默吞错。该坑同时记录于 SPEC“输入完整性”和独立决策文档。
- 派生输入首次写盘时直接序列化 `list[ReplyRecord]` 导致 `TypeError` → 根因是通用 JSON 编码器不识别 Pydantic 列表；改为逐项 `model_dump()`，全套 23 项测试通过。

- 冻结方案 B v1：逐项断言、反向条件检查、证据关系、严重度与故障聚合合同。
- 建立检测/评估隔离的 CLI、OpenAI-compatible provider、显式 mock 与本地 HTML 报告。
- `mock-rules-v2`：首轮 run `20260921T042703Z-445e88c0` 漏检完整退货地址；将“能力受限但直接给出地址”纳入通用能力越界规则。首轮也把缺少依据的“都是”断言整体判为支持，现改为无依据断言，以暴露 h16 标签边界而非迎合标签。
