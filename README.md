# 客服回复幻觉检测 · 三版本证据审计

> **规则基线 × Jev System One × 混合判断** · 同一数据、同一评估合同、自动选择最终版本

**当前状态**：三版代码已完成，23/23 测试通过；规则基线已复跑，官方 Jev 真实比较等待本机配置 `TYPESAFE_API_KEY`。在三版真实运行完成前，本项目不宣布最终赢家。

## 一句话概览

这个项目不是“把最新模型接上就算完成”，而是把客服幻觉检测拆成可追溯的事实候选与封闭判断，再用三种实现做同口径实验：

| 版本 | CLI 模式 | 核心方法 | 当前状态 |
|---|---|---|---|
| V1 | `mock` | 确定性通用关系规则 | ✅ 已完成、已复跑 |
| V2 | `jev` | Jev Choice/Noul 类型化语义判断 | ✅ 代码与契约测试完成；⏳ 等官方 key 实测 |
| V3 | `hybrid` | 硬规则处理明确冲突，Jev 处理语义关系与遗漏 | ✅ 代码与契约测试完成；⏳ 等官方 key 实测 |

最终版本不是人工拍脑袋选择，而是按预先冻结的排序规则产生：无系统错误 → 覆盖率 → Balanced Accuracy → F1 → 正常回复误报率 → 耗时。完整决策见 [决策索引](docs/decisions/README.md)。

## 为什么使用 Jev

| 任务特征 | 设计选择 |
|---|---|
| 输出空间封闭：支持、冲突、无依据、不确定 | 使用 Jev Choice，不让模型生成自由文本 |
| 一个回复可能有多条断言 | 确定性代码先切分并编号 `R01...` |
| 证据必须来自当前知识库 | 代码先编号 `K01...`，Jev 只选择关系＋证据编号 |
| 类型安全不等于语义正确 | 保存完整概率；低概率或分布不集中进入 `needs_review` |
| ground truth 不能污染检测 | 检测先落盘，独立 `evaluate` 才读取标签 |

真正的亮点不是“用了 Jev”，而是明确了它的舍弃域：Jev 不生成引文、不决定政策、不读取标签；确定性代码拥有候选、引用、阈值、严重度和最终聚合。

## 招聘方五项要求

| 要求 | 本项目证据 |
|---|---|
| 1. 自定义分类 | 四种证据关系、五类问题、五级严重度，见 [SPEC](SPEC.md) |
| 2. 自动检测 20 条 | V1 已对 20/20 生成结构化结果；V2/V3 接口与故障路径已实现 |
| 3. 对照人工标签 | V1：TP=18、FP=1、TN=1、FN=0 |
| 4. 分析误判 | 保留 h16 边界争议、h07 返工和多个主体/条件案例，见 [评估分析](docs/evaluation.md) |
| 5. README 与 AI 使用 | 本文件提供方法、命令、边界；实际 AI 使用见 [AI 使用记录](docs/ai-usage.md) |

## 已验证基线

固定的 20 条数据包含 18 个正例、2 个负例。当前规则基线结果：

| 模式 | TP | FP | TN | FN | Precision | Recall | F1 | Accuracy | 正常回复误报率 | Balanced Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `mock-rules-v2` | 18 | 1 | 1 | 0 | 94.7% | 100.0% | 97.3% | 95.0% | 50.0% | 75.0% |

这不是盲测，也不是 LLM/Jev 指标。原有标签在开发前已被读取，负例只有 2 条；最终三版比较必须保留这一限制。

## Quick Start

要求 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。原始招聘附件只读，不提交到仓库。

```powershell
# 1. 安装（约 1 分钟）
uv sync --extra dev

# 2. 测试：期望 23 passed
.venv\Scripts\python.exe -m pytest -q

# 3. 只跑规则基线
.venv\Scripts\reply-audit.exe run `
  --input <path-to-replies.json> `
  --truth <path-to-ground-truth.json> `
  --mode mock
```

### 三版本真实比较

先从 `.env.example` 创建被 Git 忽略的 `.env`，只在本机填写 TypeSafe 凭证：

```dotenv
TYPESAFE_API_KEY=...
TYPESAFE_BASE_URL=https://api.typesafe.ai
TYPESAFE_DEFAULT_MODEL=jev-1.13.0
```

然后执行：

```powershell
.venv\Scripts\reply-audit.exe benchmark `
  --input <path-to-replies.json> `
  --truth <path-to-ground-truth.json>
```

`benchmark` 会先验证 Jev 凭证，再依次运行 `mock / jev / hybrid`；任一真实运行缺失时不会产生最终赢家。详细复刻流程见 [Jev 三版本实验](docs/jev-experiment.md)。

### 输入尾部污染

当前本地 `task4_replies.json` 在合法 JSON 后出现额外文本。项目不会静默忽略，也不会修改原附件；必须显式生成带哈希清单的派生输入：

```powershell
.venv\Scripts\reply-audit.exe prepare-input `
  --source <path-to-contaminated-replies.json> `
  --output-dir artifacts/staging/current
```

## 证据与故障边界

- `reply_quote` 必须来自当前回复，`evidence_quote` 必须来自当前知识库。
- API、schema 或系统错误输出 `error / null`，不能冒充正常。
- 低概率或关系不一致输出 `needs_review / null`。
- Jev 的类型化输出避免了自由文本解析，但不保证语义判断正确。
- 三版本保存独立 run_id、输入哈希、配置哈希、代码版本、模型版本、usage、重试和耗时。
- 当前没有官方 Jev 全量运行，不得把契约测试写成真实模型效果。

## 资产清单

| 路径 | 职责 |
|---|---|
| [SPEC.md](SPEC.md) | 权威技术合同和复刻边界 |
| [CHANGELOG.md](CHANGELOG.md) | 版本演进和返工根因 |
| [docs/decisions/](docs/decisions/README.md) | 一次决策一个时间戳文件 |
| [docs/jev-experiment.md](docs/jev-experiment.md) | 三版本实验与最终选择流程 |
| [docs/evaluation.md](docs/evaluation.md) | 已验证规则基线与误判分析 |
| [docs/verification.md](docs/verification.md) | 本地与远端干净克隆验证证据 |
| [configs/jev-v1.json](configs/jev-v1.json) | Jev 版本、阈值和重试配置 |
| [docs/screenshots/mock-report.png](docs/screenshots/mock-report.png) | 当前规则基线结果截图 |

## 当前边界

- ❌ 官方 Jev key 未配置，V2/V3 尚无真实模型指标。
- ❌ 20 条数据不是盲测，且类别高度不平衡。
- ❌ 尚缺一张 IDE/Agent/终端开发过程截图，提交招聘方前需人工补充。
- ❌ 离线检测不等于已经降低线上客服幻觉率。
