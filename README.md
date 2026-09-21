# 客服回复幻觉检测

方案 B 的可复现本地交付：先把客服回复拆成可核验断言，再逐项与本条知识库核对，最后由程序验证引用、聚合结论并与人工标签独立评估。

> 当前选定运行 `20260921T042904Z-2883b270` 是**显式 mock**，不是 LLM 实测。它证明 20 条批处理、结构化证据、故障隔离、评估和报告链路可运行；由于本机未配置 API 凭证，真实模型效果尚未验证。

## 招聘方五项要求

| 要求 | 本次交付 |
|---|---|
| 1. 自定义分类 | 证据关系、五类问题和业务严重度分层定义，见下表与 [SPEC](SPEC.md) |
| 2. 自动检测 20 条 | CLI 已对 20/20 条生成结构化结果；支持 OpenAI-compatible 真实 API 与显式 mock |
| 3. 对照人工标签 | TP=18、FP=1、TN=1、FN=0；误报 `h16`，漏报无 |
| 4. 误判与边界分析 | 保留 `h16` 标签争议，并分析 unknown、普通省略、主体混淆和条件遗漏，见 [评估报告](docs/evaluation.md) |
| 5. README 与 AI 使用 | 本文件给出方法、结果、运行命令、限制；实际 AI 使用见 [AI 使用记录](docs/ai-usage.md) |

## 当前真实结果

评估集为 20 条、人工正例 18 条、负例 2 条；所有指标均由保存的预测按 ID 重新计算。

| 模式 | TP | FP | TN | FN | Precision | Recall | F1 | Accuracy | 正常回复误报率 | Balanced Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mock-rules-v2 | 18 | 1 | 1 | 0 | 94.7% | 100.0% | 97.3% | 95.0% | 50.0% | 75.0% |
| 全报幻觉基线 | 18 | 2 | 0 | 0 | 90.0% | 100.0% | 94.7% | 90.0% | 100.0% | 50.0% |

- 误报：`h16`。回复中的“商品图片都是实物拍摄”缺少直接支持，mock 按无依据确定断言报警；人工标签按核心色差说明一致判正常。
- 漏报：无。
- 覆盖率：100%（20 条均为 `ok`，无 `needs_review` / `error`）。
- 这不是盲测：开发前已读取人工标签，首轮 `mock-rules-v1` 的 `h07` 漏检也被保留在 CHANGELOG；不能用本结果证明泛化。

机器结果：[evaluation.md](artifacts/runs/20260921T042904Z-2883b270/evaluation.md) · [report.html](artifacts/runs/20260921T042904Z-2883b270/report.html) · [详细分析](docs/evaluation.md)

## 分类体系

证据关系与问题类型分开，避免把“资料没写”误说成“事实为假”。

| 问题类型 | 判断边界 | 默认严重度 |
|---|---|---|
| 事实矛盾 | 同一主体、属性、条件下，回复与知识库明确冲突 | medium；权益、关键参数、地址可升 high |
| 无依据断言 | 知识库不能支持回复中的确定事实；不表示现实中已证伪 | medium；权益、承诺可升 high |
| 能力或操作虚构 | 能力声明/操作回执与“已查询、已修改、已升级”等声称冲突 | high |
| 关键条件遗漏／过度概括 | 漏掉与问题相关、会改变决策的条件，或把条件事实绝对化 | medium；重大影响可升 high |
| 安全限制被否定 | 把明确安全注意事项改成无条件安全承诺 | critical |

证据关系为 `supported / contradicted / unsupported / uncertain`；严重度为 `none / low / medium / high / critical`。一般省略、礼貌话术和合理同义改写不算幻觉。

## 检测方法

1. **单条隔离**：检测入口只读取 `id / user_question / system_reply / knowledge_base`，不读取人工标签。
2. **逐项抽取**：真实模式提示模型覆盖数字、单位、时限、地址、属性、肯否、操作完成和承诺；同时从知识库反向寻找必要条件。
3. **证据核对**：保存回复原句、主体/属性/值/条件、证据关系、知识库原句、类型、严重度和简短理由。
4. **程序闸门**：Pydantic 严格 schema；引用必须回到当前样本原文；unsupported 不得伪造引文；故障输出 `error/null`，不冒充正常。
5. **独立评估**：预测先落盘，再由单独入口读取标签，计算混淆矩阵、常用指标、未决覆盖率和朴素基线。

`mock-rules-v2` 仅使用通用关系规则（能力限制、属性/单位对齐、明确否定、关键遗漏等），不含样本 ID、整段回复查表或人工解释。它不是完整语义裁判。

## 快速运行

要求 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。原始招聘附件只读，不会复制或改写。

```powershell
cd X:\Work-station\occupation_planning\customer-reply-audit
uv sync --extra dev

$replies = 'X:\Work-station\occupation_planning\AI-test-task\AI测评任务（研发相关） 副本\图片和附件\task4_replies.json'
$truth = 'X:\Work-station\occupation_planning\AI-test-task\AI测评任务（研发相关） 副本\图片和附件\task4_ground_truth.json'

# 一条命令完成检测 → 独立评估 → HTML 报告
.venv\Scripts\reply-audit.exe run --input $replies --truth $truth --mode mock

# 测试
.venv\Scripts\python.exe -m pytest
```

每次运行写入新的 `artifacts/runs/<run_id>/`，包括 `predictions.json`、`evaluation.json`、`evaluation.md` 和 `report.html`，不会覆盖历史证据。

### 真实 API 模式

复制 `.env.example` 为被 Git 忽略的 `.env`，在本机填写 `AUDIT_API_KEY / AUDIT_BASE_URL / AUDIT_MODEL`，不要把密钥粘贴到聊天、日志或截图。然后把上面的 `--mode mock` 改为 `--mode real`。

真实模式使用 OpenAI-compatible Chat Completions API、温度 0；schema 失败只进行一次格式修复。API、格式或系统失败按单条隔离为 `error/null`，不会静默降级为 mock。

## 截图与交付状态

- [运行结果截图](docs/screenshots/mock-report.png)：本地 HTML 报告的真实页面截图，不含密钥。
- 开发过程截图：当前自动化环境不能截取 Codex/IDE 原生窗口，需提交前由用户手动截取一次本任务的 Agent/终端界面；没有用生成图片冒充开发截图。
- [当前状态](docs/status.md) · [PR 草案](docs/pr.md) · [CHANGELOG](CHANGELOG.md)

## 限制

- 当前只有 mock 全量运行，不能声称真实模型检出率已验证。
- 20 条是已知评测集且高度不平衡；结果不证明新业务数据上的泛化能力。
- “引用存在”只证明没有伪造引文，不证明语义支持；真实模型仍可能抽取遗漏、主体混淆或错判。
- 本工具是离线检测，不包含发送前拦截和线上反馈闭环，不能声称已降低真实线上幻觉发生率。
- 未配置 remote，未推送、未创建公开仓库或 PR；招聘材料与运行日志默认留在本机。

