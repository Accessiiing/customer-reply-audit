# Jev 三版本实验 · 复刻指南

> 目的不是证明新技术一定更好，而是用冻结数据、评估合同和选择规则回答：Jev-only 或规则＋Jev 是否比规则基线更值得成为最终版本。

## 1. 三个版本

| 版本 | 模式 | 智能来源 | 失败策略 |
|---|---|---|---|
| V1 | `mock` | 确定性通用规则 | 规则异常 → error |
| V2 | `jev` | Jev typed decisions | API/格式失败 → error，不回退规则 |
| V3 | `hybrid` | 硬规则＋Jev | Jev 失败 → error，不伪装成完整 hybrid |

## 2. 环境前置

- [ ] Python 3.11+
- [ ] uv
- [ ] 合法的 `replies.json` 与 `ground_truth.json`
- [ ] TypeSafe 官方 API key，只放入被忽略的 `.env`
- [ ] 当前 Git 工作区状态已记录

```powershell
uv sync --extra dev
Copy-Item .env.example .env
# 手动编辑 .env，只填写本机 key；不要把值粘贴到聊天、截图或 Git。
```

## 3. 数据预检

先严格验证输入；当前本地附件存在尾部污染时执行：

```powershell
.venv\Scripts\reply-audit.exe prepare-input `
  --source <path-to-replies.json> `
  --output-dir artifacts/staging/current
```

期望：生成 `replies.cleaned.json` 和 `replies.cleaned.manifest.json`。manifest 应显示 `record_count=20`，原文件哈希不变。

## 4. 机械测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

期望：`23 passed`。

## 5. 正式比较

```powershell
.venv\Scripts\reply-audit.exe benchmark `
  --input artifacts/staging/current/replies.cleaned.json `
  --truth <path-to-ground-truth.json>
```

输出：

```text
artifacts/runs/<mock-run>/
artifacts/runs/<jev-run>/
artifacts/runs/<hybrid-run>/
artifacts/comparisons/<comparison-id>/
  comparison.json
  comparison.md
```

## 6. 选择与发布

comparison 的 winner 只由 [冻结选择规则](decisions/final-selection-policy-20260921-160131.md) 产生。运行完成后必须：

1. 新增 `docs/decisions/final-version-selection-<time>.md`。
2. 将三版指标、run_id、模型版本、输入/配置哈希写入决策。
3. 把选定 comparison 与最终报告复制到可提交的 `docs/results/`；原始 API 日志和招聘附件仍不提交。
4. 更新 README 第一屏和 `docs/status.md`，不得保留“等待真实运行”的旧表述。

## 7. 验收场景

| 场景 | 期望 |
|---|---|
| 无 Jev key | benchmark 退出码 2，不产生部分比较 |
| API 401/429/529 | 401 形成单条 error；429/529 最多重试配置次数 |
| 低概率/低 confidence | `needs_review / null` |
| 引用编号不存在 | provider error，不复制伪证据 |
| 三版齐全 | comparison 给出唯一 winner 和完整排名 |

## 8. 已知限制

- 中文不是 Jev 官方声明的主要训练语言，必须以本次实测为准。
- 20 条数据仅有 2 个负例，Balanced Accuracy 仍会明显波动。
- 当前标签开发前已经被读取，三版结果不是真正盲测。
- typed output 解决接口形状，不自动解决语义正确性。
